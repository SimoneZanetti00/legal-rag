# legal-v2: first evaluation (Gate 3, 2026-11-12)

*The first provision-level evaluation of the BM25 search that `ask` uses, on the frozen legal-v2
benchmark, in its two query scenarios. Run in a Claude Code session after the owner authorized
Gate 3 ([plan](legal-v2-implementation-plan.md), §8 steps 16–19).*

**How to read these numbers:**
- **They measure ranking against this benchmark's judgments.** They do not measure legal
  correctness, the quality of an answer, or production readiness.
- **Most of the judgments are unreviewed.** 28 of the 673 judgments are owner-reviewed; the
  other 645 are AI-drafted candidates.
- **Owner review is not expert legal validation.** Nothing here establishes the validity or
  currency of the Privacy Code transcription or of the 2016 GDPR text.
- **They are not comparable with legal-v1.** v2 is graded under a stricter grade-1 policy (D1),
  so a difference from v1 is not an improvement or a regression.

## What was run

**Commands,** as given in the legal-v2 README and the guidelines, from the project root:

```powershell
.\.venv\Scripts\python.exe -m src.provision_eval --benchmark data/evaluation/legal-v2 --scenario technical --output data/processed/evaluation/legal-v2-technical.json
.\.venv\Scripts\python.exe -m src.provision_eval --benchmark data/evaluation/legal-v2 --scenario natural --output data/processed/evaluation/legal-v2-natural.json
```

- **Where the reports are.** They are under `data/processed/evaluation/`, which Git ignores; as
  the guidelines say, results are not tracked.
- **What they record.** The two reports differ only in the scenario and its results. Their
  `benchmark`, `corpus`, `code` and `metrics` sections are identical.

| | Value |
|---|---|
| Benchmark | `legal` version 2, schema 2, frozen at Gate 3; review status: 28 judgments `owner_reviewed`, 645 judgments and 24 questions `candidate` |
| Corpus build | `build-f76ff6031f2fc82c4852f0a2bde27807` (recorded); corpus SHA-256 `f9d1ac881cd5bfe75c6f83a5f697f085078788f9eb9a90b9c481534b5eb0997f`; registry SHA-256 `405a5ceb266bdaaf8800793f57b69197ef9c1cc52d0cae807becec07559f9c4f` |
| Sources | `eu-reg-2016-679@oj-l119-2016-it`, `it-dlgs-2003-196@transcription-vigente-2026-11-05` (the second is an unverified user transcription; the label is its name, not a verification) |
| Code | commit `aebf7a237f94bd9a465d3b8f11738c201d8a19e6`, state **dirty**. The M4 work is uncommitted, so the report records a working-tree fingerprint, `5549007a8f13…`. |
| Retrieval | `ProvisionExplorer.search`, BM25, chunk depth 20 per query; `ask` itself requests 5. Rankings are per article: a chunk without article text adds nothing, and an article counts once, at its best chunk rank. Several queries are interleaved by chunk rank. |
| Versions | `rank-bm25` 0.2.2, CPython 3.13.2 |
| Metrics | Recall@1, Recall@5, Recall@10, MRR@10, nDCG@10. Grade ≥ 1 counts as relevant, nDCG uses the grades as gains, and unjudged articles count as not relevant. |

**The frozen benchmark files** (pinned by `tests/test_legal_benchmarks.py`, C10):

| File | SHA-256 |
|---|---|
| `README.md` | `7c694958ac98dc52198361f53bb9e9f000ecb863e59c610d2508dedb5a1d2eb6` |
| `benchmark.json` | `8e0c30617e74f019d81dab2c452ae50136816b83ac4cf79596d1631b7ef5e6e0` |
| `changes.jsonl` | `05045815cd03390206659d50977763c8a991345739e72d71f5ce602c025a9dfb` |
| `judgments.jsonl` | `ec0af92cfc1d0bbaf8f0a839507208685b0ab8fb5d9b489104a0559cf045666c` |
| `pool.jsonl` | `b193f7fea7bc70f2f94e7fb9cba3e43d8d643c20fc96f0f51196ddcc05e93ce5` |
| `questions.jsonl` | `d3276d2d20c8232de92b6c8858a96f943839f3cb1b5c27363a0d91020f5f5038` |

## Split policy

| Split | Questions | Scored | Not scored | Use |
|---|---|---|---|---|
| dev | 16 | 14 | q22 (out of scope), q23 (not in the corpus) | diagnostic analysis |
| test | 8 | 6 | q21 (out of scope), q24 (not in the corpus) | held out, reported as means only |

- **Test results** are reported only as final held-out means. No per-question test result was
  analysed.
- **Nothing was changed after seeing the results:** no query, judgment, grade, parameter or
  code.
- **Questions not scored** have no judgment of grade ≥ 1, so they are listed in the reports but
  not averaged.

## Results

Means are unweighted, over the scored questions.

**Technical scenario** (`search_queries_it`):

| | Questions | Recall@1 | Recall@5 | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---|---|---|---|---|
| all scored | 20 | 0.314 | 0.586 | 0.656 | 0.892 | 0.711 |
| dev | 14 | 0.339 | 0.613 | 0.695 | 0.881 | 0.709 |
| test (held out) | 6 | 0.256 | 0.522 | 0.564 | 0.917 | 0.715 |

