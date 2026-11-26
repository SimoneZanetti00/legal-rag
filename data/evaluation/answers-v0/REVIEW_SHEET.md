# Benchmark v0 (end-to-end answers): review sheet

> **Partly reviewed.** a01–a13 and their rows are `owner_reviewed` (2026-11-18); a14–a25 are
> still `candidate`.
>
> - **Drafted** by Claude (AI assistant, claude.ai) on 2026-11-13.
> - **Consolidated** by Claude Code (AI assistant) on 2026-11-16, applying the owner's
>   corrections listed under «Changes from the draft».
> - **Status:** a01–a13 and their rows were reviewed by the owner on 2026-11-18, with a second
>   opinion from an AI assistant (Claude, claude.ai) on each row; the decisions are the
>   owner's (see «Owner review (2026-11-18)»). a14–a25 are `candidate`: every expected
>   provision there is still a legal judgment to be checked and signed off by the owner.
> - **Files:** `benchmark.json` (the manifest), `questions.jsonl`, `expectations.jsonl`. The table
>   below is kept identical to the two JSONL files by `tests/test_answer_benchmark.py`.
> - **Split `candidate`:** a23–a25 were asked on the live demo and added on 2026-11-26 with the
>   owner's draft expectations (rows 83–90). They are in neither dev nor test, so the dev and test
>   figures do not change.
> - **Code:** `src/answer_benchmark.py` checks the files and computes the metrics. It does not run
>   the pipeline; no runner exists yet.
> - **Build:** `build-f76ff6031f2fc82c4852f0a2bde27807`, confirmed by the owner on 2026-11-16.
>   The draft named no build; this is the recorded build the expectations were checked against
>   in the 2026-11-13 audit, where all provisions and units were found.

## Review table

Roles: **core** = a complete answer must rest on it; **supporting** = useful, not required. The
role `must_not_cite` is defined but not used yet.

«direct answer» in the outcome column is `expected_direct_answer`: the values accepted as the
direct answer of a yes/no or premise question (yes, no, partly or cannot_establish; «or» separates
two accepted values). It is absent for the other questions, which expect none.

A unit is written «par. N» (paragraph «N.»), «point N» (point «N)», e.g. the definitions of GDPR
Art. 4) or «letter x» (letter «x)» inside the paragraph or point). No unit means the whole article.

