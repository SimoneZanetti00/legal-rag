"""Segment maps and passage links (P1.3): exact anchors between source text and provisions.

A segment map divides the extracted text of one source document (the content
that src.ingestion.load_document returns for one ingestion variant) into
contiguous segments, with no gaps or overlaps. Each segment has a kind:

    front_matter, preamble, recitals, enacting_formula, division_heading,
    article, editorial_note, footnote, page_furniture, closing_formula

Only `article` segments supply article text. Editorial notes and footnotes inside
an article keep the article's provision_id as context; running headers
(`page_furniture`) belong to no provision. The text of every segment is stored,
so the map reproduces the extracted text exactly; content_sha256 checks it.

Segmentation is decided only by exact lines:
- article and division headings: the line equal to the inventory's
  heading_as_printed on its page, exactly once, in inventory order;
- other regions, running headers, editorial notes and footnotes: the
  registry's rules for the version, each with an expected count.
Anything unexpected fails; nothing is guessed.

Passage links place every chunk of the variant's chunk file at exact offsets in
that text (see `locate_chunks`) and record the provisions and segments it
overlaps. No fuzzy, normalised or approximate matching is used anywhere.

Files (derived, under the corpus build directory, never overwritten):
    <build>/anchors/<variant_id>.segments.json
    <build>/anchors/<variant_id>.links.jsonl
"""

from __future__ import annotations

import hashlib
import json
import re
from bisect import bisect_right
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.chunk_store import read_chunks
from src.config import PROJECT_ROOT
from src.corpus_build import BUILD_RECORD, verify_build
from src.corpus_identity import (
    CodeVersion,
    CorpusBuild,
    IngestionVariant,
    canonical_json,
    current_dependency_versions,
    file_sha256,
    reader_for_path,
)
from src.ingestion import PAGE_SEPARATOR, load_document
from src.models import LegalChunk
from src.provisions import Provision, ProvisionStore, Registry, SegmentationRules, Version

SCHEMA_VERSION = 1
ANCHORS_DIR = "anchors"
SEGMENT_KINDS = (
    "front_matter",
    "preamble",
    "recitals",
    "enacting_formula",
    "division_heading",
    "article",
    "editorial_note",
    "footnote",
    "page_furniture",
    "closing_formula",
)


class AnchorError(RuntimeError):
    """Text, provenance or matching could not be established exactly; nothing is guessed."""


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- Extraction provenance -------------------------------------------------------------------


