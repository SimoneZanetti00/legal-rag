# legal-v2: implementation plan (M4, P2.2)

*Status: revised twice on 2026-11-11 to record the owner's decisions (§0).*
- *Phase 1 (§8, steps 0 and 2–5) was implemented on 2026-11-11.*
- *Phase 2 (§8, steps 6–14) was authorized by the owner after the Phase 1 report, and
  implemented on 2026-11-11.*
- *Gate 2 (the owner's review) was approved by the owner, and its decisions were applied on
  2026-11-12 (§0, third round; §8, step 15).*
- *Gate 3 was authorized by the owner and carried out on 2026-11-12 (§8, steps 16–19):*
  - *legal-v2 is frozen, and its six files are pinned (C10);*
  - *it is the default benchmark;*
  - *its first results are in [`legal-v2-first-evaluation.md`](legal-v2-first-evaluation.md).*
- *Not authorized: every Git write (Gate 4).*
- *`data/evaluation/legal-v1/` is unchanged and stays unchanged.*

*Every record proposed here remains an unreviewed candidate (D8). The owner approving a change
in this plan is not a review of the record that the change produces.*

*Drafted by Claude (AI assistant) in a Claude Code session on 2026-11-11, from the owner's
decisions D1–D8 of the same day and the AI pre-review
[`reviews/legal-v1-human-review.md`](reviews/legal-v1-human-review.md). The grades below are
proposals about the textual relevance of provisions in this corpus. They are not legal opinions,
and they say nothing about whether any provision is valid or in force.*

**Inspected for this plan:**
- `src/provision_eval.py` and `src/query_analysis.py` (`query_problem`);
- `docs/evaluation/guidelines.md`;
- `tests/test_provision_eval.py`;
- all five files of `data/evaluation/legal-v1/`;
- `docs/evaluation/reviews/legal-v1-human-review.md`;
- `.gitattributes`;
- the text of every article cited below, in the recorded build
  `build-f76ff6031f2fc82c4852f0a2bde27807`.

**What was run (in memory only):** the Italian-query check and a lexical-overlap check on the
draft natural queries (§4.3). After the owner's decisions, the overlap check was run again with
the approved grades; the results did not change.

No search was run with a natural query, and no metric of either split was computed.

## 0. Owner decisions of 2026-11-11

| # | Decision | Where it applies |
|---|---|---|
| 1 | Adopt D1 and its restrictive grade-1 policy. | §2.0 |
| 2 | Approve the ten grade changes c01–c10. | §2.1 |
| 3 | Approve c11 (q04, GDPR Art. 55) at grade 1. | §2.2 |
| 4 | Approve c12 (q05, GDPR Art. 4 point 12) at grade 1. | §2.2 |
| 5 | Approve c13 (q13, GDPR Art. 12) at grade 1. | §2.2 |
| 6 | Approve c14 (q14, GDPR Art. 55) at grade 0, not 1. Keep the judgment only if the change log records the decision and its rationale; otherwise omit it. Never describe Art. 55 as identifying the Italian Garante. | §2.2, §3.5, §3.6, §6 (C2–C4) |
| 7 | Approve c15–c18: GDPR Art. 4 points 13, 14 and 15 recorded separately for q17. | §2.2 |
| 8 | Approve D5, D6, D7 and D8 as described in the plan. | §2.3, §2.4, §3.9 |
| 9 | Approve the D6 wording for the Privacy Code transcription judgments. | §2.3 (c23, c25–c39) |
| 10 | Approve the natural-query scenario in principle. The owner reviews all 24 drafts before any search or pooling is run. | §4, §8 (Gate 1) |
| 11 | Approve offline BM25, dense and hybrid pooling, provided the dense model is already cached. Nothing is downloaded. | §4.5, §8 (step 7) |

**Second round of decisions (2026-11-11), after the owner reviewed the revised plan:**

| # | Decision | Where it applies |
|---|---|---|
| 12 | U4 approved: keep q03 GDPR Art. 8 and Code Art. 2-quinquies at grade 1. They are relevant specifications for digital consent by minors. GDPR Art. 9 stays at 0. | §2.5 |
| 13 | U5 approved: keep q17 Code Arts. 2-sexies and 2-septies at grade 1. They are relevant national specifications of the conditions and safeguards for special categories. | §2.5 |
| 14 | U13 approved: the new rationales of c20 (q04, GDPR Art. 34) and c24 (q20, Code Art. 167). Their grades are unchanged. | §2.3 |
| 15 | Gate 1: the 24 natural-query drafts are approved, with two edits (q19, q20; §4.4). N1–N6 are rerun on all 24, and the work stops if either edited query fails. | §4.3, §4.4 |
| 16 | Phase 1 only (§8, steps 0 and 2–5) is authorized. Phase 2 needs the owner's explicit approval after the Phase 1 report. | §8 |
| 17 | Both `.gitattributes` changes move to Gate 4. `.gitattributes` is not modified in Phase 1 or Phase 2. | §3.8, §8, §9 |

**Constraints added with the second round:**
- no search or pooling with the natural queries yet;
- no real legal-v2 metric is calculated or published;
- `DEFAULT_BENCHMARK` stays `legal-v1`;
- no Git write of any kind;
- `readme-diff-review.txt` is not touched.

**Third round: Gate 2, the owner's review (2026-11-12).**
- **The review.** The owner (reviewer Simone Zanetti, review date 2026-11-12) confirmed the
  decisions in
  [`reviews/legal-v2-uncertain-judgments-dossier.md`](reviews/legal-v2-uncertain-judgments-dossier.md),
  §0. They were applied to `legal-v2`.
- **Not expert review.** These are owner judgments about textual relevance, not expert legal
  validation.

| # | Decision | Where it applies |
|---|---|---|
| 18 | The 12 uncertain judgments keep their grades, except c130 (q06, Code Art. 110), which goes from 0 to 1 (review line c332). Code Art. 166 for q15 rests on paragraphs 1–3; its rationale is reworded (c334). | `legal-v2` |
| 19 | q15, strict reading: Code Art. 154-bis goes from 1 to 0 (c333). Code Arts. 143, 144 and 154-ter stay 0. | `legal-v2` |
| 20 | The restrictions policy is Option A, as revised: 14 additions at grade 1 (c335–c348). They are GDPR Art. 23 for q09–q13, Code Art. 2-undecies for q10–q12, and Code Art. 2-duodecies for q05 and q09–q13. q05 GDPR Art. 23 and c213 stay 1. | `legal-v2` |
| 21 | Exactly 28 judgments become `owner_reviewed`: the 12, q15 Code Art. 154-bis, q05 GDPR Art. 23, and the 14 additions. Every other record stays `candidate`. | `legal-v2` |
| 22 | The guidelines record the readings applied: a question that names the kinds it asks about (rule 1), sector cases in an all-cases question (rule 5), and restrictions (new rule 6). | guidelines |

**After Gate 2:** 673 judgments (23 grade 2, 47 grade 1, 603 grade 0), 348 change lines. Not
frozen; `DEFAULT_BENCHMARK` is still `legal-v1`; no v2 metric has been calculated.

**The owner's constraints on the implementation:**
- `legal-v1` stays byte for byte unchanged.
- `DEFAULT_BENCHMARK` points to `legal-v1` throughout implementation and review. It moves to
  `legal-v2` only after the owner has explicitly approved the completed review and the freeze
  (Gate 3).
- No Git staging, commits, pushes or merges. `legal-v1`, `.gitattributes` and every other file
  stay uncommitted.
- No change to the corpus, registry, source archives, builds, provenance or review ledger.
- No change to the retrieval ranking, the BM25 settings, the merging rules or the retrieval
  defaults.
- No real legal-v2 metric is calculated or published before the benchmark is reviewed and
  frozen.

**How c14 is resolved: kept, at grade 0.**
- **Why it is kept.** `changes.jsonl` records the owner's decision and its rationale (§3.5),
  which is the condition the owner set for keeping it.
- **Where it appears:**
  - as a grade-0 judgment in `judgments.jsonl`;
  - in the `judge_added` list of q14's row in `pool.jsonl` (§3.6);
  - as change c14;
  - in the totals (§2.6);
  - in tests C2, C3 and C4.
- **What no text says.** No rationale, here or in v2, describes Art. 55 as identifying the
  Garante.

## 1. Executive summary

- **A new directory; v1 frozen.** `legal-v2` is a new directory, `data/evaluation/legal-v2/`.
  - `legal-v1` is never opened for writing, and a test pins its five SHA-256 values.
  - Its data files use CRLF line endings, and this machine has `core.autocrlf=true`. A
    `.gitattributes` rule would stop Git from rewriting those endings when they are committed.
    The rule is added only at the separate Git step (Gate 4, §0-17), which is not authorized
    (U12).
- **D1 applied to all 388 v1 judgments.** It gives:
  - 10 grade changes (8 from 1 to 0, 2 from 0 to 1);
  - 4 new judgments:
    - 3 at grade 1: GDPR Art. 55 for q04, GDPR Art. 4 point 12 for q05, GDPR Art. 12 for q13;
    - 1 at grade 0: GDPR Art. 55 for q14, as the owner decided;
  - one article-level judgment (q17, GDPR Art. 4) recorded as its three points, with no effect
    on metrics;
  - 21 rationale-only changes, which write down the owner's decisions and apply the D6 wording;
  - 2 category changes (D7).
- **Approval status.**
  - **Approved by the owner:**
    - every grade change and addition (c01–c18), every rationale change (c19–c39) and the D5–D7
      changes;
    - the two borderline grades, kept at 1 (U4, U5);
    - the 24 natural queries, at Gate 1.
  - **Still open:** what to do if the dense model is not cached (§7.2). Phase 2 also needs the
    owner's approval.
  - Every record stays a candidate (D8).
- **Totals:** 394 judgments: 23 grade 2, 30 grade 1, 341 grade 0. The judgments that pooling the
  natural queries adds come on top (§4.5); their number is not known yet.
- **A natural-query scenario (D2).** It needs:
  - one new required question key in schema 2, `search_queries_it_natural`;
  - one evaluator option, `--scenario technical|natural`.

  The two scenarios share the questions and the judgments, and each gets its own report.
  - **The queries:** §4.4 gives natural queries for all 24 questions. The owner approved them at
    Gate 1, with two edits (q19, q20). No search or pooling has been run with them.
  - **The overlap check** (§4.3): the current queries of 19 of the 20 answerable questions copy a
    heading or a judged definition. None of the drafts does.
- **Code changes only for D2.** D1 and D3–D8 change data and documents only.
  - These are unchanged:
    - ranking and BM25;
    - the chunk depth (20) and the depth `ask` uses (5);
    - the merging rule;
    - the metrics.
  - `DEFAULT_BENCHMARK` stays `legal-v1` until the freeze is approved.
- **No v2 metric before the freeze.** No v2 metric is calculated, on either split, until the
  owner has reviewed v2 and approved its freeze.
- **Review is separate.** A record becomes `owner_reviewed` only in a later, separate step, in
  which the owner states what they approved (§3.9, D8).

## 2. Record-level changes

**Notation.**
- **G**: GDPR, `eu-reg-2016-679`. **C**: the Privacy Code transcription, `it-dlgs-2003-196`.
- **Basis** says where the outcome came from:
  - **owner**: the owner set the outcome, in D3–D7 or in a decision of §0;
  - **derived**: Claude proposed it under D1, and the owner approved the proposal on
    2026-11-11 (§0);
  - **natural_pool**: judged later, from the natural-query pool, and not yet approved.
- **Approved** gives the §0 decision that approves the change.
- **IDs** (c01…) are the `change_id` values in `changes.jsonl` (§3.5).

### 2.0 How D1 is applied (adopted, §0-1)

- **Grade 2:** the provision directly answers the question.
- **Grade 1:** the provision gives concrete information useful to formulate the answer: a
  necessary condition, an exception, a procedure, a prerequisite, or a relevant specification.
- **Grade 0:** thematic similarity, shared terminology, or related obligations or consequences
  that the answer does not need.

Five working rules follow from D1. They decide the cases below, and they go into the
guidelines.

1. **Grade against what the question asks**, not against its topic.
   - Consequences of the rule asked about are 0, and so are the obligations that follow from it.
   - Examples: q02 Arts. 33–34, q06 Art. 36, q11 Art. 19, q20 Art. 84.
2. **Cross-references.** A provision that the grade-2 article refers to is 1 when the answer
   needs what only it says.
   - For example, it fixes the scope of the rule asked about (q13 Art. 6, q16 Art. 6).
   - When the referring article states the condition in its own words, the referenced one
     stays 0 (q11 Art. 21; q12 Art. 6, not judged).
3. **Definitions.** A definition is 2 when the question asks for it (q01, q02). It is 1 when
   the defined term triggers the rule asked about, or names what the rule covers:
   - the breach in q04 and q05;
   - the supervisory authority in q14;
   - the special categories in q17.
4. **The same provision gets the same grade in questions of the same kind.**
   - Art. 12(3) sets the time limit and the manner of answering requests under Arts. 15–22. It
     is 1 in every question about exercising one of those rights (q10–q13).
   - Each breach obligation is 0 in the question about the other (q04 Art. 34, q05 Art. 33).
5. **National specifications.** A Code article that fills an option the GDPR article leaves to
   Member States is 1, even when the question does not name Italy.
   - Examples: q03 Art. 2-quinquies, q08 Art. 2-sex-decies, q17 Arts. 2-sexies and 2-septies.
   - A Code rule for a narrow sector that the question does not ask about is 0 (q17 Art. 107,
     D5).

### 2.1 Grade changes (all approved, §0-2)

| ID | Q | Judgment | v1 | v2 | Decision | Basis | D1 reading | v2 rationale |
|---|---|---|---|---|---|---|---|---|
| c01 | q02 | G Art. 32 | 1 | 0 | D3 | owner | related obligation | Not relevant: security of processing is a related obligation; the breach is defined in Art. 4 point 12. |
| c02 | q02 | G Art. 33 | 1 | 0 | D1 | derived | consequence | Not relevant: notifying the authority follows a breach; it is not part of the definition. |
| c03 | q02 | G Art. 34 | 1 | 0 | D1 | derived | consequence | Not relevant: communicating a breach to data subjects follows a breach; it is not part of the definition. |
| c04 | q03 | G Art. 6 | 1 | 0 | D1 | derived | related, not needed | Not relevant: paragraph 1, letter a), names consent as a legal basis; the requirements of valid consent are in Art. 4 point 11 and Art. 7. |
| c05 | q05 | G Art. 33 | 1 | 0 | D3 | owner | related obligation | Not relevant: notification to the authority is a related obligation, not the communication to data subjects asked about. |
| c06 | q06 | G Art. 36 | 1 | 0 | D1 | derived | consequence | Not relevant: prior consultation follows an assessment; it does not say when one is required. |
| c07 | q11 | G Art. 12 | 0 | 1 | D3 | owner | procedure | Paragraph 3: the time limit (one month, extendable) and the manner of answering a request under Arts. 15-22, erasure included. |
| c08 | q11 | G Art. 19 | 1 | 0 | D1 | derived | consequence | Not relevant: notifying recipients follows an erasure; it is not one of its grounds. |
| c09 | q13 | G Art. 6 | 0 | 1 | D1 | derived | specification of scope | Art. 21(1) allows objection to processing on the bases of Art. 6(1)(e) and (f), which only Art. 6 sets out. |
| c10 | q20 | G Art. 84 | 1 | 0 | D3 | owner | related, not needed | Not relevant: other penalties set by the Member States, not the administrative fines asked about. |

