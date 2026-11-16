# Query understanding layer: dev experiment

Run on 2026-11-12, on the dev split of legal-v2. The test split is held out: its questions were
not searched, not sent to a model and not scored.

**What was measured.** The baseline, strategy A, and controls that need no model.
**What was not.**
- Strategies B, C and D need a model, and none is configured here (`LLM_PROVIDER=mock`).
- Strategy E needs a design change, explained below.

These are retrieval figures against judgments that are mostly unreviewed candidates. They say
nothing about legal correctness.

## The layer

| Module | Role |
|---|---|
| `src/query_understanding.py` | One LLM task (`query_understanding`, prompt `query-understanding-v1`) turns a question into a reading with the fields listed below. The reply is checked by a JSON schema and by deterministic rules, then cached on disk. |
| `src/query_fusion.py` | Searches the original question and the restatements with `ProvisionExplorer.search` (BM25), then fuses the article rankings with RRF. Each article records which query found it. |
| `src/query_understanding_eval.py` | The dev-only experiment. |
| `src/query_understanding_demo.py` | One question, end to end. |

The fields of a reading:

| Field | Content |
|---|---|
| `original_query` | the question, unchanged |
| `legal_query` | the question in the legal vocabulary of the Italian texts |
| `semantic_query` | the question in plain Italian |
| `legal_concepts` | the legal concepts it involves |
| `entities` | the people and things it mentions |
| `relationships` | how those relate |
| `conditions` | the conditions it states |
| `ambiguities` | open points, with every reading kept |
| `clarification_needed` | whether it cannot be searched as it stands |

The layer is opt-in. `ask`, the evaluator and every default are unchanged, and a test checks that
no existing module imports the new ones.

**Validation** follows `src/query_analysis.py`: a JSON schema checked by the LLM client (one
retry), extra rules, then frozen dataclasses. Pydantic is not a project dependency.

**The rules reject a reply** when:
- a restatement, concept or condition contains a number that is not in the question (so no
  invented article numbers, periods or amounts);
- a restatement leaves out a number of the question;
- a restatement drops a negation;
- an entity, relationship or condition is not anchored to words copied from the question;
- a relationship joins something other than the listed entities;
- an ambiguity has fewer than two distinct readings;
- `clarification_needed` is true with no ambiguity listed;
- a restatement or concept is not a usable Italian search phrase (`query_problem`).

The rules cannot tell whether a restatement assumes a conclusion, or drops a qualifier that is
not a number or a negation. The prompt forbids both, and the original question is always
searched.

**Fusion.** An article's score is the sum, over the queries that found it, of
1 / (60 + its best chunk rank), summed exactly. Equal scores keep the order that
`provision_eval.rank_articles` gives the same queries. One query alone therefore gives exactly
the ranking of the frozen evaluator, and the run checks this on every dev question
(`A_equals_rank_articles=True`).

## Setup

| | |
|---|---|
| Benchmark | legal-v2, frozen at Gate 3; `judgments.jsonl` sha256 `ec0af92cfc1d0bbaf8f0a839507208685b0ab8fb5d9b489104a0559cf045666c` |
| Build | `build-f76ff6031f2fc82c4852f0a2bde27807` |
| Code | `aebf7a2` plus the uncommitted changes of this work (recorded in the report as `dirty`, with a fingerprint) |
| Retrieval | `ProvisionExplorer.search`, BM25, 20 chunks per query |
| Fusion | RRF, k = 60 |
| Questions | 16 dev questions; 14 scored. q22 (out of scope) and q23 (not in the corpus) have no grade-1 judgment. |
| Report | `data/processed/evaluation/query-understanding-dev.json` (not tracked) |

## Results (dev, 14 scored questions)

The «unjudged» column counts top-10 articles with no judgment, out of 140 positions. They count
as not relevant.

| Row | Queries | R@1 | R@5 | R@10 | MRR@10 | nDCG@10 | Unjudged |
|---|---|---|---|---|---|---|---|
| **A** | the original question | 0.217 | 0.460 | 0.567 | 0.614 | 0.512 | 49 |
| B, C, D | need a model | not run | | | | | |
| E | hybrid | not run | | | | | |
| ref-technical | handwritten technical, interleaved | 0.339 | 0.613 | 0.695 | 0.881 | 0.709 | 0 |
| ref-natural | handwritten natural, interleaved | 0.239 | 0.345 | 0.480 | 0.516 | 0.457 | 0 |
| ctl-technical | handwritten technical, RRF | 0.496 | 0.641 | 0.695 | 1.000 | 0.789 | 0 |
| ctl-natural | handwritten natural, RRF | 0.285 | 0.420 | 0.480 | 0.667 | 0.532 | 0 |
| ctl-original+technical | original + technical, RRF | 0.478 | 0.566 | 0.691 | 0.939 | 0.755 | 21 |
| ctl-original+natural | original + natural, RRF | 0.214 | 0.470 | 0.530 | 0.696 | 0.560 | 19 |
| ctl-original+technical+natural | original + both, RRF | 0.478 | 0.552 | 0.648 | 0.939 | 0.746 | 16 |

The ref rows reproduce the dev means of [the first evaluation](legal-v2-first-evaluation.md)
exactly, and a test checks this.

**Controls are not the layer.** The handwritten queries stand in for restatements. They were
written with the corpus in view, and the judgment pool was built from them, so they score
higher than any generated restatement is likely to.

## Findings (dev only)

- **The question text alone scores well below the handwritten technical queries.** A scores
  nDCG@10 0.512, against 0.709 for technical and 0.457 for natural. Of A's 14 scored questions:
  - two have no relevant article in the top 10: q10 (right of access) and q14 (the Italian
    supervisory authority);
  - 49 of its 140 top-10 positions are unjudged, because the pool came from searches of the
    handwritten queries. A is a lower bound.
