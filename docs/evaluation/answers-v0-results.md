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
| `2026-11-17-research-t7-outcome-rule` | outcome rule (below) | 12 items / 12,000 tokens | replayed from t7-prompt | replayed (offline: no model call) |

## Stage metrics (22 questions, means over questions with core rows)

| Metric | Baseline | T6 | T7-prompt | T7 + outcome rule |
|---|---|---|---|---|
| Issues per question | 4–8 | 4–8 | 1–2 | 1–2 |
| Core recall in candidates | 100% | 100% | 100% | 100% |
| Core recall in final evidence | 76% | 97% | 99% | 99% |
| Core recall in main-answer citations | 81% | 95% | 98% | 98% |
| Outcome matches | 3/22 | 8/22 | 9/22 | 22/22 |
| Claims in the answer / held apart | 175 / 10 | 200 / 10 | 121 / 13 | 121 / 13 |
| Claims removed by the checks | 6 | 4 | 2 | 2 |
| Core rows missing from evidence | 15 (10 `max_items`, 5 excerpt without the unit) | 4 (`reserved_for_search`) | 2 (`max_items`) | 2 (`max_items`) |

**Outcome rule** (from the T7 + outcome-rule run on): `answer` when every issue is covered by a
claim of the main answer rated SUPPORTED by the support check; otherwise `answer_limited`.
Held-apart claims, removed claims, and the model's own outcome and list of unanswered issues no
longer downgrade an answer by themselves; they stay visible in the result. Before, any of them
made the answer `answer_limited`.

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
4. **The remaining outcome gap was the outcome rule.** With one or two issues per question, 12
   of the 13 wrong outcomes of T7-prompt were answers whose issues had supported claims but also
   a partially supported claim (7) or the model's own report that the issue was only partly
   answered (5); one had a removed claim. Re-scored offline under the new rule, from the same
   saved replies, all 22 outcomes match. Five of them (a06, a07, a14, a15, a22) are `answer`
   although the model reported their only issue as partly answered; the result still lists that
   report. Counting the model's report as a downgrade too would give 17/22.
5. **Scorer caveat.** Citation recall counts a quotation whose words also occur inside the
   expected unit, wherever it was quoted from, so it can exceed evidence recall (baseline a14
   and a16).