The text behind these readings, as read in the build:
- Art. 12(3): requests under «articoli da 15 a 22» are answered «al più tardi entro un mese»;
- Art. 21(1): it concerns processing «ai sensi dell'articolo 6, paragrafo 1, lettere e) o f)»;
- Art. 36(1): it applies «qualora la valutazione d'impatto … indichi» a high risk;
- Art. 84(1): it concerns «altre sanzioni».

### 2.2 Added and removed judgments (all approved)

| ID | Q | Judgment | v1 | v2 | Decision | Basis | Approved | D1 reading | v2 rationale |
|---|---|---|---|---|---|---|---|---|---|
| c11 | q04 | G Art. 55 | not judged | 1 | D4 | owner | §0-3 | relevant specification | Art. 33(1) requires notification to the authority «competente a norma dell'articolo 55»; Art. 55(1) makes each authority competent on its own Member State's territory. |
| c12 | q05 | G Art. 4 point 12 | not judged | 1 | D1 (rules 3, 4) | derived | §0-4 | prerequisite | Point 12 defines the personal data breach to be communicated. |
| c13 | q13 | G Art. 12 | not judged | 1 | D1 (rule 4) | derived | §0-5 | procedure | Paragraph 3: the time limit and the manner of answering a request under Arts. 15-22, objection included. |
| c14 | q14 | G Art. 55 | not judged | 0 | D1 | owner | §0-6 | not needed: territorial competence in general | Not relevant: Art. 55(1) states the territorial competence of supervisory authorities in general; it names no national authority. |
| c15 | q17 | G Art. 4 (article level) | 1 | removed | D1 | derived | §0-7 | form only | (replaced by c16–c18) |
| c16 | q17 | G Art. 4 point 13 | — | 1 | D1 | derived | §0-7 | specification | Point 13 defines «dati genetici», a category Art. 9(1) names. |
| c17 | q17 | G Art. 4 point 14 | — | 1 | D1 | derived | §0-7 | specification | Point 14 defines «dati biometrici», a category Art. 9(1) names. |
| c18 | q17 | G Art. 4 point 15 | — | 1 | D1 | derived | §0-7 | specification | Point 15 defines «dati relativi alla salute», a category Art. 9(1) names. |

- **c11 (D4): q04, GDPR Art. 55, grade 1.**
  - Art. 33(1) defines the recipient of the notification by referring to Art. 55. Art. 55's
    rule on competence therefore completes the obligation the question asks about: a relevant
    specification under D1.
  - The owner set grade 1 (§0-3).
  - No retriever ranked the article in its top 10 for q04, so it was not in the v1 pool. It
    goes into the pool's `judge_added`.
- **c14: q14, GDPR Art. 55, grade 0 (§0-6).**
  - Art. 55(1) states territorial competence in general and names no national authority.
  - Which body is Italy's supervisory authority is stated, in the transcription, by Code
    Art. 2-bis. That article is already grade 2 for q14, and c14 does not change it.
  - The judgment is kept because its change line records the owner's decision and its
    rationale (§3.5); without that record it would be omitted.
  - It goes into q14's `judge_added`, so that the pool test covers it. At grade 0 it adds
    nothing to any metric.
