"""Provision store (P1.3): instruments, versions and provisions built from the inventories.

Provisions are computed in memory from tracked, human-checkable inputs only:
- the instrument registry (data/reference/instruments.json);
- the P1.2 reference inventories (data/reference/*.inventory.json);
- the review ledger (data/reference/review_ledger.json).
No PDF, parser output or chunk is read here.

Each provision keeps three separate axes:
- structural_status: how far its structure has been reviewed by a person
  (auto_unreviewed, auto_verified, manually_curated) or whether it is ambiguous;
- source_status_representation: what the source itself prints about its status;
- legal_validity: always "not_established". Nothing here establishes that a
  provision is valid or in force.

Eligibility as a citation is computed from these (see `eligibility`). A review record
may also say how the reviewer compared the text with an official source
(`official_check`); a text found to differ is not cited as primary evidence. A match
with an official source says nothing about legal validity either.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from src.config import PROJECT_ROOT
from src.reference_inventory import REPEAL_MARKER, serialize_inventory, validate_inventory
from src.text_normalization import DIFFERS, MATCH_STATUSES, PROFILES, TextDifference, compare_texts

REGISTRY_PATH = PROJECT_ROOT / "data" / "reference" / "instruments.json"
LEDGER_PATH = PROJECT_ROOT / "data" / "reference" / "review_ledger.json"
REGISTRY_SCHEMA_VERSION = 1
LEGAL_VALIDITY = "not_established"


class ProvisionError(ValueError):
    """The registry, ledger or inventories are inconsistent, or a lookup failed."""


class StructuralStatus(StrEnum):
    AUTO_UNREVIEWED = "auto_unreviewed"  # generated, not checked by a person
    AUTO_VERIFIED = "auto_verified"  # generated, confirmed by a person (ledger: confirmed)
    MANUALLY_CURATED = "manually_curated"  # corrected by a person (ledger: corrected)
    AMBIGUOUS = "ambiguous"  # the structure cannot be settled; never citable


class SourceStatus(StrEnum):
    REPRESENTED_IN_FORCE = "represented_in_force_at_reference_date"
    MARKED_REPEALED = "marked_repealed"
    NO_STATUS_REPRESENTATION = "no_status_representation"


class Tier(StrEnum):
    PRIMARY = "primary"  # may be cited as primary evidence
    INTERNAL_ONLY = "internal_only"  # may be inspected, with a qualification; not citable
    CONTEXT_ONLY = "context_only"  # divisions: context, never evidence
    BLOCKED = "blocked"  # a structural problem prevents any reliance


# Why a provision is not eligible as a primary citation.
REASONS = {
    "ambiguous_structure": "The source does not settle this provision's structure (see its "
    "notes), so text cannot be attributed to it reliably.",
    "no_anchored_text": "No exact source text is anchored to this provision.",
    "structure_not_reviewed": "Its structure has not been reviewed by a person; it can be "
    "inspected but not cited.",
    "source_marks_repealed_excluded_from_first_demo": "The source marks it as repealed. "
    "Repealed provisions are excluded from primary citations in the first demonstration; the "
    "marking is kept for historical research.",
    "division_context_only": "Divisions give context only and are never cited as evidence.",
    "official_text_differs": "The reviewer compared its text with the official source named "
    "in the review ledger and found differences (listed there), so it is not cited as primary "
    "evidence.",
}
# Statements that accompany every use of a provision, eligible or not.
QUALIFICATIONS = {
    "original_publication_not_consolidated": "Original publication, not a consolidated text: "
    "later corrigenda and amendments are not reflected.",
    "authenticity_not_established": "The authenticity of the source file is not established.",
    "unofficial_transcription": "User-provided transcription, not an official text.",
    "reference_date_unverified": "The reference date stated in the source is unverified.",
    "source_marks_repealed": "The source marks this provision as repealed. This records what "
    "the source prints, not a verified legal status.",
    "legal_validity_not_established": "This system does not establish whether the provision "
    "is legally valid or in force.",
}

VERSION_KINDS = ("original_publication", "consolidated_text", "transcription")
AUTHENTICITY = ("authentic", "official_non_authentic", "unofficial", "user_transcription")
DATE_BASES = ("stated_in_text",)
# Regions outside the articles that start at an exact line, in text order. The
# first three come before the first article heading, the closing formula after the last.
MARKER_KINDS = ("preamble", "recitals", "enacting_formula", "closing_formula")
# Inventory division kinds (Italian, as printed) and the provision kinds they become.
DIVISION_KINDS = {"parte": "part", "titolo": "title", "capo": "chapter", "sezione": "section"}
# Inventory fields a reviewer may correct (recorded in the ledger with before/after).
CORRECTABLE_FIELDS = (
    "label",
    "heading_as_printed",
    "title",
    "status_marker",
    "page_start",
    "page_end",
    "parent_id",
    "parent_path",
    "structural_status",
)
# Official sources a review may compare a provision with, and the only host each may
# be retrieved from (over HTTPS). Being official does not make a text authentic: only
# the Official Journal and the Gazzetta Ufficiale are; consolidated texts and Normattiva
# are documentation.
OFFICIAL_SOURCE_HOSTS = {
    "oj_original": "eur-lex.europa.eu",  # Official Journal publication, as on EUR-Lex
    "oj_corrigendum": "eur-lex.europa.eu",
    "eurlex_consolidated": "eur-lex.europa.eu",  # EUR-Lex consolidated version
    "normattiva_vigente": "www.normattiva.it",  # Normattiva, text in force
}
OFFICIAL_CHECK_KEYS = frozenset({
    "source_url", "source_type", "consolidation_date", "retrieved_on", "official_text_sha256",
    "normalisation", "match_status", "differences",
})
_SHA256 = re.compile(r"[0-9a-f]{64}")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_ID_SAFE = re.compile(r"[0-9a-z][0-9a-z.\-]*")


# --- Registry ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Instrument:
    instrument_id: str
    type: str
    jurisdiction: str
    aliases: tuple[str, ...]
    official_identifiers: Mapping[str, str] | None


@dataclass(frozen=True)
class Marker:
    """An exact line prefix that starts a region outside the articles (exactly one such line)."""

    kind: str  # one of MARKER_KINDS
    line_starts_with: str


@dataclass(frozen=True)
class EditorialNoteRule:
    """A separator line followed by a label line starts an editorial note inside an article."""

    separator_pattern: str  # full-line regex
    label_pattern: str  # full-line regex
    expected: int


@dataclass(frozen=True)
class FootnoteRule:
    """A footnote inside an article: from a line matching start_line_pattern (at its start)
    to the end of the first match of end_text_pattern within max_chars."""

    start_line_pattern: str
    end_text_pattern: str
    max_chars: int
    expected: int


@dataclass(frozen=True)
class SegmentationRules:
    """How a version's extracted text is divided into segments (src/provision_anchors.py).

    Every rule states how often it must match; any other count fails the segmentation.
    """

    furniture_patterns: tuple[str, ...]  # full-line regexes of running headers
    furniture_expected_lines: int
    markers: tuple[Marker, ...]  # in the order they appear in the text
    editorial_notes: EditorialNoteRule | None
    footnotes: FootnoteRule | None


@dataclass(frozen=True)
class Version:
    version_id: str
    instrument_id: str
    version_kind: str
    description: str
    language: str
    authenticity: str | None
    publication: Mapping[str, str] | None
    corpus_reference_date: Mapping[str, Any] | None
    provision_status_representation: SourceStatus
    inventory_path: str  # project-relative
    source_sha256: str
    segmentation: SegmentationRules

    @property
    def qualifications(self) -> tuple[str, ...]:
        """Codes of the statements every provision of this version carries (QUALIFICATIONS)."""
        codes = []
        if self.version_kind == "original_publication":
            codes.append("original_publication_not_consolidated")
        if self.authenticity is None:
            codes.append("authenticity_not_established")
        elif self.authenticity in ("user_transcription", "unofficial"):
            codes.append("unofficial_transcription")
        if self.corpus_reference_date is not None and not self.corpus_reference_date["verified"]:
            codes.append("reference_date_unverified")
        return tuple(codes)


@dataclass(frozen=True)
class Registry:
    instruments: tuple[Instrument, ...]
    versions: tuple[Version, ...]
    sha256: str  # of the registry file's bytes

    def version(self, version_id: str) -> Version:
        for version in self.versions:
            if version.version_id == version_id:
                return version
        raise ProvisionError(f"unknown version {version_id!r}")

    def instrument(self, instrument_id: str) -> Instrument:
        for instrument in self.instruments:
            if instrument.instrument_id == instrument_id:
                return instrument
        raise ProvisionError(f"unknown instrument {instrument_id!r}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProvisionError(message)


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _check_keys(obj: Any, keys: set[str], where: str) -> None:
    _require(isinstance(obj, Mapping), f"{where} must be an object")
    _require(set(obj) == keys, f"{where}: expected keys {sorted(keys)}, got {sorted(obj)}")


def _date(value: Any, where: str) -> datetime.date:
    ok = isinstance(value, str) and bool(_ISO_DATE.fullmatch(value))
    _require(ok, f"{where}: not YYYY-MM-DD")
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise ProvisionError(f"{where}: not a calendar date ({value!r})") from None


def _regex(value: Any, where: str) -> str:
    _require(isinstance(value, str) and bool(value), f"{where}: must be a regular expression")
    try:
        re.compile(value)
    except re.error as exc:
        raise ProvisionError(f"{where}: invalid regular expression: {exc}") from None
    return value


def _count(value: Any, where: str, minimum: int = 0) -> int:
    _require(type(value) is int and value >= minimum, f"{where}: must be an integer >= {minimum}")
    return value


def parse_segmentation(raw: Any, where: str) -> SegmentationRules:
    _check_keys(raw, {"page_furniture", "markers", "editorial_notes", "footnotes"}, where)
    furniture = raw["page_furniture"]
    _check_keys(furniture, {"line_patterns", "expected_lines"}, f"{where}.page_furniture")
    patterns = furniture["line_patterns"]
    _require(isinstance(patterns, list) and bool(patterns), f"{where}.page_furniture.line_patterns")
    patterns = tuple(_regex(p, f"{where}.page_furniture.line_patterns") for p in patterns)
    expected_lines = _count(furniture["expected_lines"], f"{where}.page_furniture.expected_lines")
    _require(isinstance(raw["markers"], list), f"{where}.markers must be a list")
    markers = []
    for j, m in enumerate(raw["markers"]):
        _check_keys(m, {"kind", "line_starts_with"}, f"{where}.markers[{j}]")
        _require(m["kind"] in MARKER_KINDS, f"{where}.markers[{j}]: kind {m['kind']!r}")
        _require(_is_text(m["line_starts_with"]), f"{where}.markers[{j}]: line_starts_with")
        markers.append(Marker(m["kind"], m["line_starts_with"]))
    kinds = [m.kind for m in markers]
    _require(len(kinds) == len(set(kinds)), f"{where}.markers: a kind is listed twice")
    _require(kinds == sorted(kinds, key=MARKER_KINDS.index),
             f"{where}.markers: kinds must follow the order {', '.join(MARKER_KINDS)}")
    notes = raw["editorial_notes"]
    if notes is not None:
        _check_keys(notes, {"separator_pattern", "label_pattern", "expected"},
                    f"{where}.editorial_notes")
        notes = EditorialNoteRule(
            _regex(notes["separator_pattern"], f"{where}.editorial_notes.separator_pattern"),
            _regex(notes["label_pattern"], f"{where}.editorial_notes.label_pattern"),
            _count(notes["expected"], f"{where}.editorial_notes.expected", 1),
        )
    footnotes = raw["footnotes"]
    if footnotes is not None:
        _check_keys(footnotes, {"start_line_pattern", "end_text_pattern", "max_chars", "expected"},
                    f"{where}.footnotes")
        footnotes = FootnoteRule(
            _regex(footnotes["start_line_pattern"], f"{where}.footnotes.start_line_pattern"),
            _regex(footnotes["end_text_pattern"], f"{where}.footnotes.end_text_pattern"),
            _count(footnotes["max_chars"], f"{where}.footnotes.max_chars", 1),
            _count(footnotes["expected"], f"{where}.footnotes.expected", 1),
        )
    return SegmentationRules(patterns, expected_lines, tuple(markers), notes, footnotes)


def parse_registry(data: Any, sha256: str) -> Registry:
    """Validate registry data (the parsed JSON of instruments.json)."""
    _check_keys(data, {"schema_version", "instruments", "versions"}, "registry")
    _require(data["schema_version"] == REGISTRY_SCHEMA_VERSION, "registry: unknown schema_version")
    instruments, aliases = [], {}
    for i, raw in enumerate(data["instruments"]):
        where = f"instruments[{i}]"
        _check_keys(
            raw,
            {"instrument_id", "type", "jurisdiction", "aliases", "official_identifiers", "notes"},
            where,
        )
        iid = raw["instrument_id"]
        _require(_is_text(iid) and bool(_ID_SAFE.fullmatch(iid)), f"{where}: bad instrument_id")
        _require(all(_is_text(raw[k]) for k in ("type", "jurisdiction")),
                 f"{where}: type/jurisdiction")
        _require(raw["official_identifiers"] is None or isinstance(raw["official_identifiers"],
                 Mapping), f"{where}: official_identifiers must be an object or null")
        _require(isinstance(raw["notes"], list), f"{where}: notes must be a list")
        _require(isinstance(raw["aliases"], list) and all(_is_text(a) for a in raw["aliases"]),
                 f"{where}: aliases must be non-empty strings")
        for name in [iid, *raw["aliases"]]:
            key = name.casefold()
            _require(key not in aliases,
                     f"{where}: name {name!r} already used by {aliases.get(key)}")
            aliases[key] = iid
        instruments.append(
            Instrument(iid, raw["type"], raw["jurisdiction"], tuple(raw["aliases"]),
                       raw["official_identifiers"])
        )
    ids = {i.instrument_id for i in instruments}
    versions, seen = [], set()
    for i, raw in enumerate(data["versions"]):
        where = f"versions[{i}]"
        _check_keys(
            raw,
            {"version_id", "instrument_id", "version_kind", "description", "language",
             "authenticity", "publication", "corpus_reference_date",
             "provision_status_representation", "inventory", "source_sha256", "segmentation",
             "notes"},
            where,
        )
        vid = raw["version_id"]
        _require(_is_text(vid) and vid not in seen, f"{where}: version_id missing or duplicated")
        _require(vid.startswith(raw["instrument_id"] + "@") and "/" not in vid,
                 f"{where}: version_id must be '<instrument_id>@<name>' without '/'")
        _require(raw["instrument_id"] in ids,
                 f"{where}: unknown instrument {raw['instrument_id']!r}")
        _require(raw["version_kind"] in VERSION_KINDS,
                 f"{where}: version_kind {raw['version_kind']!r}")
        _require(raw["authenticity"] is None or raw["authenticity"] in AUTHENTICITY,
                 f"{where}: authenticity {raw['authenticity']!r}")
        _require(_is_text(raw["description"]) and _is_text(raw["language"]), f"{where}: text")
        if raw["publication"] is not None:
            _check_keys(raw["publication"], {"date", "basis"}, f"{where}.publication")
            _date(raw["publication"]["date"], f"{where}.publication.date")
            _require(raw["publication"]["basis"] in DATE_BASES, f"{where}.publication.basis")
        ref = raw["corpus_reference_date"]
        if ref is not None:
            _check_keys(ref, {"date", "basis", "verified"}, f"{where}.corpus_reference_date")
            _date(ref["date"], f"{where}.corpus_reference_date.date")
            _require(ref["basis"] in DATE_BASES and type(ref["verified"]) is bool,
                     f"{where}.corpus_reference_date: basis or verified")
        try:
            representation = SourceStatus(raw["provision_status_representation"])
        except ValueError:
            raise ProvisionError(f"{where}: provision_status_representation") from None
        _require(representation != SourceStatus.MARKED_REPEALED,
                 f"{where}: marked_repealed comes from the printed marker, not the version")
        sha = raw["source_sha256"]
        _require(isinstance(sha, str) and bool(_SHA256.fullmatch(sha)),
                 f"{where}: source_sha256")
        _require(_is_text(raw["inventory"]), f"{where}: inventory path")
        _require(isinstance(raw["notes"], list), f"{where}: notes must be a list")
        segmentation = parse_segmentation(raw["segmentation"], f"{where}.segmentation")
        seen.add(vid)
        versions.append(
            Version(vid, raw["instrument_id"], raw["version_kind"], raw["description"],
                    raw["language"], raw["authenticity"], raw["publication"], ref,
                    representation, raw["inventory"], raw["source_sha256"], segmentation)
        )
    return Registry(tuple(instruments), tuple(versions), sha256)


def load_registry(path: Path = REGISTRY_PATH) -> Registry:
    data = path.read_bytes()
    try:
        parsed = json.loads(data.decode("utf-8"))
    except ValueError as exc:
        raise ProvisionError(f"{path}: not valid JSON: {exc}") from None
    return parse_registry(parsed, hashlib.sha256(data).hexdigest())


# --- Review ledger -------------------------------------------------------------------------


@dataclass(frozen=True)
class Correction:
    field: str
    before: Any
    after: Any


@dataclass(frozen=True)
class OfficialCheck:
    """How a reviewer compared a provision's text with an official source.

    `official_text_sha256` is the SHA-256 of the official text exactly as acquired
    and compared (UTF-8, before any normalisation). `match_status` and `differences`
    come from src.text_normalization.compare_texts under `normalisation`. A match
    does not establish legal validity or authenticity.
    """

    source_url: str
    source_type: str  # a key of OFFICIAL_SOURCE_HOSTS
    consolidation_date: str | None  # date the source is consolidated or updated to
    retrieved_on: str
    official_text_sha256: str
    normalisation: str  # a profile in src.text_normalization.PROFILES
    match_status: str  # one of src.text_normalization.MATCH_STATUSES
    differences: tuple[TextDifference, ...]  # ours vs official; only when "differs"


@dataclass(frozen=True)
class ReviewRecord:
    inventory_id: str
    entry_id: str
    outcome: str  # "confirmed" or "corrected"
    checked_by: str
    checked_on: str
    corrections: tuple[Correction, ...]
    note: str | None
    official_check: OfficialCheck | None = None  # optional; absent in older records


_LEDGER_KEYS = frozenset({"inventory_id", "entry_id", "outcome", "checked_by", "checked_on",
                          "corrections", "note"})


def parse_official_check(raw: Any, where: str, *, checked_on: datetime.date) -> OfficialCheck:
    """Validate one `official_check` object (see data/reference/README.md)."""
    _check_keys(raw, set(OFFICIAL_CHECK_KEYS), where)
    source_type = raw["source_type"]
    _require(source_type in OFFICIAL_SOURCE_HOSTS,
             f"{where}: source_type must be one of {sorted(OFFICIAL_SOURCE_HOSTS)}")
    url = raw["source_url"]
    _require(_is_text(url) and not any(c.isspace() for c in url), f"{where}: source_url")
    parts = urlsplit(url)
    host = OFFICIAL_SOURCE_HOSTS[source_type]
    _require(parts.scheme == "https" and parts.netloc == host,
             f"{where}: source_url must be https://{host}/... for {source_type}")
    retrieved = _date(raw["retrieved_on"], f"{where}.retrieved_on")
    _require(retrieved <= checked_on, f"{where}: retrieved_on is after checked_on")
    if raw["consolidation_date"] is None:
        _require(source_type != "eurlex_consolidated",
                 f"{where}: a consolidated text needs its consolidation_date")
    else:
        consolidated = _date(raw["consolidation_date"], f"{where}.consolidation_date")
        _require(consolidated <= retrieved, f"{where}: consolidation_date is after retrieved_on")
    sha = raw["official_text_sha256"]
    _require(isinstance(sha, str) and bool(_SHA256.fullmatch(sha)),
             f"{where}: official_text_sha256 must be 64 lowercase hex characters")
    _require(raw["normalisation"] in PROFILES, f"{where}: normalisation must be one of {PROFILES}")
    status = raw["match_status"]
    _require(status in MATCH_STATUSES, f"{where}: match_status must be one of {MATCH_STATUSES}")
    _require(isinstance(raw["differences"], list), f"{where}: differences must be a list")
    differences = []
    for j, d in enumerate(raw["differences"]):
        at = f"{where}.differences[{j}]"
        _check_keys(d, {"ours", "official"}, at)
        _require(isinstance(d["ours"], str) and isinstance(d["official"], str),
                 f"{at}: ours and official must be strings")
        _require(compare_texts(d["ours"], d["official"], raw["normalisation"]).status == DIFFERS,
                 f"{at}: ours and official are the same text after normalisation")
        differences.append(TextDifference(d["ours"], d["official"]))
    if status == DIFFERS:
        _require(bool(differences), f"{where}: match_status differs needs its differences")
    else:
        _require(not differences, f"{where}: differences are listed only when the text differs")
    return OfficialCheck(url, source_type, raw["consolidation_date"], raw["retrieved_on"], sha,
                         raw["normalisation"], status, tuple(differences))


def official_check_record(
    our_text: str,
    official_text: str,
    *,
    source_url: str,
    source_type: str,
    consolidation_date: str | None,
    retrieved_on: str,
    normalisation: str = PROFILES[0],
) -> dict[str, Any]:
    """A validated `official_check` object for a reviewer to put in a ledger record.

    Compares our anchored text with the official text and hashes the official text as
    given. It only prepares the object: it writes nothing and records no review.
    """
    comparison = compare_texts(our_text, official_text, normalisation)
    raw = {
        "source_url": source_url,
        "source_type": source_type,
        "consolidation_date": consolidation_date,
        "retrieved_on": retrieved_on,
        "official_text_sha256": hashlib.sha256(official_text.encode("utf-8")).hexdigest(),
        "normalisation": normalisation,
        "match_status": comparison.status,
        "differences": [{"ours": d.ours, "official": d.theirs} for d in comparison.differences],
    }
    parse_official_check(raw, "official_check", checked_on=datetime.date.today())
    return raw


def parse_ledger(data: Any, *, today: datetime.date | None = None) -> tuple[ReviewRecord, ...]:
    """Validate ledger data on its own; consistency with the inventories is checked in build."""
    today = today or datetime.date.today()
    _require(isinstance(data, list), "review ledger must be a JSON list")
    records, seen = [], set()
    for i, raw in enumerate(data):
        where = f"review_ledger[{i}]"
        has_check = isinstance(raw, Mapping) and "official_check" in raw
        _check_keys(raw, set(_LEDGER_KEYS | {"official_check"} if has_check else _LEDGER_KEYS),
                    where)
        key = (raw["inventory_id"], raw["entry_id"])
        _require(all(_is_text(k) for k in key), f"{where}: inventory_id and entry_id")
        _require(key not in seen, f"{where}: a second record for {key[1]}")
        _require(raw["outcome"] in ("confirmed", "corrected"), f"{where}: outcome")
        _require(_is_text(raw["checked_by"]), f"{where}: checked_by must name the reviewer")
        checked_on = _date(raw["checked_on"], f"{where}.checked_on")
        _require(checked_on <= today, f"{where}: checked_on is in the future")
        official_check = None
        if has_check:
            _require(raw["official_check"] is not None,
                     f"{where}: leave official_check out rather than null")
            official_check = parse_official_check(raw["official_check"],
                                                  f"{where}.official_check", checked_on=checked_on)
        _require(raw["note"] is None or _is_text(raw["note"]), f"{where}: note")
        _require(isinstance(raw["corrections"], list), f"{where}: corrections must be a list")
        corrections = []
        for j, c in enumerate(raw["corrections"]):
            _check_keys(c, {"field", "before", "after"}, f"{where}.corrections[{j}]")
            _require(c["field"] in CORRECTABLE_FIELDS, f"{where}.corrections[{j}]: field")
            _require(c["before"] != c["after"], f"{where}.corrections[{j}]: before equals after")
            corrections.append(Correction(c["field"], c["before"], c["after"]))
        fields = [c.field for c in corrections]
        _require(len(fields) == len(set(fields)), f"{where}: a field is corrected twice")
        if raw["outcome"] == "confirmed":
            _require(not corrections, f"{where}: a confirmed entry has no corrections")
        else:
            _require(bool(corrections), f"{where}: a corrected entry lists its corrections")
        seen.add(key)
        records.append(
            ReviewRecord(raw["inventory_id"], raw["entry_id"], raw["outcome"],
                         raw["checked_by"], raw["checked_on"], tuple(corrections), raw["note"],
                         official_check)
        )
    return tuple(records)


def load_ledger(path: Path = LEDGER_PATH) -> tuple[ReviewRecord, ...]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ProvisionError(f"{path}: not valid JSON: {exc}") from None
    return parse_ledger(data)


# --- Provisions ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Review:
    status: str  # "pending_human_review" or "reviewed"
    checked_by: str | None = None
    checked_on: str | None = None
    outcome: str | None = None  # "confirmed" or "corrected" when reviewed
    corrections: tuple[Correction, ...] = ()
    official_check: OfficialCheck | None = None


@dataclass(frozen=True)
class Provision:
    provision_id: str
    version_id: str
    instrument_id: str
    kind: str  # "article", or a division kind: "part", "title", "chapter", "section"
    label_as_printed: str
    normalised_label: str
    heading_as_printed: str
    title: str | None
    status_marker: str | None
    parent_id: str | None
    path: str  # printed path, e.g. "PARTE I > TITOLO I > CAPO IV > Art. 2-quaterdecies.1"
    page_start: int
    page_end: int
    structural_status: StructuralStatus
    review: Review
    source_status_representation: SourceStatus | None  # None when the structure is ambiguous
    inventory_id: str
    inventory_ref: str  # inventory entry_id (articles) or division_id (divisions)
    inventory_sha256: str
    source_sha256: str
    doc_id: str
    notes: tuple[str, ...]

    @property
    def legal_validity(self) -> str:
        return LEGAL_VALIDITY

    @property
    def is_article(self) -> bool:
        return self.kind == "article"


@dataclass(frozen=True)
class Eligibility:
    tier: Tier
    reasons: tuple[str, ...]  # codes in REASONS; empty only for PRIMARY
    qualifications: tuple[str, ...]  # codes in QUALIFICATIONS


def eligibility(provision: Provision, version: Version, *, anchored: bool) -> Eligibility:
    """How a provision may be used as evidence. `anchored`: exact source text is attached."""
    qualifications = list(version.qualifications)
    if provision.source_status_representation == SourceStatus.MARKED_REPEALED:
        qualifications.append("source_marks_repealed")
    qualifications.append("legal_validity_not_established")
    if not provision.is_article:
        return Eligibility(Tier.CONTEXT_ONLY, ("division_context_only",), tuple(qualifications))
    blocking, limiting = [], []
    if provision.structural_status == StructuralStatus.AMBIGUOUS:
        blocking.append("ambiguous_structure")
    if not anchored:
        blocking.append("no_anchored_text")
    if provision.review.status != "reviewed":  # also listed for an ambiguous provision
        limiting.append("structure_not_reviewed")
    check = provision.review.official_check
    if check is not None and check.match_status == DIFFERS:
        limiting.append("official_text_differs")
    if provision.source_status_representation == SourceStatus.MARKED_REPEALED:
        limiting.append("source_marks_repealed_excluded_from_first_demo")
    tier = Tier.BLOCKED if blocking else Tier.INTERNAL_ONLY if limiting else Tier.PRIMARY
    return Eligibility(tier, tuple(blocking + limiting), tuple(qualifications))


def normalise_label(label: str) -> str:
    """For identity and matching only: lower case, one trailing full stop removed."""
    return label.lower().removesuffix(".")


def article_id(version_id: str, label: str) -> str:
    normalised = normalise_label(label)
    _require(bool(_ID_SAFE.fullmatch(normalised)), f"label {label!r} cannot form a provision ID")
    return f"{version_id}/body/article:{normalised}"


def division_provision_id(version_id: str, prefix: str, division_id: str) -> str:
    """'<prefix>:parte:I/titolo:I/capo:IV' -> '<version_id>/body/part:i/title:i/chapter:iv'.

    A division's numeral repeats across the document ("CAPO I"), so its ID keeps the path.
    """
    _require(division_id.startswith(prefix + ":"), f"division {division_id!r} lacks the prefix")
    segments = []
    for segment in division_id[len(prefix) + 1 :].split("/"):
        kind, _, numeral = segment.partition(":")
        _require(kind.lower() in DIVISION_KINDS and bool(numeral), f"division segment {segment!r}")
        normalised = numeral.lower()
        _require(bool(_ID_SAFE.fullmatch(normalised)), f"division numeral {numeral!r}")
        segments.append(f"{DIVISION_KINDS[kind.lower()]}:{normalised}")
    return f"{version_id}/body/" + "/".join(segments)


def inventory_sha256(inventory: Mapping[str, Any]) -> str:
    """SHA-256 of the inventory's canonical serialization (equal to the LF file's bytes)."""
    return hashlib.sha256(serialize_inventory(inventory).encode("utf-8")).hexdigest()


class ProvisionStore:
    """All provisions of the registered versions, in source order, with lookups."""

    def __init__(self, registry: Registry, provisions: Iterable[Provision],
                 missing: Iterable[tuple[str, str]]) -> None:
        self.registry = registry
        self._provisions = {p.provision_id: p for p in provisions}
        self.missing = tuple(missing)  # (version_id, entry_id) of expected_missing entries

    def __iter__(self):
        return iter(self._provisions.values())

    def __len__(self) -> int:
        return len(self._provisions)

    def get(self, provision_id: str) -> Provision:
        try:
            return self._provisions[provision_id]
        except KeyError:
            raise ProvisionError(f"unknown provision {provision_id!r}") from None

    def articles(self, version_id: str | None = None) -> list[Provision]:
        return [p for p in self if p.is_article and version_id in (None, p.version_id)]

    def divisions(self, version_id: str | None = None) -> list[Provision]:
        return [p for p in self if not p.is_article and version_id in (None, p.version_id)]

    def resolve_instrument(self, name: str) -> Instrument:
        """The instrument whose ID or alias equals `name`, ignoring case and outer spaces."""
        key = name.strip().casefold()
        for instrument in self.registry.instruments:
            names = {instrument.instrument_id, *instrument.aliases}
            if key in {n.casefold() for n in names}:
                return instrument
        raise ProvisionError(f"unknown instrument {name!r}")

    def lookup(self, instrument: str, label: str) -> Provision:
        """The article printed with `label` (exactly, or equal after normalise_label).

        No fuzzy matching: '2-quindecies' never finds '2-quinquiesdecies'.
        """
        inst = self.resolve_instrument(instrument)
        versions = [v for v in self.registry.versions if v.instrument_id == inst.instrument_id]
        _require(len(versions) == 1,
                 f"{inst.instrument_id} has {len(versions)} versions; name the version")
        candidates = self.articles(versions[0].version_id)
        exact = [p for p in candidates if p.label_as_printed == label]
        found = exact or [p for p in candidates if p.normalised_label == normalise_label(label)]
        _require(len(found) == 1, f"no article {label!r} in {versions[0].version_id}"
                 if not found else f"article {label!r} is ambiguous in {versions[0].version_id}")
        return found[0]


def build_store(
    registry: Registry,
    inventories: Mapping[str, Mapping[str, Any]],
    ledger: Iterable[ReviewRecord],
) -> ProvisionStore:
    """Build all provisions. `inventories` maps version_id to the parsed inventory."""
    _require(set(inventories) == {v.version_id for v in registry.versions},
             "an inventory is needed for exactly each registered version")
    records = {(r.inventory_id, r.entry_id): r for r in ledger}
    used: set[tuple[str, str]] = set()
    provisions: list[Provision] = []
    missing: list[tuple[str, str]] = []
    article_ids: dict[str, str] = {}
    for version in registry.versions:
        inventory = inventories[version.version_id]
        try:
            validate_inventory(inventory)
        except ValueError as exc:
            raise ProvisionError(f"inventory for {version.version_id}: {exc}") from None
        document = inventory["document"]
        _require(document["sha256"] == version.source_sha256,
                 f"{version.version_id}: inventory describes another source file")
        inv_id, prefix = inventory["inventory_id"], inventory["entry_id_prefix"]
        inv_sha = inventory_sha256(inventory)
        common = {
            "version_id": version.version_id,
            "instrument_id": version.instrument_id,
            "inventory_id": inv_id,
            "inventory_sha256": inv_sha,
            "source_sha256": document["sha256"],
            "doc_id": document["doc_id"],
        }
        division_ids: dict[str, str] = {}
        paths: dict[str, str] = {}
        for d in inventory["divisions"]:
            pid = division_provision_id(version.version_id, prefix, d["division_id"])
            parent = division_ids.get(d["parent_id"]) if d["parent_id"] else None
            path = d["label"] if not d["parent_id"] else f"{paths[d['parent_id']]} > {d['label']}"
            division_ids[d["division_id"]], paths[d["division_id"]] = pid, path
            marker = d["status_marker"]
            provisions.append(
                Provision(
                    provision_id=pid, kind=DIVISION_KINDS[d["kind"]],
                    label_as_printed=d["label"], normalised_label=d["label"].lower(),
                    heading_as_printed=d["heading_as_printed"], title=d["title"],
                    status_marker=marker, parent_id=parent, path=path,
                    page_start=d["page"], page_end=d["page"],
                    structural_status=StructuralStatus.AUTO_UNREVIEWED,
                    review=Review("pending_human_review"),
                    source_status_representation=(
                        SourceStatus.MARKED_REPEALED if marker and REPEAL_MARKER.search(marker)
                        else version.provision_status_representation
                    ),
                    inventory_ref=d["division_id"], notes=tuple(d["notes"]), **common,
                )
            )
        for e in inventory["entries"]:
            record = records.get((inv_id, e["entry_id"]))
            if record is not None:
                used.add((inv_id, e["entry_id"]))
            review = _review(e, record, inv_id)
            if e["structural_status"] == "expected_missing":
                missing.append((version.version_id, e["entry_id"]))
                continue
            pid = article_id(version.version_id, e["label"])
            _require(pid not in article_ids,
                     f"{e['entry_id']} and {article_ids.get(pid)} both become {pid}")
            article_ids[pid] = e["entry_id"]
            structural = _structural_status(e["structural_status"], review)
            if structural == StructuralStatus.AMBIGUOUS:
                representation = None
            elif e["structural_status"] == "marked_repealed":
                representation = SourceStatus.MARKED_REPEALED
            else:
                representation = version.provision_status_representation
            parent_path = e["parent_path"]
            provisions.append(
                Provision(
                    provision_id=pid, kind="article", label_as_printed=e["label"],
                    normalised_label=normalise_label(e["label"]),
                    heading_as_printed=e["heading_as_printed"], title=e["title"],
                    status_marker=e["status_marker"],
                    parent_id=division_ids[e["parent_id"]] if e["parent_id"] else None,
                    path=(f"{parent_path} > " if parent_path else "") + e["heading_as_printed"],
                    page_start=e["page_start"], page_end=e["page_end"],
                    structural_status=structural, review=review,
                    source_status_representation=representation,
                    inventory_ref=e["entry_id"], notes=tuple(e["notes"]), **common,
                )
            )
    unused = sorted(set(records) - used)
    _require(not unused, f"review ledger records for unknown entries: {unused}")
    return ProvisionStore(registry, provisions, missing)


def _review(entry: Mapping[str, Any], record: ReviewRecord | None, inv_id: str) -> Review:
    where = f"{inv_id} {entry['entry_id']}"
    if entry["review_status"] == "pending_human_review":
        _require(record is None, f"{where}: ledger record for an entry that is not reviewed")
        return Review("pending_human_review")
    _require(record is not None,
             f"{where}: reviewed in the inventory but no review ledger record says how")
    _require((record.checked_by, record.checked_on) == (entry["checked_by"], entry["checked_on"]),
             f"{where}: ledger reviewer or date differs from the inventory")
    for c in record.corrections:
        _require(entry[c.field] == c.after,
                 f"{where}: corrected {c.field} is {entry[c.field]!r}, ledger says {c.after!r}")
    return Review("reviewed", record.checked_by, record.checked_on, record.outcome,
                  record.corrections, record.official_check)


def _structural_status(inventory_status: str, review: Review) -> StructuralStatus:
    if inventory_status in ("ambiguous", "uncertain", "duplicate_label"):
        return StructuralStatus.AMBIGUOUS
    if review.status == "pending_human_review":
        return StructuralStatus.AUTO_UNREVIEWED
    if review.outcome == "confirmed":
        return StructuralStatus.AUTO_VERIFIED
    return StructuralStatus.MANUALLY_CURATED


def load_store(
    registry_path: Path = REGISTRY_PATH,
    ledger_path: Path = LEDGER_PATH,
    base_dir: Path = PROJECT_ROOT,
) -> ProvisionStore:
    """Load the registry, its inventories and the ledger, and build the store."""
    registry = load_registry(registry_path)
    inventories = {}
    for version in registry.versions:
        path = base_dir / version.inventory_path
        try:
            inventories[version.version_id] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ProvisionError(f"{path}: {exc}") from None
    return build_store(registry, inventories, load_ledger(ledger_path))