**Natural scenario** (`search_queries_it_natural`):

| | Questions | Recall@1 | Recall@5 | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---|---|---|---|---|
| all scored | 20 | 0.225 | 0.347 | 0.457 | 0.570 | 0.442 |
| dev | 14 | 0.239 | 0.345 | 0.480 | 0.516 | 0.457 |
| test (held out) | 6 | 0.192 | 0.350 | 0.406 | 0.694 | 0.408 |

**The reports' warnings:**
- **Pool coverage.** Neither report has an unjudged article in the top 10 of any scored
  question, so the pool is complete at that depth in both scenarios.
- **Short rankings.** In the technical scenario, 2 scored questions (q19, q20) rank fewer than 10
  articles at chunk depth 20. Their @10 metrics count the missing positions as misses.
- **Candidates.** 669 questions or judgments are candidates that no person has reviewed (645
  judgments and 24 questions).

## Findings (dev split only)

**Measured on the 14 scored dev questions:**
- **Technical: the first relevant article is usually found early** (MRR@10 0.881). Recall@10
  (0.695) is limited by questions with many grade-1 provisions. q04, q05, q10 and q11 each have
  five relevant articles, and each finds only one of them in its top 10.
- **The restriction judgments added at Gate 2 are almost never retrieved.** GDPR Art. 23 and
  Code Art. 2-duodecies are in the top 10 of no dev question they are judged for (q05, q10, q11,
  q13), in either scenario. Code Art. 2-undecies is in the top 10 only for q13, in the natural
  scenario. These articles were added to the pool by the owner, not found by a retriever, so
  they lower recall on those questions. That is the intended effect of judging what a correct
  answer needs.
- **Natural: lower on every dev mean.**

  | Metric | Natural | Technical |
  |---|---|---|
  | Recall@1 | 0.239 | 0.339 |
  | Recall@5 | 0.345 | 0.613 |
  | Recall@10 | 0.480 | 0.695 |
  | MRR@10 | 0.516 | 0.881 |
  | nDCG@10 | 0.457 | 0.709 |

  - **Per question,** nDCG@10 is lower for natural on 9 of the 14 dev questions, equal on 3 and
    higher on 2 (q10, q13).
  - **Complete misses.** In the natural scenario, four dev questions have no relevant article in
    the top 10: q02, q05, q08 and q14.
- **Vocabulary, measured on the build's 880 chunks:**

  | Term | Occurrences |
  |---|---|
  | «data breach» | 0 |
  | «DPO» | 0 |
  | «DPIA» | 0 |
  | «fuga di dati» | 0 |
  | «vigilanza» | 6 |
  | «violazione dei dati personali» | 25 |
  | «responsabile della protezione dei dati» | 29 |
  | «valutazione d'impatto» | 26 |

  The practitioner's terms in several natural queries do not occur in the corpus at all.

**A hypothesis, not tested here.** The natural scenario's lower scores come largely from a
lexical mismatch. BM25 cannot match a loanword or an abbreviation («data breach», «DPO») to the
formal wording of the texts. This fits q02, q05 and q08, whose natural queries rely on those
terms. Testing it would need, for example, the dense or hybrid retrievers at provision level, a
later M4 phase, or query analysis. Neither was run here.

**Test split.** The held-out means point the same way as dev: natural is lower than technical on
all five. Nothing was analysed or changed on the strength of the test results.

## Limitations

- **Mostly unreviewed judgments.** Only 28 of 673 judgments are owner-reviewed. The metrics rest
  largely on AI-drafted candidate grades, most grade-0 ones on an article's heading.
- **A small benchmark.** 20 scored questions: 14 dev and 6 test. One question moves a split mean
  by several points. There are no confidence intervals or significance tests (TD-018), and none
  is claimed.
- **Pooling.** Pools come from the top 10 of three retrievers per scenario, plus the articles
  judges and the owner added. An unjudged article counts as not relevant, although none occurs in
  the top 10 here.
- **Added articles lower recall by design.** Articles added because the answer needs them, such
  as the 14 restriction judgments, lower recall wherever no retriever finds them.
- **Article-level scoring.** Points are recorded but scored at their article; q01 and q02 both
  score GDPR Art. 4.
- **BM25 only.** Dense, hybrid and reranking, and `ask`'s evidence assembly as a whole (chunk
  depth 5, lookups, references, limits), are not measured.
- **The sources.** The Privacy Code text is an unverified transcription, and the GDPR text is
  the 2016 original publication. Relevance is relevance of their text.
- **An uncommitted working tree.** The report records the code as dirty, with a fingerprint. The
  results are reproducible from that working tree and the recorded build, but not yet from a
  commit.
- **The legal-v2 README is frozen as it was.** That file is one of the six pinned at the freeze.
  Its status lines still describe the benchmark as «NOT FROZEN», and it cannot change without a
  new version (legal-v3). The freeze is recorded in the plan, the guidelines, this document and
  `tests/test_legal_benchmarks.py`.