- **c12** makes q05 consistent with q04, where a judge added Art. 4 point 12 at grade 1 in v1.
- **c13** makes q13 consistent with q10, q12 and, after c07, q11.
- **c15–c18** record the three points that the v1 rationale already named.
  - The article still counts at grade 1, so no metric changes.
  - The points exist as `13)`, `14)` and `15)` lines in the anchored text; this was checked.
- **Pool:** c11, c12, c13 and c14 go into `judge_added` in `pool.jsonl` (§3.6).

### 2.3 Rationale-only changes

The grade stays the same in every row.
- Where the owner decided the grade (D3, D5), the new rationale says why.
- On the transcription, the new wording keeps textual relevance apart from legal validity (D6).

| ID | Q | Judgment | Grade | Decision | Approved | v2 rationale |
|---|---|---|---|---|---|---|
| c19 | q03 | G Art. 9 | 0 | D5 | §0-8 | Not relevant: explicit consent under Art. 9(2)(a) lifts the ban on special categories; it is not a general requirement of valid consent. |
| c20 | q04 | G Art. 34 | 0 | D3 | §0-14 | Not relevant: communication to data subjects is a related obligation, not the notification to the Garante asked about. |
| c21 | q17 | C Art. 107 | 0 | D5 | §0-8 | Not relevant: in the transcription, a rule on consent for special categories in statistics and research only; not needed to state what GDPR Art. 9 provides. |
| c22 | q18 | G Art. 8 | 2 | D5 | §0-8 | Sets the rule (16 years) and lets Member States set a lower age, not below 13; the age in Italy is answered by reading it with Code Art. 2-quinquies. |
| c23 | q18 | C Art. 2-quinquies | 2 | D5, D6 | §0-8, §0-9 | In the transcription: sets the age of 14 «in attuazione dell'articolo 8, paragrafo 1»; answered by reading it with GDPR Art. 8. Relevance of the text only, not a statement of the law in force. |
| c24 | q20 | C Art. 167 | 0 | D3 | §0-14 | Not relevant: in the transcription, a criminal offence, not the administrative fines asked about. |
| c25–c39 | — | the other 15 Code judgments of grade 1 or 2 | kept | D6 | §0-9 | The v1 rationale, prefixed «In the transcription: ». A leading «In the Privacy Code: » or «In this transcription: » is replaced by the prefix. Nothing else changes. |

**c20 and c24.** Their grades are the owner's D3 decisions and do not change. The owner
approved their new wording (§0-14).

c25–c39, in order:

| Question | Code articles (grade) |
|---|---|
| q03 | 2-quinquies (1) |
| q04 | 2-quaterdecies.1 (1), 2-bis (1) |
| q08 | 2-sex-decies (1) |
| q13 | 130 (1) |
| q14 | 2-bis (2), 153 (1) |
| q15 | 154-bis, 157, 158 (1) |
| q16 | 2-ter (2) |
| q17 | 2-sexies, 2-septies (1) |
| q19 | 2-terdecies (2) |
| q20 | 166 (2) |

**D6: what these 16 judgments mean (approved, §0-8 and §0-9).** c23 and c25–c39 grade the text
of an unverified user transcription.
- Its version is `it-dlgs-2003-196@transcription-vigente-2026-11-05`. The label is the name it
  was given, not a verification.
- A grade of 1 or 2 says that the text answers the question, or helps to answer it. It does not
  say the transcription is accurate, verified or the law in force, and no rationale may say so.
- The M1 provenance warning stays. The corpus, registry, source archives, builds, provenance
  and review ledger are not touched.
- Code Art. 2-quaterdecies.1 keeps its grade 1, although the pre-review could not tell from the
  corpus whether it is in force (INSUFFICIENT_CORPUS_EVIDENCE).

### 2.4 Question changes

| ID | Q | Field | v1 | v2 | Decision | Approved | Reason |
|---|---|---|---|---|---|---|---|
| c40 | q03 | `category` | `definition` | `obligation` | D7 | §0-8 | It asks for the requirements valid consent must meet: what the controller must ensure and be able to prove (Art. 7), not what a term means. |
| c41 | q19 | `category` | `cross_instrument` | `rights` | D7 | §0-8 | Only Code Art. 2-terdecies answers it, and it asks who may exercise the rights of Arts. 15-22. |
| c42 | q18 | `notes` | The age of digital consent: the GDPR rule and the age set in the Privacy Code. | The age of digital consent: GDPR Art. 8 sets the rule and the Member States' option; Art. 2-quinquies of the Code transcription uses the option. Both are needed. | D5 | §0-8 | Writes down the combined reading. |
| c43–c66 | q01–q24 | `search_queries_it_natural` | — | §4.4 | D2 | §0-10; the wording was approved at Gate 1 (§0-15), with q19 and q20 edited | The natural scenario. |

**D7 (approved, §0-8).**
- No new category is needed; the enum stays as it is.
- Categories are metadata. The evaluator reports means by split, not by category, so c40 and
  c41 change no metric.
- q18 and q20 stay `cross_instrument`: both instruments are needed to answer them.

### 2.5 Checked and kept

These judgments were checked against D1 and keep their v1 grade.

| Q | Judgment | Grade | Why it stays under D1 |
|---|---|---|---|
| q02 | G Art. 5, C Art. 132-ter | 0 | Shared terminology (the same risks), not part of the definition. |
| q03 | G Art. 8, C Art. 2-quinquies | 1 | Relevant specifications for one case: digital consent by minors. GDPR Art. 9 stays at 0. **Kept at 1 by the owner (U4, §0-12).** |
| q04 | C Art. 2-quaterdecies.1 | 1 | A specific notification procedure for firms with fewer than five employees. D6 applies. |
| q04 | C Art. 2-bis | 1 | Identifies the Garante, which the question names, as the authority to notify (in the transcription). |
| q04 | G Art. 4 point 12 | 1 | A prerequisite: what must be notified (rule 3). c12 gives q05 the same grade (§0-4). |
| q05 | G Art. 23 | 1 | An exception: Union or Member State law may restrict Art. 34. |
| q05 | G Art. 58 | 1 | A procedure: under paragraph 2, letter e), the authority may order the communication, as Art. 34(4) foresees. |
| q08 | C Art. 2-sex-decies | 1 | A national specification (rule 5). Art. 37(4) lets Member State law require a DPO, and this article extends designation to judicial authorities. |
| q08 | G Arts. 38, 39 | 0 | The DPO's position and tasks, not when one must be designated. |
| q09 | G Art. 12 | 1 | A procedure: how the information of Art. 13 is given. |
| q09 | G Art. 14, C Art. 80 | 0 | Data not obtained from the data subject, and information given by other subjects: not what is asked. |
| q10, q12 | G Art. 12 | 1 | The procedure and the time limit (rule 4). |
| q11 | G Art. 21 | 0 | A related right. Art. 17(1)(c) states that ground in its own words (rule 2). |
| q13 | C Art. 130 | 1 | A relevant specification: objection to marketing communications, in the transcription. |
| q14 | G Art. 51, G Art. 4 point 21, C Art. 153 | 1 | A prerequisite (Member States provide supervisory authorities), the definition, and the body that Art. 2-bis names. |
| q15 | G Art. 83 | 1 | A relevant specification: the conditions and amounts of the fining power of Art. 58(2)(i). |
| q15 | C Arts. 154-bis, 157, 158 | 1 | National specifications of the Garante's powers. |
| q15 | G Art. 55 | 0 | Competence, not powers. |
| q16 | G Art. 6 | 1 | Art. 2-ter refers to Art. 6(3) for its content (rule 2). |
| q17 | C Arts. 2-sexies, 2-septies | 1 | Relevant national specifications of the conditions and safeguards for special categories (rule 5). **Kept at 1 by the owner (U5, §0-13).** |
| q18 | G Art. 4 | 0 | Point 25 only refers to a directive outside the corpus. |
| q20 | C Art. 171 | 0 | A different offence. |
| q21–q24 | all | 0 | Out of scope or not in the corpus. No change. |

U4 and U5 were decided as grade 1 (§0-12, §0-13). The four judgments keep their v1 grade, so
they need no change line.

### 2.6 Totals

| | v1 | v2 (§0 applied) |
|---|---|---|
| Judgments | 388 | 394 (1 removed, 7 added) |
| Grade 2 | 23 | 23 |
| Grade 1 | 31 | 30: 31, less 8 regraded to 0, plus 2 regraded from 0, less the removed article-level record, plus the 3 points and the 3 additions at grade 1 |
| Grade 0 | 334 | 341: 334, plus 8 regraded, less 2 regraded, plus c14 |
| Questions | 24 (16 dev, 8 test) | 24, with the same IDs, splits, question texts and technical queries |

**Change lines in `changes.jsonl`:**

| Kind | IDs | Count |
|---|---|---|
| Grade changes | c01–c10 | 10 |
| Added judgments | c11–c14, c16–c18 | 7 (6 at grade 1; c14 at grade 0) |
| Removed judgments | c15 | 1 |
| Rationale only | c19–c39 | 21 |
| Question fields | c40–c42 | 3 |
| Natural queries | c43–c66 | 24 |
| **Total** | c01–c66 | **66** |

The judgments from the natural-query pool (§4.5) come after these, each a `natural_pool` line
numbered from c67. The totals above then grow by the number of newly pooled articles.

