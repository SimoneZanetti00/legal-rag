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
- **Phase 3 (lexical retrieval):** in-memory BM25 search over the chunks.
- **Phase 4A (retrieval evaluation):** Recall@k, MRR@k and nDCG@k over
  labelled queries, with a BM25 baseline runner.

Dense and hybrid retrieval, reranking, generation, verification, grounding
evaluation, and the UI are **not implemented yet**. No curated legal benchmark
exists yet; only a synthetic test fixture.

## Repository layout

```text
src/
  config.py      # centralized, validated settings (env / .env)
  models.py      # LegalDocument, LegalChunk, RetrievedPassage, Citation, Claim, LegalAnswer
  ingestion.py   # TXT/PDF loading, batch ingestion, CLI
  chunking.py    # legal-aware chunking
  chunk_store.py # JSONL serialization of chunks
  retrieval.py   # tokenizer and BM25 retriever, search CLI
  retrieval_eval.py # retrieval metrics, evaluation data loading, evaluation CLI
tests/           # pytest suite; builds synthetic TXT/PDF fixtures on the fly
  fixtures/synthetic_retrieval/ # SYNTHETIC chunks, queries and judgments for tests only
data/
  raw/           # your source documents (git-ignored)
  processed/     # parsed documents and chunks (git-ignored)
  evaluation/    # curated queries.jsonl and qrels.jsonl (version-controlled; none yet)
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
licensed AGPL-3.0 or commercial), `rank-bm25` (BM25 scoring; installs
`numpy`), and `pytest` (tests).

## Usage

```powershell
# Validate the configuration and print it (the API key is masked)
.\.venv\Scripts\python.exe -m src.config

# Ingest documents (see "Ingestion" below)
.\.venv\Scripts\python.exe -m src.ingestion --input data/raw --output data/processed/chunks.jsonl

# Search the ingested chunks with BM25 (see "Lexical retrieval (BM25)" below)
.\.venv\Scripts\python.exe -m src.retrieval "obblighi del datore di lavoro" --top-k 5

# Evaluate retrieval against labelled queries (see "Retrieval evaluation" below)
.\.venv\Scripts\python.exe -m src.retrieval_eval --k 1 5 10 --output data/processed/eval_bm25.json

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

## Lexical retrieval (BM25)

BM25 ranks chunks by the query words they contain. A chunk scores higher when
it uses a query word often, when the word is rare in the corpus, and when the
chunk is short. It matches words, not meaning.

**Command line** (run ingestion first):

```powershell
.\.venv\Scripts\python.exe -m src.retrieval "sanzioni del Garante" --top-k 3
.\.venv\Scripts\python.exe -m src.retrieval "data breach" --chunks path\to\chunks.jsonl
```

The command prints each result's rank, score, chunk ID, source (file, page
range, article, paragraph), and a text excerpt. Exit code `2` means a missing
or malformed chunk file or an invalid query or `--top-k`.

**Python:**

```python
from pathlib import Path
from src.retrieval import BM25Retriever

retriever = BM25Retriever.from_jsonl(Path("data/processed/chunks.jsonl"))
for passage in retriever.search("obblighi del datore di lavoro", top_k=5):
    chunk = passage.chunk
    print(passage.rank, round(passage.score, 3), chunk.chunk_id,
          chunk.location.source_path, chunk.location.page, chunk.location.article)
```

`BM25Retriever(chunks)` also accepts any iterable of `LegalChunk`. Each
result is a `RetrievedPassage` with `method=RetrievalMethod.BM25`, a 1-based
`rank`, the BM25 `score`, and the unchanged `LegalChunk`, which carries its
IDs, text, source location, and metadata.

**Behavior**

- *Tokenization* is the same for chunks and queries:
  - case and accents are folded (`Responsabilità`, `RESPONSABILITA'` and
    `responsabilita` all match);
  - punctuation splits words, and Italian elisions are separated
    (`dell'articolo` → `dell`, `articolo`);
  - compound identifiers are kept whole and also split into their parts
    (`2016/679` → `2016/679`, `2016`, `679`; `2-bis`; `d.lgs`);
  - an article or paragraph keyword followed by a number becomes a structural
    token in place of the keyword:
    - `Articolo 5`, `art. 5`, `Art.5` and `Article 5` → `art:5`, `5`;
    - `comma 2`, `paragrafo 2` and `paragraph 2` → `par:2`, `2`;
    - only the first number is linked (`artt. 5 e 6` → `art:5`, `5`, `e`, `6`);
  - no stop words are removed and no stemming is applied.
