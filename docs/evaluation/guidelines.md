# Provision-level retrieval evaluation: guidelines and schema

*Milestone 4, phases P1, P2 and P2.2 (Phase 1).*
- *The schema (versions 1 and 2) and the evaluator (`src/provision_eval.py`) exist.*
- *A first real benchmark exists, [`data/evaluation/legal-v1/`](../../data/evaluation/legal-v1/README.md).
  It is provisional: all its questions and judgments are candidates that no person has
  reviewed.*
- *Its revision, [`data/evaluation/legal-v2/`](../../data/evaluation/legal-v2/README.md), was
  built in Phase 2 of [`legal-v2-implementation-plan.md`](legal-v2-implementation-plan.md). At
  Gate 2 (2026-11-12), the owner reviewed 28 of its judgments (`owner_reviewed`).*
  - *Its other records are candidates.*
  - *It was frozen at Gate 3 (2026-11-12). Its six files are pinned in
    `tests/test_legal_benchmarks.py`, and any change makes legal-v3.*
  - *It is the default benchmark. Its first results are in
    [`legal-v2-first-evaluation.md`](legal-v2-first-evaluation.md).*
- *The synthetic test fixture is in `tests/fixtures/synthetic_provision_eval/`.*

## What is measured

The evaluator measures the BM25 search that `ask` uses, `ProvisionExplorer.search`, at the
level where legal relevance is judged: the article.

- Each question has fixed Italian search queries, written by hand. Query analysis (an LLM) is
  not involved, so these results say nothing about the queries a model would write.
- A schema-2 benchmark gives each question two lists of queries, one per **query scenario**
  ("technical" and "natural", below). A run uses one scenario, and its report names it.
- Each query runs through `ProvisionExplorer.search` unchanged. The search groups its results
  by article:
  - a chunk without article text adds nothing (recitals, front matter, the enacting formula,
    division headings, running headers);
  - an article found in several chunks counts once, at its best chunk rank.
- When a question has several queries, their rankings are interleaved by chunk rank, query by
  query, the way evidence assembly takes search hits. An article keeps its first position.
- The ranking is compared with the question's judgments.

It measures how well that search ranks the articles that the judges marked relevant. It does
not measure legal correctness, the quality of an answer, or whether a provision is valid or in
force.

## Benchmark layout

A benchmark is a directory holding three files. The command's default is
`data/evaluation/legal-v2/`. It was reviewed and frozen, and it replaced `legal-v1` as the
default at Gate 3 (2026-11-12). `legal-v1` stays in place, byte for byte, and is evaluated by
naming it with `--benchmark`.

| File | Content |
|---|---|
| `benchmark.json` | the manifest: one JSON object |
| `questions.jsonl` | one question per line |
| `judgments.jsonl` | one judgment per line |

The `.jsonl` files follow the conventions of `src/retrieval_eval.py`:
- UTF-8 JSON Lines, one object per line;
- blank lines are ignored;
- unknown keys, missing keys and duplicates are errors that name the file and line.

**Versions.**
- **Once results have been reported for a version, it does not change.** Any edit to its
  questions or judgments makes a new version, with a new `version`, and preferably a new
  directory.
- **Reports.** Every report records the benchmark version and the SHA-256 of all three files.
- **legal-v1 is kept byte for byte.** `tests/test_legal_benchmarks.py` pins the SHA-256 of its
  five files, because results have been computed on it. Its records are still unreviewed
  candidates.
- **Freezing a new version.**
  - A new version stays open while it is reviewed. No metric of it is calculated or published
    in that time.
  - It is frozen once the owner has reviewed its records and explicitly approved the freeze.
    A test then pins its file hashes, and only after that are its results calculated.
  - From then on, any edit makes the next version.
- **Grading policies differ between versions.** legal-v1 was graded under the earlier wording
  of grade 1 (below). Results on v1 and on a later version are therefore not comparable, and a
  difference between them is not an improvement.

### `benchmark.json`

