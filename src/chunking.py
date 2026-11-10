"""Legal-aware chunking of a `LegalDocument` into `LegalChunk`s.

The heuristics are deliberately conservative; they will miss some structures
and occasionally misread one (see README, "Limitations").

1. The text is split into blocks: paragraphs separated by blank lines, heading
   lines, and, inside an article, lines that start with a paragraph number
   such as "1.", "2)", "(3)" or "1-bis.".
2. A heading line is recognized only if it is short and its number is followed
   by nothing, by a separator and a title, or by a parenthesized title:
     article: "Article 5", "Art. 5 - Scope", "Articolo 2-bis (Definizioni)"
     section: "Chapter II", "Section 3: Duties", "Titolo I", "Capo II", ...
   "Article 5 of Directive ..." at the start of a line is not a heading.
3. Every heading starts a new structural unit (consecutive headings share one).
   Chunks never cross unit boundaries, so a chunk belongs to at most one article.
4. Within a unit, whole blocks are packed into chunks of at most `chunk_size`
   characters, cutting at the last paragraph end that fits. A heading is never
   the last block of a chunk; it stays with the text that follows it.
5. Fallback for a block longer than `chunk_size`: cut at the last sentence end
   in the window, else the last whitespace, else exactly at `chunk_size`. Such
   in-block cuts overlap by up to `chunk_overlap` characters (snapped to a word
   start). Cuts at block or unit boundaries break no text and are not overlapped.

Every chunk's text is an exact substring of the document content, so its page
range is derived from character offsets.

Chunk IDs are "<doc_id>-<index:04d>-<first 8 hex chars of SHA-256(text)>":
stable for the same document, chunking settings and text, and different
whenever the chunk text changes.
"""

from __future__ import annotations

import hashlib
import re
from bisect import bisect_left
from dataclasses import dataclass

from src.models import LegalChunk, LegalDocument, SourceLocation

_MAX_HEADING_LENGTH = 150

# Latin ordinal suffixes used in Italian legislation for inserted articles and
# paragraphs ("2-bis", "2-undecies"). This is the only list of supported
# suffixes, in two groups that differ in how a suffix may follow its number:
# - the original suffixes, after a hyphen, a space or nothing ("2-bis",
#   "2 bis", "2bis"), as before;
# - the suffixes added later, after a hyphen only ("2-undecies"), so that adding
#   them does not make new forms such as "Art. 2 undecies" recognisable.
# The list is not exhaustive: an unlisted form (e.g. "tricies", or the two-word
# "vicies semel") is not part of the identifier, so "Art. 2-tricies" is read as
# article "2".
_ORDINAL_SUFFIXES_ANY_JOINER = (
    "bis", "ter", "quater", "quinquies", "sexies", "septies", "octies", "novies", "decies",
)
_ORDINAL_SUFFIXES_AFTER_HYPHEN = (
    "undecies", "duodecies", "terdecies", "quaterdecies", "quinquiesdecies", "sexiesdecies",
    "septiesdecies", "octiesdecies", "noviesdecies", "vicies",
    # Alternative forms of 15, 16, 18 and 19.
    "quindecies", "sedecies", "duodevicies", "undevicies",
    # Hyphenated spellings used in the Privacy Code ("Art. 2-sex-decies",
    # "Art. 2-septies-decies").
    "sex-decies", "septies-decies",
)
# The hyphen-only group is tried first, so "-terdecies" is never read as "-ter"
# and "-septies-decies" never as "-septies".
_ORDINAL_SUFFIX_FORM = (
    r"(?:-(?:" + "|".join(_ORDINAL_SUFFIXES_AFTER_HYPHEN) + r")"
    r"|[-\s]?(?:" + "|".join(_ORDINAL_SUFFIXES_ANY_JOINER) + r"))"
)
_ORDINAL_SUFFIX = rf"{_ORDINAL_SUFFIX_FORM}?"
# After the number: nothing, a separator plus a title, or a parenthesized title.
_HEADING_TAIL = r"\s*(?:[-–—:.]\s*\S.*|\(.+\))?\s*$"