| ID | Split | Category | Expected outcome | Question | Core | Supporting | ✔ / correction |
|---|---|---|---|---|---|---|---|
| a01 | dev | breach | answer | When is a personal data breach required to be notified to the Italian Data Protection Authority? | GDPR 33 (par. 1) | GDPR 55 (par. 1), Codice 2-bis, GDPR 4 (point 12), GDPR 33 (par. 2), GDPR 34 | ✔ owner_reviewed, 2026-11-18 |
| a02 | dev | definition | answer | Che cos'è una violazione dei dati personali? | GDPR 4 (point 12) | — | ✔ owner_reviewed, 2026-11-18 |
| a03 | dev | breach | answer | Quando il titolare deve comunicare una violazione dei dati personali agli interessati? | GDPR 34 (par. 1), GDPR 34 (par. 3) | GDPR 33, GDPR 34 (par. 4) | ✔ owner_reviewed, 2026-11-18 |
| a04 | dev | authority | answer | Quale autorità di controllo è competente in Italia? | Codice 2-bis | GDPR 51 (par. 1), Codice 153, GDPR 55 | ✔ owner_reviewed, 2026-11-18 |
| a05 | dev | overview | answer | What are the main principles governing the processing of personal data under the GDPR? | GDPR 5 (par. 1), GDPR 5 (par. 2) | — | ✔ owner_reviewed, 2026-11-18 |
| a06 | dev | overview | answer | What rights do individuals have regarding their personal data under the GDPR? | GDPR 15, GDPR 16, GDPR 17, GDPR 18, GDPR 20, GDPR 21, GDPR 22 | GDPR 12, GDPR 13, GDPR 14, GDPR 19, GDPR 77, GDPR 79, GDPR 82, GDPR 7 (par. 3) | ✔ owner_reviewed, 2026-11-18 |
| a07 | dev | overview | answer | What are the main obligations of a data controller under the GDPR? | GDPR 5 (par. 2), GDPR 24, GDPR 25, GDPR 30, GDPR 32, GDPR 33, GDPR 34, GDPR 35, GDPR 37 | GDPR 26, GDPR 28, GDPR 12, GDPR 13, GDPR 14 | ✔ owner_reviewed, 2026-11-18 |
| a08 | dev | lawfulness | answer; direct answer: yes | Can a company process personal data without the consent of the data subject? | GDPR 6 (par. 1) | GDPR 9 (par. 2), GDPR 10, GDPR 7, GDPR 21 | ✔ owner_reviewed, 2026-11-18 |
| a09 | dev | out_of_scope | abstain (out_of_scope) | What are the legal requirements for establishing a company in Germany? | — | — | ✔ owner_reviewed, 2026-11-18 |
| a10 | dev | breach | answer | Entro quanto tempo va notificata una violazione dei dati personali al Garante? | GDPR 33 (par. 1) | Codice 2-bis | ✔ owner_reviewed, 2026-11-18 |
| a11 | dev | false_premise | answer; direct answer: no | Il responsabile del trattamento deve notificare la violazione al Garante? | GDPR 33 (par. 2) | GDPR 33 (par. 1), GDPR 28 (par. 3, letter f) | ✔ owner_reviewed, 2026-11-18 |
| a12 | dev | false_premise | answer; direct answer: no | Il GDPR prevede un termine di 96 ore per notificare una violazione dei dati personali? | GDPR 33 (par. 1) | — | ✔ owner_reviewed, 2026-11-18 |
| a13 | test | definition | answer | Che cos'è un dato personale secondo il GDPR? | GDPR 4 (point 1) | — | ✔ owner_reviewed, 2026-11-18 |
| a14 | test | obligations | answer | Quando è obbligatoria una valutazione d'impatto sulla protezione dei dati? | GDPR 35 (par. 1), GDPR 35 (par. 3) | GDPR 35 (par. 4), GDPR 36 | |
| a15 | test | obligations | answer | Quando un'azienda deve designare un responsabile della protezione dei dati (DPO)? | GDPR 37 (par. 1) | GDPR 38, GDPR 39 | |
| a16 | test | rights | answer; direct answer: yes or partly | Posso chiedere a un'azienda di cancellare i miei dati? In quali casi? | GDPR 17 (par. 1), GDPR 17 (par. 3) | GDPR 12 (par. 3) | |
| a17 | test | italian_specific | answer | A partire da quale età un minore può prestare da solo il consenso ai servizi della società dell'informazione in Italia? | GDPR 8 (par. 1), Codice 2-quinquies | — | |
| a18 | test | historical | answer_limited | Qual era la disciplina applicabile alla notifica di una violazione dei dati personali avvenuta nel 2017? | GDPR 99 (par. 2) | — | |
| a19 | test | out_of_scope | abstain (out_of_scope) | Quali sono i requisiti per il licenziamento per giusta causa in Italia? | — | — | |
| a20 | test | transfers | answer; direct answer: yes or partly | Si possono trasferire dati personali verso un paese terzo senza una decisione di adeguatezza? | GDPR 46, GDPR 49 | GDPR 45, GDPR 44, GDPR 47 | |
| a21 | test | sanctions | answer | Qual è la sanzione massima per la violazione dell'obbligo di notificare una violazione dei dati personali? | GDPR 83 (par. 4) | GDPR 83 (par. 2) | |
| a22 | test | italian_specific | answer | Come si presenta un reclamo al Garante e cosa prevede il Codice privacy? | GDPR 77, Codice 141, Codice 142 | Codice 143 | |
| a23 | candidate | italian_specific | answer | Qual è l'età minima per il consenso del minore ai servizi della società dell'informazione in Italia? | Codice 2-quinquies (par. 1) | GDPR 8 (par. 1) | |
| a24 | candidate | false_premise | answer; direct answer: no | Is it true that every company with more than 250 employees must appoint a DPO? | GDPR 37 (par. 1) | GDPR 30 (par. 5), GDPR 37 (par. 4) | |
| a25 | candidate | rights | answer; direct answer: no | Il diritto alla portabilità dei dati si applica anche ai trattamenti basati sul legittimo interesse? | GDPR 20 (par. 1) | GDPR 6 (par. 1, letter f), GDPR 21 (par. 1) | |

**How to record a review.** In the record's `provenance`:
- set `review_status` to `owner_reviewed` (or `expert_reviewed`), and fill in `reviewed_by` and
  `reviewed_on`;
