# Benchmark answers-v0: results and findings

*All results below are on **candidate expectations, not owner-reviewed** (scope "all rows").
The owner-reviewed scope is empty until the review sheet is applied. Runs are saved under
`data/evaluation/answers-v0/runs/` and re-scored offline with
`python -m src.answer_benchmark_run report --run-id <id>`. Research mode, claude-sonnet-5-5,
build `build-f76ff6031f2fc82c4852f0a2bde27807`.*

## Runs

| Run | Change | Evidence limits | Analysis | Generation and support check |
|---|---|---|---|---|
| `2026-11-17-research-baseline` | none | 5 items / 3,000 tokens | live | live |
| `2026-11-17-research-t6` | evidence selection (T6) | 12 items / 12,000 tokens | replayed from the baseline | live (20 of 20 answered questions: every evidence set changed) |
| `2026-11-17-research-t7-prompt` | query-analysis prompt v3: only the issues asked, at most 4; at most 8 lookups | 12 items / 12,000 tokens | live | live |
| `2026-11-17-research-t7-outcome-rule` | outcome rule, first version (rejected, below) | 12 items / 12,000 tokens | replayed from t7-prompt | replayed (offline: no model call) |
| `2026-11-17-research-t7-outcome-rule-2` | outcome rule, adopted version (below) | 12 items / 12,000 tokens | re-scored from t7-prompt's saved results (`rescore`: outcome only, no model call) | same |

## Stage metrics (22 questions, means over questions with core rows)

| Metric | Baseline | T6 | T7-prompt | T7, rule v1 (rejected) | T7, rule v2 (adopted) |
|---|---|---|---|---|---|
| Issues per question | 4–8 | 4–8 | 1–2 | 1–2 | 1–2 |
| Core recall in candidates | 100% | 100% | 100% | 100% | 100% |
| Core recall in final evidence | 76% | 97% | 99% | 99% | 99% |
| Core recall in main-answer citations | 81% | 95% | 98% | 98% | 98% |
| Outcome matches | 3/22 | 8/22 | 9/22 | 22/22 | 17/22 |
| Claims in the answer / held apart | 175 / 10 | 200 / 10 | 121 / 13 | 121 / 13 | 121 / 13 |
| Claims removed by the checks | 6 | 4 | 2 | 2 | 2 |
| Core rows missing from evidence | 15 (10 `max_items`, 5 excerpt without the unit) | 4 (`reserved_for_search`) | 2 (`max_items`) | 2 (`max_items`) | 2 (`max_items`) |

**Outcome rule, adopted (v2):** `answer` when every issue is covered by a claim of the main
answer rated SUPPORTED by the support check, and the model reported no issue as not or only
partly answered; otherwise `answer_limited`. Held-apart claims and removed claims do not
downgrade an answer by themselves; they stay visible in the result. Before T7 (the original
rule), any of them, or the model's own outcome label, made the answer `answer_limited`.

**Rule v1, rejected:** the same without the model's report. It scored 22/22 because five
answers (a06, a07, a14, a15, a22) became `answer` although the model had reported their only
issue as only partly answered, and the result listed that report under unanswered issues next to
a "complete" outcome. The model's report is the only signal that the evidence missed part of a
question (an overview question, as in a06 and a07, or a part the evidence does not cover), so
discarding it made the outcome claim more than the system knows. v2 keeps it, and the five
return to `answer_limited`: the 17/22 is the honest figure.

The candidate and evidence figures of T6 are deterministic given the replayed analysis. The
citation and outcome figures also include run-to-run variation of the live generation and
support calls; one run of each cannot separate the two.

## Findings

1. **Retrieval is not the bottleneck on this benchmark.** Every core provision is already among
   the candidates (core recall in candidates 100% in both runs), so a better retriever cannot
   raise any metric here. The planned comparison of BM25, hybrid and hybrid+rerank (T7) was
   dropped for this reason. It would need a benchmark whose questions BM25 plus the analysis's
   lookups do not already cover.