# An article identifier: a number, then optionally a suffix and, directly after
# the suffix, a numeric sub-number ("2-quaterdecies.1"). A sub-number is not
# accepted after a bare number, so "Art. 5. Scope" and "Art. 1." read as before.
_ARTICLE_HEADING = re.compile(
    rf"(?:article|articolo|art\.)\s*(\d+[a-z]?(?:{_ORDINAL_SUFFIX_FORM}(?:\.\d+)?)?)"
    rf"{_HEADING_TAIL}",
    re.IGNORECASE,
)
_SECTION_HEADING = re.compile(
    rf"(?:book|part|title|chapter|section|libro|parte|titolo|capo|sezione)\s+"
    rf"(?:[IVXLCDM]+|\d+){_HEADING_TAIL}",
    re.IGNORECASE,
)
_PARAGRAPH_NUMBER = re.compile(
    rf"(?:\((\d{{1,3}}{_ORDINAL_SUFFIX})\)|(\d{{1,3}}{_ORDINAL_SUFFIX})[.)])\s+\S",
    re.IGNORECASE,
)
# A sentence end: punctuation (optionally followed by a closing quote or
# bracket) that is followed by whitespace.
_SENTENCE_END = re.compile(r"[.;:!?][\"'”»)\]]*(?=\s)")
_WHITESPACE = re.compile(r"\s")


@dataclass(frozen=True)
class _Block:
    start: int
    end: int
    kind: str  # "section", "article", or "text"
    # Section heading text, article number, or paragraph number (text blocks
    # inside an article only).
    label: str | None = None


@dataclass(frozen=True)
class _Unit:
    blocks: list[_Block]
    section: str | None
    article: str | None


def chunk_document(document: LegalDocument, chunk_size: int, chunk_overlap: int) -> list[LegalChunk]:
    """Split a document into traceable chunks. Returns [] for blank content."""
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive (got {chunk_size}).")
    if not 0 <= chunk_overlap < chunk_size:
        raise ValueError(
            f"chunk_overlap must be >= 0 and smaller than chunk_size "
            f"(got {chunk_overlap} and {chunk_size})."
        )

    text = document.content
    chunks: list[LegalChunk] = []
    for unit in _group_units(_split_blocks(text)):
        for start, end in _unit_spans(text, unit, chunk_size, chunk_overlap):
            chunk_text = text[start:end]
            index = len(chunks)
            text_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()[:8]
            location = SourceLocation(
                source_path=document.source_path,
                page=document.page_at(start),
                page_end=document.page_at(end - 1),
                section=unit.section,
                article=unit.article,
                paragraph=_paragraph_label(unit, start, end),
            )
            chunks.append(
                LegalChunk(
                    chunk_id=f"{document.doc_id}-{index:04d}-{text_hash}",
                    doc_id=document.doc_id,
                    text=chunk_text,
                    chunk_index=index,
                    location=location,
                    metadata=document.metadata,
                )
            )
    return chunks


def _classify_heading(line: str) -> tuple[str, str] | None:
    if len(line) > _MAX_HEADING_LENGTH:
        return None
    if match := _ARTICLE_HEADING.match(line):
        return "article", re.sub(r"\s+", " ", match.group(1))
    if _SECTION_HEADING.match(line):
        return "section", line
    return None


