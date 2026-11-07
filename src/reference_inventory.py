"""Reference inventories of legal provisions (P1.2): format, validation, serialization.

An inventory lists the articles of one source document as printed in it, with
pages, parent divisions and a structural status. It is built from the source
document, not from parser or chunk output, and records separately whether a
person has reviewed each entry. The format is documented in
data/reference/README.md.

Nothing here reads a PDF, runs the parser or writes files.
"""

from __future__ import annotations

import datetime
import json
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

STRUCTURAL_STATUSES = (
    "present",
    "marked_repealed",
    "duplicate_label",
    "uncertain",
    "ambiguous",
    "expected_missing",
)
REVIEW_STATUSES = ("pending_human_review", "reviewed")

# Key order used when writing; keys not listed here are rejected (entries,
# divisions) or written after the listed ones in sorted order (other objects).
TOP_KEYS = (
    "schema_version",
    "inventory_id",
    "entry_id_prefix",
    "document",
    "scope",
    "provenance",
    "source_notes",
    "divisions",
    "entries",
)
DOCUMENT_KEYS = (
    "doc_id",
    "path",
    "sha256",
    "size_bytes",
    "page_count",
    "title_as_printed",
    "nature",
    "caveats",
)
SCOPE_KEYS = ("description", "first_page", "last_page", "starts_at", "ends_before", "excluded")
PROVENANCE_KEYS = (
    "generated_on",
    "generated_by",
    "method",
    "parser_output_used",
    "human_review",
)
DIVISION_KEYS = (
    "division_id",
    "kind",
    "label",
    "heading_as_printed",
    "title",
    "status_marker",
    "page",
    "parent_id",
    "notes",
)
ENTRY_KEYS = (
    "entry_id",
    "document_id",
    "ordinal",
    "kind",
    "heading_as_printed",
    "label",
    "title",
    "status_marker",
    "page_start",
    "page_end",
    "parent_id",
    "parent_path",
    "structural_status",
    "review_status",
    "checked_by",
    "checked_on",
    "source_sha256",
    "notes",
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# Printed text that marks an article as repealed or no longer provided for.
REPEAL_MARKER = re.compile(r"ABROGAT|NON PI[UÙ] PREVIST", re.IGNORECASE)
# Fields an expected_missing entry must leave null: nothing about it is printed.
_UNPRINTED_FIELDS = (
    "label",
    "heading_as_printed",
    "title",
    "status_marker",
    "page_start",
    "page_end",
    "parent_id",
    "parent_path",
)


class InventoryError(ValueError):
    """An inventory does not follow the format; the message lists every problem found."""


def entry_id_for(prefix: str, label: str, occurrence: int = 1) -> str:
    """The ID of the `occurrence`-th entry printed with `label` (1 for the first)."""
    base = f"{prefix}:art:{label}"
    return base if occurrence == 1 else f"{base}~{occurrence}"


def missing_entry_id_for(prefix: str, expected_label: str) -> str:
    """The ID of an `expected_missing` entry: a label implied by the numbering but not printed."""
    return f"{prefix}:missing:art:{expected_label}"


def validate_inventory(inventory: Any, *, today: datetime.date | None = None) -> None:
    """Raise InventoryError listing every format problem; return None if there are none.

    `today` (default: the current date) is the latest date accepted as checked_on.
    """
    problems: list[str] = []
    try:
        _check(inventory, problems, today or datetime.date.today())
    except (TypeError, KeyError, AttributeError) as exc:  # a value of an unexpected type
        problems.append(f"malformed inventory: {exc!r}")
    if problems:
        raise InventoryError("invalid inventory:\n- " + "\n- ".join(problems))


def serialize_inventory(inventory: Mapping[str, Any]) -> str:
    """Validated, deterministic JSON text: fixed key order, 2-space indent, UTF-8, final newline."""
    validate_inventory(inventory)
    ordered = _ordered(inventory, TOP_KEYS)
    for key, order in (
        ("document", DOCUMENT_KEYS),
        ("scope", SCOPE_KEYS),
        ("provenance", PROVENANCE_KEYS),
    ):
        ordered[key] = _ordered(inventory[key], order)
    ordered["divisions"] = [_ordered(d, DIVISION_KEYS) for d in inventory["divisions"]]
    ordered["entries"] = [_ordered(e, ENTRY_KEYS) for e in inventory["entries"]]
    return json.dumps(ordered, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def load_inventory(path: Path) -> dict[str, Any]:
    """Read and validate an inventory file."""
    inventory = json.loads(path.read_text(encoding="utf-8"))
    validate_inventory(inventory)
    return inventory


def _ordered(obj: Mapping[str, Any], order: tuple[str, ...]) -> dict[str, Any]:
    known = {key: obj[key] for key in order if key in obj}
    rest = {key: obj[key] for key in sorted(obj) if key not in order}
    return {**known, **rest}


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _is_page(value: Any) -> bool:
    return type(value) is int and value >= 1


def _check(inventory: Any, problems: list[str], today: datetime.date) -> None:
    if not isinstance(inventory, Mapping):
        problems.append("the inventory must be a JSON object")
        return
    missing = [key for key in TOP_KEYS if key not in inventory]
    unknown = sorted(set(inventory) - set(TOP_KEYS))
    if missing or unknown:
        problems.append(f"top-level keys: missing {missing}, unknown {unknown}")
        return
    if inventory["schema_version"] != SCHEMA_VERSION:
        problems.append(f"schema_version must be {SCHEMA_VERSION}")
    prefix = inventory["entry_id_prefix"]
    if not _is_text(inventory["inventory_id"]) or not _is_text(prefix):
        problems.append("inventory_id and entry_id_prefix must be non-empty strings")
        return

    document = inventory["document"]
    if not isinstance(document, Mapping) or not all(
        key in document for key in ("doc_id", "path", "sha256", "page_count")
    ):
        problems.append("document must give doc_id, path, sha256 and page_count")
        return
    sha256 = document["sha256"]
    if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
        problems.append("document.sha256 must be 64 lowercase hex characters")
    elif document["doc_id"] != "doc-" + sha256[:16]:
        problems.append("document.doc_id must be 'doc-' plus the first 16 hex characters of sha256")
    page_count = document["page_count"]
    if not _is_page(page_count):
        problems.append("document.page_count must be a positive integer")
        return
    for key in ("scope", "provenance"):
        if not isinstance(inventory[key], Mapping):
            problems.append(f"{key} must be an object")
    if not isinstance(inventory["source_notes"], list) or not all(
        _is_text(note) for note in inventory["source_notes"]
    ):
        problems.append("source_notes must be a list of non-empty strings")

    paths = _check_divisions(inventory["divisions"], page_count, problems)
    _check_entries(
        inventory["entries"], prefix, document["doc_id"], sha256, page_count, paths, problems, today
    )


def _check_divisions(divisions: Any, page_count: int, problems: list[str]) -> dict[str, str]:
    """Check the divisions; return each valid division's printed path ("CAPO III > Sezione 1")."""
    if not isinstance(divisions, list):
        problems.append("divisions must be a list")
        return {}
    paths: dict[str, str] = {}
    for index, division in enumerate(divisions):
        where = f"divisions[{index}]"
        if not isinstance(division, Mapping) or set(division) != set(DIVISION_KEYS):
            problems.append(f"{where}: must have exactly the keys {list(DIVISION_KEYS)}")
            continue
        division_id, parent_id = division["division_id"], division["parent_id"]
        if not _is_text(division_id) or division_id in paths:
            problems.append(f"{where}: division_id missing, not a string or duplicated")
            continue
        for key in ("kind", "label", "heading_as_printed"):
            if not _is_text(division[key]):
                problems.append(f"{where}: {key} must be a non-empty string")
        for key in ("title", "status_marker"):
            if division[key] is not None and not _is_text(division[key]):
                problems.append(f"{where}: {key} must be a non-empty string or null")
        if not _is_page(division["page"]) or division["page"] > page_count:
            problems.append(f"{where}: page must be between 1 and {page_count}")
        if parent_id is not None and not (isinstance(parent_id, str) and parent_id in paths):
            problems.append(f"{where}: parent_id must name an earlier division or be null")
            continue
        _check_notes(division["notes"], where, problems)
        if _is_text(division["label"]):
            label = division["label"]
            paths[division_id] = label if parent_id is None else f"{paths[parent_id]} > {label}"
    return paths


def _check_entries(
    entries: Any,
    prefix: str,
    doc_id: str,
    sha256: str,
    page_count: int,
    division_paths: dict[str, str],
    problems: list[str],
    today: datetime.date,
) -> None:
    if not isinstance(entries, list) or not entries:
        problems.append("entries must be a non-empty list")
        return
    ids: Counter[str] = Counter()
    occurrences: Counter[str] = Counter()
    labels = Counter(
        entry["label"]
        for entry in entries
        if isinstance(entry, Mapping) and isinstance(entry.get("label"), str)
    )
    for index, entry in enumerate(entries):
        where = f"entries[{index}]"
        if not isinstance(entry, Mapping) or set(entry) != set(ENTRY_KEYS):
            problems.append(f"{where}: must have exactly the keys {list(ENTRY_KEYS)}")
            continue
        if not _is_text(entry["entry_id"]):
            problems.append(f"{where}: entry_id must be a non-empty string")
            continue
        not_text = [
            key
            for key in ("label", "parent_id", "parent_path")
            if entry[key] is not None and not isinstance(entry[key], str)
        ]
        if not_text:
            problems.append(f"{where}: {not_text} must be strings or null")
            continue
        where = f"{where} ({entry['entry_id']!r})"
        ids[entry["entry_id"]] += 1
        status, review = entry["structural_status"], entry["review_status"]
        if entry["ordinal"] != index + 1 or type(entry["ordinal"]) is not int:
            problems.append(f"{where}: ordinal must be {index + 1} (the position in source order)")
        if entry["kind"] != "article":
            problems.append(f"{where}: kind must be 'article'")
        if entry["document_id"] != doc_id:
            problems.append(f"{where}: document_id must be the document's doc_id {doc_id}")
        if entry["source_sha256"] != sha256:
            problems.append(f"{where}: source_sha256 differs from the document's sha256")
        if status not in STRUCTURAL_STATUSES:
            problems.append(f"{where}: unknown structural_status {status!r}")
        if review not in REVIEW_STATUSES:
            problems.append(f"{where}: unknown review_status {review!r}")
        _check_review(entry, where, problems, today)
        _check_notes(entry["notes"], where, problems)

        label, heading = entry["label"], entry["heading_as_printed"]
        if status == "expected_missing":
            printed = [key for key in _UNPRINTED_FIELDS if entry[key] is not None]
            if printed:
                problems.append(
                    f"{where}: an expected_missing entry is not printed, so {printed} must be null"
                )
            if not entry["entry_id"].startswith(f"{prefix}:missing:art:"):
                problems.append(f"{where}: an expected_missing ID starts {prefix}:missing:art:")
            if not entry["notes"]:
                problems.append(f"{where}: an expected_missing entry must explain the gap in notes")
            continue
        if not _is_text(label) or not _is_text(heading) or not heading.endswith(" " + label):
            problems.append(f"{where}: heading_as_printed must end with the label as printed")
            continue
        occurrences[label] += 1
        expected_id = entry_id_for(prefix, label, occurrences[label])
        if entry["entry_id"] != expected_id:
            problems.append(f"{where}: entry_id must be {expected_id!r}")
        if labels[label] > 1 and status not in ("duplicate_label", "ambiguous"):
            problems.append(f"{where}: label printed more than once: needs duplicate_label")
        if status == "duplicate_label" and labels[label] == 1:
            problems.append(f"{where}: duplicate_label but the label is printed only once")
        for key in ("title", "status_marker"):
            if entry[key] is not None and not _is_text(entry[key]):
                problems.append(f"{where}: {key} must be a non-empty string or null")
        marker = entry["status_marker"] if isinstance(entry["status_marker"], str) else None
        if status == "marked_repealed" and not (marker and REPEAL_MARKER.search(marker)):
            problems.append(f"{where}: marked_repealed needs the printed repeal status_marker")
        if status == "present" and marker and REPEAL_MARKER.search(marker):
            problems.append(f"{where}: a present entry cannot carry a repeal status_marker")
        if status in ("uncertain", "ambiguous", "duplicate_label") and not entry["notes"]:
            problems.append(f"{where}: status {status} must be explained in notes")
        start, end = entry["page_start"], entry["page_end"]
        if not (_is_page(start) and _is_page(end) and start <= end <= page_count):
            problems.append(f"{where}: pages must satisfy 1 <= start <= end <= {page_count}")
        parent_id, parent_path = entry["parent_id"], entry["parent_path"]
        if parent_id is None:
            if parent_path is not None:
                problems.append(f"{where}: parent_path must be null when parent_id is null")
        elif parent_id not in division_paths:
            problems.append(f"{where}: parent_id {parent_id!r} is not a division")
        elif parent_path != division_paths[parent_id]:
            problems.append(
                f"{where}: parent_path must be {division_paths[parent_id]!r}, the printed "
                "path of parent_id"
            )

    duplicated = sorted(entry_id for entry_id, count in ids.items() if count > 1)
    if duplicated:
        problems.append(f"duplicate entry IDs: {duplicated}")


def _check_review(
    entry: Mapping[str, Any], where: str, problems: list[str], today: datetime.date
) -> None:
    checked_by, checked_on = entry["checked_by"], entry["checked_on"]
    if entry["review_status"] == "pending_human_review":
        if checked_by is not None or checked_on is not None:
            problems.append(f"{where}: a pending entry must have checked_by and checked_on null")
        return
    if entry["review_status"] != "reviewed":
        return
    if not _is_text(checked_by):
        problems.append(f"{where}: a reviewed entry needs checked_by (the person who checked it)")
    date = _calendar_date(checked_on)
    if date is None:
        problems.append(f"{where}: a reviewed entry needs checked_on as a date YYYY-MM-DD")
    elif date > today:
        problems.append(f"{where}: checked_on {checked_on} is in the future")


def _calendar_date(value: Any) -> datetime.date | None:
    """The date written exactly as YYYY-MM-DD, or None (other ISO forms are not accepted)."""
    if not isinstance(value, str) or not _ISO_DATE.fullmatch(value):
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:  # e.g. 2026-02-30
        return None


def _check_notes(notes: Any, where: str, problems: list[str]) -> None:
    if not isinstance(notes, list) or not all(_is_text(note) for note in notes):
        problems.append(f"{where}: notes must be a list of non-empty strings")
