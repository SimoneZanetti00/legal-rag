# Synthetic provision-level benchmark (NOT a legal benchmark)

Test data for `src/provision_eval.py`. Everything here is invented: the act (*Atto
sintetico di Corvalle*), the questions and the judgments. Every record's provenance is
`synthetic`. Results on it test the evaluator only and say nothing about legal retrieval
quality.

The act is built at test time by `tests/test_provision_eval.py`, as a PDF in a temporary
directory, with the project's own build, anchor and link steps. It has a title, a
preamble, three recitals (context only), five articles and two numbered points (Art. 5).
Art. 1 is long enough to span three chunks.

What each question exercises is in its `notes`. The schema and the judging rules are in
[docs/evaluation/guidelines.md](../../../docs/evaluation/guidelines.md).