- if you are unsure about a row, leave it `candidate` and say why in this sheet.

A question is scored only when the question and all its rows are reviewed.

## Changes from the draft

The draft folder (`banchmark/v0-draft/`, the downloaded draft files) was deleted on 2026-11-16 at the owner's request. IDs map one for one: `aNN` is draft `qNN`.

| # | Change | Reason |
|---|---|---|
| 1 | Moved to `data/evaluation/answers-v0/`, without the download suffixes « (1)» | The project's place for benchmarks, next to legal-v1 and legal-v2 |
| 2 | `benchmark.json` added | A manifest, as in legal-v2 |
| 3 | IDs `q01`–`q22` became `a01`–`a22` | legal-v1 and legal-v2 use q01–q24 for different questions |
| 4 | Provenance is legal-v2's object on every question and row (`drafted_by`, `drafted_on`, `review_status`, `reviewed_by`, `reviewed_on`); draft «pending» became `candidate` | Questions can now be reviewed too; statuses are the project's |
| 5 | Units are objects `{"paragraph", "point", "letter"}` | Machine-checkable; a letter can be named, e.g. GDPR 6(1)(b) as `{"paragraph": "1", "letter": "b"}` |
| 6 | `expected_reason` holds a pipeline reason code only; explanations moved to `notes` | `outside_source_coverage` is not a code the pipeline produces |
| 7 | **a18**: `answer_limited`, GDPR Art. 99(2) core (new row) | The corpus states the GDPR applies from 25 May 2018, so a correct answer can say it did not govern a 2017 breach; it cannot state the regime then in force, which is not in the corpus |
| 8 | **a22**: Code Art. 142 supporting → core; Code Art. 143 supporting (new row); Code Art. 141 stays core | Art. 142 («Proposizione del reclamo») says how to lodge the complaint; Art. 141 gives the route, by reference to GDPR Art. 77; Art. 143 says how it is decided |
| 9 | **a01**: Code Art. 2-bis core → supporting; GDPR Art. 55(1) core → supporting | Consistency with a10, where Art. 2-bis was already supporting: both questions name the authority, and when notification is due is answered by GDPR Art. 33(1). Confirmed by the owner on 2026-11-16. |
| 10 | **a06**: GDPR Art. 7(3) supporting (new row) | The right to withdraw consent, where consent is the legal basis (text verified in the corpus) |
| 11 | **a11**: GDPR Art. 28(3)(f) supporting (new row) | The processor assists the controller with Arts. 32–36, breach notification included (text verified in the corpus: «assista il titolare … articoli da 32 a 36») |
| 12 | **a14**: the Art. 35(4) rationale says the Garante's own list is not in the corpus | The list is a measure of the Garante, outside the corpus |
| 13 | Privacy Code rationales: «check in the transcription» replaced by a standing caveat | Each Code row was checked in the stored transcription in the 2026-11-13 audit; the transcription itself remains unverified (see «Caveats») |
| 14 | Time-sensitive questions gained `verified_by` and `verified_on`, both null | For the next person who re-checks them; `valid_as_of` and `basis` are kept as drafted |
| 15 | **a07**: GDPR Art. 34 supporting → core; GDPR Arts. 13 and 14 supporting (new rows) | The owner's criterion for a07 (2026-11-16) makes conditional obligations core like general ones, so Art. 34 joins Art. 33. The question does not require exhaustive coverage, so the information duties sit with their modalities (Art. 12) as supporting. See «Core in overview questions» |

## Criteria for core and supporting

- **Single-provision questions:** core = the provisions whose text answers the question; supporting = provisions an answer may use for context (definitions, related duties, procedure).
- **Units.** A unit narrows a row when only part of a long article answers the question (e.g. GDPR 17(1) and 17(3)). A row with no unit means the article as a whole.

**Core in overview questions (a05, a06, a07).** An overview question («the main principles»,
«what rights», «the main obligations») has no single answering provision. The criterion proposed
for v0: **core = the provisions that state, in general terms, each item the question asks to
list**. Provisions that only qualify, condition or proceduralise those items are supporting.