## 3. Proposed v2 schema and versioning

### 3.1 Directory

`data/evaluation/legal-v2/` holds six files:

| File | Read by the evaluator | Content |
|---|---|---|
| `benchmark.json` | yes (hashed) | the manifest, schema 2 |
| `questions.jsonl` | yes (hashed) | 24 questions, with both query lists |
| `judgments.jsonl` | yes (hashed) | the v1 judgments with §2 applied, plus the natural-pool judgments |
| `pool.jsonl` | no | the v1 pool, the added articles, and the natural-query pool |
| `changes.jsonl` | no | every difference from v1, one per line |
| `README.md` | no | what v2 is, its relation to v1, the decisions, and how to run it |

### 3.2 `benchmark.json`

The manifest keeps the five keys of schema 1; only the values change:

```json
{"schema_version": 2, "benchmark_id": "legal", "version": "2", "kind": "real",
 "description": "24 Italian questions on the GDPR (2016 publication) and the Privacy Code transcription, revised from legal v1 under the owner's decisions D1-D8; two query scenarios (technical, natural); all records are unreviewed candidates."}
```

- **The ID stays `legal`.** v2 is the next version of the same benchmark, and reports tell the
  versions apart by `version` and the file hashes.
- **The relation to v1** lives in the README and in `changes.jsonl`, not in the manifest. The
  manifest therefore needs no new key.

### 3.3 `questions.jsonl` (schema 2)

Schema 2 is schema 1 plus one required key:

| Key | Required | Value |
|---|---|---|
| `search_queries_it` | yes | unchanged: the **technical** scenario. In v2 it is identical to v1 for every question. |
| `search_queries_it_natural` | yes in schema 2; not allowed in schema 1 | the **natural** scenario. A non-empty list, checked exactly like `search_queries_it`: each query must pass `query_problem`. |

Every other key, and its validation, is unchanged. An example (q04, with the draft queries):

```json
{"query_id": "q04", "question": "Entro quanto tempo il titolare deve notificare al Garante una violazione dei dati personali?",
 "search_queries_it": ["notifica di una violazione dei dati personali all'autorità di controllo", "senza ingiustificato ritardo entro 72 ore"],
 "search_queries_it_natural": ["termine per la notifica del data breach al Garante", "ritardo nella segnalazione di una fuga di dati all'autorità"],
 "category": "procedure", "expected_outcome": "answerable", "split": "dev",
 "provenance": {"drafted_by": "…", "drafted_on": "YYYY-MM-DD", "review_status": "candidate", "reviewed_by": null, "reviewed_on": null},
 "notes": "The deadline and conditions for notifying a breach to the supervisory authority."}
```

The v2 tests check the design rules of this benchmark: as many natural queries as technical
ones, and no copying. The loader does not check them, because they belong to this benchmark,
not to the schema.

### 3.4 `judgments.jsonl`, and the provenance of v2 records

- **Schema:** unchanged from schema 1.
- **Order:**
  - the v1 order is kept;
  - changed records stay in place;
  - c16–c18 take the place of c15;
  - an added record follows the last record of its question.
- **Provenance** of each kind of record:

| Record | Provenance |
|---|---|
| Unchanged judgment | the v1 provenance object, unchanged |
| Judgment changed or added by §2 | `drafted_by`: «Claude (AI assistant), revised from legal v1 in a Claude Code session under the owner's decisions D1-D8 and the plan decisions of 2026-11-11 (docs/evaluation/legal-v2-implementation-plan.md)». `drafted_on`: the day it is written. `review_status`: `candidate`. `reviewed_by` and `reviewed_on`: null. |
| Natural-pool judgment | the same, with «judged from the natural-query pool on build-f76ff6031f2fc82c4852f0a2bde27807» |
| Question (every question gains natural queries) | the same as a changed judgment, naming both sources: «question and technical queries from legal v1; natural queries and v2 changes drafted in a Claude Code session» |

**A plan approval is not a review.** Every one of these records is a `candidate`, including
those whose change the owner approved in §0. The provenance keys are fixed by the schema, so
the decision behind each change, and the owner's approval of it, are recorded in
`changes.jsonl` (§3.5).

### 3.5 `changes.jsonl`

`changes.jsonl` has one line per changed, added or removed record. The evaluator does not read
it; test C2 checks it against v1 and v2 (§6).

```json
{"change_id": "c01", "decision": "D3", "basis": "owner", "record": "judgment",
 "query_id": "q02", "instrument": "eu-reg-2016-679", "article": "32", "point": null,
 "before": {"grade": 1, "rationale": "Security of processing: names the same risks …"},
 "after": {"grade": 0, "rationale": "Not relevant: security of processing is a related obligation; …"},
 "owner_decision": "2026-11-11, plan decision 2: approved.",
 "reason": "D1: a related obligation, not needed to define a breach."}
{"change_id": "c14", "decision": "D1", "basis": "owner", "record": "judgment",
 "query_id": "q14", "instrument": "eu-reg-2016-679", "article": "55", "point": null,
 "before": null,
 "after": {"grade": 0, "rationale": "Not relevant: Art. 55(1) states the territorial competence of supervisory authorities in general; it names no national authority."},
 "owner_decision": "2026-11-11, plan decision 6: approved with grade 0, not 1; Art. 55 is not to be described as identifying the Garante.",
 "reason": "Considered with the D4 review of Art. 55. Kept at grade 0 so that the decision is on record; Code Art. 2-bis, already grade 2, is the article that names Italy's authority, in the transcription."}
{"change_id": "c15", "decision": "D1", "basis": "derived", "record": "judgment",
 "query_id": "q17", "instrument": "eu-reg-2016-679", "article": "4", "point": null,
 "before": {"grade": 1, "rationale": "Points 13-15 define genetic, biometric and health data."}, "after": null,
 "owner_decision": "2026-11-11, plan decision 7: approved.",
 "reason": "Recorded as points 13, 14 and 15 (c16-c18); the article still counts at grade 1."}
{"change_id": "c40", "decision": "D7", "basis": "owner", "record": "question", "query_id": "q03",
 "instrument": null, "article": null, "point": null,
 "before": {"category": "definition"}, "after": {"category": "obligation"},
 "owner_decision": "2026-11-11, plan decision 8: approved.", "reason": "…"}
```

**The keys of each line:**

| Key | Value |
|---|---|
| `query_id`, `instrument`, `article`, `point` | identify the record: a judgment, or a question (with the last three null) |
| `before`, `after` | only the fields that change, apart from the key and the provenance. For an addition, `before` is null; for a removal, `after` is null. |
| `decision` | one of D1–D8 |
| `basis` | `owner`, `derived` or `natural_pool` (§2) |
| `owner_decision` | the owner's decision on the change, with its date |
| `reason` | why the change was made |

**When `owner_decision` is null:** only for `natural_pool` lines, until the owner's review.
- c20 and c24 carry the approval of §0-14.
- c43–c66 carry the Gate 1 decision (§0-15): approved, or edited for q19 and q20. They are
  written in Phase 2 (§8, step 6).

**What `owner_decision` does not do:** it records approval of the change. It never sets
`review_status`, which follows §3.9.

**Later changes:** any change from the owner's review is appended, with the decision `review`.

### 3.6 `pool.jsonl`

Each v2 row is the v1 row with:
- its `bm25`, `dense` and `hybrid` lists unchanged;
- four entries appended to `judge_added`:

  | Question | Entry | Change |
  |---|---|---|
  | q04 | `eu-reg-2016-679:55` | c11 |
  | q05 | `eu-reg-2016-679:4 point 12` | c12 |
  | q13 | `eu-reg-2016-679:12` | c13 |
  | q14 | `eu-reg-2016-679:55` | c14, judged 0 |

- a new `natural` object holding the natural-query pool.

```json
{"query_id": "q04", "bm25": ["…as in v1…"], "dense": ["…as in v1…"], "hybrid": ["…as in v1…"],
 "judge_added": ["it-dlgs-2003-196:2-bis", "eu-reg-2016-679:4 point 12", "eu-reg-2016-679:55"],
 "natural": {"bm25": ["…"], "dense": ["…"], "hybrid": ["…"]}}
```

- **What `judge_added` means in v2.** In v2 it lists every article added to the pool by a judge
  or by the owner's decision, whatever its grade. The v2 README says so, because in v1 it held
  only articles judged essential.
- **The technical lists are not rerun:** their queries and the build have not changed.

### 3.7 The v2 `README.md`

The README states:
- what v2 is, and that every record is a candidate;
- the five v1 SHA-256 values v2 derives from (§3.8);
- the decisions D1–D8 and §0, one line each, with a pointer to this plan;
- the totals of §2.6;
- the two scenarios, and what may be compared after freezing (§4.6);
- the D6 statement;
- the pooling, including the natural pool and the meaning of `judge_added`;
- that `DEFAULT_BENCHMARK` stays `legal-v1` until the freeze is approved;
- that no v2 metric exists before the freeze;
- whether v2 is frozen;
- the limitations carried over from v1.

### 3.8 Keeping `legal-v1` byte for byte

1. **Never write to it.** A one-off script in the session scratchpad produces the v2 files.
   - It opens v1 read-only, applies `changes.jsonl`, and writes only into `legal-v2/`.
   - The v1 hashes are compared before and after.
