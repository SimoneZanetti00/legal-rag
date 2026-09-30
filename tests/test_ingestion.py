import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from src.chunk_store import read_chunks
from src.config import PROJECT_ROOT
from src.ingestion import (
    IngestionError,
    display_path,
    find_input_files,
    ingest,
    load_document,
    main,
)

LAW_TEXT = "Article 1 - Scope\n1. This synthetic act applies to tests.\n2. Nothing else.\n"


def write(path: Path, content: str | bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def run_ingest(input_path: Path, output_path: Path):
    return ingest(input_path, output_path, chunk_size=1200, chunk_overlap=150)


# --- Single documents: TXT -----------------------------------------------------


def test_txt_is_loaded_with_provenance(tmp_path):
    path = write(tmp_path / "act.txt", LAW_TEXT)
    document, warnings = load_document(path)
    assert document.content == LAW_TEXT
    assert document.title == "act"
    assert document.source_path == display_path(path)
    assert document.page_starts == ()
    assert warnings == []


def test_utf8_bom_is_removed_and_newlines_normalized(tmp_path):
    path = write(tmp_path / "bom.txt", "﻿Articolo 1\r\nPerché è così.\r\n".encode("utf-8"))
    document, _ = load_document(path)
    assert document.content == "Articolo 1\nPerché è così.\n"


def test_missing_metadata_stays_unknown(tmp_path):
    document, _ = load_document(write(tmp_path / "act.txt", LAW_TEXT))
    assert all(value is None for value in vars(document.metadata).values())


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "file is empty"),
        (b"  \n\t\n", "only whitespace"),
        (b"\xef\xbb\xbf", "only whitespace"),  # BOM only
        (b"caf\xe9", "not valid UTF-8"),
        (b"abc\x00def", "NUL bytes"),
    ],
)
def test_bad_txt_files_are_rejected(tmp_path, content, message):
    path = write(tmp_path / "bad.txt", content)
    with pytest.raises(IngestionError, match=message):
        load_document(path)


@pytest.mark.parametrize("name", ["contract.docx", "notes.md", "README"])
def test_unsupported_types_are_rejected(tmp_path, name):
    path = write(tmp_path / name, "text")
    with pytest.raises(IngestionError, match="unsupported file type"):
        load_document(path)


# --- Single documents: PDF -----------------------------------------------------


def test_pdf_pages_are_preserved(tmp_path, write_pdf):
    path = write_pdf(
        tmp_path / "act.pdf",
        [["Article 1 - Scope", "1. Applies to tests."], ["Article 2", "Second page text."]],
    )
    document, warnings = load_document(path)
    assert warnings == []
    assert len(document.page_starts) == 2
    assert document.page_at(document.content.index("Applies")) == 1
    assert document.page_at(document.content.index("Second page")) == 2


def test_malformed_pdf_is_rejected(tmp_path):
    path = write(tmp_path / "broken.pdf", b"%PDF-1.7\nthis is not really a pdf")
    with pytest.raises(IngestionError, match="cannot open PDF"):
        load_document(path)


def test_scanned_pdf_requires_ocr(tmp_path, write_pdf):
    path = write_pdf(tmp_path / "scan.pdf", [None, None])
    with pytest.raises(IngestionError, match="OCR is required"):
        load_document(path)


def test_pdf_without_text_is_rejected(tmp_path, write_pdf):
    path = write_pdf(tmp_path / "blank.pdf", [[]])
    with pytest.raises(IngestionError, match="no extractable text"):
        load_document(path)


def test_partially_scanned_pdf_warns_about_missing_pages(tmp_path, write_pdf):
    path = write_pdf(tmp_path / "mixed.pdf", [["Article 1", "Text."], None, ["Article 2", "More."]])
    document, warnings = load_document(path)
    assert len(warnings) == 1
    assert "page(s) 2" in warnings[0]
    assert "OCR" in warnings[0]
    assert document.page_at(document.content.index("More.")) == 3


# --- Document IDs and metadata ------------------------------------------------


def test_document_id_depends_only_on_file_content(tmp_path):
    first, _ = load_document(write(tmp_path / "a" / "act.txt", LAW_TEXT))
    moved, _ = load_document(write(tmp_path / "b" / "renamed.txt", LAW_TEXT))
    edited, _ = load_document(write(tmp_path / "c" / "act.txt", LAW_TEXT + "3. Added.\n"))
    assert re.fullmatch(r"doc-[0-9a-f]{16}", first.doc_id)
    assert first.doc_id == moved.doc_id
    assert first.doc_id != edited.doc_id


