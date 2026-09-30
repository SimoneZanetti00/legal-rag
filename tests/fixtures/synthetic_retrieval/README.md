# Synthetic retrieval fixture (NOT a legal benchmark)

Test data for `src/retrieval_eval.py`. Everything here is invented:

- `chunks.jsonl`: nine short synthetic passages written in the chunk-store
  format. The source paths (`synthetic/...`) are labels only; no such files exist.
- `queries.jsonl` and `qrels.jsonl`: six queries and their relevance judgments,
  chosen to exercise the metrics. Cases covered: graded relevance, two relevant
  chunks, a synonym the lexical retriever cannot match (so it returns
  nothing), a query with only
  "not relevant" judgments, and an unjudged query.

The judgments were not produced by legal experts. Scores computed on this
fixture only check that the evaluation code works. They say nothing about
real-world legal retrieval quality. Curated benchmarks belong in
`data/evaluation/`, never here.