| Key | Value |
|---|---|
| `schema_version` | `1`, or `2` for a benchmark with two query scenarios |
| `benchmark_id` | letters, digits, `_`, `.`, `-` (for example `legal`) |
| `version` | a non-empty string (for example `"1"`) |
| `kind` | `"real"` (judgments about the real corpus) or `"synthetic"` (invented test data) |
| `description` | what the benchmark covers |

### `questions.jsonl`

| Key | Required | Value |
|---|---|---|
| `query_id` | yes | unique; letters, digits, `_`, `.`, `-` |
| `question` | yes | the question in Italian, as a user would ask it |
| `search_queries_it` | yes | a non-empty list of Italian search queries written by hand: the **technical** scenario. Each must pass the check `ask` applies to model-written queries: short, Italian, not English. |
| `search_queries_it_natural` | in schema 2 (not allowed in schema 1) | the **natural** scenario: a non-empty list, checked the same way. See "Query scenarios" below. |
| `category` | yes | see the categories below |
| `expected_outcome` | yes | see the expected outcomes below |
| `split` | yes | `"dev"` (may be used while tuning) or `"test"` (held out: look at it only to report) |
| `provenance` | yes | see provenance below |
| `notes` | no | free text |

**Categories** (the kind of legal question):

| Category | The question asks |
|---|---|
| `definition` | what a term means (for example a definition in GDPR Art. 4) |
| `obligation` | what someone must or must not do |
| `procedure` | how, when or by what deadline something is done |
| `authority` | which authority is competent, or what its powers are |
| `rights` | what rights a person has, and how they are exercised |
| `cross_instrument` | how the GDPR and the Privacy Code relate on a point |
| `explicit_citation` | about an article the question names (for example "articolo 2-bis del Codice") |
| `other` | anything else, including questions outside the corpus |

**Expected outcomes** (what a correct system should do):

| Outcome | Meaning | Judgments |
|---|---|---|
| `answerable` | the corpus contains the provisions needed to answer | at least one grade 2 |
| `needs_clarification` | the question is too vague to answer without asking | as found |
| `out_of_scope` | the question is not about data protection | usually none |
| `not_in_corpus` | about data protection, but needs a source the corpus lacks | grade 0 for misleading near-misses |

### `judgments.jsonl`

| Key | Required | Value |
|---|---|---|
| `query_id` | yes | a question of this benchmark |
| `instrument` | yes | the instrument ID from `data/reference/instruments.json` (`eu-reg-2016-679`, `it-dlgs-2003-196`), not an alias |
| `article` | yes | the article label exactly as printed (`33`, `2-bis`) |
| `point` | no | a numbered point `N)` of the article, as digits in a string (`"12"`) |
| `grade` | yes | `0`, `1` or `2` (below) |
| `rationale` | yes | one sentence: why this grade |
| `provenance` | yes | see provenance below |

Judgments are keyed by instrument and article label, never by chunk ID or provision ID. They
therefore survive re-chunking and rebuilds (TECHNICAL_DEBT.md TD-016).

**Resolution.** Judgments are resolved against the provision store when the evaluation runs.
Every unknown instrument, article or point is reported at once, with its file and line:
- an alias where the ID is expected is an error that names the ID;
- a label that matches only after normalisation (for example `1.` for `1`) is an error that
  names the label as printed;
- a point must appear as a line starting `N)` in the article's anchored text.

**One article, several judgments.** A question may judge an article and some of its points
separately. Metrics are computed per article, using the highest grade given to it or to any of
its points. A judgment repeated for the same question, instrument, article and point is an
error.

## Query scenarios

A schema-2 benchmark measures the same questions, against the same judgments, with two lists of
search queries:

| Scenario | Field | What it measures |
|---|---|---|
| `technical` (the default) | `search_queries_it` | retrieval when the user already uses the corpus's own words; such queries often reuse an article's heading or definition |
| `natural` | `search_queries_it_natural` | retrieval when a practitioner phrases the same information need in their own words |