@dataclass(frozen=True)
class Extraction:
    """What produced the extracted text of one source: equal for a map and its variant."""

    source_sha256: str
    doc_id: str
    reader: str
    end_before: str | None
    page_separator: str
    code: Mapping[str, Any]  # CodeVersion record
    dependencies: Mapping[str, str]

    @classmethod
    def of_variant(cls, variant: IngestionVariant) -> Extraction:
        return cls(
            source_sha256=variant.source_sha256,
            doc_id=variant.doc_id,
            reader=variant.reader,
            end_before=variant.end_before,
            page_separator=PAGE_SEPARATOR,
            code=variant.code.to_record(),
            dependencies=dict(variant.dependencies),
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "source_sha256": self.source_sha256,
            "doc_id": self.doc_id,
            "reader": self.reader,
            "end_before": self.end_before,
            "page_separator": self.page_separator,
            "code": dict(self.code),
            "dependencies": dict(self.dependencies),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Extraction:
        keys = {"source_sha256", "doc_id", "reader", "end_before", "page_separator", "code",
                "dependencies"}
        if not isinstance(record, Mapping) or set(record) != keys:
            raise AnchorError(f"extraction record must have the keys {sorted(keys)}")
        return cls(**{k: record[k] for k in keys})


def structure_sha256(provisions: Iterable[Provision]) -> str:
    """Hash of the inventory fields that decide segmentation, in source order.

    Review fields and titles are left out, so recording a review does not make
    anchors stale; a changed heading, page or label (provision ID) does.
    """
    rows = [[p.kind, p.provision_id, p.heading_as_printed, p.page_start] for p in provisions]
    return hashlib.sha256(canonical_json(rows)).hexdigest()


# --- Segments ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Segment:
    index: int
    char_start: int
    char_end: int
    kind: str
    provision_id: str | None
    page: int
    page_end: int
    text: str

    @property
    def text_sha256(self) -> str:
        return _sha(self.text)

    def to_record(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "kind": self.kind,
            "provision_id": self.provision_id,
            "page": self.page,
            "page_end": self.page_end,
            "text_sha256": self.text_sha256,
            "text": self.text,
        }


@dataclass(frozen=True)
class _Line:
    start: int  # offset of the first non-space character
    text: str  # the line stripped of surrounding whitespace

    @property
    def end(self) -> int:
        return self.start + len(self.text)


def _lines(content: str) -> list[_Line]:
    lines, offset = [], 0
    for raw in content.split("\n"):
        stripped = raw.strip()
        if stripped:
            lines.append(_Line(offset + len(raw) - len(raw.lstrip()), stripped))
        offset += len(raw) + 1
    return lines


def _page_at(page_starts: Sequence[int], offset: int) -> int:
    return bisect_right(page_starts, offset)


def _skip_whitespace(content: str, pos: int) -> int:
    while pos < len(content) and content[pos].isspace():
        pos += 1
    return pos


def segment_text(
    content: str,
    page_starts: Sequence[int],
    rules: SegmentationRules,
    articles: Sequence[Provision],
    divisions: Sequence[Provision],
) -> list[Segment]:
    """Divide `content` into segments; raise AnchorError when anything is not as expected."""
    if not page_starts or page_starts[0] != 0:
        raise AnchorError("segmentation needs paginated text (page_starts starting at 0)")
    if not articles:
        raise AnchorError("segmentation needs at least one article")
    lines = _lines(content)

    def page(offset: int) -> int:
        return _page_at(page_starts, offset)

    # Running headers: lines fully matching a furniture pattern.
    furniture_res = [re.compile(p) for p in rules.furniture_patterns]
    furniture = [ln for ln in lines if any(r.fullmatch(ln.text) for r in furniture_res)]
    if len(furniture) != rules.furniture_expected_lines:
        raise AnchorError(
            f"expected {rules.furniture_expected_lines} running-header lines, "
            f"found {len(furniture)}"
        )
    furniture_starts = {ln.start for ln in furniture}
    text_lines = [ln for ln in lines if ln.start not in furniture_starts]

    events: list[tuple[int, str, str | None]] = []  # (offset, kind, provision_id)

    def place(provisions: Sequence[Provision], kind: str) -> list[int]:
        """Each heading's line: on its page, in source order, and the only possible choice.

        A heading may be printed more than once on its page ("CAPO I" under two TITOLI).
        The headings must take lines in strictly increasing order, so the earliest and the
        latest feasible line are computed for each; they must coincide, or the placement
        is not forced by the source and fails.
        """
        candidates = []
        for p in provisions:
            hits = [ln.start for ln in text_lines
                    if ln.text == p.heading_as_printed and page(ln.start) == p.page_start]
            if not hits:
                raise AnchorError(
                    f"heading {p.heading_as_printed!r} of {p.provision_id} is not printed as a "
                    f"line on page {p.page_start}"
                )
            candidates.append(hits)
        earliest, position = [], -1
        for p, hits in zip(provisions, candidates):
            later = [h for h in hits if h > position]
            if not later:
                raise AnchorError(f"heading of {p.provision_id} cannot follow the one before it")
            position = later[0]
            earliest.append(position)
        latest, position = [], len(content)
        for p, hits in zip(reversed(provisions), reversed(candidates)):
            earlier = [h for h in hits if h < position]
            if not earlier:
                raise AnchorError(f"heading of {p.provision_id} cannot precede the one after it")
            position = earlier[-1]
            latest.append(position)
        latest.reverse()
        for p, low, high, hits in zip(provisions, earliest, latest, candidates):
            if low != high:
                raise AnchorError(
                    f"heading {p.heading_as_printed!r} of {p.provision_id} is printed "
                    f"{len(hits)} times on page {p.page_start} and the source order does not "
                    "decide which line it is"
                )
        for p, offset in zip(provisions, earliest):
            events.append((offset, kind, p.provision_id))
        return earliest

    article_offsets = place(articles, "article")
    division_offsets = dict(zip((d.provision_id for d in divisions),
                                place(divisions, "division_heading")))
    for p, offset in zip(articles, article_offsets):
        if p.parent_id is not None and division_offsets.get(p.parent_id, -1) >= offset:
            raise AnchorError(f"{p.provision_id} is printed before its parent division")

    # Regions outside the articles: exactly one line each, in the stated order.
    previous = -1
    for marker in rules.markers:
        hits = [ln.start for ln in text_lines if ln.text.startswith(marker.line_starts_with)]
        if len(hits) != 1:
            raise AnchorError(
                f"{marker.kind}: expected exactly one line starting with "
                f"{marker.line_starts_with!r}, found {len(hits)}"
            )
        offset = hits[0]
        if offset <= previous:
            raise AnchorError(f"{marker.kind} is out of the expected order")
        if marker.kind == "closing_formula":
            if offset <= max(o for o, _, _ in events):
                raise AnchorError("the closing formula is not after the last heading")
        elif offset >= article_offsets[0]:
            raise AnchorError(f"{marker.kind} is not before the first article heading")
        previous = offset
        events.append((offset, marker.kind, None))

    events.sort()
    offsets = [e[0] for e in events]
    if len(offsets) != len(set(offsets)):
        raise AnchorError("two headings or markers start at the same offset")

    def state_at(offset: int) -> tuple[str, str | None]:
        i = bisect_right(offsets, offset) - 1
        return ("front_matter", None) if i < 0 else (events[i][1], events[i][2])

    # Editorial notes: a separator line directly followed by a label line, inside an article.
    note_events = []
    if rules.editorial_notes is not None:
        sep = re.compile(rules.editorial_notes.separator_pattern)
        label = re.compile(rules.editorial_notes.label_pattern)
        for i, ln in enumerate(text_lines):
            is_sep, is_label = bool(sep.fullmatch(ln.text)), bool(label.fullmatch(ln.text))
            if is_sep and not (i + 1 < len(text_lines) and label.fullmatch(text_lines[i + 1].text)):
                raise AnchorError(f"separator line at {ln.start} is not followed by a note label")
            if is_label and not (i > 0 and sep.fullmatch(text_lines[i - 1].text)):
                raise AnchorError(f"note label at {ln.start} has no separator line before it")
            if is_sep:
                kind, owner = state_at(ln.start)
                if kind not in ("article", "editorial_note"):
                    raise AnchorError(f"editorial note at {ln.start} is not inside an article")
                note_events.append((ln.start, "editorial_note", owner))
        if len(note_events) != rules.editorial_notes.expected:
            raise AnchorError(
                f"expected {rules.editorial_notes.expected} editorial notes, found "
                f"{len(note_events)}"
            )
    events = sorted(events + note_events)
    offsets = [e[0] for e in events]

    # Interruptions: running-header spans and footnote spans, each with trailing whitespace.
    spans: list[tuple[int, int, str, str | None]] = []
    i = 0
    furniture_sorted = sorted(furniture, key=lambda ln: ln.start)
    while i < len(furniture_sorted):
        start, end = furniture_sorted[i].start, furniture_sorted[i].end
        while (i + 1 < len(furniture_sorted)
               and not content[end:furniture_sorted[i + 1].start].strip()):
            i += 1
            end = furniture_sorted[i].end
        spans.append((start, _skip_whitespace(content, end), "page_furniture", None))
        i += 1
    if rules.footnotes is not None:
        start_re = re.compile(rules.footnotes.start_line_pattern)
        end_re = re.compile(rules.footnotes.end_text_pattern)
        found = 0
        for ln in text_lines:
            if not start_re.match(ln.text):
                continue
            kind, owner = state_at(ln.start)
            if kind != "article":
                continue  # outside the articles, e.g. in the recitals: not handled here
            window = content[ln.start : ln.start + rules.footnotes.max_chars]
            m = end_re.search(window)
            if m is None:
                raise AnchorError(
                    f"footnote at {ln.start} (page {page(ln.start)}) has no end within "
                    f"{rules.footnotes.max_chars} characters"
                )
            spans.append((ln.start, _skip_whitespace(content, ln.start + m.end()), "footnote",
                          owner))
            found += 1
        if found != rules.footnotes.expected:
            raise AnchorError(f"expected {rules.footnotes.expected} footnotes, found {found}")
    spans.sort()
    for (a_start, a_end, a_kind, _), (b_start, _, b_kind, _) in zip(spans, spans[1:]):
        if b_start < a_end:
            raise AnchorError(f"{a_kind} at {a_start} overlaps {b_kind} at {b_start}")
    for start, end, kind, _ in spans:
        inside = [o for o in offsets if start < o < end]
        if inside:
            raise AnchorError(f"{kind} at {start} contains a heading or marker at {inside[0]}")

    # Sweep: every boundary starts a new segment.
    boundaries = sorted({0, len(content), *offsets, *(s for s, *_ in spans),
                         *(e for _, e, *_ in spans)})
    span_starts = [s for s, *_ in spans]
    segments: list[Segment] = []
    for a, b in zip(boundaries, boundaries[1:]):
        if a >= b:
            continue
        j = bisect_right(span_starts, a) - 1
        if j >= 0 and spans[j][0] <= a < spans[j][1]:
            kind, owner = spans[j][2], spans[j][3]
        else:
            k = bisect_right(offsets, a) - 1
            kind, owner = ("front_matter", None) if k < 0 else (events[k][1], events[k][2])
        segments.append(
            Segment(len(segments), a, b, kind, owner, page(a), page(b - 1), content[a:b])
        )

    covered = {s.provision_id for s in segments if s.kind == "article"}
    missing = [p.provision_id for p in articles if p.provision_id not in covered]
    if missing:
        raise AnchorError(f"articles without text: {missing[:5]}")
    first = {}
    for s in segments:
        if s.kind == "article":
            first.setdefault(s.provision_id, s)
    for p, offset in zip(articles, article_offsets):
        if first[p.provision_id].char_start != offset or not first[
            p.provision_id
        ].text.startswith(p.heading_as_printed):
            raise AnchorError(f"{p.provision_id}: its first segment does not start at its heading")
    return segments


# --- Segment maps ----------------------------------------------------------------------------


@dataclass(frozen=True)
class SegmentMap:
    build_id: str
    variant_id: str
    version_id: str
    extraction: Extraction
    content_sha256: str
    content_length: int
    page_starts: tuple[int, ...]
    structure_sha256: str
    registry_sha256: str
    segments: tuple[Segment, ...]

    @property
    def content(self) -> str:
        return "".join(s.text for s in self.segments)

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "segment-map",
            "build_id": self.build_id,
            "variant_id": self.variant_id,
            "version_id": self.version_id,
            "extraction": self.extraction.to_record(),
            "content_sha256": self.content_sha256,
            "content_length": self.content_length,
            "page_starts": list(self.page_starts),
            "structure_sha256": self.structure_sha256,
            "registry_sha256": self.registry_sha256,
            "segments": [s.to_record() for s in self.segments],
        }

    @classmethod
    def from_record(cls, record: Any) -> SegmentMap:
        """Rebuild a map and check its own integrity (coverage, offsets, pages, hashes)."""
        keys = {"schema_version", "kind", "build_id", "variant_id", "version_id", "extraction",
                "content_sha256", "content_length", "page_starts", "structure_sha256",
                "registry_sha256", "segments"}
        if not isinstance(record, Mapping) or set(record) != keys:
            raise AnchorError("segment map: unexpected or missing keys")
        if record["schema_version"] != SCHEMA_VERSION or record["kind"] != "segment-map":
            raise AnchorError("segment map: unknown schema or kind")
        page_starts = tuple(record["page_starts"])
        segments = []
        position = 0
        seg_keys = {"index", "char_start", "char_end", "kind", "provision_id", "page", "page_end",
                    "text_sha256", "text"}
        for i, raw in enumerate(record["segments"]):
            if not isinstance(raw, Mapping) or set(raw) != seg_keys:
                raise AnchorError(f"segment {i}: unexpected or missing keys")
            segment = Segment(raw["index"], raw["char_start"], raw["char_end"], raw["kind"],
                              raw["provision_id"], raw["page"], raw["page_end"], raw["text"])
            problems = []
            if segment.index != i or segment.char_start != position:
                problems.append("not contiguous with the previous segment")
            if segment.char_end <= segment.char_start or len(segment.text) != (
                segment.char_end - segment.char_start
            ):
                problems.append("length does not match its offsets")
            if segment.kind not in SEGMENT_KINDS:
                problems.append(f"unknown kind {segment.kind!r}")
            if raw["text_sha256"] != segment.text_sha256:
                problems.append("text does not match text_sha256")
            if (segment.page, segment.page_end) != (
                _page_at(page_starts, segment.char_start),
                _page_at(page_starts, segment.char_end - 1),
            ):
                problems.append("pages do not match its offsets")
            if problems:
                raise AnchorError(f"segment {i}: {'; '.join(problems)}")
            segments.append(segment)
            position = segment.char_end
        result = cls(
            build_id=record["build_id"],
            variant_id=record["variant_id"],
            version_id=record["version_id"],
            extraction=Extraction.from_record(record["extraction"]),
            content_sha256=record["content_sha256"],
            content_length=record["content_length"],
            page_starts=page_starts,
            structure_sha256=record["structure_sha256"],
            registry_sha256=record["registry_sha256"],
            segments=tuple(segments),
        )
        if position != result.content_length:
            raise AnchorError("segment map: segments do not cover the whole text")
        if _sha(result.content) != result.content_sha256:
            raise AnchorError("segment map: the text does not match content_sha256")
        return result


