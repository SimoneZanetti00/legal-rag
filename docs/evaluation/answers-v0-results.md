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

## Stage metrics (22 questions, means over questions with core rows)

| Metric | Baseline | T6 |
|---|---|---|
| Core recall in candidates | 100% | 100% |
| Core recall in final evidence | 76% | 97% |
| Core recall in main-answer citations | 81% | 95% |
| Outcome matches | 3/22 | 8/22 |
| Claims removed by the checks | 6 | 4 |
| Core rows missing from evidence | 15 (10 `max_items`, 5 excerpt without the unit) | 4 (`reserved_for_search`) |

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
4. **Scorer caveat.** Citation recall counts a quotation whose words also occur inside the
   expected unit, wherever it was quoted from, so it can exceed evidence recall (baseline a14
   and a16).
