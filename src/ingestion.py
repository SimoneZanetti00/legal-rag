"""Ingest local TXT and PDF files into traceable chunks stored as JSONL.

Usage (from the project root):

    .\\.venv\\Scripts\\python.exe -m src.ingestion --input data/raw --output data/processed/chunks.jsonl

Policies
--------
Input: a single file, or a directory scanned recursively in sorted path order.
Supported types are .txt (UTF-8, optional BOM) and .pdf. Hidden files (such as
.gitkeep) and metadata sidecars are not documents. Any other file is reported
as a failure, never skipped silently.

Document ID: "doc-" plus the first 16 hex characters of the SHA-256 of the
file's bytes. It does not depend on the file name, folder, or machine, and it
changes whenever the file changes. If two files in one run have identical
bytes, the later one is reported as a duplicate instead of reusing the ID.

Metadata: the title is the file name without its extension. No legal metadata
is inferred from the text. Known metadata can be supplied in an optional
sidecar next to the document named "<file name>.meta.json", for example
"law.pdf.meta.json" containing {"jurisdiction": "IT", "effective_from": "2024-01-01"}.
Allowed keys are the DocumentMetadata fields; dates use YYYY-MM-DD.

Output: the output file is rebuilt from scratch on every run (written to a
temporary file, then atomically replaced), so it contains exactly the
documents ingested successfully in that run. Source files are never modified.

End boundary (optional, single file only): `--end-before "ALLEGATO A.1"` keeps
only the text before the one line whose content, ignoring the whitespace around
it, is exactly that string (case-sensitive). The line itself and everything
after it are left out before chunking, so no excluded text can reach a chunk.
The kept text is an unchanged prefix of the extracted text, so page numbers and
character offsets are the same as in whole-file ingestion, and the document ID
is still the hash of the whole file. If the line occurs zero or several times,
nothing is written and the existing output file is left as it was; there is no
fallback to whole-file ingestion. The ingestion report states where the text
was cut.

Exit codes: 0 = every file ingested; 1 = at least one file failed or no files
were found; 2 = invalid arguments, paths, or configuration, or an end boundary
that is missing or not unique.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from bisect import bisect_right
from dataclasses import dataclass, field, fields
from datetime import date
from pathlib import Path
from typing import TextIO

import pymupdf  # PyMuPDF; "import fitz" is its deprecated alias.

from src.chunk_store import write_chunks
from src.chunking import chunk_document
from src.config import PROJECT_ROOT, ConfigError, load_settings
from src.models import METADATA_DATE_FIELDS, DocumentMetadata, LegalDocument

SUPPORTED_SUFFIXES = (".pdf", ".txt")
METADATA_SUFFIX = ".meta.json"
PAGE_SEPARATOR = "\n\n"
_METADATA_FIELDS = {f.name for f in fields(DocumentMetadata)}


class IngestionError(Exception):
    """A single file could not be ingested; the message explains why."""


class BoundaryError(ValueError):
    """An end boundary was requested but cannot be applied exactly; nothing is written."""


@dataclass(frozen=True)
class FileResult:
    source_path: str
    doc_id: str | None = None
    chunk_count: int = 0
    warnings: tuple[str, ...] = ()
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class IngestionReport:
    output_path: Path
    results: list[FileResult] = field(default_factory=list)

    @property
    def succeeded(self) -> list[FileResult]:
        return [r for r in self.results if r.ok]

    @property
    def failed(self) -> list[FileResult]:
        return [r for r in self.results if not r.ok]

    @property
    def chunk_count(self) -> int:
        return sum(r.chunk_count for r in self.results)


def display_path(path: Path) -> str:
    """Source identifier: project-relative if possible, else absolute; POSIX separators."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def find_input_files(input_path: Path) -> list[Path]:
    """List candidate files; unsupported ones are included so they get reported."""
    if input_path.is_file():
        return [input_path]

    files = []
    for path in input_path.rglob("*"):
        relative = path.relative_to(input_path)
        if not path.is_file() or any(part.startswith(".") for part in relative.parts):
            continue
        if path.name.endswith(METADATA_SUFFIX) and _document_for_sidecar(path).is_file():
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.relative_to(input_path).as_posix())


