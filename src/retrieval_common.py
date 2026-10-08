"""Helpers shared by the retrievers, the evaluator and their command-line interfaces.

This module depends only on `src.models`, so every retrieval module can import
it without creating an import cycle or loading a heavy library.

- `Retriever`: the `search(query, top_k)` interface every retriever provides.
- `require_query`, `require_positive_int`: argument checks with one set of
  error messages for all retrievers.
- `format_passage`: how the search CLIs print one result.
"""

from __future__ import annotations

from typing import Protocol

from src.models import RetrievedPassage


class Retriever(Protocol):
    """Anything that can be searched and returns ranked passages.

    A retriever may also define `describe() -> dict`, to record its settings
    (e.g. the embedding model) in an evaluation report, and `max_results`, the
    most results it can return, so that evaluation cutoffs above it are flagged.
    """

    def search(self, query: str, top_k: int = ...) -> list[RetrievedPassage]: ...


def require_query(query: object) -> None:
    """Raise TypeError for a non-string query and ValueError for a blank one."""
    if not isinstance(query, str):
        raise TypeError(f"query must be a string (got {type(query).__name__}).")
    if not query.strip():
        raise ValueError("query must not be empty or whitespace.")


def require_positive_int(value: object, name: str) -> None:
    """Raise TypeError unless `value` is an int (booleans are rejected), ValueError if < 1."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int (got {type(value).__name__}).")
    if value < 1:
        raise ValueError(f"{name} must be >= 1 (got {value}).")


def format_passage(passage: RetrievedPassage, excerpt_length: int = 240) -> str:
    """Three lines for one search result: rank, score and chunk ID; source; text excerpt."""
    chunk = passage.chunk
    location = chunk.location
    parts = [location.source_path or "unknown source"]
    if location.page is not None:
        pages = str(location.page)
        if location.page_end not in (None, location.page):
            pages += f"-{location.page_end}"
        parts.append(f"p. {pages}")
    if location.article:
        parts.append(f"art. {location.article}")
    if location.paragraph:
        parts.append(f"par. {location.paragraph}")

    excerpt = " ".join(chunk.text.split())
    if len(excerpt) > excerpt_length:
        excerpt = excerpt[:excerpt_length].rstrip() + " ..."
    return (
        f"#{passage.rank}  score={passage.score:.4f}  {chunk.chunk_id}\n"
        f"    {' | '.join(parts)}\n"
        f"    {excerpt}"
    )
