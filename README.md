# Legal Research RAG

An experimental retrieval-augmented generation (RAG) prototype for legal
research, built around traceable citations and explicit abstention.

> **Not legal advice.** This is a research and software-engineering prototype.
> Its output must not be relied on as a legal opinion.

See [PROJECT_SPEC.md](PROJECT_SPEC.md) for the specification and
[MASTER_PROMPT.md](MASTER_PROMPT.md) for the implementation plan.

## Status

- **Phase 1 (project skeleton):** configuration, data models, tests.
- **Phase 2 (ingestion and chunking):** TXT/PDF ingestion, legal-aware
  chunking, and JSONL output.

Retrieval, reranking, generation, verification, evaluation, and the UI are
**not implemented yet**.

## Repository layout

```text
src/
  config.py      # centralized, validated settings (env / .env)
  models.py      # LegalDocument, LegalChunk, RetrievedPassage, Citation, Claim, LegalAnswer
  ingestion.py   # TXT/PDF loading, batch ingestion, CLI
  chunking.py    # legal-aware chunking
  chunk_store.py # JSONL serialization of chunks
tests/           # pytest suite; builds synthetic TXT/PDF fixtures on the fly
data/
  raw/           # your source documents (git-ignored)
  processed/     # parsed documents and chunks (git-ignored)
  evaluation/    # evaluation questions and labels
```

## Setup (Windows, PowerShell)

Requires Python 3.11+ (developed on 3.13.2). Always use the project's
virtual environment interpreter so nothing is installed globally.

```powershell
# Create the virtual environment (skip if .venv already exists)
py -3.13 -m venv .venv

# Install dependencies into .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Optional: create a local configuration file
Copy-Item .env.example .env
```

Activating the environment is optional, because every command below calls
`.\.venv\Scripts\python.exe` explicitly. To activate it anyway:

```powershell
.\.venv\Scripts\Activate.ps1
# If scripts are blocked, allow them for the current user once:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
deactivate  # when finished
```

On macOS/Linux, use `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`.

Dependencies: `python-dotenv` (loads `.env`), `PyMuPDF` (PDF text extraction;
licensed AGPL-3.0 or commercial), and `pytest` (tests).

## Usage

```powershell
# Validate the configuration and print it (the API key is masked)
.\.venv\Scripts\python.exe -m src.config

# Ingest documents (see "Ingestion" below)
.\.venv\Scripts\python.exe -m src.ingestion --input data/raw --output data/processed/chunks.jsonl

# Run the tests
.\.venv\Scripts\python.exe -m pytest -v
```

## Ingestion

Ingestion turns local documents into small, traceable chunks. Each chunk keeps
its document ID, source file, page range, and detected article, section, or
paragraph, so later phases can cite it precisely.

1. Put `.txt` (UTF-8) and/or `.pdf` files in `data/raw/`. Subfolders are fine.
   Use only synthetic or public documents you are allowed to process.
   `data/raw/` is git-ignored.
2. Optionally add known legal metadata in a sidecar next to a document,
   named `<file name>.meta.json` (for example `law.pdf.meta.json`):

   ```json
   {"jurisdiction": "IT", "language": "it", "document_type": "statute",
    "issuing_authority": "Parliament", "publication_date": "2023-12-20",
    "effective_from": "2024-01-01", "effective_to": null}
   ```

   All keys are optional, and dates use `YYYY-MM-DD`. Without a sidecar every
   legal metadata field is `null` (unknown). Nothing is guessed from the text.
3. Run:

   ```powershell
   .\.venv\Scripts\python.exe -m src.ingestion --input data/raw --output data/processed/chunks.jsonl
   ```

   Both arguments are optional and default to `<DATA_DIR>/raw` and
   `<DATA_DIR>/processed/chunks.jsonl`. `--input` may also be a single file.
   Chunk size and overlap come from `CHUNK_SIZE` and `CHUNK_OVERLAP`.

The command prints one line per file (`OK`, `WARNING`, or `FAILED` with the
reason), followed by a summary:

```text
OK       data/raw/act.txt: 3 chunk(s) [doc-1a2b3c4d5e6f7a8b]
FAILED   data/raw/scan.pdf: no extractable text: the PDF appears to be scanned (...). OCR is required and is not implemented.
Documents processed: 1
Documents failed:    1
Chunks written:      3
Output:              data/processed/chunks.jsonl
```

Exit codes: `0` means every file was ingested. `1` means at least one file
failed or no files were found; the successful files are still written. `2`
means invalid arguments, paths, or configuration.

**Output.** `data/processed/chunks.jsonl` is git-ignored UTF-8 JSON Lines, one
chunk per line:

```json
{"chunk_id": "doc-1a2b3c4d5e6f7a8b-0000-9f86d081", "doc_id": "doc-1a2b3c4d5e6f7a8b",
 "chunk_index": 0, "text": "Article 1 - Scope\n1. ...",
 "location": {"source_path": "data/raw/act.txt", "page": null, "page_end": null,
              "section": "Chapter I", "article": "1", "paragraph": "1, 2"},
 "metadata": {"jurisdiction": null, "language": null, "document_type": null,
              "issuing_authority": null, "publication_date": null,
              "effective_from": null, "effective_to": null}}
```