2. **Pin it in a test.** `test_legal_v1_files_are_unchanged` checks that the directory holds
   exactly five files, with these SHA-256 values:

   | File | SHA-256 |
   |---|---|
   | `README.md` | `ef0fd2e54c69b9d7a8aecd693444926e80fb57d69683fdf7505bcf8e31c01c17` |
   | `benchmark.json` | `a7cf326089e2d93b2552de2a4333a8df89fe2689dbb50eec755c8723870ad6c7` |
   | `judgments.jsonl` | `293fdfa976b49f08cd2ac378c32eb49e575899cdf00d42b56d1a106042f64c0f` |
   | `pool.jsonl` | `7e7ec00d90618a76f7cf3f161801223ec73e1423c2177cc2c7f0bfc77165949f` |
   | `questions.jsonl` | `3c4e118f80f5cd5cda7d7af12aa8cbddff1092785bbc5cd5513ce09780f8151d` |

3. **Prepare Git not to change its bytes.**
   - **The facts.** The four v1 data files end their lines with CRLF, and the v1 README uses
     LF. This machine has `core.autocrlf=true`, and `.gitattributes` has no rule for
     `data/evaluation/`.
   - **What would happen.** Committing and checking out would turn the README into CRLF on this
     machine, and every file into LF on other platforms. Both the hashes the test pins and the
     hashes every report records would change.
   - **The fix.** Add `data/evaluation/legal-v1/** -text` and `data/evaluation/legal-v2/** -text`
     to `.gitattributes`. The archived official sources already get this treatment, and v2 is
     written with LF.
   - **When.** At Gate 4 only (§0-17), which is not authorized (U12).
     - `.gitattributes` is not modified in Phase 1 or Phase 2.
     - The rules must be in place before any `git add` under `data/evaluation/`.
     - Until then they have no effect to lose: nothing under `data/evaluation/` is staged.
4. **Keep the v1 tests on v1.** The four existing `legal_v1` tests use `pe.DEFAULT_BENCHMARK`.
   - They get an explicit `LEGAL_V1` path.
   - The default stays `legal-v1` until Gate 3 (U9). The explicit path keeps these tests on v1
     when the default later moves.

**v1 is still untracked**, and stays so, because committing it is not authorized (U12). Until
then, only the hash test protects it, and a `git clean` would delete it.

### 3.9 When v2 is frozen

1. **Open (after implementation).**
   - v2 may still change: the owner's review may change grades, and each such change is
     appended to `changes.jsonl`.
   - No v2 metric is calculated, on either split, and none is published.
   - `DEFAULT_BENCHMARK` is `legal-v1`.
2. **Review (Gate 2: a separate step that needs the owner's explicit input).**
   - The owner lists the records they approve, and the name to record.
   - The implementation then sets `owner_reviewed` on those records only, with `reviewed_by`
     and `reviewed_on` as the owner states them. It records any disagreement as a `review`
     change, then reports and stops (§8, step 15).
   - Approving this plan, or a change in it, is not that review (D8, §0-8).
3. **Freeze approval (Gate 3).** The owner explicitly approves the completed review and the
   freeze.
4. **Frozen.**
   - A test pins the six v2 hashes, as for v1 (C10). Then the real-report determinism test is
     added (C8).
   - `DEFAULT_BENCHMARK` moves to `legal-v2`.
   - Only then are v2 metrics calculated and reported.
   - From then on, any edit makes `legal-v3`, as the guidelines require.

### 3.10 Compatibility

| | v1 (schema 1) | v2 (schema 2) |
|---|---|---|
| Today's P1 evaluator | loads | rejected: «schema_version must be 1» |
| The v2 evaluator | loads, with the `technical` scenario only; `--scenario natural` exits 2 with a clear message | loads, with `technical` or `natural`. Until v2 is frozen (§8, step 16), it is only loaded and resolved, never evaluated. |

The synthetic fixture stays at schema 1, and its expected metrics do not change. That is the
backward-compatibility test.

## 4. Query-scenario design

### 4.1 Scenarios

| Scenario | Field | What it measures |
|---|---|---|
| `technical` | `search_queries_it` | The v1 queries, unchanged. Most reuse an article's heading or definition, so they measure retrieval when the user already uses the corpus's own words. |
| `natural` | `search_queries_it_natural` | What a practitioner would type: the same information need, in their own words. They measure retrieval when the vocabulary differs. |

Both scenarios share the questions, judgments, splits, build and settings. Only the query list
differs.

### 4.2 Rules for writing natural queries

1. **Natural Italian, as a lawyer would type it** into a legal search tool.
   - The first query is the practitioner's shorthand («nozione di data breach», «istanza di
     accesso»).
   - The second describes the client's facts («smarrimento o accesso abusivo ai dati dei
     clienti»).
2. **Terms of art are allowed**, including common loanwords: data breach, DPO, DPIA,
   telemarketing. Copied headings and definitions are not.
3. **Never the answer.** A query must not contain a deadline, threshold or age that the
   question does not contain («72 ore», «250 dipendenti», «quattordici anni»).
4. **As many queries as the technical scenario:** two for q01–q20, one for q21–q24. The
   interleaving then gives both scenarios the same number of searches.
5. **Explicit citations stay explicit.** q16 and q17 name their article, as a lawyer would.
6. **Reviewed, written blind, then frozen.**
   - **Reviewed.** The owner reviews all 24 drafts, approving or editing each, before any search
     or pooling is run with them (Gate 1, §0-10).
   - **Written blind.** No search is run with them before that review, on either split.
   - **Frozen.** After the review the queries are frozen, and they are not edited after seeing
     what they retrieve. A change after the first run makes a new version.
   - This applies to the dev split too: tuning natural queries to the search would turn them
     back into technical ones.

### 4.3 The no-copying check

This automated check is only a guard; the owner's review is the real check. Before comparing,
text is lower-cased, apostrophes become spaces, and only letters and digits count. For each
question:

| Check | Rule |
|---|---|
| N1 | No 4-word sequence shared with the heading of an article graded 1 or 2 for the question (v2 grades). |
| N2 | No whole heading of 2 or 3 words («autorità di controllo», «diritto di opposizione», «liceità del trattamento»). One-word headings (Definizioni, Poteri) are exempt. |
| N3 | No 4-word sequence shared with the text of a judged point (the Art. 4 definitions). |
| N4 | No 4-word sequence shared with the question's technical queries, and no query equal to one of them. |
| N5 | Every number in a natural query appears in the question. |
| N6 | Each query passes `query_problem`, and there are as many as technical queries. |

Results, measured in memory against the build under the approved grades (q14 Art. 55 at 0):
- **Technical queries:** the queries of **19 of the 20 answerable questions** fail N1–N3 (all
  but q15).
- **Natural queries:**
  - **Drafts:** none of the 24 failed N1–N6.
  - **Gate 1 wording:** rerun on 2026-11-11, after the owner's two edits (q19, q20). **All 24
    questions pass all six checks**, the edited ones included. The per-question results are in
    the review checklist, `reviews/legal-v2-review-checklist.md`.
- One earlier draft for q04 («… comunicata al Garante una violazione dei dati») failed N1 and
  was rewritten before the owner's review.

### 4.4 Natural queries (approved at Gate 1 on 2026-11-11; never run)

| Q | Split | Natural queries |
|---|---|---|
| q01 | dev | «nozione di dato personale»; «informazioni che rendono riconoscibile una persona» |
| q02 | dev | «nozione di data breach»; «smarrimento o accesso abusivo ai dati dei clienti» |
| q03 | test | «requisiti di validità del consenso privacy»; «consenso privacy inserito nelle condizioni generali del contratto» |
| q04 | dev | «termine per la notifica del data breach al Garante»; «ritardo nella segnalazione di una fuga di dati all'autorità» |
| q05 | dev | «obbligo di informare gli interessati del data breach»; «quando avvisare i clienti di una fuga di dati» |
| q06 | test | «quando è obbligatoria la DPIA»; «trattamenti ad alto rischio che richiedono un'analisi preventiva» |
| q07 | dev | «obbligo di tenuta del registro dei trattamenti»; «esenzione dal registro per le piccole imprese» |
| q08 | dev | «obbligo di nomina del DPO»; «aziende ed enti tenuti ad avere un DPO» |
| q09 | test | «contenuto dell'informativa privacy al cliente»; «cosa indicare nell'informativa al momento della raccolta» |
| q10 | dev | «istanza di accesso ai propri dati personali»; «ottenere copia dei dati trattati dal titolare» |
| q11 | dev | «presupposti della richiesta di cancellazione dei dati»; «quando spetta il diritto all'oblio» |
| q12 | test | «portabilità dei dati verso un altro fornitore»; «esportare i dati del proprio account in un formato riutilizzabile» |
| q13 | dev | «opposizione dell'interessato al marketing»; «opporsi al trattamento basato sul legittimo interesse» |
| q14 | dev | «autorità di vigilanza privacy in Italia»; «chi vigila sul trattamento dei dati personali in Italia» |
| q15 | test | «poteri ispettivi del Garante privacy»; «provvedimenti che il Garante può adottare contro un'azienda» |
| q16 | dev | «art. 2-ter codice privacy»; «art. 2-ter base normativa dei trattamenti pubblici» |
| q17 | dev | «art. 9 GDPR dati sensibili»; «divieto di trattare dati sanitari e relative eccezioni» |
| q18 | test | «età minima per il consenso digitale del minore»; «iscrizione di un minorenne a un social network senza i genitori» |
| q19 | dev | «dati personali di un familiare defunto»; «chi può esercitare i diritti privacy dopo la morte di una persona» (edited at Gate 1) |
| q20 | dev | «quantificazione delle sanzioni privacy»; «criteri per stabilire l'importo di una sanzione privacy» (edited at Gate 1) |
| q21 | test | «IVA su fattura a cliente estero» |
| q22 | dev | «giusta causa di recesso dal rapporto di lavoro» |
| q23 | dev | «adempimenti per chi immette sul mercato sistemi di IA ad alto rischio» |
| q24 | test | «sanzioni del Garante al telemarketing nel 2025» |

