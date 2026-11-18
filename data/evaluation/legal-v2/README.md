# legal-v2: revised provision-level retrieval benchmark (M4 P2.2) — PARTLY OWNER-REVIEWED, NOT FROZEN

*Built on 2026-11-11, in Phase 2 of [the legal-v2 implementation plan](../../../docs/evaluation/legal-v2-implementation-plan.md).
Gate 2 decisions applied on 2026-11-12.*

**Status:**
- **Partly owner-reviewed.** At Gate 2 (2026-11-12) the owner, Simone Zanetti, reviewed 28
  judgments, which are now `owner_reviewed` (see "Gate 2" below). The other 645 judgments and
  all 24 questions are `candidate`: drafted by an AI assistant and reviewed by no one.
  - Approving a change in the plan is not reviewing the record it produces (D8).
  - Owner review is not expert legal validation, and it says nothing about the validity or
    currency of any provision.
- **Not frozen.** Freezing needs the owner's explicit approval (Gate 3, plan §3.9).
- **No metric exists.** No v2 metric has been calculated, and none may be until the owner has
  approved the completed review and the freeze.
- **Not the default.** `DEFAULT_BENCHMARK` stays `legal-v1` until then.

The grades describe the textual relevance of provisions in this corpus. They are not legal
opinions, and they say nothing about whether any provision is valid or in force.

## What it is

The same 24 questions as legal-v1, revised under the owner's decisions D1–D8 and the plan
decisions of 2026-11-11, in schema 2, with two query scenarios:

| Scenario | Field | Queries |
|---|---|---|
| `technical` | `search_queries_it` | the v1 queries, unchanged |
| `natural` | `search_queries_it_natural` | a practitioner's wording, reviewed and approved by the owner at Gate 1, with q19 and q20 edited by the owner |

Both scenarios share the same questions, judgments, splits and build. Results on v1 and v2 are
not comparable: v2 uses the stricter grade-1 policy D1 (`docs/evaluation/guidelines.md`).

## Relation to legal-v1

v2 derives from legal-v1 at these SHA-256 values. legal-v1 is unchanged, and
`tests/test_legal_benchmarks.py` pins them.

| v1 file | SHA-256 |
|---|---|
| `README.md` | `ef0fd2e54c69b9d7a8aecd693444926e80fb57d69683fdf7505bcf8e31c01c17` |
| `benchmark.json` | `a7cf326089e2d93b2552de2a4333a8df89fe2689dbb50eec755c8723870ad6c7` |
| `judgments.jsonl` | `293fdfa976b49f08cd2ac378c32eb49e575899cdf00d42b56d1a106042f64c0f` |
| `pool.jsonl` | `7e7ec00d90618a76f7cf3f161801223ec73e1423c2177cc2c7f0bfc77165949f` |
| `questions.jsonl` | `3c4e118f80f5cd5cda7d7af12aa8cbddff1092785bbc5cd5513ce09780f8151d` |

`changes.jsonl` lists every difference. v2 is exactly v1 with those changes applied, leaving
provenance aside, and `tests/test_legal_benchmarks.py` checks this.

## Decisions applied