Use `src.chunk_store.read_chunks(path)` to load the file back as `LegalChunk` objects.

**Policies**

- *Repeated runs:* the output file is rebuilt from scratch on every run. It is
  written to a temporary file and then replaced, so it contains exactly the
  documents ingested in the latest run and never mixes in stale records.
  Source files are never modified.
- *Document ID:* `doc-` plus the first 16 hex characters of the SHA-256 of the
  file's bytes. It does not depend on file name, location, or machine, and it
  changes whenever the file changes. Byte-identical files in one run are
  reported as duplicates.
- *Chunk ID:* `<doc_id>-<index>-<first 8 hex chars of SHA-256(chunk text)>`.
  It is stable for the same file and chunk settings, and never reused for
  different text.
- *Skipped silently:* only hidden files (such as `.gitkeep`) and metadata
  sidecars. Any other unsupported file is reported as a failure.

**Chunking**

- Text is split into paragraphs (at blank lines), heading lines, and numbered
  paragraphs inside an article (`1.`, `2)`, `(3)`, `1-bis.`).
- Headings are recognized conservatively, in English and Italian:
  - article headings such as `Article 5`, `Art. 5 - Scope`, `Articolo 2-bis (Definizioni)`;
  - section-level headings: Book/Part/Title/Chapter/Section and
    Libro/Parte/Titolo/Capo/Sezione, followed by a Roman or Arabic number.
- A chunk never crosses an article or section heading, and a heading stays
  with the text that follows it.
- Whole paragraphs are packed into chunks of at most `CHUNK_SIZE` characters.
- A paragraph longer than `CHUNK_SIZE` is split at the last sentence end in the
  window (or at whitespace, or as a last resort exactly at the limit).
  Consecutive pieces then overlap by up to `CHUNK_OVERLAP` characters. Clean
  paragraph or heading boundaries are not overlapped.
- Chunk text is always an exact excerpt of the extracted document text.
  PDF page ranges (`page` to `page_end`) are computed from character offsets.

## Configuration

All settings come from environment variables, optionally loaded from a
`.env` file in the project root. Variables already set in the process
environment take precedence over `.env`. Every variable is optional, and the
defaults are listed in [.env.example](.env.example).

| Variable | Default | Meaning |
|---|---|---|
| `DATA_DIR` | `data` | Data root; relative paths resolve against the project root |
| `INDEX_DIR` | `data/indexes` | Where local search indexes will be stored |
| `EMBEDDING_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Dense embedding model |
| `RERANKER_ENABLED` | `false` | Enable cross-encoder reranking |
| `RERANKER_MODEL` | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | Reranker model |
| `LLM_PROVIDER` | `mock` | `mock`, `anthropic`, or `openai`; `mock` never calls an external service |
| `LLM_MODEL` | *(empty)* | Required when a real provider is selected |
| `LLM_API_KEY` | *(empty)* | Required only by real providers; keep it in `.env`, never commit it |
| `BM25_TOP_K` / `DENSE_TOP_K` | `20` | Candidates retrieved by each method |
| `RERANK_TOP_K` | `20` | Candidates passed to the reranker |
| `FINAL_EVIDENCE_COUNT` | `5` | Passages given to the LLM |
| `RRF_K` | `60` | Reciprocal Rank Fusion constant |
| `CONTEXT_TOKEN_BUDGET` | `3000` | Maximum evidence size in the prompt |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1200` / `150` | Chunking size and overlap in characters |
| `MIN_RETRIEVAL_SCORE` / `MIN_RERANK_SCORE` | *(empty = disabled)* | Abstention thresholds |
| `UNDATED_SOURCE_POLICY` | `warn` | For "as of" questions, `warn` about or `exclude` sources without effective dates |
| `MAX_GENERATION_RETRIES` | `1` | Retries for malformed LLM output (0 or 1) |

Invalid settings stop the program with a message that lists every problem.

The model defaults are provisional choices for this prototype. They are
downloaded and exercised only in the phases that use them.

## Limitations

- **Scanned PDFs:** there is no OCR. Image-only PDFs fail with an explicit
  message. Image-only pages inside otherwise readable PDFs produce a warning,
  and their content is missing from the output.
- **PDF extraction** follows PyMuPDF's text blocks. Multi-column layouts,
  tables, headers/footers, footnotes, and hyphenation may come out in an
  imperfect order or form. Page headers and footers are not removed.
- **Structure detection is heuristic.** It misses headings in other formats,
  such as `Art. 1 Oggetto` (no separator), `§ 1`, or languages other than English
  and Italian. It may also misread a short numbered line as a heading. Numbered
  lists inside articles are treated as paragraphs. Documents without
  recognized structure are still chunked by paragraphs.
- **TXT files must be UTF-8.** Other encodings fail with a message asking
  for conversion. DOCX is not supported.
- **Chunk sizes are in characters, not model tokens.**
- **Password-protected PDFs** are rejected.

## Privacy

- `.env`, `.venv/`, `data/raw/`, `data/processed/`, and `data/indexes/` are git-ignored.
- Use only synthetic or public-domain documents in this public repository.
- The default `mock` provider sends nothing to an external service. Only
  select a real provider if you are permitted to send your documents to it.