def build_segment_map(
    content: str,
    page_starts: Sequence[int],
    *,
    variant: IngestionVariant,
    version: Version,
    store: ProvisionStore,
    registry: Registry,
    build_id: str,
) -> SegmentMap:
    """The segment map of one variant's extracted text."""
    articles = store.articles(version.version_id)
    divisions = store.divisions(version.version_id)
    segments = segment_text(content, page_starts, version.segmentation, articles, divisions)
    return SegmentMap(
        build_id=build_id,
        variant_id=variant.variant_id,
        version_id=version.version_id,
        extraction=Extraction.of_variant(variant),
        content_sha256=_sha(content),
        content_length=len(content),
        page_starts=tuple(page_starts),
        structure_sha256=structure_sha256([*articles, *divisions]),
        registry_sha256=registry.sha256,
        segments=tuple(segments),
    )


def check_segment_map(
    segment_map: SegmentMap,
    *,
    variant: IngestionVariant,
    build_id: str,
    structure: str,
    registry_sha256: str,
) -> None:
    """Refuse a map whose provenance differs from the variant, build, inventory or registry."""
    expected = Extraction.of_variant(variant)
    problems = []
    if segment_map.build_id != build_id:
        problems.append(f"build {segment_map.build_id} is not {build_id}")
    if segment_map.variant_id != variant.variant_id:
        problems.append(f"variant {segment_map.variant_id} is not {variant.variant_id}")
    for field in ("source_sha256", "doc_id", "reader", "end_before", "page_separator", "code",
                  "dependencies"):
        if getattr(segment_map.extraction, field) != getattr(expected, field):
            problems.append(f"extraction {field} differs")
    if segment_map.structure_sha256 != structure:
        problems.append("the inventory structure (headings, pages, labels) changed")
    if segment_map.registry_sha256 != registry_sha256:
        problems.append("the instrument registry changed")
    if problems:
        raise AnchorError("stale or inconsistent segment map: " + "; ".join(problems))