- **a05:** GDPR Art. 5(1) and 5(2) state the principles. Consistent.
- **a06:** the rights of Chapter III that the data subject exercises (Arts. 15–18, 20–22) are core.
  - **Information duties** (Arts. 12–14) are supporting (confirmed by the owner on 2026-11-16): they are the controller's duties through which the data subject is informed, not rights the data subject exercises.
  - Art. 19 is a controller duty, and Arts. 77, 79, 82 are remedies.
  - **Art. 7(3)** (withdrawing consent) is supporting, because it exists only where consent is the legal basis.
- **a07** (criterion decided by the owner on 2026-11-16): core = accountability and the controller's main obligations, whether they bind every controller or are triggered by a condition.
  - **Not exhaustive.** This v0 overview question does not require coverage of every controller obligation. Core is the central set a sound overview must name, not a complete list of the controller's duties.
  - **General:** Arts. 5(2), 24, 25, 30, 32.
  - **Conditional:** Art. 33 (a breach), Art. 34 (a breach likely to result in a high risk to data subjects), Art. 35 (likely high risk), Art. 37 (the listed cases).
  - **Supporting:** the information duties (Arts. 12–14), which an answer may name but need not; Arts. 26 and 28, which govern how the controller's responsibility (Art. 24) is shared with joint controllers or delegated to processors.
  - **Not listed:** other obligations (e.g. Arts. 27, 31, 36) are neither required nor penalised. If cited, they appear as unlisted citations, a diagnostic.
  - **Corrections:** Art. 34 moved to core, since it is conditional like Art. 33. Arts. 13 and 14 were added as supporting, next to Art. 12.
  - **Ceiling:** with 9 core rows and at most 5 evidence items per answer, a07's evidence and citation recall cannot exceed 5/9 (see «Limits of the retrieval metrics»).

## Scoring rules (implemented in `src/answer_benchmark.py`)

**Three metrics per expected row,** each reported for core rows and, separately, for supporting rows:

| Metric | A row counts when |
|---|---|
| **Candidate recall** | Its article is among the recorded candidates of the result: the evidence items and the candidates dropped by the evidence limits. Article level, units ignored. |
| **Evidence recall** | Its unit's text is inside an evidence item sent to the model. For a whole-article row: the article is in the evidence. Whether the item was whole, a point or an excerpt is reported. |
| **Citation recall** | A surviving claim quotes text inside its unit. For a whole-article row: anywhere in the article. Quotations are compared in the shared normalised form. |

**Main score.** It is the three core recalls, averaged over questions, each question counting
once. **Supporting recall is reported apart** and never enters the main score.

**Per question:**
- the **exact outcome match** (`answer`, `answer_limited` and `abstain` are distinct);
- **whether the system abstained**, reported separately;
- for an expected abstention, the **reason match**;
- **unlisted citations**: provisions cited but listed in no row. A diagnostic, not a penalty. Citation precision is not a v0 metric.

**Eligibility:**
- Only questions whose record and all rows are `owner_reviewed` or `expert_reviewed` are scored.
- The others are listed as excluded, with no metrics. With `include_unreviewed`, their metrics
  appear apart, labelled `unreviewed`, never in the summary. Pending or uncertain rows are never
  scored silently.

**Time-sensitive questions** (a01, a10, a12):
- reported apart unless someone re-verified them (`verified_by`, `verified_on`) within `freshness_days` of the run date. The window counts from `verified_on`; `valid_as_of` records the date the drafted basis describes;
- the default window is **30 days** (`DEFAULT_FRESHNESS_DAYS`). `score(freshness_days=…)` overrides it, and `None` means no window, so they are always apart;
- an unverified question is apart under any window. a01, a10 and a12 are unverified, so they stay apart until the Digital Omnibus status is re-checked and recorded.

## Human legal review of an answer

One record per reviewed answer, checked by `check_legal_review()`. **No record exists yet.**

| Field | Content |
|---|---|
| `query_id` | the question (`aNN`) |
| `run_id` | the run that produced the answer |
| `answer_sha256` | the SHA-256 of the answer reviewed (`answer_sha256()`: canonical JSON of the result) |
| `reviewer`, `review_date` | the person, and the date (`YYYY-MM-DD`, not in the future) |
| `verdict` | `correct`, `partial`, `incorrect` or `unsafe` |
| `error_type` | null for a correct answer; otherwise `wrong_law`, `missing_condition`, `premise_accepted`, `temporal_error` or `other` |
| `notes` | free text; required with `other` |

## Caveats