- **On purpose,** some drafts use words the corpus does not use, such as «dati sensibili» and
  «fuga di dati». That vocabulary mismatch is what the scenario tests, so a lower BM25 score on
  this scenario is the expected finding, not a defect to tune away.
- **Gate 1 edits.** The owner replaced two second queries:

  | Question | Draft | Approved |
  |---|---|---|
  | q19 | «esercizio dei diritti privacy da parte degli eredi» | «chi può esercitare i diritti privacy dopo la morte di una persona» |
  | q20 | «procedimento sanzionatorio del Garante» | «criteri per stabilire l'importo di una sanzione privacy» |

  Both pass N1–N6 (§4.3). The other 22 drafts are approved unchanged. The queries are frozen in
  Phase 2 (§8, step 6).

### 4.5 Pooling the natural queries

**Why.** The v1 pool comes from the technical queries only. An article retrieved only by a
natural query would be unjudged, so it would count as not relevant and understate recall in
the natural scenario.

**What, in order, before v2 is frozen:**
1. **Owner review, then freeze.** The owner reviewed and approved all 24 queries at Gate 1, on
   2026-11-11 (§0-15). They are frozen at the start of Phase 2 (§4.2, rule 6). Nothing is
   searched before then.
2. **Check that the dense model is cached, without downloading anything.**
   - The model is `intfloat/multilingual-e5-small` at revision `614241f622f5`. Look for it in
     the local cache with `HF_HUB_OFFLINE=1` set, so no download is possible.
   - If it is not there, stop and ask the owner. The owner approved pooling only on that
     condition (§0-11), and BM25-only pooling is not pre-approved.
3. **Pool them the way v1 was pooled.** Record the lists in each row's `natural` object:

   | Retriever | Settings | Articles kept |
   |---|---|---|
   | BM25 | `rank_articles`, chunk depth 20 (not `evaluate` or `run`) | top 10 |
   | Dense | the cached model, offline; top 20 chunks mapped to articles | top 10 |
   | Hybrid | RRF with `BM25_TOP_K` 20, `DENSE_TOP_K` 20, `RRF_K` 60 | top 10 |

   This produces lists only; no metric is computed.
4. **Judge every newly pooled article under D1.**
   - Each judgment becomes a `natural_pool` change and stays a candidate.
   - The owner reviews them with the rest at Gate 2.

### 4.6 Reporting, and what may be compared

- **Before the freeze:** until v2 is reviewed and frozen (Gate 3, then §8 step 16), no v2
  metric is calculated or published, on either split.
- **One scenario per run, and one report per scenario.**
  - `retrieval.query_scenario` names the scenario, and each question's `searches` shows the
    queries used.
  - The `benchmark`, `corpus` and `code` sections of the two reports are identical.
- **After the freeze, allowed:** technical against natural, within v2. The test split is used
  only to report.
- **Never allowed:** v1 against v2. Their judgments differ (D1), so a difference between them is
  not an improvement.

## 5. Evaluator changes

D2 is the only decision that needs code. Today the evaluator has no notion of a query scenario,
and it reads only `search_queries_it`. D1 and D3–D8 are changes to data and documents.

The proposed changes to `src/provision_eval.py`:

| Item | Today | Proposed |
|---|---|---|
| Schema versions | `SCHEMA_VERSION = 1` | `SCHEMA_VERSIONS = (1, 2)`. The manifest check accepts either, and still rejects `true`. |
| Scenarios | none | `QUERY_SCENARIOS = ("technical", "natural")` and `DEFAULT_SCENARIO = "technical"`, read from `search_queries_it` and `search_queries_it_natural` |
| `Benchmark` | no schema field | gains `schema_version: int`, and a `query_scenarios` tuple (`("technical",)` for schema 1) |
| `Question` | `search_queries_it` | also `search_queries_it_natural: tuple[str, ...] = ()`, and a public `queries(scenario)` that raises `EvaluationDataError` for a scenario the benchmark lacks |
| `_load_questions` | one set of keys | the set of keys depends on the schema. Schema 2 requires the natural key and validates it like the technical one; schema 1 still rejects it as unknown. |
| `evaluate(…)` | ranks `q.search_queries_it` | `evaluate(benchmark, explorer, *, chunk_depth=…, scenario=DEFAULT_SCENARIO)` ranks `q.queries(scenario)` |
| `run(…)` | no scenario | `scenario=DEFAULT_SCENARIO`. The report records `retrieval.query_scenario`, `retrieval.query_field` and `benchmark.query_scenarios`. |
| Schema in the report | `"schema_version": SCHEMA_VERSION`, the module's constant | `benchmark.schema_version` is the benchmark's own. The constant would be wrong for one of the two schemas. |
| Report ID | `provision-retrieval-evaluation/1` | `provision-retrieval-evaluation/2`, because of the new keys |
| `format_summary` | no scenario | the header names the scenario |
| CLI | `--benchmark`, `--build-dir`, `--chunk-depth`, `--output`, `--json` | adds `--scenario {technical,natural}`, default `technical`. A scenario the benchmark lacks exits 2. |
| `DEFAULT_BENCHMARK` | `legal-v1` | **unchanged** through implementation and review. It moves to `legal-v2` only after the owner explicitly approves the completed review and the freeze (Gate 3), in a separate change. |

**What does not change:**
- `rank_articles`, the BM25 search and the merging rule;
- the metric functions, `RELEVANT_GRADE = 1` and the linear gains;
- `DEFAULT_CHUNK_DEPTH = 20`, and the depth `ask` uses (5);
- the resolution of judgments and the warnings;
- the exit codes 0, 1 and 2, and `BENCHMARK_FILES`;
- no private name is imported across modules, as the architecture test requires.

**Alternatives considered:**

| Alternative | For | Against | Verdict |
|---|---|---|---|
| A mapping `search_queries: {"technical": […], "natural": […]}` | cleaner if scenarios multiply | renames a key that v1, the fixture and the tests use | rejected for now |
| Two directories (`legal-v2-technical`, `legal-v2-natural`) | needs no code | duplicates 394 judgments that would have to stay identical; a report could not name its scenario | rejected |
| A fourth file, `queries.jsonl` | none over the chosen design | adds a hashed file and more loader code, for the same result | rejected |
| Both scenarios in one report | one run | doubles the report's shape, and makes it easy to mix the scenarios up | one scenario per run instead |

## 6. Test plan

- **Where:** the new data tests go in a new file, `tests/test_legal_benchmarks.py`. The
  evaluator tests stay in `tests/test_provision_eval.py`.
- **Without the build:** tests that need the recorded build skip when it is missing, as today.
- **No real metrics in tests:**
  - no test asserts, prints or records a metric of the real benchmark;
  - until v2 is frozen (§8, step 16, after Gate 3), no test calls `evaluate` or `run` on
    `legal-v2` at all;
  - C8 is added only after the freeze.

**A. v1 immutability**

| Test | What it checks |
|---|---|
| A1 | `test_legal_v1_files_are_unchanged`: exactly the five files, with the SHA-256 values of §3.8. |
| A2 | The four existing `legal_v1` tests use an explicit `LEGAL_V1` path. |
| A3 | v1 loads under the new evaluator as schema 1, with `query_scenarios == ("technical",)`. `--scenario natural` on v1 exits 2 and gives the reason, before any build is opened. `DEFAULT_BENCHMARK` is still `legal-v1`. A1 and A3 live in `tests/test_legal_benchmarks.py`. |

**B. The evaluator, on the synthetic fixture**
- **B1: backward compatibility.** The schema-1 fixture gives exactly the current `EXPECTED`
  metrics and rankings. All current tests pass, with two edits:
  - A2 (the path of the four v1 tests);
  - `test_the_manifest_is_checked`, whose invalid example was `schema_version` 2. Schema 2 is
    now valid, so the example becomes 3, and the message names both versions. This edit was
    found during implementation; the earlier version of this plan said A2 was the only edit.
- **B2: schema 2.** A copy of the fixture, written to `tmp_path` with natural queries, loads.
  Each of these is an error that names the file and line:
  - the natural key missing in schema 2;
  - the natural key present in schema 1;
  - an empty list, an English query or a non-string;
  - `schema_version` 3, or `true`.
- **B3: scenario selection.**
  - In the copy, one natural query is written to retrieve a different article.
  - The technical run uses only `search_queries_it`, and the natural run only the natural
    list, as each question's `searches` shows.
  - The natural metrics equal values computed by hand.
- **B4: reports.**
  - They record `query_scenario`, `query_field`, the benchmark's own `schema_version`, and the
    report ID `/2`.
  - Two runs of the same scenario give identical reports.
  - The two scenarios' reports have identical `benchmark`, `corpus` and `code` sections.
  - There is no timestamp and no absolute path (the existing check, extended).
- **B5: CLI.**
  - `--scenario natural` works.
  - An unknown scenario is rejected with exit 2.
  - The summary header names the scenario.

