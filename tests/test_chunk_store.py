import json
from datetime import date

import pytest

from src.chunk_store import read_chunks, write_chunks
from src.models import DocumentMetadata, LegalChunk, SourceLocation


def sample_chunks() -> list[LegalChunk]:
    metadata = DocumentMetadata(
        jurisdiction="IT",
        language="it",
        publication_date=date(2023, 12, 20),
        effective_from=date(2024, 1, 1),
    )
    return [
        LegalChunk(
            chunk_id="doc-1-0000-aaaaaaaa",
            doc_id="doc-1",
            text="Art. 1 (Oggetto)\n1. Il presente testo è sintetico — «esempio» §.",
            chunk_index=0,
            location=SourceLocation("data/raw/legge.pdf", 1, 2, "Capo I", "1", "1"),
            metadata=metadata,
        ),
        LegalChunk(chunk_id="doc-1-0001-bbbbbbbb", doc_id="doc-1", text="Plain.", chunk_index=1),
    ]


def test_round_trip_preserves_everything(tmp_path):
    path = tmp_path / "chunks.jsonl"
    chunks = sample_chunks()
    with path.open("w", encoding="utf-8", newline="\n") as file:
        assert write_chunks(file, chunks) == 2

    assert list(read_chunks(path)) == chunks


def test_output_is_one_readable_utf8_json_object_per_line(tmp_path):
    path = tmp_path / "chunks.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as file:
        write_chunks(file, sample_chunks())

    raw = path.read_bytes()
    assert b"\r\n" not in raw
    lines = raw.decode("utf-8").splitlines()
    assert len(lines) == 2
    record = json.loads(lines[0])
    assert "è sintetico" in lines[0]  # stored as readable UTF-8, not \u escapes
    assert record["location"]["page"] == 1
    assert record["location"]["page_end"] == 2
    assert record["metadata"]["effective_from"] == "2024-01-01"
    assert record["metadata"]["issuing_authority"] is None
    assert json.loads(lines[1])["metadata"]["jurisdiction"] is None


def test_malformed_line_reports_line_number(tmp_path):
    path = tmp_path / "chunks.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as file:
        write_chunks(file, sample_chunks()[:1])
        file.write("{not json}\n")

    with pytest.raises(ValueError, match="line 2"):
        list(read_chunks(path))


def test_record_with_missing_field_is_rejected(tmp_path):
    path = tmp_path / "chunks.jsonl"
    path.write_text(json.dumps({"chunk_id": "c", "doc_id": "d"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 1"):
        list(read_chunks(path))