- **One scenario per run.** `--scenario technical|natural` chooses the scenario, and each run
  gives one report.
  - The report records the scenario and its field (`retrieval.query_scenario`,
    `retrieval.query_field`), and each question's `searches` lists the queries used.
  - A schema-1 benchmark has the technical scenario only, so `--scenario natural` on it exits
    with code 2 before any build is opened.
- **What may be compared:** the two scenarios of one version, which share questions,
  judgments, build and settings. Never compare versions that are graded differently.

**Rules for natural queries:**
1. **Natural Italian, as a lawyer would type it.**
   - The first query is the practitioner's shorthand.
   - The second describes the client's facts.
   - Terms of art and common loanwords (data breach, DPO) are allowed. Copied headings and
     definitions are not.
2. **Never the answer.** A query must not contain a deadline, threshold or age that the
   question does not contain.
3. **As many queries as the technical scenario,** so that both scenarios interleave the same
   number of searches.
4. **Explicit citations stay explicit.** A question that names an article is searched by that
   article.
5. **Reviewed, written blind, then frozen.**
   - The owner reviews the queries before any search or pooling is run with them.
   - After that review they are frozen, and they are never edited after seeing what they
     retrieve, on either split.
   - A change makes a new version. Tuning natural queries to the search would turn them back
     into technical ones.
6. **Pool them before judging is complete.** An article that only the natural queries retrieve
   would otherwise be unjudged, and would count as not relevant.

**The no-copying check.** Before comparing, text is lower-cased, apostrophes become spaces, and
only letters and digits count. A natural query must pass all six checks:

| Check | Rule |
|---|---|
| N1 | No 4-word sequence shared with the heading of an article graded 1 or 2 for the question. |
| N2 | No whole heading of 2 or 3 words of such an article. One-word headings are exempt. |
| N3 | No 4-word sequence shared with the text of a judged point. |
| N4 | No 4-word sequence shared with the question's technical queries, and no query equal to one of them. |
| N5 | Every number in the query appears in the question. |
| N6 | It passes the query check, and the question has as many natural as technical queries. |

The check is a lexical guard: close paraphrases pass it. The owner's review is the real check.

## Relevance grades

This is the grade policy adopted for legal-v2 by the owner's decision D1 (2026-11-11):

| Grade | Meaning |
|---|---|
| **2** | The provision directly answers the question. |
| **1** | The provision gives concrete information useful to formulate the answer: a necessary condition, an exception, a procedure, a prerequisite, or a relevant specification. |
| **0** | Thematic similarity, shared terminology, or related obligations or consequences that the answer does not need. Also any judged provision of no use for the question. |

*legal-v1 was graded under the earlier wording of grade 1:* "Partially relevant: useful context,
a definition the answer relies on, or a provision that covers only part of the question". That
wording is looser, so v1 and v2 grades are not comparable.

*Example from the synthetic fixture (an invented act, not legal content):* for «Entro quando il
custode deve segnalare un incidente?»:
- Art. 1, which states the deadline, is a 2.
- Art. 3, which names the office that receives the reports, is a 1: it gives a procedure.
- Art. 4, on penalties, would be a 0: a consequence the answer does not need.

The fixture's other grades exist to exercise the evaluator, and some predate this policy. For
example, a penalty is graded 1 for a question about obligations.

**Working rules.** These follow from the grade policy and decide the common cases:
1. **Grade against what the question asks, not its topic.** Consequences of the rule asked
   about, and obligations that follow from it, are 0. When a question names the kinds of rule it
   asks about (for example two kinds of power), a provision of another kind is 0, even if it
   belongs to the same body.
2. **Cross-references.** A provision that the grade-2 provision refers to is 1 when the answer
   needs what only it says, for example when it fixes the scope of the rule asked about. When
   the referring provision states the condition in its own words, the referenced one stays 0.
3. **Definitions.** A definition is 2 when the question asks for it. It is 1 when the defined
   term triggers the rule asked about, or names what the rule covers.
   - *Synthetic example:* for «Che cosa si intende per incidente?», Art. 5 point 2 is a 2. For
     the reporting deadline, the same point would be a 1, because it says which events must
     be reported.