**C. The legal-v2 data** (`tests/test_legal_benchmarks.py`)
- **C1: schema and references.**
  - v2 loads as schema 2, kind `real`, version `"2"`.
  - Its 24 questions have v1's IDs, splits, question texts and `search_queries_it`, unchanged.
  - It resolves on the recorded build. The count is of distinct (question, instrument,
    article). q17 now has three points of one article, so today's test, which expects one
    article per record, would fail on v2.
- **C2: v2 is v1 plus `changes.jsonl`.**
  - Applying the changes to v1, leaving provenance aside, gives exactly v2's questions and
    judgments, and nothing unlisted differs.
  - Each `change_id` is unique, with a valid `decision` and `basis`.
  - `owner_decision` is non-empty for every change except those §3.5 leaves null.
  - c14's line carries both the owner's decision (grade 0) and a `reason`.
- **C3: grade consistency** (table-driven).
  - Each record of §2.1–2.3 has its v2 grade.
  - The grades the owner fixed hold:

    | Question | Judgment | Grade | Source |
    |---|---|---|---|
    | q03 | G Art. 9 | 0 | D5 |
    | q04 | G Art. 34 | 0 | D3 |
    | q04 | G Art. 55 | 1 | §0-3 (c11) |
    | q05 | G Art. 33 | 0 | D3 |
    | q05 | G Art. 4 point 12 | 1 | §0-4 (c12) |
    | q11 | G Art. 12 | 1 | D3 |
    | q13 | G Art. 12 | 1 | §0-5 (c13) |
    | q14 | G Art. 55 | 0 | §0-6 (c14) |
    | q17 | C Art. 107 | 0 | D5 |
    | q18 | G Art. 8 | 2 | D5 |
    | q20 | C Art. 167 | 0 | D3 |
    | q20 | G Art. 84 | 0 | D3 |
    | q03 | G Art. 8, C Art. 2-quinquies | 1 | §0-12 (U4) |
    | q17 | C Arts. 2-sexies, 2-septies | 1 | §0-13 (U5) |

  - Rule 4: G Art. 12 is grade 1 in q10–q13, and q04 and q05 give G Art. 4 point 12 the same
    grade.
  - No rationale of a GDPR Art. 55 judgment contains «Garante» (§0-6).
  - `answerable` questions have a grade 2, and the others have none.
  - The U4 and U5 records keep grade 1, with no change line (§0-12, §0-13).
- **C4: pool.** v2 judges exactly the union of its technical lists, its natural lists and
  `judge_added`. That union includes q14 Art. 55.
- **C5: scenario isolation.**
  - Every question has natural queries, as many as technical ones, and none equals a technical
    one.
  - Checks N4 and N5 hold.
  - Checks N1–N3 hold on the recorded build (skipped without it).
- **C6: provenance and review status.**
  - Every record is `candidate`, with null `reviewed_by` and `reviewed_on`, including every
    record whose change the owner approved in §0.
  - Unchanged judgments carry v1's provenance, unchanged.
  - Changed, added and natural-pool records carry the v2 `drafted_by`.
  - After Gate 2, the test lists exactly the records the owner approved, and no other record
    may be `owner_reviewed`.
  - No record is ever `expert_reviewed` unless the owner names an expert.
- **C7: D6.**
  - Every rationale of a grade-1 or grade-2 judgment on `it-dlgs-2003-196` starts «In the
    transcription:».
  - No rationale calls the transcription verified, current or in force: none contains
    «verified», «current law», «vigente» or «is in force».
  - The approved c23 wording «not a statement of the law in force» passes, because it denies
    the claim. The earlier version of this check, which banned «in force» outright, would have
    failed on c23.
- **C8 (after the freeze, §8 step 17): deterministic real reports.** For each scenario, two runs
  of `run(LEGAL_V2, scenario=…)` give equal reports. The test checks equality only; it asserts
  and prints no value.
- **C9:** the v1 hashes quoted in `legal-v2/README.md` equal those of the v1 files.
- **C10 (the freeze itself, §8 step 16):** `test_legal_v2_files_are_unchanged` pins the six
  v2 hashes.

**D. The whole suite.** It still passes: 1836 passed and 5 skipped before this work, plus the
new tests. That includes the architecture test (no private imports across modules).

## 7. Risks and unresolved decisions

### 7.1 Risks

| Risk | Effect | Mitigation |
|---|---|---|
| Natural queries retrieve unjudged articles | Recall in the natural scenario is understated. | Pool them before freezing (§4.5). The report warns about unjudged articles in the top 10. |
| Natural queries are tuned to the search | The scenario stops measuring vocabulary mismatch. | The owner reviewed them first (Gate 1); they are frozen before pooling and never edited after a run (§4.2). |
| The no-copying check is only lexical | It passes close paraphrases and catches nothing subtler. | It is a guard; the owner reviews the queries at Gate 1. |
| v2 metrics computed before the freeze | Results exist for a benchmark not yet reviewed. | No `evaluate` or `run` on v2 until it is frozen (§8, step 16). Pooling uses `rank_articles` only. C8 is added after the freeze. `DEFAULT_BENCHMARK` stays `legal-v1`. |
| A plan approval read as a review | Records marked `owner_reviewed` without a record-level review. | D8. `owner_decision` is kept apart from `review_status` (§3.5). Test C6. Gate 2 is a separate step. |
| Git rewrites line endings | The v1 hashes change, and reports differ across platforms. | `-text` rules at Gate 4, before any `git add` under `data/evaluation/` (§3.8, §0-17). |
| v1 is untracked | A `git clean` deletes it. | Commit it only with a separate Git approval (U12). |
| v1 and v2 compared as before and after | A grading change is read as a retrieval change. | The README and the guidelines say they are not comparable. Reports carry the version and the hashes. |
| D1 still leaves borderline cases | Grade 1 becomes inconsistent again. | The five working rules (§2.0) go into the guidelines. The two residual cases were decided by the owner (U4, U5). |
| Art. 55 read as naming the Garante | A false claim in the data. | The c11 and c14 wording; the C3 check (§0-6). |
| The transcription is read as law | An overclaim. | The D6 wording and test C7. No change to the corpus or provenance. |
| Article-level scoring | q01 and q02 both score GDPR Art. 4 alone; points never count separately. | Already a stated limitation. Fine-grained provisions are later roadmap work. |
| 24 questions, 8 in the test split | Means are unstable, and differences between scenarios may be noise. | Report counts beside the means. There are no confidence intervals yet (TD-018). |
| The report ID moves to `/2` | Breaks anything that reads `/1` reports. | Nothing in the repository does; the tests are updated. |
| The dense model is not cached | Pooling cannot proceed as approved. | Stop and ask the owner. Nothing is downloaded, and BM25-only pooling needs the owner's approval. |
| The owner's review is not yet scheduled | v2 stays open, and all candidates. | The README says so, and nothing is reported from v2 until it is frozen. |

### 7.2 Decisions

| # | Decision | Status |
|---|---|---|
| U1 | The grade of q04 GDPR Art. 55 (c11) | **Decided:** 1 (§0-3). |
| U2 | q14 GDPR Art. 55 (c14) | **Decided:** kept at grade 0, with the owner's decision and rationale recorded in `changes.jsonl` (§0-6). |
| U3 | The derived changes c02, c03, c04, c06, c08, c09, c12, c13 and c15–c18 | **Decided:** approved (§0-2, §0-4, §0-5, §0-7). |
| U4 | q03 GDPR Art. 8 and Code Art. 2-quinquies | **Decided:** keep 1 (§0-12). |
| U5 | q17 Code Arts. 2-sexies and 2-septies | **Decided:** keep 1 (§0-13). |
| U6 | The breach definition in q04 and q05 | **Decided:** 1 in both. c12 was approved at 1 (§0-4), and q04 keeps its v1 grade 1. |
| U7 | Categories | **Decided:** q03 `obligation`, q19 `rights` (§0-8, D7). |
| U8 | The natural queries and their pool | **Decided** (§0-10, §0-11). The 24 queries were approved at Gate 1 (§0-15). **Pending:** if the dense model is not cached, whether to pool with BM25 only. |
| U9 | `DEFAULT_BENCHMARK` | **Decided:** `legal-v1` throughout implementation and review. It moves to `legal-v2` only after the owner explicitly approves the completed review and the freeze (Gate 3). |
| U10 | When v2 is frozen | **Decided:** only after the human review (Gate 2) and the owner's explicit approval of the freeze (Gate 3). |
| U11 | The D6 wording on the 15 other Code judgments (c25–c39) | **Decided:** approved (§0-9). |
| U12 | Any Git operation: staging or committing `legal-v1`, `legal-v2`, `.gitattributes` or any other file; pushing; merging. This includes adding the `-text` rules to `.gitattributes`. | **Not authorized.** Deferred to a separate Git approval (Gate 4, §0-17). |
| U13 | The wording of c20 (q04 GDPR Art. 34) and c24 (q20 Code Art. 167) | **Decided:** approved; the grades are unchanged (§0-14). |
| U14 | Phase 2 | **Decided:** authorized after the Phase 1 report, and implemented on 2026-11-11. The dense model was cached, so U8's fallback question did not arise. |
| U15 | Gate 2 | **Decided:** approved and applied on 2026-11-12 (§0, decisions 18–22). |
| U16 | Gate 3 | **Decided:** authorized by the owner and carried out on 2026-11-12. legal-v2 is frozen (C10 pins its six files) and is the default benchmark. The first technical and natural results are in [`legal-v2-first-evaluation.md`](legal-v2-first-evaluation.md). |