- **Fusion helps the same queries.** The handwritten technical queries score nDCG@10 0.789
  fused with RRF, against 0.709 interleaved, and MRR@10 rises from 0.881 to 1.000.
  - This is a finding about the merge rule, made on dev. The frozen evaluator, and `ask`'s
    evidence assembly, still interleave; neither has been changed.
- **Adding the original to good restatements does not help on these numbers.**
  - Original + technical gives 0.755, against 0.789 for technical alone.
  - But 21 of its top-10 positions are unjudged, against none for technical alone. These
    numbers cannot separate a real loss from pool bias.
- **Adding the original to plain-wording queries helps a little:** 0.560 against 0.532.

## Not run

**B, C and D: no model.** They need `LLM_PROVIDER=anthropic`, a model and an API key; see [Running B-D with Anthropic](#running-b-d-with-anthropic).

**E: design change needed.** Hybrid retrieval returns chunks. Scoring it per article needs the
build's chunk-to-article links, which `ProvisionExplorer` keeps private. Reading them through a
private field, or reloading the link files outside the explorer, would bypass the explorer's
build verification. Either of two additive changes would allow it:

1. **A public read-only accessor:** `ProvisionExplorer.articles_of(chunk_id)` and the explorer's
   chunk list.
2. **A pluggable retriever:** `ProvisionExplorer.search(..., retriever=...)`, accepting any
   `Retriever` over the explorer's own chunks.

Option 2 keeps the mapping and evidence code in one place. Neither change is made here.

## Running B-D with Anthropic

Not run yet: no API key is configured. Nothing below has been executed against the API.

**Before you start.**
- You need an API key from the Claude Console (https://platform.claude.com/settings/keys).
  API use is billed to that Console account. A Claude subscription, including Claude Code,
  does not by itself provide API access.
- The 16 dev question texts are sent to Anthropic. No test question, judgment or corpus text
  is sent.

**Steps.** In PowerShell, from the project root:

1. Install the dependencies, if not done (`anthropic` is pinned in `requirements.txt`):

   ```
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. Create `.env`, without overwriting an existing one. It is Git-ignored.

   ```
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   ```

   Set these three lines in `.env`. Never pass the key on the command line, where it would
   stay in the shell history.

   ```
   LLM_PROVIDER=anthropic
   LLM_MODEL=<a Claude model ID>
   ANTHROPIC_API_KEY=<your Console API key>
   ```

   The project sets no default model. `.env.example` gives `claude-opus-5-5` as an example.
3. Check that the frozen benchmarks are unchanged. These tests pin the six legal-v2 hashes and
   the legal-v1 files:

   ```
   .\.venv\Scripts\python.exe -m pytest tests/test_legal_benchmarks.py -q
   ```

4. Run the preflight. It sends nothing, and shows:
   - the provider, model, prompt version and hash;
   - the client settings;
   - the benchmark file hashes;
   - how many readings are cached, and the most requests the run can send (16 readings, at
     most 32 requests with retries).

   ```
   .\.venv\Scripts\python.exe -m src.query_understanding_eval --check
   ```

5. Run the experiment. A separate output file keeps the offline baseline report:

   ```
   .\.venv\Scripts\python.exe -m src.query_understanding_eval --output data/processed/evaluation/query-understanding-dev-anthropic.json
   ```

6. Rerun step 3.

**Exit status.**

| Status | Meaning |
|---|---|
| 0 | Done. |
| 1 | Some readings failed. The report is written: those questions used the original query alone in B-D, and are listed in `understanding.failures` and in each strategy's `fallbacks`. |
| 2 | Error, no report written. |

**Errors that stop the run.** A rejected key (401 or 403), an unknown model (404) or a rejected
request (400) would fail every question alike. The run stops with exit 2 rather than writing a
report in which B-D silently equal A.

**Failures that fall back.** These are recorded per question, never turned into readings:
- timeouts, rate or spend limits (429), server errors and connection failures;
- refusals;
- replies that are malformed, cut off, or still break the rules after the one retry.

**What the report records** under `understanding`:

| Field | Content |
|---|---|
| `provider`, `model` | the configured provider and model |
| `real_model`, `source` | `true` and «Anthropic API: real model calls»; the mock provider would say «mock provider: scripted replies, not model output» |
| `sdk` | the installed `anthropic` version |
| `prompt_version`, `prompt_sha256` | the prompt the readings were generated with |
| `generation` | timeout, retries and refusal fallback. No temperature is sent, so the provider default applies, and a fresh generation can differ from an earlier one. |
| `generated_this_run`, `requests_for_generated`, `from_cache`, `real_model_calls_this_run` | what this run sent |
| `failures` | the questions whose reading failed |

Each reading is under `representations`, with:
- `served_by`, the model that answered;
- `attempts` and `request_ids`;
- its cache status.

**No credential is recorded.** The report holds no key, and tests check that neither the
report nor the cache holds one.

**Rerunning.**
- Readings are cached in `data/processed/query_understanding/`, which Git ignores, and the
  files contain the question texts. A rerun reads the cache and sends nothing.
- To generate anew, pass `--no-cache` or a new `--cache-dir`.
- Do not set `ANTHROPIC_LOG=debug` for these runs: the SDK would log every request.

## Reproduce

```
python -m src.query_understanding_eval --output data/processed/evaluation/query-understanding-dev.json
python -m src.query_understanding_demo --scripted
python -m pytest tests/test_query_understanding.py tests/test_query_fusion.py
```