- *Indexed structure:* each chunk is indexed as its text plus tokens from its
  metadata: the section heading, `art:<article>`, and `par:<label>` for each
  paragraph label.
  - A metadata token is added only if the text lacks it, and only once, so the
    text's term counts are not inflated.
  - Continuation chunks, which don't repeat their article's heading, are
    therefore found by `articolo 5` or by the heading words.
  - Structural tokens come only from metadata. A reference in running text
    ("chi viola l'articolo 5") is indexed as ordinary words, so a chunk citing
    article 5 ranks below article 5 itself.
  - Displayed text is never changed. The document title is not stored on
    chunks and is not indexed.
- *Results* are chunks that contain at least one indexed query token, ordered
  by descending score. Ties keep corpus order. Fewer than `top_k` results are
  returned rather than padding with unrelated chunks, and a query with no
  matching words returns an empty list.
- *Scores* are BM25 with k1=1.5 and b=0.75, computed by `rank_bm25.BM25Okapi`
  with one change: the IDF is `ln(1 + (N − n + 0.5) / (n + 0.5))`, the formula
  Lucene uses, where N is the number of chunks and n the number containing
  the word.
  - This IDF is always positive, so every match scores above 0, and matching
    one more query word never lowers a chunk's score.
  - The library's original Okapi IDF, `ln((N − n + 0.5) / (n + 0.5))`, is 0
    for a word in exactly half of the chunks. For a word in more than half it
    is replaced by a floor that can itself be ≤ 0 in small or repetitive
    corpora. There, a matching chunk scored 0, and a chunk matching two query
    words ranked below one matching only one of them.
  - The Okapi behavior stays available for comparison with
    `BM25Retriever(chunks, positive_idf=False)`.
  - The trade-off is that very common words still add a little to the score
    instead of being ignored.
  - Scores only order the results of a single query. They are not
    probabilities and cannot be compared across queries or corpora.
- *Validation:* a blank query raises `ValueError`. `top_k` must be an `int`
  ≥ 1, and booleans are rejected with `TypeError`. An empty corpus returns `[]`.

**Limitations**

- It is purely lexical:
  - different word forms don't match (`obbligo` vs `obblighi`, `lavoratore`
    vs `lavoratori`, `sanzione` vs `sanzioni`);
  - abbreviations aren't expanded (`decreto legislativo` vs `d.lgs.`);
  - synonyms and related concepts aren't matched (`licenziamento` vs `recesso
    del datore`).

  The tests record these cases. Stemming is deliberately not used yet (see
  below), and dense retrieval is planned for a later phase.
- Structural tokens depend on the chunker's heading detection. An article
  whose heading was not recognized has no `art:` token. A range such as
  `artt. 5-7` or a list such as `artt. 5 e 6` links only the first number.
- Stemming is not added. An Italian stemmer (for example Snowball) would
  connect `obbligo` and `obblighi`, but it also merges distinct legal terms
  and makes article identifiers harder to reason about. Whether it helps
  should be measured on the labelled retrieval set planned for the
  evaluation phase, not assumed.
- The index lives in memory and is rebuilt from the JSONL file each time a
  retriever is created, so re-run ingestion and rebuild after the corpus
  changes. Nothing is persisted, and search is a linear scan, which is
  adequate for prototype-sized corpora.
- A high score only means the words match. It is not evidence that a passage
  answers a legal question.

## Retrieval evaluation

`src/retrieval_eval.py` measures whether a retriever ranks the chunks a person
judged relevant near the top of its results. It only sees ranked chunk IDs, so
the same queries, judgments and metrics can compare any retriever.

**Data format** (UTF-8 JSON Lines, one object per line):

```jsonl
# queries.jsonl: query_id must be unique; "notes" is optional
{"query_id": "q01", "text": "obblighi del datore di lavoro", "notes": "..."}

# qrels.jsonl: one line per judged (query, chunk) pair
{"query_id": "q01", "chunk_id": "doc-5de8c317e7a9f3d7-0001-da460b66", "relevance": 2}
{"query_id": "q01", "chunk_id": "doc-5de8c317e7a9f3d7-0002-a03d3cee", "relevance": 0}
```

(The `#` lines above are explanations; JSON Lines has no comments.)