4. **The same provision gets the same grade in questions of the same kind.** For example, a
   provision that sets the procedure for a family of requests gets the same grade in every
   question about one of those requests.
5. **National specifications.** A provision of a national act that fills an option a European
   provision leaves to Member States is 1, even when the question does not name the country.
   A national rule for a narrow sector that the question does not ask about is 0.
   - *Clarified at Gate 2 (2026-11-12):* a question that asks for every case of a rule does ask
     about sector cases. A national rule that adds such a case is therefore 1.
6. **Restrictions** *(added at Gate 2, 2026-11-12)*.
   - A provision that allows or imposes restrictions on the right or obligation asked about is
     an exception, so 1. This applies in every question about a right or obligation within its
     scope.
   - The scope is read from the provision's own text, for example the range of articles it
     names.

**Judging rules:**
- **Judge the text in the corpus, not the law as you know it.** The GDPR is the 2016
  original publication; the Privacy Code is a transcription. Relevance does not mean that a
  provision is valid, in force or correctly transcribed.
- **Keep textual relevance apart from legal validity on the transcription.**
  - A judgment of grade 1 or 2 on the Privacy Code grades the text of an unverified user
    transcription. Its rationale begins «In the transcription:».
  - No rationale calls the transcription verified, current or in force.
  - The provenance warning on the source stays, and grading changes nothing in the corpus, the
    registry or the provenance.
- **Relevance is not citability.** Grade an article whatever its eligibility tier. Today no
  article is citable.
- **Pool before judging.** Run the evaluator and judge every article in the top 10 of each
  question. Add any article a judge knows is needed, even if it was not retrieved. Every
  unjudged article counts as not relevant, so gaps in the pool understate recall.
- **Give each grade a rationale,** in one sentence.
- **Keep the test split held out.** Do not change queries, judgments or settings after
  looking at test-split results; use the dev split for that.

## Provenance and review status

Every question and every judgment carries a `provenance` object:

| Key | Required | Value |
|---|---|---|
| `drafted_by` | yes | who or what wrote it. Name the tool if a model drafted it. |
| `drafted_on` | yes | `YYYY-MM-DD` |
| `review_status` | yes | one of the four statuses below |
| `reviewed_by` | for reviewed statuses | the reviewer's name; `null` otherwise |
| `reviewed_on` | for reviewed statuses | `YYYY-MM-DD`; `null` otherwise |

| Status | Meaning |
|---|---|
| `synthetic` | invented test data, about an invented act. Allowed only, and required, in a benchmark of kind `synthetic`. |
| `candidate` | drafted, by a person or a model, and reviewed by no one |
| `owner_reviewed` | checked by the project owner |
| `expert_reviewed` | checked by a person qualified to judge legal relevance, named in `reviewed_by` |

**Approving a change is not reviewing a record.**
- When the owner approves a proposed change, for example in a plan, the approval is recorded
  with the change (in legal-v2, in `changes.jsonl`).
- The record that the change produces stays `candidate`. It becomes `owner_reviewed` only when
  the owner reviews that record and names it as approved, with the name and date to record.

**Owner review is not expert legal validation.** An `owner_reviewed` judgment records that
the project owner checked it, nothing more. An `expert_reviewed` judgment records an expert's
view of relevance only. It is not a legal opinion, and it says nothing about the validity of
any provision. Reports count the statuses, and warn while any record is still a candidate.

## Metric conventions

Each scored question gives five metrics. They are computed by the functions of
`src/retrieval_eval.py`, on the question's ranked articles:

| Metric | Definition |
|---|---|
| Recall@1, Recall@5, Recall@10 | relevant articles in the top k ÷ all relevant articles of the question |
| MRR@10 | 1 / position of the first relevant article in the top 10 (0 if none) |
| nDCG@10 | DCG@10 ÷ IDCG@10, with DCG@10 = Σ grade_i / log2(i + 1) over positions 1–10 |