# --- Exact chunk placement ---------------------------------------------------------------------


def expected_chunk_id(doc_id: str, index: int, text: str) -> str:
    """The chunk ID src.chunking assigns: doc ID, index and the first 8 hex of the text hash."""
    return f"{doc_id}-{index:04d}-{_sha(text)[:8]}"


def locate_chunks(
    content: str,
    page_starts: Sequence[int],
    chunks: Sequence[LegalChunk],
    doc_id: str,
) -> list[tuple[int, int]]:
    """Exact offsets of each chunk, in index order. Raise AnchorError unless every placement
    is exact and unique.

    Chunk i must start strictly after chunk i-1's start and no later than the end of
    chunk i-1 plus the whitespace that follows it (chunks overlap or are separated only
    by whitespace). Exactly one occurrence of its text may start in that window, and its
    first and last characters must be on its recorded pages. Afterwards, every
    non-whitespace character of the content must lie inside some chunk.
    """
    if not chunks:
        raise AnchorError(f"{doc_id}: no chunks to place")
    spans: list[tuple[int, int]] = []
    for expected_index, chunk in enumerate(chunks):
        where = f"chunk {chunk.chunk_id}"
        if chunk.doc_id != doc_id:
            raise AnchorError(f"{where}: belongs to {chunk.doc_id}, not {doc_id}")
        if chunk.chunk_index != expected_index:
            raise AnchorError(f"{where}: index {chunk.chunk_index}, expected {expected_index}")
        if chunk.chunk_id != expected_chunk_id(doc_id, chunk.chunk_index, chunk.text):
            raise AnchorError(f"{where}: the ID does not match its document, index and text")
        text = chunk.text
        if spans:
            previous_start, previous_end = spans[-1]
            low, high = previous_start + 1, _skip_whitespace(content, previous_end)
        else:
            low, high = 0, _skip_whitespace(content, 0)
        candidates = []
        position = content.find(text, low)
        while position != -1 and position <= high:
            candidates.append(position)
            position = content.find(text, position + 1)
        if len(candidates) != 1:
            state = "not found" if not candidates else f"found {len(candidates)} times"
            raise AnchorError(
                f"{where}: text {state} where it must start (offsets {low}..{high}); no "
                "placement is assumed"
            )
        start = candidates[0]
        end = start + len(text)
        location = chunk.location
        if location.page is not None and (
            _page_at(page_starts, start) != location.page
            or _page_at(page_starts, end - 1) != location.page_end
        ):
            raise AnchorError(
                f"{where}: placed on pages {_page_at(page_starts, start)}-"
                f"{_page_at(page_starts, end - 1)}, recorded {location.page}-{location.page_end}"
            )
        spans.append((start, end))
    covered_to = 0
    for start, end in spans:
        if content[covered_to:start].strip():
            raise AnchorError(f"{doc_id}: text at {covered_to}..{start} is in no chunk")
        covered_to = max(covered_to, end)
    if content[covered_to:].strip():
        raise AnchorError(f"{doc_id}: text after {covered_to} is in no chunk")
    return spans