def test_metadata_sidecar_is_loaded(tmp_path):
    path = write(tmp_path / "act.txt", LAW_TEXT)
    write(
        tmp_path / "act.txt.meta.json",
        json.dumps({"jurisdiction": "IT", "effective_from": "2024-01-01", "language": " "}),
    )
    document, _ = load_document(path)
    assert document.metadata.jurisdiction == "IT"
    assert document.metadata.effective_from == date(2024, 1, 1)
    assert document.metadata.language is None  # blank means unknown
    assert document.metadata.publication_date is None


@pytest.mark.parametrize(
    ("sidecar", "message"),
    [
        ('{"effective_from": "01/01/2024"}', "YYYY-MM-DD"),
        ('{"country": "IT"}', "unknown keys"),
        ('{"jurisdiction": 5}', "string or null"),
        ('["IT"]', "JSON object"),
        ("{not json", "cannot read metadata"),
        ('{"effective_from": "2024-02-01", "effective_to": "2024-01-01"}', "effective_to"),
    ],
)
def test_invalid_metadata_sidecar_fails_the_document(tmp_path, sidecar, message):
    path = write(tmp_path / "act.txt", LAW_TEXT)
    write(tmp_path / "act.txt.meta.json", sidecar)
    with pytest.raises(IngestionError, match=message):
        load_document(path)


# --- Batch ingestion ------------------------------------------------------------


@pytest.fixture
def mixed_input(tmp_path, write_pdf) -> Path:
    raw = tmp_path / "raw"
    write(raw / "act.txt", LAW_TEXT)
    write(raw / "act.txt.meta.json", '{"jurisdiction": "EU"}')
    write_pdf(raw / "sub" / "code.pdf", [["Article 1", "Page one."], ["Page two text."]])
    write(raw / "broken.pdf", b"not a pdf")
    write(raw / "empty.txt", b"")
    write(raw / "memo.docx", b"PK")
    write(raw / "orphan.pdf.meta.json", "{}")
    write(raw / ".gitkeep", b"")
    return raw


def test_one_failure_does_not_stop_the_batch(mixed_input, tmp_path):
    output = tmp_path / "out" / "chunks.jsonl"
    report = run_ingest(mixed_input, output)

    names = [Path(r.source_path).name for r in report.results]
    assert names == [
        "act.txt", "broken.pdf", "empty.txt", "memo.docx", "orphan.pdf.meta.json", "code.pdf"
    ]
    assert [Path(r.source_path).name for r in report.succeeded] == ["act.txt", "code.pdf"]
    errors = {Path(r.source_path).name: r.error for r in report.failed}
    assert "cannot open PDF" in errors["broken.pdf"]
    assert "empty" in errors["empty.txt"]
    assert "unsupported" in errors["memo.docx"]
    assert "no matching document" in errors["orphan.pdf.meta.json"]

    chunks = list(read_chunks(output))
    assert len(chunks) == report.chunk_count
    assert {c.doc_id for c in chunks} == {r.doc_id for r in report.succeeded}


def test_written_chunks_keep_provenance(mixed_input, tmp_path):
    output = tmp_path / "chunks.jsonl"
    run_ingest(mixed_input, output)
    chunks = list(read_chunks(output))

    txt_chunks = [c for c in chunks if c.location.source_path.endswith("act.txt")]
    assert txt_chunks[0].metadata.jurisdiction == "EU"
    assert txt_chunks[0].location.article == "1"
    assert txt_chunks[0].location.page is None

    pdf_chunks = [c for c in chunks if c.location.source_path.endswith("code.pdf")]
    assert pdf_chunks[0].metadata.jurisdiction is None
    assert (pdf_chunks[0].location.page, pdf_chunks[0].location.page_end) == (1, 2)


def test_repeated_runs_are_identical_and_drop_stale_records(mixed_input, tmp_path):
    output = tmp_path / "chunks.jsonl"
    run_ingest(mixed_input, output)
    first = output.read_bytes()
    run_ingest(mixed_input, output)
    assert output.read_bytes() == first

    (mixed_input / "act.txt").unlink()
    (mixed_input / "act.txt.meta.json").unlink()
    run_ingest(mixed_input, output)
    sources = {c.location.source_path for c in read_chunks(output)}
    assert not any(s.endswith("act.txt") for s in sources)
    assert not list(output.parent.glob("*.tmp"))


def test_source_files_are_not_modified(mixed_input, tmp_path):
    before = {p: p.read_bytes() for p in mixed_input.rglob("*") if p.is_file()}
    run_ingest(mixed_input, tmp_path / "chunks.jsonl")
    after = {p: p.read_bytes() for p in mixed_input.rglob("*") if p.is_file()}
    assert after == before


