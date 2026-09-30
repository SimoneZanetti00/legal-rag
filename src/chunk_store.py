"""JSONL serialization of `LegalChunk`s: one UTF-8 JSON object per line.

Record layout (unknown values are null, never guessed):

    {"chunk_id": "...", "doc_id": "...", "chunk_index": 0, "text": "...",
     "location": {"source_path", "page", "page_end", "section", "article", "paragraph"},
     "metadata": {"jurisdiction", "language", "document_type", "issuing_authority",
                  "publication_date", "effective_from", "effective_to"}}

Dates are ISO 8601 strings ("2024-01-31").
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, TextIO

from src.models import METADATA_DATE_FIELDS, DocumentMetadata, LegalChunk, SourceLocation


def chunk_to_record(chunk: LegalChunk) -> dict[str, Any]:
    metadata = {
        name: value.isoformat() if isinstance(value, date) else value
        for name, value in asdict(chunk.metadata).items()
    }
    return {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "chunk_index": chunk.chunk_index,
        "text": chunk.text,
        "location": asdict(chunk.location),
        "metadata": metadata,
    }


def chunk_from_record(record: dict[str, Any]) -> LegalChunk:
    """Rebuild a chunk; raises ValueError if the record is malformed."""
    try:
        metadata = {
            name: date.fromisoformat(value)
            if name in METADATA_DATE_FIELDS and value is not None
            else value
            for name, value in record["metadata"].items()
        }
        return LegalChunk(
            chunk_id=record["chunk_id"],
            doc_id=record["doc_id"],
            text=record["text"],
            chunk_index=record["chunk_index"],
            location=SourceLocation(**record["location"]),
            metadata=DocumentMetadata(**metadata),
        )
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"malformed chunk record: {exc!r}") from exc


def write_chunks(file: TextIO, chunks: Iterable[LegalChunk]) -> int:
    """Append chunks as JSON lines to an open text file; return how many were written."""
    count = 0
    for chunk in chunks:
        file.write(json.dumps(chunk_to_record(chunk), ensure_ascii=False) + "\n")
        count += 1
    return count


def read_chunks(path: Path) -> Iterator[LegalChunk]:
    """Yield chunks from a JSONL file, failing with the line number on bad input."""
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                chunk = chunk_from_record(json.loads(line))
            except ValueError as exc:  # includes json.JSONDecodeError
                raise ValueError(f"{path}, line {line_number}: {exc}") from exc
            yield chunk