- `relevance` is an integer ≥ 0. `0` means judged not relevant, and `1` or
  more means relevant; higher grades are only used by nDCG. A 0–2 scale is
  typical: 2 = directly answers, 1 = partly relevant.
- Loading fails with the file name and line number on:
  - invalid JSON, missing or unknown keys, or empty IDs or text;
  - duplicate query IDs or duplicate (query, chunk) judgments;
  - relevance that isn't an integer ≥ 0 (booleans included);
  - judgments that reference an unknown query.
- **Judgments are tied to one chunk file.** Chunk IDs change whenever a
  document or `CHUNK_SIZE`/`CHUNK_OVERLAP` changes. Judgments that reference a
  chunk ID missing from the chunk file are therefore an error, not a silent
  zero. Re-run ingestion with the settings used for labelling, or relabel.

**Metrics** (k = cutoff; only the first k retrieved IDs count):

| Metric | Definition |
|---|---|
| Recall@k | relevant chunks in the top k ÷ all relevant chunks for the query (cannot reach 1 if there are more than k) |
| MRR@k | mean over queries of 1/rank of the first relevant chunk in the top k (0 if none) |
| nDCG@k | DCG@k ÷ ideal DCG@k, where DCG@k = Σ relevance_i / log2(i + 1) (linear gain) and the ideal ranking sorts the judged grades |

Edge cases:
- *Unjudged* retrieved chunks count as not relevant.
- *Duplicate* chunk IDs count only at their first position; repeats still use
  up positions but earn nothing.
- *Fewer than k results, or none,* score lower; denominators never shrink.
- *Ties in relevance:* the order among equally graded chunks does not change nDCG.
- *Queries without any relevant judgment* (unjudged, or judged only 0) can't
  be scored. They are listed as skipped and excluded from the means.
- *Aggregates* are unweighted means over the evaluated queries.

**Running it:**

```powershell
# Defaults: data/processed/chunks.jsonl, data/evaluation/queries.jsonl, data/evaluation/qrels.jsonl
.\.venv\Scripts\python.exe -m src.retrieval_eval --retriever bm25 --k 1 5 10 --output data/processed/eval_bm25.json

# The synthetic fixture (a smoke test, not a benchmark):
.\.venv\Scripts\python.exe -m src.retrieval_eval --chunks tests/fixtures/synthetic_retrieval/chunks.jsonl `
    --queries tests/fixtures/synthetic_retrieval/queries.jsonl --qrels tests/fixtures/synthetic_retrieval/qrels.jsonl
```

The terminal shows mean metrics at each k and per-query scores at the largest
k. The `--output` JSON report records:
- the retriever name and the k values;
- the chunk count, and the path and SHA-256 of the chunk, query and judgment files;
- per query: the retrieved IDs, the duplicate count, the metrics or the skip reason;
- the means.

The report is deterministic: same files and retriever, same report. It
contains no timestamps. Exit codes: `0` evaluated; `1` no query had a
relevant judgment; `2` missing or invalid files or arguments.

`--retriever` accepts `bm25` (the default, positive IDF) and `bm25-okapi`
(the library's original IDF).

**Synthetic tests vs a curated benchmark**
- `tests/fixtures/synthetic_retrieval/` holds invented passages and judgments.
  They only check that the evaluation code works, and their scores say nothing
  about legal retrieval quality.
- A real benchmark goes in `data/evaluation/` (version-controlled), next to the
  chunk file it was labelled against. Its judgments should come from people
  qualified to judge the legal relevance of the documents. None exists yet.
- The evaluation reports say which files were used (path and hash), so it is
  always visible which data a score came from.

**Comparing retrievers later.** A retriever only needs a
`search(query, top_k) -> list[RetrievedPassage]` method and an entry in
`RETRIEVERS` in `src/retrieval_eval.py`. A future dense retriever is compared
with BM25 by running the same command with `--retriever dense` on the same
files, and comparing the two JSON reports query by query.

**Limitations**

- Retrieval metrics measure ranking against the judgments given. They depend
  on judgment quality and completeness: relevant chunks nobody judged count as
  misses.
- A small query set gives unstable means. No significance tests or confidence
  intervals are computed.
- Only chunk-level relevance is supported, not document-level relevance.
- Answer quality and grounding are evaluated separately, in a later phase.

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