- **Relevant** means grade ≥ 1, for Recall and MRR. This is the convention of
  `src/retrieval_eval.py`. Partially relevant articles (grade 1) therefore count as relevant
  there.
- **Gains:** nDCG uses the grades themselves (linear gain), so a grade 2 counts twice as much
  as a grade 1. IDCG@10 is the DCG of the question's judged grades in the ideal order.
- **Unjudged** articles count as not relevant.
- **Short rankings:** a ranking shorter than k scores lower; the denominators do not shrink.
  The report warns about rankings shorter than 10.
- **Unscored questions:** a question with no judgment of grade ≥ 1 is listed with its ranking
  but not scored. This includes `out_of_scope` and `not_in_corpus` questions.
- **Means** are unweighted, over the scored questions: all of them, then by split.

## Reproducibility

A report records:
- the benchmark: its ID, version, kind, the SHA-256 of all three files, and counts of review
  statuses;
- the corpus: the build ID, its kind, the corpus SHA-256, the code the build was made with, the
  registry SHA-256, and each source's SHA-256;
- the code running the evaluation: its commit and whether the tree had uncommitted changes. If
  this cannot be read (for example outside a Git checkout), the report says so instead of
  recording a value;
- the retrieval:
  - the query scenario and its field;
  - the search function, the chunk depth, and the depth `ask` itself requests;
  - the ranking and merging rules;
  - the `rank-bm25` and Python versions;
- the benchmark's own schema version, and the scenarios it carries;
- the metric names and conventions.

The evaluation is deterministic: the same inputs give the same report. The report contains no
timestamp and no absolute path.

**Results are not tracked.** Write reports to a git-ignored place, such as
`data/processed/evaluation/`.

## Running

```powershell
# The default benchmark, data/evaluation/legal-v2 (frozen at Gate 3), one report per scenario:
.\.venv\Scripts\python.exe -m src.provision_eval --benchmark data/evaluation/legal-v2 --scenario technical --output data/processed/evaluation/legal-v2-technical.json
.\.venv\Scripts\python.exe -m src.provision_eval --benchmark data/evaluation/legal-v2 --scenario natural --output data/processed/evaluation/legal-v2-natural.json

# legal-v1 (provisional, all candidates; technical scenario only), named explicitly:
.\.venv\Scripts\python.exe -m src.provision_eval --benchmark data/evaluation/legal-v1 --output data/processed/evaluation/legal-v1.json

# Options: --benchmark DIR, --scenario technical|natural (default technical), --build-dir DIR,
#          --chunk-depth N (default 20), --json
# `ask` requests 5 chunks per query; --chunk-depth 5 measures exactly what evidence assembly receives.
# --scenario natural needs a schema-2 benchmark; on schema 1 it exits with code 2.

# The synthetic fixture runs in the tests:
.\.venv\Scripts\python.exe -m pytest tests/test_provision_eval.py
```

Exit codes:

| Code | Meaning |
|---|---|
| 0 | the report was produced |
| 1 | no question could be scored |
| 2 | a missing or invalid benchmark, or an unusable build |

## Limitations

- **BM25 only.** The dense, hybrid and reranking retrievers, and evidence assembly as a whole
  (lookups, references, item and token limits), are not evaluated yet. They are later M4
  phases.
- **Fixed queries.** They are written by hand, so query analysis is not measured. The natural
  scenario measures a different wording of the same need, but it is still hand-written, and
  it is only as good as the owner's review and the no-copying check.
- **Article level.** Points are recorded and checked, but scored at the level of their article.
- **Incomplete pools.** Unjudged articles count as not relevant, so judging only part of the
  pool understates recall.
- **Small benchmark.** A benchmark of 20–30 questions gives unstable means. There are no
  confidence intervals or significance tests yet (TD-018).
- **Tied to today's labels.** Judgments follow the current instrument IDs and article labels.
  A new version of a source keeps its labels, but they must resolve again; any renumbered
  article must be judged again.
- **Synthetic results** come from an invented act. They test the evaluator only and are not
  evidence of legal retrieval quality.