This plan does not decide, and the implementation must never infer, who reviews, under what
name, or on what date (D8). The owner states these at Gate 2.

## 8. Ordered implementation steps

Each step ends with the full test suite passing and the v1 hashes checked.

**Throughout every phase:**
- `DEFAULT_BENCHMARK` is `legal-v1` until step 18;
- no v2 metric is calculated before v2 is frozen (step 16);
- `.gitattributes` is not modified before Gate 4 (§0-17);
- no Git staging, commit, push or merge, and no other Git write.

**Phase 1: no search, no metric. Authorized (§0-16).**

0. **Preflight.**
   - Record the v1 hashes and the list of untracked files in the scratchpad.
   - Record HEAD and the stash list (`f554c75`), using read-only Git commands only.
   - Confirm that `readme-diff-review.txt` is untouched.
   - The owner's answers to U4, U5 and U13 are in §0 (decisions 12–14).
1. **Line endings: moved to Gate 4 (§0-17).** `.gitattributes` is not modified in Phase 1 or
   Phase 2.
2. **v1 tests.** Add A1, and point the four v1 tests at v1 explicitly (A2). These must pass
   before anything else changes.
3. **Evaluator.** Add schema 2 and the scenarios (§5), with tests A3 and B1–B5, on synthetic
   data only. `DEFAULT_BENCHMARK` is unchanged.
4. **Guidelines.** Update `docs/evaluation/guidelines.md` with:
   - the D1 grade definitions and the five working rules, with examples from the synthetic act
     only, never from real law;
   - schema 2 and the scenarios;
   - the rules for natural queries;
   - the D6 statement;
   - a note that v1 used the earlier wording of grade 1 and is not comparable with v2;
   - the freeze rule and the gates.
5. **Review checklist, part 1.** Create `docs/evaluation/reviews/legal-v2-review-checklist.md`.
   - It lists the 24 natural queries of §4.4 with their N1–N6 results.
   - It records the owner's Gate 1 decision, received before this step (§0-15).
   - No search is run.

   **Stop, and report Phase 1.**

**Gate 1: the owner's review of the natural queries.** Done on 2026-11-11 (§0-15): 22 drafts
approved unchanged, and q19 and q20 edited. Nothing has been searched or pooled.

**Phase 2: searches for pooling only; no metric.** It needs Gate 1 (done) and the owner's
explicit approval after the Phase 1 report (§0-16, U14). It is not yet authorized.

6. **Freeze the natural queries.** Record the approved wording in c43–c66, with their
   `owner_decision`. Any edited query must pass N1–N6 again.
7. **Dense model check.** Look for the cached model offline (`HF_HUB_OFFLINE=1`). If it is
   missing, stop and ask the owner; download nothing.
8. **Natural pool.** Run BM25 (`rank_articles`), dense and hybrid for all 24 questions, and
   record the lists only. No `evaluate` or `run` call, and no metric.
9. **Judge the newly pooled articles** under D1, as `natural_pool` changes, numbered after
   c66 and any U4 or U5 line.
10. **Generate v2.**
    - The scratchpad script reads v1 read-only and applies `changes.jsonl`.
    - It writes the six files of `legal-v2/` with LF endings.
    - Then check that the v1 hashes have not changed.
11. **v2 tests.** Add C1–C7 and C9; none of them evaluates v2.
12. **Pre-freeze checks, without metrics.**
    - v2 loads and resolves, and C4 holds.
    - With `rank_articles` alone, the top 10 of every question under both scenarios is judged.
13. **Documents.**
    - Write the v2 README.
    - Complete the review checklist, part 2. It covers every change ID, in this order: the open
      items U4, U5 and U13 first, then c01–c42, then the natural-pool judgments.
    - Add one paragraph to `README.md` and one line to `docs/ROADMAP.md`: P2.2, legal-v2, two
      scenarios, all candidates, `legal-v1` still the default. No v2 metric is reported.
14. **Report and stop.**
    - Report the files changed, the tests run, the Git status (read-only) and the v1 hashes.
    - The untracked files and stash `f554c75` are untouched, and nothing is staged or
      committed.

**Gate 2: the owner's review of the records.** The owner names the records they approve, and
the name and date to record.

15. **Apply the review.**
    - Set `owner_reviewed`, with the stated name and date, on exactly the records the owner
      named.
    - Record the owner's disagreements as `review` changes in `changes.jsonl`.
    - Update C6 to list the approved records, and run the full suite. No metric is calculated.
    - Report and stop.

    **Done on 2026-11-12** (§0, third round).
    - **Data:** review lines c332–c348, and 28 records `owner_reviewed`.
    - **Tests:** C6 now lists the reviewed records, in `GATE2_REVIEWED`.

**Gate 3: the owner explicitly approves the completed review and the freeze.**

**Phase 3: after Gate 3**

16. **Freeze.** Add C10, which pins the six v2 hashes. From here on v2 is frozen, and any edit
    makes `legal-v3`.
17. **Check the freeze.** Add C8 (deterministic real reports, equality only). Then run the full
    suite and check the v1 and v2 hashes.
18. **Move the default.** Set `DEFAULT_BENCHMARK` to `legal-v2`. Update A3 and the documents
    that name the default benchmark.
19. **First v2 metrics.** Calculate the technical and natural metrics and report them as §4.6
    allows.

**Phase 3 done on 2026-11-12** (U16).

| Step | What was done |
|---|---|
| 16 | C10 pins the six v2 hashes. |
| 17 | C8 compares two whole reports per scenario. The full suite passed. |
| 18 | `DEFAULT_BENCHMARK` is `legal-v2`. The v1 tests stay pinned to `LEGAL_V1`. |
| 19 | The results are in [`legal-v2-first-evaluation.md`](legal-v2-first-evaluation.md): dev for diagnosis, test as held-out means only. |

**The v2 README.** It is one of the six pinned files, so it still carries its pre-freeze status
lines. The freeze is recorded here, in the guidelines and in the results document.

**Gate 4 (separate, not authorized): Git.** This needs the owner's separate Git approval
(U12). It covers:
- adding the two `-text` rules to `.gitattributes` (§3.8, §0-17), first, before any `git add`
  under `data/evaluation/`;
- then staging and committing `legal-v1`, `legal-v2`, `.gitattributes`, the code and the
  documents;
- any push or merge.

## 9. Files

**Created by the implementation:**

| File | When |
|---|---|
| `docs/evaluation/reviews/legal-v2-review-checklist.md` | Phase 1; completed in Phase 2 |
| `data/evaluation/legal-v2/benchmark.json` | Phase 2 |
| `data/evaluation/legal-v2/questions.jsonl` | Phase 2 |
| `data/evaluation/legal-v2/judgments.jsonl` | Phase 2 |
| `data/evaluation/legal-v2/pool.jsonl` | Phase 2 |
| `data/evaluation/legal-v2/changes.jsonl` | Phase 2 |
| `data/evaluation/legal-v2/README.md` | Phase 2 |
| `tests/test_legal_benchmarks.py` | Phase 1 (A1, A3); C tests in Phase 2; C8 and C10 in Phase 3 |

**Modified in Phase 1:**

| File | Change |
|---|---|
| `src/provision_eval.py` | schema 2, the scenarios, the report fields and the CLI option; not `DEFAULT_BENCHMARK` |
| `tests/test_provision_eval.py` | the v1 tests pinned to v1; `test_the_manifest_is_checked` (schema 3); the scenario tests |
| `docs/evaluation/guidelines.md` | as in step 4 |
| `docs/evaluation/legal-v2-implementation-plan.md` | the owner's decisions (§0) |

**Modified in Phase 2:**

| File | Change |
|---|---|
| `README.md` | one paragraph. The file already has uncommitted M4 edits, which stay. |
| `docs/ROADMAP.md` | one line. It also has uncommitted M4 edits, which stay. |

**Modified only at Gate 4 (not authorized):** `.gitattributes`, two `-text` rules (§0-17).

**Modified between Gate 2 and Gate 3 (step 15):**
- `data/evaluation/legal-v2/judgments.jsonl`, `questions.jsonl` and `changes.jsonl`: the review
  statuses and any `review` changes;
- `tests/test_legal_benchmarks.py`: C6 lists the approved records.

**Modified in Phase 3 only (after Gate 3):**
- `tests/test_legal_benchmarks.py`: C10, then C8;
- `src/provision_eval.py`: `DEFAULT_BENCHMARK` moves to `legal-v2`;
- `tests/test_legal_benchmarks.py`: A3 expects the new default;
- the documents that name the default benchmark.

**Kept outside the repository:** the v2 generator and the natural-pool script, in the session
scratchpad.

**Not touched:**
- the five files of `data/evaluation/legal-v1/`;
- the synthetic fixture (its schema-2 variant is built in `tmp_path`);
- the corpus, registry, source archives, builds, provenance and review ledger;
- retrieval, ranking, the BM25 settings, the merging rules and their defaults;
- `docs/evaluation/reviews/legal-v1-human-review.md`;
- `readme-diff-review.txt`, the other untracked documents, and stash `f554c75`.

**Created by the planning tasks:** this file only. It was revised twice on 2026-11-11, to
record the owner's decisions.