| Decision | What it changed |
|---|---|
| D1 | The grade policy: 2 directly answers; 1 gives concrete information useful to formulate the answer; 0 thematic similarity, shared terminology, or related obligations or consequences not needed. Five working rules (plan §2.0) |
| D2 | The natural-query scenario (schema 2) and the natural-query pool |
| D3 | q02 GDPR Art. 32 → 0; q05 Art. 33 and q04 Art. 34 both 0; q11 Art. 12 → 1; q20 Art. 84 → 0, Code Art. 167 stays 0 |
| D4 | q04 GDPR Art. 55, added at grade 1 (owner's choice) |
| D5 | q03 GDPR Art. 9 at 0; q18 GDPR Art. 8 at 2, read with Code Art. 2-quinquies; q17 Code Art. 107 at 0 |
| D6 | Judgments on the transcription grade its text, not its validity; their rationales begin «In the transcription:» |
| D7 | q03 `obligation`, q19 `rights` |
| D8 | Nothing is marked reviewed |
| Plan §0 | q14 GDPR Art. 55 kept at grade 0, with the decision recorded (c14). U4 and U5: four borderline grades kept at 1. U13: two rationales approved |

## Files

| File | Read by the evaluator | Content |
|---|---|---|
| `benchmark.json` | yes (hashed) | schema 2, `legal` version `"2"`, kind `real` |
| `questions.jsonl` | yes (hashed) | 24 questions (16 dev, 8 test), with both query lists |
| `judgments.jsonl` | yes (hashed) | 673 judgments |
| `pool.jsonl` | no | per question: the v1 lists `bm25`, `dense` and `hybrid` (technical queries), `judge_added`, and the `natural` lists |
| `changes.jsonl` | no | 348 change lines, c01–c348 |
| `README.md` | no | this file |

The files are UTF-8 with LF line endings. They are not committed, which needs the owner's
separate Git approval (plan Gate 4).

## Totals

| | v1 | v2 |
|---|---|---|
| Judgments | 388 | 673 |
| Grade 2 | 23 | 23 |
| Grade 1 | 31 | 47 |
| Grade 0 | 334 | 603 |
| Distinct (question, article) pairs | 388 | 671 (q17 judges three points of GDPR Art. 4) |

**How 388 became 673:**
- c01–c66 bring v1's 388 to 394: 23 at grade 2, 30 at grade 1, 341 at grade 0 (plan §2.6);
- the natural-query pool then adds 265 judgments: 3 at grade 1, 262 at grade 0 (659 in all);
- the Gate 2 review changes (c332–c348) then:
  - regrade two records, q06 Code Art. 110 from 0 to 1 and q15 Code Art. 154-bis from 1 to 0;
  - add 14 judgments at grade 1, for 673 in all.

**Change lines by basis:**
- `owner`: 49, outcomes the owner set, including the 17 Gate 2 review lines;
- `derived`: 34, proposed by Claude and approved by the owner in the plan, including 22 natural
  queries approved at Gate 1;
- `natural_pool`: 265, judged after pooling. Their lines keep `owner_decision` null; the owner's
  later decision on any of them is a separate review line, or the record's review status.

**Review status:** 28 judgments are `owner_reviewed`. The other 645 judgments and all 24
questions are `candidate`.

## The changes (`changes.jsonl`)

| IDs | Kind | Count |
|---|---|---|
| c01–c10 | grade changes | 10 |
| c11–c14 | added judgments (c14 at grade 0) | 4 |
| c15 | removed article-level judgment (q17 GDPR Art. 4) | 1 |
| c16–c18 | its three points (13, 14, 15) | 3 |
| c19–c39 | rationale only (D3, D5, D6) | 21 |
| c40–c42 | question fields (two categories, one note) | 3 |
| c43–c66 | natural queries, one line per question | 24 |
| c67–c331 | natural-pool judgments | 265 |
| c332–c348 | Gate 2 review changes: two grade changes, one rationale change and 14 added judgments | 17 |

**The keys of each line:**

| Key | Value |
|---|---|
| `change_id` | the change's ID |
| `decision` | one of D1–D8, or `review` for a change made at the owner's review (Gate 2) |
| `basis` | `owner`, `derived` or `natural_pool` |
| `record` | `judgment` or `question` |
| `query_id`, `instrument`, `article`, `point` | identify the record |
| `before`, `after` | only the fields that change, provenance aside. `before` is null for an added judgment, and `{}` for an added field. `after` is null for a removed judgment. |
| `owner_decision` | the owner's decision on the change, with its date. Null for the natural-pool lines, which the owner has not yet reviewed. |
| `reason` | why the change was made |

`owner_decision` never sets `review_status`.

## Provenance

| Record | Provenance |
|---|---|
| Unchanged judgment (356 of the 388 v1 records) | the v1 provenance object, unchanged. For q05 GDPR Art. 23, reviewed at Gate 2, only the review fields changed. |
| Changed or added judgment (c01–c39) | drafted by Claude under the owner's decisions; `candidate` |
| Natural-pool judgment | drafted by Claude from the natural-query pool; `candidate`, unless reviewed at Gate 2 |
| Changed or added at Gate 2 (c332–c348) | drafted by Claude at Gate 2 from the owner's decisions; `owner_reviewed` |
| Question | question and technical queries from v1; natural queries and v2 changes drafted by Claude; `candidate` |

**Review fields.** For the 28 records reviewed at Gate 2, `review_status` is `owner_reviewed`,
`reviewed_by` is «Simone Zanetti» and `reviewed_on` is 2026-11-12. Their drafting fields are
unchanged, except for the 17 records changed or added at Gate 2. Everywhere else `reviewed_by`
and `reviewed_on` are null.

## Pooling

**Technical queries.** The v1 pool, unchanged, because neither the queries nor the build
changed. See the legal-v1 README.

**Natural queries.** Pooled on 2026-11-11, after Gate 1, with the method of v1 unchanged:

| Retriever | Settings | Articles kept |
|---|---|---|
| BM25 | `src.provision_eval.rank_articles` (so `ProvisionExplorer.search`), chunk depth 20 | top 10 |
| Dense | `src.dense_retrieval.DenseRetriever`, model `intfloat/multilingual-e5-small` at revision `614241f622f53c4eeff9890bdc4f31cfecc418b3` | top 20 chunks per query mapped to articles, then top 10 |
| Hybrid | `src.hybrid_retrieval.HybridRetriever`, Reciprocal Rank Fusion with `BM25_TOP_K` 20, `DENSE_TOP_K` 20, `RRF_K` 60 | top 10 |

- **The model ran offline.** It came from the local Hugging Face cache, with `HF_HUB_OFFLINE=1`;
  nothing was downloaded. The chunk embeddings computed for the v1 pool were reused.
- **Mapping.** As in v1: chunks without article text add nothing, an article counts once at its
  best rank, and several queries are interleaved by rank.
- **No metric was computed.**
- **The build** is `build-f76ff6031f2fc82c4852f0a2bde27807`.
- **Sizes.** The natural lists hold 238 (BM25), 236 (dense) and 240 (hybrid) entries. Most lists
  have 10 articles; q21 dense has 7, q23 BM25 8 and q24 dense 9, because their top 20 chunks
  map to fewer articles. Across the three lists there are 416 (question, article) pairs: 151
  were already judged, and 265 are new.
- **How the new articles were judged.**
  - Each was graded under D1, from its heading and, where it could matter, from its text in the
    build.
  - They were listed by article, not by rank, and no ranking or metric was looked at.
  - An article with no heading in the transcription is graded 0 as «marked repealed in the
    transcription», as in v1.
- **Completeness.** Every pooled article is judged, and nothing else is. In both scenarios,
  the top 10 BM25 articles at chunk depth 20 of every question are judged.

**`judge_added`.** In v2 it lists every article added to the pool by a judge or by the owner's
decision, whatever its grade. In v1 it held only articles judged essential. v2 adds:
- q04 GDPR Art. 55 (c11);
- q05 GDPR Art. 4 point 12 (c12);
- q13 GDPR Art. 12 (c13);
- q14 GDPR Art. 55 (c14, graded 0);
- at Gate 2, the 14 restriction judgments (c335–c348): GDPR Art. 23 for q09–q13, Code
  Art. 2-undecies for q10–q12, and Code Art. 2-duodecies for q05 and q09–q13.

## Gate 2: the owner's review (2026-11-12)

The owner reviewed the 12 natural-pool judgments flagged as uncertain, and the records their
decisions touched. The analysis is in
[`legal-v2-uncertain-judgments-dossier.md`](../../../docs/evaluation/reviews/legal-v2-uncertain-judgments-dossier.md).

These are owner judgments about the textual relevance of the corpus text. They are not expert
legal validation. They establish nothing about the legal validity or currency of the Privacy
Code transcription, or of the 2016 GDPR text.

**The 12 uncertain judgments** (all `owner_reviewed`):

| Change | Question | Article | Final grade | Change at Gate 2 |
|---|---|---|---|---|
| c141 | q06 | GDPR Art. 9 | 1 | none |
| c130 | q06 | Code Art. 110 | 1 | 0 → 1 (c332) |
| c213 | q13 | Code Art. 2-undecies | 1 | none |
| c231 | q15 | Code Art. 166 | 1 | rationale only: on paragraphs 1–3 (c334) |
| c232 | q15 | Code Art. 144 | 0 | none |
| c234 | q15 | Code Art. 143 | 0 | none |
| c241 | q15 | Code Art. 154-ter | 0 | none |
| c103 | q04 | GDPR Art. 51 | 0 | none |
| c181 | q09 | Code Art. 111-bis | 0 | none |
| c264 | q17 | Code Art. 75 | 0 | none |
| c283 | q19 | GDPR Art. 12 | 0 | none |
| c298 | q20 | GDPR Art. 58 | 0 | none |

**The records their decisions touched** (also `owner_reviewed`):
- **q15 Code Art. 154-bis: 1 → 0** (c333). This is the strict reading of q15: guidelines,
  deontological rules, cooperation, publication and simplification are not the investigative or
  corrective powers asked about. Its grade 1 had been inherited from v1.
- **q05 GDPR Art. 23:** kept at 1.
- **The restrictions policy, Option A as revised: 14 additions at grade 1** (c335–c348):

  | Provision | Questions | Count |
  |---|---|---|
  | GDPR Art. 23 | q09, q10, q11, q12, q13 | 5 |
  | Code Art. 2-undecies | q10, q11, q12 | 3 |
  | Code Art. 2-duodecies | q05, q09, q10, q11, q12, q13 | 6 |

  - **Why these questions.** GDPR Art. 23(1) and Code Art. 2-duodecies cover Arts. 12–22 and
    34, so both include q09's Art. 13. Code Art. 2-undecies covers Arts. 15–22, so it does not
    include q09.

**Unreviewed.** The remaining 253 natural-pool judgments are grade 0 on their heading or text:
the article concerns something else, or is a repealed stub. Like the other records not listed
above, they are still candidates.

## Running (only after the freeze)

Do not run the evaluator on v2 before the owner has approved the completed review and the
freeze (plan §3.9): that would calculate v2 metrics.

After the freeze, from the project root:

```powershell
.\.venv\Scripts\python.exe -m src.provision_eval --benchmark data/evaluation/legal-v2 --scenario technical --output data/processed/evaluation/legal-v2-technical.json
.\.venv\Scripts\python.exe -m src.provision_eval --benchmark data/evaluation/legal-v2 --scenario natural --output data/processed/evaluation/legal-v2-natural.json
```

Compare the two scenarios with each other, never with legal-v1. Use the test split only to
report.

## Limitations

- **Mostly unreviewed and AI-drafted.** 645 of the 673 judgments are candidates that still need
  the owner's review. Most grade-0 judgments rest on the article's heading.
- **Pools.** They come from the top 10 of three retrievers per scenario, plus `judge_added`. An
  unjudged article counts as not relevant.
- **Consistency gaps.** Gate 2 filled the restrictions gap of the rights questions (14
  additions). Gaps of other kinds may remain among the unreviewed records.
- **Article-level scoring.** q01 and q02 both score GDPR Art. 4 alone.
- **The Privacy Code is an unverified transcription.** Relevance is relevance of its text.
- **Small.** 24 questions, 8 in the test split; there are no confidence intervals.
- **Tied to the recorded build's labels.**