2. **Evidence selection was the bottleneck at 5 items / 3,000 tokens.** Ten core rows were
   dropped by the item limit and five fell outside the excerpt chosen for a long article. T6
   removes both causes; the four remaining misses (a06 Arts. 21–22, a07 Arts. 35 and 37) are
   lookups beyond the eight lookup slots left when search adds new articles.
3. **The outcome gap comes from query analysis.** The analysis splits a question into 4–8
   issues, including related obligations the user did not ask about, and the model then
   reports at least one issue as unanswered and returns `answer_limited` itself (10 of 11
   answered dev questions in the baseline). This is addressed in the query-analysis prompt,
   not in retrieval or selection.
4. **Most of the remaining outcome gap was the outcome rule.** With one or two issues per
   question, the 13 wrong outcomes of T7-prompt were answers whose issues had supported claims
   but also a partially supported claim (7), a removed claim (1), or the model's own report that
   the issue was only partly answered (5). Under the adopted rule (v2) the first eight become
   `answer`; the five the model reported as partly answered stay `answer_limited` (17/22). Those
   five are open: a06 and a07 are overview questions; for a14, a15 and a22 the model reported
   part of the question as not answered by the evidence it was given (why has not been
   investigated).
5. **Scorer caveat.** Citation recall counts a quotation whose words also occur inside the
   expected unit, wherever it was quoted from, so it can exceed evidence recall (baseline a14
   and a16).

## Final run: `2026-11-17-final`

**This is a single run. Model variance is not measured.** Every generation and support-check
figure below comes from one sample of each live call, so the differences from T7 combine the
changes and run-to-run variation. Repeated runs were not made, to keep within the budget.

**Configuration**
- **Code:** commit `fa2810a`. The only uncommitted files were three untracked documents
  outside the pipeline.
- **Prompts:** query-analysis-v3, answer-generation-v5 and claim-verification-v3. The support
  check rates each claim against its own quotations.
- **Rules and additions:** outcome rule v2. The T9 qualifications and summary are added by the
  application.
- **Evidence and model:** 12 items / 12,000 tokens, research mode, claude-sonnet-5-5.

**Model calls**
- **Analysis:** all 22 calls replayed from `2026-11-17-research-t7-prompt`. The prompt and
  messages are unchanged.
- **Generation and support check:** 40 live calls, with no retries.

**Cost: $1.08** in total, $0.57 for the 12 dev questions.
- **Tokens:** 309,210 input and 46,266 output (output includes thinking).
- **Prices:** $2 input and $10 output per million tokens.
- **Budget:** $2.50, enforced by `--budget-usd`. It was not reached.

| Question | Split | Outcome | Expected | Match | Core in evidence | Core in citations | Claims in answer / held apart | Cost |
|---|---|---|---|---|---|---|---|---|
| a01 | dev | `answer` | `answer` | yes | 100% | 100% | 7 / 2 | $0.052 |
| a02 | dev | `answer` | `answer` | yes | 100% | 100% | 1 / 1 | $0.027 |
| a03 | dev | `answer` | `answer` | yes | 100% | 100% | 5 / 0 | $0.033 |
| a04 | dev | `answer` | `answer` | yes | 100% | 100% | 7 / 1 | $0.066 |
| a05 | dev | `answer` | `answer` | yes | 100% | 100% | 5 / 2 | $0.044 |
| a06 | dev | `answer_limited` | `answer` | **no** | 86% | 71% | 8 / 1 | $0.091 |
| a07 | dev | `answer_limited` | `answer` | **no** | 89% | 56% | 6 / 4 | $0.094 |
| a08 | dev | `answer` | `answer` | yes | 100% | 100% | 10 / 2 | $0.064 |
| a09 | dev | `abstain` | `abstain` | yes | — | — | 0 / 0 | $0.000 |
| a10 | dev | `answer` | `answer` | yes | 100% | 100% | 5 / 1 | $0.035 |
| a11 | dev | `answer` | `answer` | yes | 100% | 100% | 3 / 1 | $0.036 |
| a12 | dev | `answer` | `answer` | yes | 100% | 100% | 3 / 1 | $0.031 |
| a13 | test | `answer` | `answer` | yes | 100% | 100% | 3 / 0 | $0.028 |
| a14 | test | `answer` | `answer` | yes | 100% | 100% | 5 / 2 | $0.060 |
| a15 | test | `answer_limited` | `answer` | **no** | 100% | 100% | 5 / 1 | $0.053 |
| a16 | test | `answer` | `answer` | yes | 100% | 100% | 7 / 3 | $0.065 |
| a17 | test | `answer` | `answer` | yes | 100% | 100% | 5 / 0 | $0.041 |
| a18 | test | `answer_limited` | `answer_limited` | yes | 100% | 0% | 0 / 3 | $0.033 |
| a19 | test | `abstain` | `abstain` | yes | — | — | 0 / 0 | $0.000 |
| a20 | test | `answer` | `answer` | yes | 100% | 100% | 7 / 4 | $0.083 |
| a21 | test | `answer` | `answer` | yes | 100% | 100% | 3 / 2 | $0.065 |
| a22 | test | `answer_limited` | `answer` | **no** | 100% | 100% | 10 / 2 | $0.081 |