- **Privacy Code rows** (a01, a04, a10, a17, a22, a23) rest on a user transcription of the Code, not verified against an official text. Its reference date is unverified.
- **Digital Omnibus.** a01, a10 and a12 carry `valid_as_of` 2026-11-08, the date of the M1 record, and their `basis` as drafted.
  - Their status has **not** been re-verified for this benchmark. The procedure number and status quoted in `basis` come from the draft and were not checked in this repository.
  - Whether the proposal amends other provisions used as core here (e.g. GDPR 4(1) in a13, Art. 35 in a14, Art. 33 in a07 and a11) has not been checked.
  - The status stays unverified by the owner's decision of 2026-11-16, and nothing here presents it as current. Until `verified_by` and `verified_on` are filled in, a01, a10 and a12 are reported apart from the main score.
- **GDPR text:** the 2016 Official Journal original, without later corrigenda. The system does not establish legal validity or currency.
- **a14:** the Garante's list under GDPR Art. 35(4) is not in the corpus.

## Limits of the retrieval metrics

**Not addressed in v0. The `ask` pipeline is unchanged.**

- **Query analysis varies between runs.** The search queries and suggested articles come from a model call. Candidate and evidence recall therefore mix retrieval quality with the analysis of that run. A later version should replay a saved query analysis, so that retrieval and selection can be measured on fixed inputs.
- **Not every candidate is recorded.** The pipeline records the evidence items and the candidates dropped by the limits, with origins and best BM25 rank. It does not record search results below the per-query cutoff (5 chunks), so a candidate-recall miss cannot tell «not retrieved» from «ranked below the cutoff».
- **Some overview questions have more core rows than an answer can carry.** An answer has at most 5 evidence items (`FINAL_EVIDENCE_COUNT`, unchanged), so evidence and citation recall cannot exceed 5/7 for a06 and 5/9 for a07. Compare them across runs rather than against 1.

## Owner decisions (2026-11-16)

1. **Build:** `build-f76ff6031f2fc82c4852f0a2bde27807` confirmed.
2. **a01 / a10:** Code Art. 2-bis stays supporting in both.
3. **a06:** the information duties (Arts. 12–14) stay supporting.
4. **a07:** core covers general and conditional controller obligations, without requiring exhaustive coverage. Art. 34 moved to core; Arts. 13 and 14 were added as supporting. See «Core in overview questions».
5. **Freshness window:** 30 days by default, overridable.
6. **Splits:** unchanged. These categories appear only in test: `historical`, `transfers`, `sanctions`, `rights`, `italian_specific` and `obligations`. Dev holds the four questions already run (a05–a08).
7. **Draft folder:** `banchmark/v0-draft/` was deleted on 2026-11-16 (owner's decision).
8. **Status:** every question and row stays `candidate`.
9. **Digital Omnibus:** stays unverified. It was not re-checked and is not presented as current.

**Still open:** the review of every question and row, and the re-verification of the Digital Omnibus status for a01, a10 and a12 (`verified_by`, `verified_on`).

## Owner review (2026-11-18)

- **Reviewer:** Simone Zanetti (owner), on 2026-11-18. An AI assistant (Claude, claude.ai) gave a
  second opinion on each row; the decisions are the owner's. The decision for every question and
  row is in `docs/evaluation/answers-v0-review-sheet.md`.
- **Reviewed:** questions a01–a13 and expectation rows 1–57, all accepted as drafted (`ok`).
  They are now `owner_reviewed`, and `reviewed_by` records the second opinion.
- **Added:** a03, GDPR Art. 34 par. 4, supporting: the supervisory authority may require the
  communication or decide that a condition of par. 3 is met. It is row 82, appended so that no
  row number changes.
- **Not reviewed yet:** a14–a22 (rows 58–81) stay `candidate`. They are not scored in the
  owner-reviewed scope.

## Owner decisions (2026-11-26): expected direct answers

- **Decided by** Simone Zanetti (owner) on 2026-11-26, after a draft by Claude Code (AI assistant).
- **Owner-reviewed questions:** a08 yes; a11 no; a12 no, each with exactly one accepted value.
  These questions and their rows stay `owner_reviewed` as on 2026-11-18. Only
  `expected_direct_answer` was added, by this decision.
- **Candidate questions:** a16 and a20 accept yes or partly: the right, or the transfer, exists, but
  only under conditions. a24 and a25 accept no. These four questions stay `candidate`.
- **Every other question** expects no direct answer: it is an open question.