def load_document(
    path: Path, *, end_before: str | None = None
) -> tuple[LegalDocument, list[str]]:
    """Read one file into a LegalDocument plus warnings; raise IngestionError on failure.

    With `end_before`, the content stops before the unique line equal to it (see
    the module docstring); BoundaryError is raised if that line is missing or
    repeated, or if no text would remain.
    """
    if path.name.endswith(METADATA_SUFFIX):
        raise IngestionError(
            f"metadata file has no matching document ({_document_for_sidecar(path).name})"
        )
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise IngestionError(
            f"unsupported file type {suffix or '(no extension)'!r}; supported: "
            + ", ".join(SUPPORTED_SUFFIXES)
        )

    try:
        if path.stat().st_size == 0:
            raise IngestionError("file is empty")
        with path.open("rb") as file:  # hashed in blocks, not loaded at once
            doc_id = "doc-" + hashlib.file_digest(file, "sha256").hexdigest()[:16]
    except OSError as exc:
        raise IngestionError(f"cannot read file: {exc.strerror or exc}") from exc

    warnings: list[str] = []
    page_starts: tuple[int, ...] = ()
    if suffix == ".txt":
        content = _read_txt(path)
    else:
        content, page_starts, warnings = _read_pdf(path)

    if not content.strip():
        raise IngestionError("file contains only whitespace")
    if end_before is not None:
        content, page_starts, note = _cut_before_line(content, page_starts, end_before)
        warnings.append(note)

    document = LegalDocument(
        doc_id=doc_id,
        title=path.stem,
        content=content,
        source_path=display_path(path),
        metadata=_read_metadata(path),
        page_starts=page_starts,
    )
    return document, warnings


def _cut_before_line(
    content: str, page_starts: tuple[int, ...], boundary: str
) -> tuple[str, tuple[int, ...], str]:
    """Keep the text before the unique line equal to `boundary`; return it with its pages.

    The kept text is a prefix of `content`, so every offset and page number in it
    is unchanged. Pages that start after the cut are dropped.
    """
    if not boundary.strip() or boundary != boundary.strip() or "\n" in boundary:
        raise BoundaryError(
            f"end boundary must be one line without surrounding whitespace (got {boundary!r})"
        )

    def page_of(offset: int) -> str:
        return f"page {bisect_right(page_starts, offset)}" if page_starts else "no page"

    starts = []
    offset = 0
    for line in content.split("\n"):
        if line.strip() == boundary:
            starts.append(offset + len(line) - len(line.lstrip()))
        offset += len(line) + 1
    if not starts:
        raise BoundaryError(f"end boundary {boundary!r} not found as a line of its own")
    if len(starts) > 1:
        where = ", ".join(page_of(s) for s in starts)
        raise BoundaryError(
            f"end boundary {boundary!r} occurs {len(starts)} times ({where}); it must be unique"
        )

    cut = starts[0]
    kept = content[:cut].rstrip()
    if not kept.strip():
        raise BoundaryError(f"no text before end boundary {boundary!r}")
    kept_pages = tuple(start for start in page_starts if start < len(kept))
    note = (
        f"text cut before the line {boundary!r} ({page_of(cut)}); "
        f"{len(content) - len(kept)} of {len(content)} characters excluded"
    )
    return kept, kept_pages, note


def _read_txt(path: Path) -> str:
    try:
        # "utf-8-sig" drops a leading BOM; newlines are normalized to "\n".
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IngestionError(
            f"not valid UTF-8 text (invalid byte at position {exc.start}); "
            "convert the file to UTF-8"
        ) from exc
    except OSError as exc:
        raise IngestionError(f"cannot read file: {exc.strerror or exc}") from exc
    if "\x00" in text:
        raise IngestionError("contains NUL bytes; this looks like a binary file, not text")
    return text