def test_duplicate_content_is_reported(tmp_path):
    raw = tmp_path / "raw"
    write(raw / "a.txt", LAW_TEXT)
    write(raw / "b.txt", LAW_TEXT)
    report = run_ingest(raw, tmp_path / "chunks.jsonl")
    assert [Path(r.source_path).name for r in report.succeeded] == ["a.txt"]
    assert "identical content" in report.failed[0].error


def test_single_file_input(tmp_path):
    path = write(tmp_path / "act.txt", LAW_TEXT)
    assert find_input_files(path) == [path]
    report = run_ingest(path, tmp_path / "chunks.jsonl")
    assert len(report.succeeded) == 1


def test_invalid_paths_are_rejected(tmp_path):
    raw = tmp_path / "raw"
    write(raw / "act.txt", LAW_TEXT)
    with pytest.raises(ValueError, match="does not exist"):
        run_ingest(tmp_path / "missing", tmp_path / "chunks.jsonl")
    with pytest.raises(ValueError, match=".jsonl"):
        run_ingest(raw, raw / "act.txt")
    with pytest.raises(ValueError, match="inside the input directory"):
        run_ingest(raw, raw / "chunks.jsonl")
    assert (raw / "act.txt").read_text(encoding="utf-8") == LAW_TEXT


def test_display_path_is_project_relative_when_possible():
    assert display_path(PROJECT_ROOT / "data" / "raw" / "x.txt") == "data/raw/x.txt"


# --- CLI ------------------------------------------------------------------------


@pytest.fixture
def default_chunking(monkeypatch):
    monkeypatch.setenv("CHUNK_SIZE", "1200")
    monkeypatch.setenv("CHUNK_OVERLAP", "150")


def test_cli_success(tmp_path, capsys, default_chunking):
    raw = tmp_path / "raw"
    write(raw / "a.txt", LAW_TEXT)
    write(raw / "b.txt", "Another synthetic document.")
    output = tmp_path / "chunks.jsonl"

    code = main(["--input", str(raw), "--output", str(output)])
    out = capsys.readouterr().out
    assert code == 0
    assert "Documents processed: 2" in out
    assert "Documents failed:    0" in out
    assert "Chunks written:      2" in out
    assert len(list(read_chunks(output))) == 2


def test_cli_reports_failures_with_nonzero_exit(tmp_path, capsys, default_chunking):
    raw = tmp_path / "raw"
    write(raw / "good.txt", LAW_TEXT)
    write(raw / "bad.pdf", b"not a pdf")
    output = tmp_path / "chunks.jsonl"

    code = main(["--input", str(raw), "--output", str(output)])
    captured = capsys.readouterr()
    assert code == 1
    assert "FAILED" in captured.err and "bad.pdf" in captured.err
    assert "Documents processed: 1" in captured.out
    assert "Documents failed:    1" in captured.out
    assert len(list(read_chunks(output))) == 1  # the good file is still written


def test_cli_empty_directory_fails(tmp_path, capsys, default_chunking):
    raw = tmp_path / "raw"
    raw.mkdir()
    code = main(["--input", str(raw), "--output", str(tmp_path / "chunks.jsonl")])
    assert code == 1
    assert "No files found" in capsys.readouterr().err


def test_cli_invalid_input_path(tmp_path, capsys, default_chunking):
    code = main(["--input", str(tmp_path / "missing"), "--output", str(tmp_path / "c.jsonl")])
    assert code == 2
    assert "does not exist" in capsys.readouterr().err


def test_cli_invalid_configuration(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("CHUNK_SIZE", "100")
    monkeypatch.setenv("CHUNK_OVERLAP", "100")
    code = main(["--input", str(tmp_path), "--output", str(tmp_path / "c.jsonl")])
    assert code == 2
    assert "CHUNK_OVERLAP" in capsys.readouterr().err


def test_cli_module_entry_point(tmp_path):
    """Runs `python -m src.ingestion` as a real subprocess."""
    help_run = subprocess.run(
        [sys.executable, "-m", "src.ingestion", "--help"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, check=False,
    )
    assert help_run.returncode == 0
    assert "--input" in help_run.stdout

    raw = tmp_path / "raw"
    write(raw / "bad.txt", b"")
    run = subprocess.run(
        [sys.executable, "-m", "src.ingestion", "--input", str(raw),
         "--output", str(tmp_path / "chunks.jsonl")],
        cwd=PROJECT_ROOT, capture_output=True, text=True, check=False,
    )
    assert run.returncode == 1
    assert "bad.txt" in run.stderr
