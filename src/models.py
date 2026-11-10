"""Core data models (PROJECT_SPEC.md §6).

Missing metadata is represented as None, meaning "unknown". Never fill it
with guessed values. Source-side models are frozen so that provenance cannot
be changed after ingestion. `Claim` and `LegalAnswer` stay mutable because
verification updates them.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

# Source IDs are assigned by the application for each answer: S1, S2, ...
SOURCE_ID_PATTERN = re.compile(r"S[1-9][0-9]*")


class RetrievalMethod(StrEnum):
    BM25 = "bm25"
    DENSE = "dense"
    HYBRID = "hybrid"
    RERANKED = "reranked"


class VerificationStatus(StrEnum):
    # A claim is only SUPPORTED after an explicit verification step.
    NOT_VERIFIED = "NOT_VERIFIED"
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    # The evidence is insufficient, ambiguous or contradictory, so support cannot be decided.
    UNCERTAIN = "UNCERTAIN"


def _require_non_empty(value: str, name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{name} must not be empty.")


METADATA_DATE_FIELDS = ("publication_date", "effective_from", "effective_to")


@dataclass(frozen=True)
class DocumentMetadata:
    """Legal metadata of a document. Every field is optional (None = unknown)."""

    jurisdiction: str | None = None
    language: str | None = None
    document_type: str | None = None
    issuing_authority: str | None = None
    # Publication and effective dates are distinct and must not be conflated.
    publication_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None

    def __post_init__(self) -> None:
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to < self.effective_from
        ):
            raise ValueError(
                f"effective_to ({self.effective_to}) is before "
                f"effective_from ({self.effective_from})."
            )


@dataclass(frozen=True)
class SourceLocation:
    """Where a passage sits in its original source. Unknown parts are None."""

    source_path: str | None = None
    page: int | None = None  # First (or only) page, 1-based.
    page_end: int | None = None  # Last page; equals `page` for single-page passages.
    section: str | None = None
    article: str | None = None
    paragraph: str | None = None

    def __post_init__(self) -> None:
        if self.page is not None and self.page < 1:
            raise ValueError(f"page must be >= 1 (got {self.page}).")
        if self.page_end is not None and (self.page is None or self.page_end < self.page):
            raise ValueError(
                f"page_end ({self.page_end}) requires a page and must be >= page ({self.page})."
            )


@dataclass(frozen=True)
class LegalDocument:
    doc_id: str
    title: str
    content: str
    source_path: str | None = None
    source_url: str | None = None
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    # Paginated sources only (PDF): character offset in `content` where each
    # page begins, so page_starts[0] is page 1. Empty for unpaginated text.
    page_starts: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.doc_id, "doc_id")
        starts = self.page_starts
        if starts and (
            starts[0] != 0
            or any(b < a for a, b in zip(starts, starts[1:]))
            or starts[-1] > len(self.content)
        ):
            raise ValueError(
                "page_starts must begin at 0, be non-decreasing, and lie within content."
            )

    def page_at(self, offset: int) -> int | None:
        """1-based page containing the character at `offset`, or None if unpaginated."""
        if not self.page_starts:
            return None
        return bisect_right(self.page_starts, offset)


@dataclass(frozen=True)
class LegalChunk:
    chunk_id: str
    doc_id: str
    text: str
    chunk_index: int
    location: SourceLocation = field(default_factory=SourceLocation)
    # Inherited from the parent document.
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)

    def __post_init__(self) -> None:
        _require_non_empty(self.chunk_id, "chunk_id")
        _require_non_empty(self.doc_id, "doc_id")
        if self.chunk_index < 0:
            raise ValueError(f"chunk_index must be >= 0 (got {self.chunk_index}).")


@dataclass(frozen=True)
class RetrievedPassage:
    chunk: LegalChunk
    method: RetrievalMethod
    rank: int  # 1-based rank in the list produced by `method`.
    score: float
    # Per-method ranks and scores (e.g. for fused results), kept for debugging.
    method_ranks: dict[RetrievalMethod, int] = field(default_factory=dict)
    method_scores: dict[RetrievalMethod, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise ValueError(f"rank must be >= 1 (got {self.rank}).")


@dataclass(frozen=True)
class Citation:
    source_id: str  # Application-assigned, e.g. "S1".
    chunk_id: str
    doc_id: str
    text: str
    location: SourceLocation = field(default_factory=SourceLocation)

    def __post_init__(self) -> None:
        if not SOURCE_ID_PATTERN.fullmatch(self.source_id):
            raise ValueError(
                f"source_id must look like 'S1', 'S2', ... (got {self.source_id!r})."
            )
        _require_non_empty(self.chunk_id, "chunk_id")
        _require_non_empty(self.doc_id, "doc_id")


@dataclass
class Claim:
    text: str
    source_ids: list[str] = field(default_factory=list)
    status: VerificationStatus = VerificationStatus.NOT_VERIFIED


@dataclass
class LegalAnswer:
    answer_text: str
    claims: list[Claim] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    abstained: bool = False
    reason: str | None = None
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.abstained and not (self.reason and self.reason.strip()):
            raise ValueError("An abstaining answer must state a reason.")

    @classmethod
    def abstain(cls, reason: str, warnings: list[str] | None = None) -> LegalAnswer:
        return cls(answer_text="", abstained=True, reason=reason, warnings=warnings or [])