def _split_blocks(text: str) -> list[_Block]:
    """Split text into heading and paragraph blocks (offsets exclude surrounding whitespace)."""
    blocks: list[_Block] = []
    para_start: int | None = None
    para_end = 0
    in_article = False

    def close_paragraph() -> None:
        nonlocal para_start
        if para_start is None:
            return
        label = None
        if in_article and (match := _PARAGRAPH_NUMBER.match(text, para_start, para_end)):
            label = match.group(1) or match.group(2)
        blocks.append(_Block(para_start, para_end, "text", label))
        para_start = None

    offset = 0
    for line in text.split("\n"):
        line_start = offset + len(line) - len(line.lstrip())
        line_end = offset + len(line.rstrip())
        offset += len(line) + 1
        if line_start >= line_end:  # blank line
            close_paragraph()
            continue

        stripped = text[line_start:line_end]
        heading = _classify_heading(stripped)
        if heading is not None:
            close_paragraph()
            kind, label = heading
            blocks.append(_Block(line_start, line_end, kind, label))
            in_article = kind == "article"
            continue

        if in_article and para_start is not None and _PARAGRAPH_NUMBER.match(stripped):
            close_paragraph()  # a numbered paragraph starts a new block
        if para_start is None:
            para_start = line_start
        para_end = line_end

    close_paragraph()
    return blocks


def _group_units(blocks: list[_Block]) -> list[_Unit]:
    """Group blocks into units that each start at a heading (or the document start)."""
    units: list[_Unit] = []
    section: str | None = None
    article: str | None = None
    current: list[_Block] = []
    has_text = False

    for block in blocks:
        if block.kind != "text" and has_text:
            units.append(_Unit(current, section, article))
            current, has_text = [], False
        if block.kind == "section":
            section, article = block.label, None
        elif block.kind == "article":
            article = block.label
        else:
            has_text = True
        current.append(block)

    if current:
        units.append(_Unit(current, section, article))
    return units


def _unit_spans(text: str, unit: _Unit, chunk_size: int, overlap: int) -> list[tuple[int, int]]:
    """Return (start, end) offsets of the chunks covering one unit."""
    block_starts = [b.start for b in unit.blocks]
    # Headings stay attached to the text that follows, so only text blocks end a chunk.
    text_ends = [b.end for b in unit.blocks if b.kind == "text"]
    unit_end = unit.blocks[-1].end
    spans: list[tuple[int, int]] = []

    pos = block_starts[0]
    while pos < unit_end:
        limit = pos + chunk_size
        if unit_end <= limit:
            spans.append((pos, unit_end))
            break

        fitting_ends = [e for e in text_ends if pos < e <= limit]
        if fitting_ends:
            cut = fitting_ends[-1]
            spans.append((pos, cut))
            pos = block_starts[bisect_left(block_starts, cut)]
        else:
            cut = _cut_inside_block(text, pos, limit, chunk_size)
            spans.append((pos, cut))
            pos = _overlap_start(text, pos, cut, overlap)
    return spans


def _cut_inside_block(text: str, pos: int, limit: int, chunk_size: int) -> int:
    """Choose where to cut a block that does not fit (see module docstring, step 5)."""
    window_start = pos + chunk_size // 2  # avoid very short pieces
    window = text[window_start : limit + 1]  # +1 lets a cut land exactly at `limit`

    sentence_ends = [m.end() for m in _SENTENCE_END.finditer(window)]
    if sentence_ends:
        return window_start + sentence_ends[-1]

    spaces = [m.start() for m in _WHITESPACE.finditer(window)]
    if spaces and window_start + spaces[-1] > pos:
        # Trim trailing whitespace so the chunk text stays stripped.
        return len(text[pos : window_start + spaces[-1]].rstrip()) + pos
    return limit


def _overlap_start(text: str, pos: int, cut: int, overlap: int) -> int:
    """Start of the next chunk after an in-block cut; always > pos."""
    start = cut - overlap
    if overlap == 0 or start <= pos:
        start = cut
    else:
        # Snap forward to the beginning of a word.
        while start < cut and not text[start - 1].isspace():
            start += 1
    while start < len(text) and text[start].isspace():
        start += 1
    return start


def _paragraph_label(unit: _Unit, start: int, end: int) -> str | None:
    labels = [
        b.label
        for b in unit.blocks
        if b.kind == "text" and b.label and b.start < end and b.end > start
    ]
    # Listed rather than given as a range: "1-bis" style labels make ranges ambiguous.
    return ", ".join(labels) if labels else None