def _read_pdf(path: Path) -> tuple[str, tuple[int, ...], list[str]]:
    """Extract text page by page. Returns (content, page start offsets, warnings)."""
    try:
        pdf = pymupdf.open(path, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises several exception types for bad files.
        raise IngestionError(f"cannot open PDF (malformed or not a PDF): {exc}") from exc

    pages: list[str] = []
    empty_pages: list[int] = []
    image_only_pages: list[int] = []
    with pdf:
        if pdf.needs_pass:
            raise IngestionError("PDF is password-protected; provide a decrypted copy")
        for number, page in enumerate(pdf, start=1):
            try:
                blocks = page.get_text("blocks")
                has_images = bool(page.get_images())
            except Exception as exc:
                raise IngestionError(f"cannot extract text from page {number}: {exc}") from exc
            # Block tuples: (x0, y0, x1, y1, text, block_no, block_type); type 0 is text.
            text = PAGE_SEPARATOR.join(
                b[4].strip() for b in blocks if b[6] == 0 and b[4].strip()
            )
            if not text:
                empty_pages.append(number)
                if has_images:
                    image_only_pages.append(number)
            pages.append(text)

    if not pages:
        raise IngestionError("PDF has no pages")
    if len(empty_pages) == len(pages):
        if image_only_pages:
            raise IngestionError(
                "no extractable text: the PDF appears to be scanned (pages contain only "
                "images). OCR is required and is not implemented."
            )
        raise IngestionError("no extractable text found in the PDF")

    warnings = []
    if empty_pages:
        detail = " (image-only, possibly scanned; OCR is not implemented)" if image_only_pages else ""
        warnings.append(
            f"no extractable text on page(s) {', '.join(map(str, empty_pages))}{detail}; "
            "their content is missing from the output"
        )

    page_starts = []
    offset = 0
    for text in pages:
        page_starts.append(offset)
        offset += len(text) + len(PAGE_SEPARATOR)
    return PAGE_SEPARATOR.join(pages), tuple(page_starts), warnings


def _document_for_sidecar(sidecar: Path) -> Path:
    return sidecar.with_name(sidecar.name.removesuffix(METADATA_SUFFIX))


def _read_metadata(path: Path) -> DocumentMetadata:
    """Load user-supplied metadata from "<file>.meta.json"; all unknown if absent."""
    sidecar = path.with_name(path.name + METADATA_SUFFIX)
    if not sidecar.is_file():
        return DocumentMetadata()

    name = sidecar.name
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise IngestionError(f"cannot read metadata file {name}: {exc}") from exc
    if not isinstance(data, dict):
        raise IngestionError(f"metadata file {name} must contain a JSON object")
    unknown = sorted(set(data) - _METADATA_FIELDS)
    if unknown:
        raise IngestionError(
            f"metadata file {name} has unknown keys {unknown}; "
            f"allowed: {sorted(_METADATA_FIELDS)}"
        )

    values: dict[str, object] = {}
    for key, value in data.items():
        if value is not None and not isinstance(value, str):
            raise IngestionError(f"metadata file {name}: {key!r} must be a string or null")
        if isinstance(value, str):
            value = value.strip() or None  # blank means unknown
        if key in METADATA_DATE_FIELDS and value is not None:
            try:
                value = date.fromisoformat(value)
            except ValueError:
                raise IngestionError(
                    f"metadata file {name}: {key!r} must be a date as YYYY-MM-DD (got {value!r})"
                ) from None
        values[key] = value
    try:
        return DocumentMetadata(**values)  # type: ignore[arg-type]
    except ValueError as exc:
        raise IngestionError(f"metadata file {name}: {exc}") from exc


def ingest(
    input_path: Path,
    output_path: Path,
    chunk_size: int,
    chunk_overlap: int,
    *,
    end_before: str | None = None,
) -> IngestionReport:
    """Ingest a file or directory and rebuild `output_path`.

    Raises ValueError for invalid paths; per-file problems are recorded in the
    report and never stop the rest of the batch.

    `end_before` (see the module docstring) needs a single input file. If the
    boundary cannot be applied, BoundaryError is raised and `output_path` is
    neither created nor changed.
    """
    if not input_path.exists():
        raise ValueError(f"input path does not exist: {input_path}")
    if end_before is not None and not input_path.is_file():
        raise ValueError("an end boundary can only be used with a single input file")
    if output_path.suffix.lower() != ".jsonl":
        raise ValueError(f"output file must have a .jsonl extension: {output_path}")
    if input_path.is_dir() and output_path.resolve().is_relative_to(input_path.resolve()):
        raise ValueError("output file must not be inside the input directory")

    report = IngestionReport(output_path)
    files = find_input_files(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name(output_path.name + ".tmp")
    seen: dict[str, str] = {}  # doc_id -> source path
    try:
        with tmp_path.open("w", encoding="utf-8", newline="\n") as out:
            for path in files:
                report.results.append(
                    _ingest_file(path, out, seen, chunk_size, chunk_overlap, end_before)
                )
        os.replace(tmp_path, output_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    return report


def _ingest_file(
    path: Path,
    out: TextIO,
    seen: dict[str, str],
    chunk_size: int,
    chunk_overlap: int,
    end_before: str | None = None,
) -> FileResult:
    source = display_path(path)
    try:
        document, warnings = load_document(path, end_before=end_before)
        if document.doc_id in seen:
            raise IngestionError(
                f"identical content to {seen[document.doc_id]}; skipped to avoid duplicate IDs"
            )
        chunks = chunk_document(document, chunk_size, chunk_overlap)
    except BoundaryError:
        raise  # stops the run: no output rather than a document without its boundary
    except IngestionError as exc:
        return FileResult(source, error=str(exc))
    except Exception as exc:  # keep the batch going and report it for this file
        return FileResult(source, error=f"unexpected error: {type(exc).__name__}: {exc}")

    seen[document.doc_id] = source
    count = write_chunks(out, chunks)
    return FileResult(source, document.doc_id, count, tuple(warnings))


def _print_report(report: IngestionReport, input_path: Path) -> None:
    # Flushing keeps stdout and stderr lines in processing order when piped.
    if not report.results:
        print(f"No files found in {input_path}.", file=sys.stderr, flush=True)
    for result in report.results:
        if result.ok:
            print(
                f"OK       {result.source_path}: {result.chunk_count} chunk(s) [{result.doc_id}]",
                flush=True,
            )
            for warning in result.warnings:
                print(f"WARNING  {result.source_path}: {warning}", flush=True)
        else:
            print(f"FAILED   {result.source_path}: {result.error}", file=sys.stderr, flush=True)

    print(f"Documents processed: {len(report.succeeded)}")
    print(f"Documents failed:    {len(report.failed)}")
    print(f"Chunks written:      {report.chunk_count}")
    print(f"Output:              {display_path(report.output_path)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.ingestion",
        description="Ingest TXT and PDF files into traceable chunks (JSONL). "
        "The output file is rebuilt from scratch on every run.",
    )
    parser.add_argument(
        "--input", type=Path, help="file or directory to ingest (default: <DATA_DIR>/raw)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="JSONL file to write (default: <DATA_DIR>/processed/chunks.jsonl)",
    )
    parser.add_argument(
        "--end-before",
        metavar="LINE",
        help="single-file input only: keep only the text before the unique line equal to "
        "LINE (case-sensitive); fails if the line is missing or repeated",
    )
    args = parser.parse_args(argv)

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2
    input_path = args.input or settings.raw_dir
    output_path = args.output or settings.processed_dir / "chunks.jsonl"

    try:
        report = ingest(
            input_path,
            output_path,
            settings.chunk_size,
            settings.chunk_overlap,
            end_before=args.end_before,
        )
    except ValueError as exc:  # BoundaryError is a ValueError
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    _print_report(report, input_path)
    return 0 if report.results and not report.failed else 1


if __name__ == "__main__":
    sys.exit(main())
