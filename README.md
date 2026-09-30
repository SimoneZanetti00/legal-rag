# Legal Research RAG

An experimental retrieval-augmented generation (RAG) prototype for legal
research, built around traceable citations and explicit abstention.

> **Not legal advice.** This is a research and software-engineering prototype.
> Its output must not be relied on as a legal opinion.

See [PROJECT_SPEC.md](PROJECT_SPEC.md) for the specification and
[MASTER_PROMPT.md](MASTER_PROMPT.md) for the implementation plan.

## Status

**Phase 1 (project skeleton) is complete:** configuration, data models,
and tests. Ingestion, retrieval, reranking, generation, verification,
evaluation, and the UI are **not implemented yet**.

## Repository layout

```text
src/
  config.py      # centralized, validated settings (env / .env)
  models.py      # LegalDocument, LegalChunk, RetrievedPassage, Citation, Claim, LegalAnswer
tests/
  test_config.py
  test_models.py
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

On macOS/Linux, use `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`.

## Usage

```powershell
# Validate the configuration and print it (the API key is masked)
.\.venv\Scripts\python.exe -m src.config

# Run the tests
.\.venv\Scripts\python.exe -m pytest
```

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

## Privacy

- `.env`, `.venv/`, `data/raw/`, `data/processed/`, and `data/indexes/` are git-ignored.
- Use only synthetic or public-domain documents in this public repository.
- The default `mock` provider sends nothing to an external service. Only
  select a real provider if you are permitted to send your documents to it.