# --- Passage links ---------------------------------------------------------------------------


def _non_whitespace(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def link_chunks(segment_map: SegmentMap, chunks: Sequence[LegalChunk]) -> list[dict[str, Any]]:
    """One link record per chunk: exact offsets and every non-empty overlap.

    `provisions` lists the article provisions whose article text the chunk overlaps;
    `context` lists the other segments it overlaps (division headings, editorial notes,
    footnotes, running headers, and so on). Overlaps of whitespace only are left out.
    """
    content = segment_map.content
    spans = locate_chunks(content, segment_map.page_starts, chunks,
                          segment_map.extraction.doc_id)
    segments = segment_map.segments
    starts = [s.char_start for s in segments]
    links = []
    for chunk, (start, end) in zip(chunks, spans):
        provisions: dict[str, list[int]] = {}
        context: dict[tuple[str, str | None], list[int]] = {}
        i = bisect_right(starts, start) - 1
        while i < len(segments) and segments[i].char_start < end:
            segment = segments[i]
            a, b = max(start, segment.char_start), min(end, segment.char_end)
            count = _non_whitespace(content[a:b])
            if count:
                bucket = provisions if segment.kind == "article" else context
                key = segment.provision_id if segment.kind == "article" else (
                    segment.kind, segment.provision_id)
                entry = bucket.setdefault(key, [a, b, 0])
                entry[0], entry[1], entry[2] = min(entry[0], a), max(entry[1], b), entry[2] + count
            i += 1
        links.append(
            {
                "chunk_id": chunk.chunk_id,
                "chunk_index": chunk.chunk_index,
                "char_start": start,
                "char_end": end,
                "page": _page_at(segment_map.page_starts, start),
                "page_end": _page_at(segment_map.page_starts, end - 1),
                "provisions": [
                    {"provision_id": pid, "char_start": a, "char_end": b, "chars": n}
                    for pid, (a, b, n) in sorted(provisions.items(), key=lambda kv: kv[1][0])
                ],
                "context": [
                    {"kind": kind, "provision_id": pid, "char_start": a, "char_end": b,
                     "chars": n}
                    for (kind, pid), (a, b, n) in sorted(context.items(),
                                                         key=lambda kv: (kv[1][0], kv[0][0]))
                ],
            }
        )
    return links


# --- Files -------------------------------------------------------------------------------------


def _dump(record: Any) -> str:
    return json.dumps(record, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def _line(record: Any) -> str:
    return canonical_json(record).decode("utf-8") + "\n"


def segment_map_path(build_dir: Path, variant_id: str) -> Path:
    return build_dir / ANCHORS_DIR / f"{variant_id}.segments.json"


def links_path(build_dir: Path, variant_id: str) -> Path:
    return build_dir / ANCHORS_DIR / f"{variant_id}.links.jsonl"


def _resolve(path: str, base_dir: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else base_dir / p


def _build_sources(build_dir: Path, build: CorpusBuild) -> dict[str, str]:
    """variant_id -> version_id, from the build record."""
    record = json.loads((build_dir / BUILD_RECORD).read_text(encoding="utf-8"))
    mapping = {s["variant_id"]: s["version_id"] for s in record["sources"]}
    if set(mapping) != {v.variant_id for v in build.variants}:
        raise AnchorError(f"{build_dir}: the record's sources do not match its variants")
    return mapping


def write_segment_maps(
    build_dir: Path,
    *,
    store: ProvisionStore,
    registry: Registry,
    detect_code: Callable[[], CodeVersion],
    base_dir: Path = PROJECT_ROOT,
) -> list[Path]:
    """Write one segment map per variant of a finished build; never overwrite one.

    The text is extracted again with the same code and libraries as the build; any
    difference in code version, dependency versions, source file or document refuses.
    """
    build = verify_build(build_dir, base_dir=base_dir)
    versions = _build_sources(build_dir, build)
    targets = {v.variant_id: segment_map_path(build_dir, v.variant_id) for v in build.variants}
    existing = [str(p) for p in targets.values() if p.exists()]
    if existing:
        raise AnchorError(f"segment maps already exist and are never overwritten: {existing}")
    code = detect_code()
    dependencies = current_dependency_versions()
    maps = []
    for variant in build.variants:
        version = registry.version(versions[variant.variant_id])
        if version.source_sha256 != variant.source_sha256:
            raise AnchorError(f"{variant.variant_id}: the registry expects another source file")
        if variant.code != code:
            raise AnchorError(
                f"{variant.variant_id}: built with {variant.code.describe()}, current code is "
                f"{code.describe()}; extract with the build's code or make a new build"
            )
        if dict(variant.dependencies) != dependencies:
            raise AnchorError(f"{variant.variant_id}: built with {dict(variant.dependencies)}, "
                              f"installed {dependencies}")
        source = _resolve(variant.source_path or "", base_dir)
        if not source.is_file() or file_sha256(source) != variant.source_sha256:
            raise AnchorError(f"{variant.variant_id}: source file {source} missing or changed")
        if reader_for_path(source) != variant.reader:
            raise AnchorError(f"{variant.variant_id}: reader differs from the variant's")
        document, _ = load_document(source, end_before=variant.end_before)
        if document.doc_id != variant.doc_id:
            raise AnchorError(f"{variant.variant_id}: extracted document is {document.doc_id}")
        maps.append(build_segment_map(document.content, document.page_starts, variant=variant,
                                      version=version, store=store, registry=registry,
                                      build_id=build.build_id))
    (build_dir / ANCHORS_DIR).mkdir(exist_ok=True)
    for segment_map in maps:  # only after every map was built
        target = targets[segment_map.variant_id]
        target.write_text(_dump(segment_map.to_record()), encoding="utf-8", newline="\n")
    return [targets[m.variant_id] for m in maps]


def load_segment_map(
    build_dir: Path,
    variant: IngestionVariant,
    *,
    build_id: str,
    store: ProvisionStore,
    registry: Registry,
    version_id: str,
) -> SegmentMap:
    """Read a map, check its integrity and refuse it if any provenance part is stale."""
    path = segment_map_path(build_dir, variant.variant_id)
    try:
        segment_map = SegmentMap.from_record(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError) as exc:
        raise AnchorError(f"{path}: {exc}") from None
    if segment_map.version_id != version_id:
        raise AnchorError(f"{path}: version {segment_map.version_id} is not {version_id}")
    structure = structure_sha256(
        [*store.articles(version_id), *store.divisions(version_id)])
    check_segment_map(segment_map, variant=variant, build_id=build_id, structure=structure,
                      registry_sha256=registry.sha256)
    return segment_map


def write_passage_links(
    build_dir: Path,
    *,
    store: ProvisionStore,
    registry: Registry,
    base_dir: Path = PROJECT_ROOT,
) -> list[Path]:
    """Write one links file per variant from its chunk file and segment map; never overwrite."""
    build = verify_build(build_dir, base_dir=base_dir)
    versions = _build_sources(build_dir, build)
    targets = {v.variant_id: links_path(build_dir, v.variant_id) for v in build.variants}
    existing = [str(p) for p in targets.values() if p.exists()]
    if existing:
        raise AnchorError(f"passage links already exist and are never overwritten: {existing}")
    texts = {}
    for variant in build.variants:
        path = segment_map_path(build_dir, variant.variant_id)
        segment_map = load_segment_map(build_dir, variant, build_id=build.build_id, store=store,
                                       registry=registry, version_id=versions[variant.variant_id])
        chunk_path = _resolve(variant.output.path, base_dir)
        chunks = list(read_chunks(chunk_path))
        links = link_chunks(segment_map, chunks)
        header = {
            "schema_version": SCHEMA_VERSION,
            "kind": "passage-links",
            "build_id": build.build_id,
            "variant_id": variant.variant_id,
            "doc_id": variant.doc_id,
            "chunk_file_sha256": variant.output.sha256,
            "segment_map_sha256": file_sha256(path),
            "content_sha256": segment_map.content_sha256,
            "chunk_count": len(chunks),
        }
        texts[targets[variant.variant_id]] = _line(header) + "".join(_line(x) for x in links)
    for target, text in texts.items():  # only after every variant was linked
        target.write_text(text, encoding="utf-8", newline="\n")
    return list(texts)