| Metric (22 questions) | T7, rule v2 | Final |
|---|---|---|
| Core recall in candidates | 100% | 100% |
| Core recall in final evidence | 99% | 99% |
| Core recall in main-answer citations | 98% | 91% |
| Outcome matches | 17/22 | 18/22 |
| Claims in the answer / held apart | 121 / 13 | 105 / 33 |
| Claims removed by the checks | 2 | 4 (`unsupported_reference`) |
| Core rows missing from evidence | 2 (`max_items`) | 2 (`max_items`: a06 Art. 22, a07 Art. 34) |

**Reading.**

1. **The stricter support check moves claims out of the answer.** Each claim is now rated
   against its own quotations, and 33 claims are held apart (13 in T7). Citation recall falls
   from 98% to 91%, and the fall is concentrated in three questions:
   - a06 and a07, overview questions;
   - a18, whose three claims were all held apart. Its expected outcome is `answer_limited`, so
     its outcome still matches.

   This is the intended trade: a claim whose quotations do not cover every element it states
   is no longer part of the answer.
2. **Four wrong outcomes remain, all `answer_limited` where `answer` was expected.** In each,
   the model reported its only issue as partly answered, and rule v2 keeps that report:
   - a06 and a07 are overview questions;
   - for a15 and a22, the model reported part of the question as not covered by the evidence.

   a14 had the same report in T7 and is an `answer` here. One run cannot tell whether the
   prompt change or run-to-run variation caused that.
3. **The summary was withheld in 17 of 20 answers.** The rule was all-or-nothing: a summary
   was shown only if every claim it cited was rated SUPPORTED. Under the stricter check, almost
   every summary cited at least one claim that is held apart.

   **The rule now works sentence by sentence.** A sentence is shown only if every claim it
   cites is SUPPORTED and in the main answer and it passes the reference check. If no sentence
   is left, no summary is shown.

   **Re-render.** The run was re-rendered offline under the new rule as
   `2026-11-17-final-summary`:
   - every call was replayed from this run, with no model call;
   - the results are identical apart from the summary fields;
   - the report is identical.

   Summaries now appear in 18 of 20 answers, 15 of them with some sentences left out. The
   replay in `demo/replay/` comes from this re-render.

   **Limits of the sentence rule** (open):
   - **It checks citations, not content.** It confirms that a sentence's cited claims are
     supported, not that the sentence says what they say. In a01 the only sentence left is "The
     evidence does not contain any sector-specific rules [C3]", and C3 is the definition of a
     breach.
   - **Some sentences do not stand alone.** In a05, a06 and a07 the sentence left starts with
     "…adds", "They" or "It", which refer back to a sentence that was left out.
