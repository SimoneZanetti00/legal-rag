# legal-v2 review checklist

*Prepared by Claude (AI assistant) in a Claude Code session on 2026-11-11, under the plan
[`../legal-v2-implementation-plan.md`](../legal-v2-implementation-plan.md) (Phase 1, step 5).*

*This checklist records the owner's decisions. It is not a review of benchmark records:*
- *`legal-v2` does not exist yet, and every record it will hold starts as an unreviewed
  candidate;*
- *a record becomes `owner_reviewed` only at Gate 2, when the owner names it as approved, with
  the name and date to record (D8).*

**What it holds:**
- **Part 1** (now): the natural queries, the results of the no-copying check, and the owner's
  Gate 1 decision.
- **Part 2** (Phase 2, step 13): every change ID and every natural-pool judgment, for the
  owner's review at Gate 2.

## Part 1: natural queries (Gate 1)

**The owner's decision, given in the session on 2026-11-11 (plan §0-15):**
- The 24 drafts are approved, with two edits (q19 and q20, below).
- N1–N6 were to be rerun on all 24, and the work was to stop if either edited query failed.
  Neither failed.

**What was not done:** no search or pooling has been run with these queries, and no metric has
been calculated.

**How the checks were run:**
- **Method:** in memory, on 2026-11-11, by a scratchpad script that reads text only. It
  compares the queries with the article headings and point texts of the recorded build
  `build-f76ff6031f2fc82c4852f0a2bde27807`, with the v1 technical queries, and with the
  questions. It runs no search.
- **The grades used** are the approved v2 grades of plan §2:
  - v1, less the eight regrades to 0;
  - plus the two regrades to 1 (q11 GDPR Art. 12, q13 GDPR Art. 6);
  - plus the three additions at grade 1 (q04 GDPR Art. 55, q05 GDPR Art. 4 point 12, q13 GDPR
    Art. 12);
  - plus the judged points (q05 point 12, q17 points 13–15).

  q14 GDPR Art. 55 is graded 0, so its heading is not checked.
- **The checks** (plan §4.3; guidelines, "Query scenarios"):

  | Check | Rule |
  |---|---|
  | N1 | no 4-word sequence shared with the heading of an article graded 1 or 2 |
  | N2 | no whole heading of 2 or 3 words of such an article |
  | N3 | no 4-word sequence shared with the text of a judged point |
  | N4 | no 4-word sequence shared with the technical queries, and no equal query |
  | N5 | every number in the query appears in the question |
  | N6 | it passes `query_problem`, and there are as many natural as technical queries |

### The edits made by the owner

| Q | Draft (replaced) | Approved wording |
|---|---|---|
| q19 | «esercizio dei diritti privacy da parte degli eredi» | «chi può esercitare i diritti privacy dopo la morte di una persona» |
| q20 | «procedimento sanzionatorio del Garante» | «criteri per stabilire l'importo di una sanzione privacy» |

### Results

"Compared with" counts the headings (of articles graded 1 or 2) and the judged points that N1–N3
checked the queries against. q21–q24 are out of scope or not in the corpus, so they have none.

| Q | Split | Approved natural queries | N1 | N2 | N3 | N4 | N5 | N6 | Compared with | Gate 1 |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | dev | «nozione di dato personale»; «informazioni che rendono riconoscibile una persona» | pass | pass | pass | pass | pass | pass | 1 heading, 1 point | approved |
| q02 | dev | «nozione di data breach»; «smarrimento o accesso abusivo ai dati dei clienti» | pass | pass | pass | pass | pass | pass | 1 heading, 1 point | approved |
| q03 | test | «requisiti di validità del consenso privacy»; «consenso privacy inserito nelle condizioni generali del contratto» | pass | pass | pass | pass | pass | pass | 4 headings, 1 point | approved |
| q04 | dev | «termine per la notifica del data breach al Garante»; «ritardo nella segnalazione di una fuga di dati all'autorità» | pass | pass | pass | pass | pass | pass | 5 headings, 1 point | approved |
| q05 | dev | «obbligo di informare gli interessati del data breach»; «quando avvisare i clienti di una fuga di dati» | pass | pass | pass | pass | pass | pass | 4 headings, 1 point | approved |
| q06 | test | «quando è obbligatoria la DPIA»; «trattamenti ad alto rischio che richiedono un'analisi preventiva» | pass | pass | pass | pass | pass | pass | 1 heading | approved |
| q07 | dev | «obbligo di tenuta del registro dei trattamenti»; «esenzione dal registro per le piccole imprese» | pass | pass | pass | pass | pass | pass | 1 heading | approved |
| q08 | dev | «obbligo di nomina del DPO»; «aziende ed enti tenuti ad avere un DPO» | pass | pass | pass | pass | pass | pass | 2 headings | approved |
| q09 | test | «contenuto dell'informativa privacy al cliente»; «cosa indicare nell'informativa al momento della raccolta» | pass | pass | pass | pass | pass | pass | 2 headings | approved |
| q10 | dev | «istanza di accesso ai propri dati personali»; «ottenere copia dei dati trattati dal titolare» | pass | pass | pass | pass | pass | pass | 2 headings | approved |
| q11 | dev | «presupposti della richiesta di cancellazione dei dati»; «quando spetta il diritto all'oblio» | pass | pass | pass | pass | pass | pass | 2 headings | approved |
| q12 | test | «portabilità dei dati verso un altro fornitore»; «esportare i dati del proprio account in un formato riutilizzabile» | pass | pass | pass | pass | pass | pass | 2 headings | approved |
| q13 | dev | «opposizione dell'interessato al marketing»; «opporsi al trattamento basato sul legittimo interesse» | pass | pass | pass | pass | pass | pass | 4 headings | approved |
| q14 | dev | «autorità di vigilanza privacy in Italia»; «chi vigila sul trattamento dei dati personali in Italia» | pass | pass | pass | pass | pass | pass | 4 headings, 1 point | approved |
| q15 | test | «poteri ispettivi del Garante privacy»; «provvedimenti che il Garante può adottare contro un'azienda» | pass | pass | pass | pass | pass | pass | 5 headings | approved |
| q16 | dev | «art. 2-ter codice privacy»; «art. 2-ter base normativa dei trattamenti pubblici» | pass | pass | pass | pass | pass | pass | 2 headings | approved |
| q17 | dev | «art. 9 GDPR dati sensibili»; «divieto di trattare dati sanitari e relative eccezioni» | pass | pass | pass | pass | pass | pass | 4 headings, 3 points | approved |
| q18 | test | «età minima per il consenso digitale del minore»; «iscrizione di un minorenne a un social network senza i genitori» | pass | pass | pass | pass | pass | pass | 2 headings | approved |
| q19 | dev | «dati personali di un familiare defunto»; «chi può esercitare i diritti privacy dopo la morte di una persona» | pass | pass | pass | pass | pass | pass | 1 heading | approved; second query edited by the owner |
| q20 | dev | «quantificazione delle sanzioni privacy»; «criteri per stabilire l'importo di una sanzione privacy» | pass | pass | pass | pass | pass | pass | 2 headings | approved; second query edited by the owner |
| q21 | test | «IVA su fattura a cliente estero» | pass | pass | pass | pass | pass | pass | none | approved |
| q22 | dev | «giusta causa di recesso dal rapporto di lavoro» | pass | pass | pass | pass | pass | pass | none | approved |
| q23 | dev | «adempimenti per chi immette sul mercato sistemi di IA ad alto rischio» | pass | pass | pass | pass | pass | pass | none | approved |
| q24 | test | «sanzioni del Garante al telemarketing nel 2025» | pass | pass | pass | pass | pass | pass | none | approved |

**Summary:** all 24 questions pass all six checks, and no check failed for any query. This
includes the two edited queries.

**Next (Phase 2, not yet authorized):** the queries are frozen as changes c43–c66, before any
search is run with them (plan §8, step 6).

## Part 2: records for the owner's review (Gate 2)

*Completed in Phase 2 (plan §8, step 13) on 2026-11-11. Updated on 2026-11-12, after the owner's
Gate 2 decisions were applied (plan §8, step 15).*

*legal-v2 was frozen at Gate 3 (2026-11-12).*
- *Its six files are pinned, so the review status recorded below is final for v2.*
- *Reviewing the remaining candidates, or changing any record, would make legal-v3.*

### 2.0 Gate 2 outcome (2026-11-12)

**The review.** The owner, Simone Zanetti, reviewed 28 judgments, now `owner_reviewed`:
- the 12 uncertain judgments (§2.2);
- q15 Code Art. 154-bis;
- q05 GDPR Art. 23;
- the 14 restriction judgments added at Gate 2 (§2.6).

The analysis behind the decisions is in
[`legal-v2-uncertain-judgments-dossier.md`](legal-v2-uncertain-judgments-dossier.md).

**What it is not.** These are owner judgments about textual relevance, not expert legal
validation. They establish nothing about the validity or currency of the Privacy Code
transcription, or of the 2016 GDPR text.

**Still unreviewed.** The other 645 judgments and all 24 questions are still `candidate`. Their
boxes below are unchecked.

**Totals:**
- 673 judgments and 24 questions;
- 348 change lines:
  - 66 approved in the plan (c01–c66);
  - 265 natural-pool judgments (c67–c331);
  - 17 Gate 2 review changes (c332–c348).

**How to use the boxes.** For each record not yet reviewed, mark *approve* or *change*. At a
later review, state the name and date to record. Only the records you name become
`owner_reviewed` (plan §3.9, D8).

### 2.1 Decided borderline items (U4, U5, U13)

U4 and U5 kept four unchanged v1 records at grade 1, and U13 approved two rationales. The
decisions on these changes are recorded in the plan (§0). The records themselves are not yet
reviewed.

| Item | Question | Record | Grade | Owner review |
|---|---|---|---|---|
| U4 | q03 | GDPR Art. 8 | 1 (kept) | [ ] approve · [ ] change |
| U4 | q03 | Code Art. 2-quinquies | 1 (kept) | [ ] approve · [ ] change |
| U5 | q17 | Code Art. 2-sexies | 1 (kept) | [ ] approve · [ ] change |
| U5 | q17 | Code Art. 2-septies | 1 (kept) | [ ] approve · [ ] change |
| U13 (c20) | q04 | GDPR Art. 34 | rationale only | [ ] approve · [ ] change |
| U13 (c24) | q20 | Code Art. 167 | rationale only | [ ] approve · [ ] change |

### 2.2 Flagged natural-pool judgments: decided at Gate 2

| Change | Question | Article | Grade as pooled | Why it was uncertain | Owner review |
|---|---|---|---|---|---|
| c103 | q04 | GDPR Art. 51 | 0 | low. Related to Code Art. 2-bis, which is graded 1 for q04. | **owner_reviewed** 2026-11-12: grade 0 |
| c130 | q06 | Code Art. 110 | 0 | rule 5 (a narrow sector rule), as D5 decided for Code Art. 107. It does name one case where an assessment is required. | **owner_reviewed** 2026-11-12: grade 1 |
| c141 | q06 | GDPR Art. 9 | 1 | rule 2 (the scope of one listed case is fixed by reference). Under a stricter reading, 0: the question is answered by Art. 35. | **owner_reviewed** 2026-11-12: grade 1 |
| c181 | q09 | Code Art. 111-bis | 0 | low. Rule 5 (a narrow case). | **owner_reviewed** 2026-11-12: grade 0 |
| c213 | q13 | Code Art. 2-undecies | 1 | an exception under D1, like GDPR Art. 23 for q05. Consistency: this article and GDPR Art. 23 are not in the pools of q10-q12, and GDPR Art. 23 is not judged for q13. | **owner_reviewed** 2026-11-12: grade 1 |
| c231 | q15 | Code Art. 166 | 1 | a specification of the fining power, as GDPR Art. 83 is graded 1 for q15. Under a stricter reading, 0: a procedure, not a power. | **owner_reviewed** 2026-11-12: grade 1 |
| c232 | q15 | Code Art. 144 | 0 | 1 if procedural specifications of the powers count. | **owner_reviewed** 2026-11-12: grade 0 |
| c234 | q15 | Code Art. 143 | 0 | 1 if procedural specifications of the powers count. | **owner_reviewed** 2026-11-12: grade 0 |
| c241 | q15 | Code Art. 154-ter | 0 | a power, but not of the two kinds the question names. | **owner_reviewed** 2026-11-12: grade 0 |
| c264 | q17 | Code Art. 75 | 0 | low. Rule 5, as D5 decided for Code Art. 107. | **owner_reviewed** 2026-11-12: grade 0 |
| c283 | q19 | GDPR Art. 12 | 0 | low. Rule 4 grades Art. 12 at 1 in questions about exercising the rights (q10-q13); this question asks who. | **owner_reviewed** 2026-11-12: grade 0 |
| c298 | q20 | GDPR Art. 58 | 0 | low. GDPR Art. 83 answers the question; Art. 58 adds only that the power exists. | **owner_reviewed** 2026-11-12: grade 0 |

### 2.3 The plan's changes, c01–c66

c43–c66 are the natural queries. You approved their wording at Gate 1 (Part 1); they are
reviewed here as part of the question records.

| Change | Question | Record | Change | v2 rationale | Owner decision (plan) | Owner review |
|---|---|---|---|---|---|---|
| c01 | q02 | GDPR Art. 32 | grade 1 → 0 | Not relevant: security of processing is a related obligation; the breach is defined in Art. 4 point 12. | 2026-11-11, plan decision 2: approved. | [ ] approve · [ ] change |
| c02 | q02 | GDPR Art. 33 | grade 1 → 0 | Not relevant: notifying the authority follows a breach; it is not part of the definition. | 2026-11-11, plan decision 2: approved. | [ ] approve · [ ] change |
| c03 | q02 | GDPR Art. 34 | grade 1 → 0 | Not relevant: communicating a breach to data subjects follows a breach; it is not part of the definition. | 2026-11-11, plan decision 2: approved. | [ ] approve · [ ] change |
| c04 | q03 | GDPR Art. 6 | grade 1 → 0 | Not relevant: paragraph 1, letter a), names consent as a legal basis; the requirements of valid consent are in Art. 4 point 11 and Art. 7. | 2026-11-11, plan decision 2: approved. | [ ] approve · [ ] change |
| c05 | q05 | GDPR Art. 33 | grade 1 → 0 | Not relevant: notification to the authority is a related obligation, not the communication to data subjects asked about. | 2026-11-11, plan decision 2: approved. | [ ] approve · [ ] change |
| c06 | q06 | GDPR Art. 36 | grade 1 → 0 | Not relevant: prior consultation follows an assessment; it does not say when one is required. | 2026-11-11, plan decision 2: approved. | [ ] approve · [ ] change |
| c07 | q11 | GDPR Art. 12 | grade 0 → 1 | Paragraph 3: the time limit (one month, extendable) and the manner of answering a request under Arts. 15-22, erasure included. | 2026-11-11, plan decision 2: approved. | [ ] approve · [ ] change |
| c08 | q11 | GDPR Art. 19 | grade 1 → 0 | Not relevant: notifying recipients follows an erasure; it is not one of its grounds. | 2026-11-11, plan decision 2: approved. | [ ] approve · [ ] change |
| c09 | q13 | GDPR Art. 6 | grade 0 → 1 | Art. 21(1) allows objection to processing on the bases of Art. 6(1)(e) and (f), which only Art. 6 sets out. | 2026-11-11, plan decision 2: approved. | [ ] approve · [ ] change |
| c10 | q20 | GDPR Art. 84 | grade 1 → 0 | Not relevant: other penalties set by the Member States, not the administrative fines asked about. | 2026-11-11, plan decision 2: approved. | [ ] approve · [ ] change |
| c11 | q04 | GDPR Art. 55 | added, grade 1 | Art. 33(1) requires notification to the authority «competente a norma dell'articolo 55»; Art. 55(1) makes each authority competent on its own Member State's territory. | 2026-11-11, plan decision 3: approved at grade 1. | [ ] approve · [ ] change |
| c12 | q05 | GDPR Art. 4 point 12 | added, grade 1 | Point 12 defines the personal data breach to be communicated. | 2026-11-11, plan decision 4: approved at grade 1. | [ ] approve · [ ] change |
| c13 | q13 | GDPR Art. 12 | added, grade 1 | Paragraph 3: the time limit and the manner of answering a request under Arts. 15-22, objection included. | 2026-11-11, plan decision 5: approved at grade 1. | [ ] approve · [ ] change |
| c14 | q14 | GDPR Art. 55 | added, grade 0 | Not relevant: Art. 55(1) states the territorial competence of supervisory authorities in general; it names no national authority. | 2026-11-11, plan decision 6: approved with grade 0, not 1; Art. 55 is not to be described as identifying the Garante. | [ ] approve · [ ] change |
| c15 | q17 | GDPR Art. 4 | removed (grade 1) | (removed) | 2026-11-11, plan decision 7: approved. | (removed) |
| c16 | q17 | GDPR Art. 4 point 13 | added, grade 1 | Point 13 defines «dati genetici», a category Art. 9(1) names. | 2026-11-11, plan decision 7: approved. | [ ] approve · [ ] change |
| c17 | q17 | GDPR Art. 4 point 14 | added, grade 1 | Point 14 defines «dati biometrici», a category Art. 9(1) names. | 2026-11-11, plan decision 7: approved. | [ ] approve · [ ] change |
| c18 | q17 | GDPR Art. 4 point 15 | added, grade 1 | Point 15 defines «dati relativi alla salute», a category Art. 9(1) names. | 2026-11-11, plan decision 7: approved. | [ ] approve · [ ] change |
| c19 | q03 | GDPR Art. 9 | rationale only | Not relevant: explicit consent under Art. 9(2)(a) lifts the ban on special categories; it is not a general requirement of valid consent. | 2026-11-11, plan decision 8: approved (D5). | [ ] approve · [ ] change |
| c20 | q04 | GDPR Art. 34 | rationale only | Not relevant: communication to data subjects is a related obligation, not the notification to the Garante asked about. | 2026-11-11, plan decision 14: approved (U13). | [ ] approve · [ ] change |
| c21 | q17 | Code Art. 107 | rationale only | Not relevant: in the transcription, a rule on consent for special categories in statistics and research only; not needed to state what GDPR Art. 9 provides. | 2026-11-11, plan decision 8: approved (D5). | [ ] approve · [ ] change |
| c22 | q18 | GDPR Art. 8 | rationale only | Sets the rule (16 years) and lets Member States set a lower age, not below 13; the age in Italy is answered by reading it with Code Art. 2-quinquies. | 2026-11-11, plan decision 8: approved (D5). | [ ] approve · [ ] change |
| c23 | q18 | Code Art. 2-quinquies | rationale only | In the transcription: sets the age of 14 «in attuazione dell'articolo 8, paragrafo 1»; answered by reading it with GDPR Art. 8. Relevance of the text only, not a statement of the law in force. | 2026-11-11, plan decisions 8 and 9: approved (D5, D6). | [ ] approve · [ ] change |
| c24 | q20 | Code Art. 167 | rationale only | Not relevant: in the transcription, a criminal offence, not the administrative fines asked about. | 2026-11-11, plan decision 14: approved (U13). | [ ] approve · [ ] change |
| c25 | q03 | Code Art. 2-quinquies | rationale only | In the transcription: The age of a minor's own consent in Italy for information society services: one specific case. | 2026-11-11, plan decision 9: approved (D6 wording). | [ ] approve · [ ] change |
| c26 | q04 | Code Art. 2-quaterdecies.1 | rationale only | In the transcription: a specific notification procedure under GDPR Art. 33 for firms with fewer than five employees. | 2026-11-11, plan decision 9: approved (D6 wording). | [ ] approve · [ ] change |
| c27 | q04 | Code Art. 2-bis | rationale only | In the transcription: Identifies the Garante, which the question names, as the supervisory authority of GDPR Art. 51. | 2026-11-11, plan decision 9: approved (D6 wording). | [ ] approve · [ ] change |
| c28 | q08 | Code Art. 2-sex-decies | rationale only | In the transcription: a DPO is designated also for processing by judicial authorities. | 2026-11-11, plan decision 9: approved (D6 wording). | [ ] approve · [ ] change |
| c29 | q13 | Code Art. 130 | rationale only | In the transcription: rules on unsolicited marketing communications, including the right to object. | 2026-11-11, plan decision 9: approved (D6 wording). | [ ] approve · [ ] change |
| c30 | q14 | Code Art. 2-bis | rationale only | In the transcription: Identifies the Garante as Italy's supervisory authority under GDPR Art. 51. | 2026-11-11, plan decision 9: approved (D6 wording). | [ ] approve · [ ] change |
| c31 | q14 | Code Art. 153 | rationale only | In the transcription: Establishes the Garante, to which Art. 2-bis refers. | 2026-11-11, plan decision 9: approved (D6 wording). | [ ] approve · [ ] change |
| c32 | q15 | Code Art. 154-bis | rationale only | In the transcription: Further powers of the Garante under GDPR Art. 58(6). | 2026-11-11, plan decision 9: approved (D6 wording). | **owner_reviewed** 2026-11-12: grade 0 |
| c33 | q15 | Code Art. 157 | rationale only | In the transcription: The Garante's requests for information and documents, within the Art. 58 powers. | 2026-11-11, plan decision 9: approved (D6 wording). | [ ] approve · [ ] change |
| c34 | q15 | Code Art. 158 | rationale only | In the transcription: The Garante's access to databases, inspections and verifications. | 2026-11-11, plan decision 9: approved (D6 wording). | [ ] approve · [ ] change |
| c35 | q16 | Code Art. 2-ter | rationale only | In the transcription: The article the question names: the legal basis for processing in the public interest or in the exercise of public powers. | 2026-11-11, plan decision 9: approved (D6 wording). | [ ] approve · [ ] change |
| c36 | q17 | Code Art. 2-sexies | rationale only | In the transcription: special categories processed for reasons of substantial public interest, under Art. 9(2)(g). | 2026-11-11, plan decision 9: approved (D6 wording). | [ ] approve · [ ] change |
| c37 | q17 | Code Art. 2-septies | rationale only | In the transcription: safeguards for genetic, biometric and health data, under Art. 9(4). | 2026-11-11, plan decision 9: approved (D6 wording). | [ ] approve · [ ] change |
| c38 | q19 | Code Art. 2-terdecies | rationale only | In the transcription: Who may exercise the rights of Arts. 15-22 over a deceased person's data, and the limits. | 2026-11-11, plan decision 9: approved (D6 wording). | [ ] approve · [ ] change |
| c39 | q20 | Code Art. 166 | rationale only | In the transcription: which violations carry the Art. 83 fines, and the Garante's procedure. | 2026-11-11, plan decision 9: approved (D6 wording). | [ ] approve · [ ] change |
| c40 | q03 | question | category: definition → obligation |  | 2026-11-11, plan decision 8: approved (D7). | [ ] approve · [ ] change |
| c41 | q19 | question | category: cross_instrument → rights |  | 2026-11-11, plan decision 8: approved (D7). | [ ] approve · [ ] change |
| c42 | q18 | question | notes: The age of digital consent: the GDPR rule and the age set in the Privacy Code. → The age of digital consent: GDPR Art. 8 sets the rule and the Member States' option; Art. 2-quinquies of the Code transcription uses the option. Both are needed. |  | 2026-11-11, plan decision 8: approved (D5). | [ ] approve · [ ] change |
| c43 | q01 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c44 | q02 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c45 | q03 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c46 | q04 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c47 | q05 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c48 | q06 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c49 | q07 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c50 | q08 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c51 | q09 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c52 | q10 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c53 | q11 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c54 | q12 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c55 | q13 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c56 | q14 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c57 | q15 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c58 | q16 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c59 | q17 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c60 | q18 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c61 | q19 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved, with the second query edited by the owner. | [ ] approve · [ ] change |
| c62 | q20 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved, with the second query edited by the owner. | [ ] approve · [ ] change |
| c63 | q21 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c64 | q22 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c65 | q23 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |
| c66 | q24 | question | natural queries added (Part 1) |  | 2026-11-11, Gate 1 (plan decision 15): approved. | [ ] approve · [ ] change |

### 2.4 Natural-pool judgments, c67–c331

**How they were judged.** Each article the natural queries pooled, and that was not judged
already, was graded under D1:
- from its heading and, where it could matter, its text in the build;
- listed by article, not by rank;
- with no ranking and no metric looked at.

The flagged ones of §2.2 are included again here, with their outcome at Gate 2.

| Change | Question | Article | Grade as pooled | Rationale as pooled | Owner review |
|---|---|---|---|---|---|
| c67 | q01 | GDPR Art. 64 | 0 | Not relevant: the article concerns Parere del comitato europeo per la protezione dei dati. | [ ] approve · [ ] change |
| c68 | q01 | Code Art. 93 | 0 | Not relevant: the article concerns Certificato di assistenza al parto. | [ ] approve · [ ] change |
| c69 | q01 | Code Art. 111-bis | 0 | Not relevant: the article concerns (Informazioni in caso di ricezione di curriculum). | [ ] approve · [ ] change |
| c70 | q01 | Code Art. 108 | 0 | Not relevant: the article concerns (Sistema statistico nazionale). | [ ] approve · [ ] change |
| c71 | q01 | GDPR Art. 14 | 0 | Not relevant: the article concerns Informazioni da fornire qualora i dati personali non siano stati ottenuti presso l'interessato. | [ ] approve · [ ] change |
| c72 | q01 | Code Art. 116 | 0 | Not relevant: the article concerns Conoscibilità di dati su mandato dell'interessato. | [ ] approve · [ ] change |
| c73 | q01 | Code Art. 131 | 0 | Not relevant: the article concerns Informazioni a contraenti e utenti. | [ ] approve · [ ] change |
| c74 | q01 | Code Art. 107 | 0 | Not relevant: the article concerns (Trattamento di categorie particolari di dati personali). | [ ] approve · [ ] change |
| c75 | q01 | Code Art. 183 | 0 | Not relevant: the article concerns Norme abrogate. | [ ] approve · [ ] change |
| c76 | q02 | Code Art. 37 | 0 | Not relevant: the article is marked repealed in the transcription. | [ ] approve · [ ] change |
| c77 | q02 | GDPR Art. 86 | 0 | Not relevant: the article concerns Trattamento e accesso del pubblico ai documenti ufficiali. | [ ] approve · [ ] change |
| c78 | q02 | Code Art. 183 | 0 | Not relevant: the article concerns Norme abrogate. | [ ] approve · [ ] change |
| c79 | q02 | Code Art. 123 | 0 | Not relevant: the article concerns Dati relativi al traffico. | [ ] approve · [ ] change |
| c80 | q02 | Code Art. 152 | 0 | Not relevant: the article concerns Autorità giudiziaria ordinaria. | [ ] approve · [ ] change |
| c81 | q02 | GDPR Art. 96 | 0 | Not relevant: the article concerns Rapporto con accordi precedentemente conclusi. | [ ] approve · [ ] change |
| c82 | q02 | GDPR Art. 15 | 0 | Not relevant: the article concerns Diritto di accesso dell'interessato. | [ ] approve · [ ] change |
| c83 | q02 | Code Art. 186 | 0 | Not relevant: the article concerns Entrata in vigore. | [ ] approve · [ ] change |
| c84 | q02 | Code Art. 167 | 0 | Not relevant: the article concerns Trattamento illecito di dati. | [ ] approve · [ ] change |
| c85 | q02 | Code Art. 126 | 0 | Not relevant: the article concerns Dati relativi all'ubicazione. | [ ] approve · [ ] change |
| c86 | q02 | Code Art. 130 | 0 | Not relevant: the article concerns Comunicazioni indesiderate. | [ ] approve · [ ] change |
| c87 | q02 | Code Art. 2-octies | 0 | Not relevant: the article concerns Principi relativi al trattamento di dati relativi a condanne penali e reati. | [ ] approve · [ ] change |
| c88 | q02 | Code Art. 108 | 0 | Not relevant: the article concerns (Sistema statistico nazionale). | [ ] approve · [ ] change |
| c89 | q03 | Code Art. 160-bis | 0 | Not relevant: the article concerns (Validità, efficacia e utilizzabilità nel procedimento giudiziario di atti, documenti e provvedimenti basati sul trattamento di dati personali non conforme a disposizioni di legge o di Regolamento). | [ ] approve · [ ] change |
| c90 | q03 | GDPR Art. 40 | 0 | Not relevant: the article concerns Codici di condotta. | [ ] approve · [ ] change |
| c91 | q03 | Code Art. 106 | 0 | Not relevant: the article concerns (Regole deontologiche per trattamenti a fini statistici o di ricerca scientifica). | [ ] approve · [ ] change |
| c92 | q03 | GDPR Art. 70 | 0 | Not relevant: the article concerns Compiti del comitato. | [ ] approve · [ ] change |
| c93 | q03 | GDPR Art. 42 | 0 | Not relevant: the article concerns Certificazione. | [ ] approve · [ ] change |
| c94 | q03 | Code Art. 111-bis | 0 | Not relevant: the article concerns (Informazioni in caso di ricezione di curriculum). | [ ] approve · [ ] change |
| c95 | q03 | GDPR Art. 28 | 0 | Not relevant: the article concerns Responsabile del trattamento. | [ ] approve · [ ] change |
| c96 | q03 | GDPR Art. 13 | 0 | Not relevant: the article concerns Informazioni da fornire qualora i dati personali siano raccolti presso l'interessato. | [ ] approve · [ ] change |
| c97 | q03 | Code Art. 126 | 0 | Not relevant: the article concerns Dati relativi all'ubicazione. | [ ] approve · [ ] change |
| c98 | q04 | Code Art. 143 | 0 | Not relevant: the article concerns Decisione del reclamo. | [ ] approve · [ ] change |
| c99 | q04 | Code Art. 144-bis | 0 | Not relevant: the article concerns (Revenge porn). | [ ] approve · [ ] change |
| c100 | q04 | Code Art. 144 | 0 | Not relevant: the article concerns Segnalazioni. | [ ] approve · [ ] change |
| c101 | q04 | Code Art. 166 | 0 | Not relevant: the article concerns Criteri di applicazione delle sanzioni amministrative pecuniarie e procedimento per l'adozione dei provvedimenti correttivi e sanzionatori. | [ ] approve · [ ] change |
| c102 | q04 | GDPR Art. 92 | 0 | Not relevant: the article concerns Esercizio della delega. | [ ] approve · [ ] change |
| c103 | q04 | GDPR Art. 51 | 0 | Not relevant: it requires Member States to provide supervisory authorities; it adds nothing to the notification or its deadline. | **owner_reviewed** 2026-11-12: grade 0 |
| c104 | q04 | GDPR Art. 66 | 0 | Not relevant: the article concerns Procedura d'urgenza. | [ ] approve · [ ] change |
| c105 | q04 | Code Art. 110-bis | 0 | Not relevant: the article concerns (Trattamento ulteriore da parte di terzi dei dati personali a fini di ricerca scientifica o a fini statistici). | [ ] approve · [ ] change |
| c106 | q04 | Code Art. 167 | 0 | Not relevant: the article concerns Trattamento illecito di dati. | [ ] approve · [ ] change |
| c107 | q04 | Code Art. 168 | 0 | Not relevant: the article concerns (Falsità nelle dichiarazioni al Garante e interruzione dell'esecuzione dei compiti o dell'esercizio dei poteri del Garante). | [ ] approve · [ ] change |
| c108 | q04 | Code Art. 175 | 0 | Not relevant: the article concerns Forze di polizia. | [ ] approve · [ ] change |
| c109 | q04 | Code Art. 2-ter | 0 | Not relevant: the article concerns Base giuridica per il trattamento di dati personali effettuato per l'esecuzione di un compito di interesse pubblico o connesso all'esercizio di pubblici poteri. | [ ] approve · [ ] change |
| c110 | q05 | Code Art. 110-bis | 0 | Not relevant: the article concerns (Trattamento ulteriore da parte di terzi dei dati personali a fini di ricerca scientifica o a fini statistici). | [ ] approve · [ ] change |
| c111 | q05 | Code Art. 186 | 0 | Not relevant: the article concerns Entrata in vigore. | [ ] approve · [ ] change |
| c112 | q05 | GDPR Art. 64 | 0 | Not relevant: the article concerns Parere del comitato europeo per la protezione dei dati. | [ ] approve · [ ] change |
| c113 | q05 | Code Art. 183 | 0 | Not relevant: the article concerns Norme abrogate. | [ ] approve · [ ] change |
| c114 | q05 | Code Art. 123 | 0 | Not relevant: the article concerns Dati relativi al traffico. | [ ] approve · [ ] change |
| c115 | q05 | Code Art. 110 | 0 | Not relevant: the article concerns Ricerca medica, biomedica ed epidemiologica. | [ ] approve · [ ] change |
| c116 | q05 | GDPR Art. 96 | 0 | Not relevant: the article concerns Rapporto con accordi precedentemente conclusi. | [ ] approve · [ ] change |
| c117 | q05 | Code Art. 154 | 0 | Not relevant: the article concerns Compiti. | [ ] approve · [ ] change |
| c118 | q05 | Code Art. 130 | 0 | Not relevant: the article concerns Comunicazioni indesiderate. | [ ] approve · [ ] change |
| c119 | q05 | Code Art. 132 | 0 | Not relevant: the article concerns (Conservazione di dati di traffico per altre finalità). | [ ] approve · [ ] change |
| c120 | q05 | GDPR Art. 27 | 0 | Not relevant: the article concerns Rappresentanti di titolari del trattamento o dei responsabili del trattamento non stabiliti nell'Unione. | [ ] approve · [ ] change |
| c121 | q05 | Code Art. 127 | 0 | Not relevant: the article concerns Chiamate di disturbo e di emergenza. | [ ] approve · [ ] change |
| c122 | q05 | Code Art. 126 | 0 | Not relevant: the article concerns Dati relativi all'ubicazione. | [ ] approve · [ ] change |
| c123 | q05 | Code Art. 144-bis | 0 | Not relevant: the article concerns (Revenge porn). | [ ] approve · [ ] change |
| c124 | q05 | GDPR Art. 36 | 0 | Not relevant: the article concerns Consultazione preventiva. | [ ] approve · [ ] change |
| c125 | q05 | GDPR Art. 17 | 0 | Not relevant: the article concerns Diritto alla cancellazione («diritto all'oblio»). | [ ] approve · [ ] change |
| c126 | q06 | Code Art. 167 | 0 | Not relevant: the article concerns Trattamento illecito di dati. | [ ] approve · [ ] change |
| c127 | q06 | Code Art. 131 | 0 | Not relevant: the article concerns Informazioni a contraenti e utenti. | [ ] approve · [ ] change |
| c128 | q06 | Code Art. 132-ter | 0 | Not relevant: the article concerns Sicurezza del trattamento. | [ ] approve · [ ] change |
| c129 | q06 | Code Art. 60 | 0 | Not relevant: the article concerns Dati relativi alla salute o alla vita sessuale o all'orientamento sessuale). | [ ] approve · [ ] change |
| c130 | q06 | Code Art. 110 | 0 | Not relevant: in the transcription, an impact assessment as a condition for medical research without consent; a sector rule the question does not ask about. | **owner_reviewed** 2026-11-12: grade 1 |
| c131 | q06 | Code Art. 57 | 0 | Not relevant: the article concerns Disposizioni di attuazione. | [ ] approve · [ ] change |
| c132 | q06 | Code Art. 132 | 0 | Not relevant: the article concerns (Conservazione di dati di traffico per altre finalità). | [ ] approve · [ ] change |
| c133 | q06 | Code Art. 159 | 0 | Not relevant: the article concerns Modalita. | [ ] approve · [ ] change |
| c134 | q06 | Code Art. 132-quater | 0 | Not relevant: the article concerns Informazioni sui rischi. | [ ] approve · [ ] change |
| c135 | q06 | Code Art. 37 | 0 | Not relevant: the article is marked repealed in the transcription. | [ ] approve · [ ] change |
| c136 | q06 | GDPR Art. 92 | 0 | Not relevant: the article concerns Esercizio della delega. | [ ] approve · [ ] change |
| c137 | q06 | Code Art. 154 | 0 | Not relevant: the article concerns Compiti. | [ ] approve · [ ] change |
| c138 | q06 | Code Art. 170 | 0 | Not relevant: the article concerns Inosservanza di provvedimenti del Garante. | [ ] approve · [ ] change |
| c139 | q06 | Code Art. 2-octies | 0 | Not relevant: the article concerns Principi relativi al trattamento di dati relativi a condanne penali e reati. | [ ] approve · [ ] change |
| c140 | q06 | Code Art. 175 | 0 | Not relevant: the article concerns Forze di polizia. | [ ] approve · [ ] change |
| c141 | q06 | GDPR Art. 9 | 1 | Art. 35(3)(b) names large-scale processing of the special categories «di cui all'articolo 9, paragrafo 1» as a case that requires an assessment; only Art. 9(1) says which data those are. | **owner_reviewed** 2026-11-12: grade 1 |
| c142 | q07 | Code Art. 2-sexies | 0 | Not relevant: the article concerns Trattamento di categorie particolari di dati personali necessario per motivi di interesse pubblico rilevante. | [ ] approve · [ ] change |
| c143 | q07 | GDPR Art. 42 | 0 | Not relevant: the article concerns Certificazione. | [ ] approve · [ ] change |
| c144 | q07 | Code Art. 154-bis | 0 | Not relevant: the article concerns Poteri. | [ ] approve · [ ] change |
| c145 | q07 | GDPR Art. 40 | 0 | Not relevant: the article concerns Codici di condotta. | [ ] approve · [ ] change |
| c146 | q07 | Code Art. 2-ter | 0 | Not relevant: the article concerns Base giuridica per il trattamento di dati personali effettuato per l'esecuzione di un compito di interesse pubblico o connesso all'esercizio di pubblici poteri. | [ ] approve · [ ] change |
| c147 | q07 | Code Art. 144-bis | 0 | Not relevant: the article concerns (Revenge porn). | [ ] approve · [ ] change |
| c148 | q07 | Code Art. 106 | 0 | Not relevant: the article concerns (Regole deontologiche per trattamenti a fini statistici o di ricerca scientifica). | [ ] approve · [ ] change |
| c149 | q08 | GDPR Art. 54 | 0 | Not relevant: the article concerns Norme sull'istituzione dell'autorità di controllo. | [ ] approve · [ ] change |
| c150 | q08 | Code Art. 153 | 0 | Not relevant: the article concerns Garante per la protezione dei dati personali. | [ ] approve · [ ] change |
| c151 | q08 | Code Art. 2-sexies | 0 | Not relevant: the article concerns Trattamento di categorie particolari di dati personali necessario per motivi di interesse pubblico rilevante. | [ ] approve · [ ] change |
| c152 | q08 | Code Art. 79 | 0 | Not relevant: the article concerns Informazioni da parte di strutture pubbliche e private che erogano prestazioni sanitarie e socio-sanitarie. | [ ] approve · [ ] change |
| c153 | q08 | GDPR Art. 14 | 0 | Not relevant: the article concerns Informazioni da fornire qualora i dati personali non siano stati ottenuti presso l'interessato. | [ ] approve · [ ] change |
| c154 | q08 | Code Art. 156 | 0 | Not relevant: the article concerns Ruolo organico e personale. | [ ] approve · [ ] change |
| c155 | q08 | GDPR Art. 53 | 0 | Not relevant: the article concerns Condizioni generali per i membri dell'autorità di controllo. | [ ] approve · [ ] change |
| c156 | q08 | Code Art. 159 | 0 | Not relevant: the article concerns Modalita. | [ ] approve · [ ] change |
| c157 | q08 | GDPR Art. 90 | 0 | Not relevant: the article concerns Obblighi di segretezza. | [ ] approve · [ ] change |
| c158 | q08 | Code Art. 2-quaterdecies.1 | 0 | Not relevant: the article concerns (Procedura di notifica delle violazioni di dati personali da parte di microimprese). | [ ] approve · [ ] change |
| c159 | q08 | Code Art. 111 | 0 | Not relevant: the article concerns (Regole deontologiche per trattamenti nell'ambito del rapporto di lavoro). | [ ] approve · [ ] change |
| c160 | q08 | Code Art. 2-ter | 0 | Not relevant: the article concerns Base giuridica per il trattamento di dati personali effettuato per l'esecuzione di un compito di interesse pubblico o connesso all'esercizio di pubblici poteri. | [ ] approve · [ ] change |
| c161 | q08 | Code Art. 2-octies | 0 | Not relevant: the article concerns Principi relativi al trattamento di dati relativi a condanne penali e reati. | [ ] approve · [ ] change |
| c162 | q08 | Code Art. 170 | 0 | Not relevant: the article concerns Inosservanza di provvedimenti del Garante. | [ ] approve · [ ] change |
| c163 | q08 | GDPR Art. 92 | 0 | Not relevant: the article concerns Esercizio della delega. | [ ] approve · [ ] change |
| c164 | q08 | Code Art. 154-bis | 0 | Not relevant: the article concerns Poteri. | [ ] approve · [ ] change |
| c165 | q08 | Code Art. 116 | 0 | Not relevant: the article concerns Conoscibilità di dati su mandato dell'interessato. | [ ] approve · [ ] change |
| c166 | q08 | Code Art. 100 | 0 | Not relevant: the article concerns Dati relativi ad attività di studio e ricerca. | [ ] approve · [ ] change |
| c167 | q09 | Code Art. 131 | 0 | Not relevant: the article concerns Informazioni a contraenti e utenti. | [ ] approve · [ ] change |
| c168 | q09 | Code Art. 130 | 0 | Not relevant: the article concerns Comunicazioni indesiderate. | [ ] approve · [ ] change |
| c169 | q09 | GDPR Art. 41 | 0 | Not relevant: the article concerns Monitoraggio dei codici di condotta approvati. | [ ] approve · [ ] change |
| c170 | q09 | Code Art. 157 | 0 | Not relevant: the article concerns (Richiesta di informazioni e di esibizione di documenti). | [ ] approve · [ ] change |
| c171 | q09 | Code Art. 144-bis | 0 | Not relevant: the article concerns (Revenge porn). | [ ] approve · [ ] change |
| c172 | q09 | GDPR Art. 88 | 0 | Not relevant: the article concerns Trattamento dei dati nell'ambito dei rapporti di lavoro. | [ ] approve · [ ] change |
| c173 | q09 | Code Art. 52 | 0 | Not relevant: the article concerns Dati identificativi degli interessati. | [ ] approve · [ ] change |
| c174 | q09 | Code Art. 132 | 0 | Not relevant: the article concerns (Conservazione di dati di traffico per altre finalità). | [ ] approve · [ ] change |
| c175 | q09 | Code Art. 113 | 0 | Not relevant: the article concerns Raccolta di dati e pertinenza. | [ ] approve · [ ] change |
| c176 | q09 | GDPR Art. 34 | 0 | Not relevant: the article concerns Comunicazione di una violazione dei dati personali all'interessato. | [ ] approve · [ ] change |
| c177 | q09 | Code Art. 132-quater | 0 | Not relevant: the article concerns Informazioni sui rischi. | [ ] approve · [ ] change |
| c178 | q09 | GDPR Art. 36 | 0 | Not relevant: the article concerns Consultazione preventiva. | [ ] approve · [ ] change |
| c179 | q09 | Code Art. 2-sexies | 0 | Not relevant: the article concerns Trattamento di categorie particolari di dati personali necessario per motivi di interesse pubblico rilevante. | [ ] approve · [ ] change |
| c180 | q09 | Code Art. 105 | 0 | Not relevant: the article concerns Modalità di trattamento. | [ ] approve · [ ] change |
| c181 | q09 | Code Art. 111-bis | 0 | Not relevant: in the transcription, when the Art. 13 information is given for unsolicited CVs; a narrow case, not the content asked about. | **owner_reviewed** 2026-11-12: grade 0 |
| c182 | q10 | GDPR Art. 17 | 0 | Not relevant: the article concerns Diritto alla cancellazione («diritto all'oblio»). | [ ] approve · [ ] change |
| c183 | q10 | Code Art. 153 | 0 | Not relevant: the article concerns Garante per la protezione dei dati personali. | [ ] approve · [ ] change |
| c184 | q10 | GDPR Art. 58 | 0 | Not relevant: the article concerns Poteri. | [ ] approve · [ ] change |
| c185 | q10 | GDPR Art. 49 | 0 | Not relevant: the article concerns Deroghe in specifiche situazioni. | [ ] approve · [ ] change |
| c186 | q10 | Code Art. 2-sexies | 0 | Not relevant: the article concerns Trattamento di categorie particolari di dati personali necessario per motivi di interesse pubblico rilevante. | [ ] approve · [ ] change |
| c187 | q10 | Code Art. 157 | 0 | Not relevant: the article concerns (Richiesta di informazioni e di esibizione di documenti). | [ ] approve · [ ] change |
| c188 | q10 | GDPR Art. 37 | 0 | Not relevant: the article concerns Designazione del responsabile della protezione dei dati. | [ ] approve · [ ] change |
| c189 | q10 | Code Art. 126 | 0 | Not relevant: the article concerns Dati relativi all'ubicazione. | [ ] approve · [ ] change |
| c190 | q11 | Code Art. 175 | 0 | Not relevant: the article concerns Forze di polizia. | [ ] approve · [ ] change |
| c191 | q11 | Code Art. 59 | 0 | Not relevant: the article concerns Accesso a documenti amministrativi e accesso civico. | [ ] approve · [ ] change |
| c192 | q11 | GDPR Art. 61 | 0 | Not relevant: the article concerns Assistenza reciproca. | [ ] approve · [ ] change |
| c193 | q11 | Code Art. 105 | 0 | Not relevant: the article concerns Modalità di trattamento. | [ ] approve · [ ] change |
| c194 | q11 | GDPR Art. 70 | 0 | Not relevant: the article concerns Compiti del comitato. | [ ] approve · [ ] change |
| c195 | q11 | Code Art. 57 | 0 | Not relevant: the article concerns Disposizioni di attuazione. | [ ] approve · [ ] change |
| c196 | q11 | Code Art. 123 | 0 | Not relevant: the article concerns Dati relativi al traffico. | [ ] approve · [ ] change |
| c197 | q11 | Code Art. 96 | 0 | Not relevant: the article concerns (Trattamento di dati relativi a studenti). | [ ] approve · [ ] change |
| c198 | q11 | Code Art. 52 | 0 | Not relevant: the article concerns Dati identificativi degli interessati. | [ ] approve · [ ] change |
| c199 | q11 | Code Art. 2-octies | 0 | Not relevant: the article concerns Principi relativi al trattamento di dati relativi a condanne penali e reati. | [ ] approve · [ ] change |
| c200 | q12 | GDPR Art. 44 | 0 | Not relevant: the article concerns Principio generale per il trasferimento. | [ ] approve · [ ] change |
| c201 | q12 | GDPR Art. 40 | 0 | Not relevant: the article concerns Codici di condotta. | [ ] approve · [ ] change |
| c202 | q12 | GDPR Art. 45 | 0 | Not relevant: the article concerns Trasferimento sulla base di una decisione di adeguatezza. | [ ] approve · [ ] change |
| c203 | q12 | GDPR Art. 7 | 0 | Not relevant: the article concerns Condizioni per il consenso. | [ ] approve · [ ] change |
| c204 | q12 | Code Art. 132-bis | 0 | Not relevant: the article concerns Procedure istituite dai fornitori. | [ ] approve · [ ] change |
| c205 | q12 | Code Art. 127 | 0 | Not relevant: the article concerns Chiamate di disturbo e di emergenza. | [ ] approve · [ ] change |
| c206 | q12 | GDPR Art. 42 | 0 | Not relevant: the article concerns Certificazione. | [ ] approve · [ ] change |
| c207 | q12 | Code Art. 132 | 0 | Not relevant: the article concerns (Conservazione di dati di traffico per altre finalità). | [ ] approve · [ ] change |
| c208 | q12 | Code Art. 132-ter | 0 | Not relevant: the article concerns Sicurezza del trattamento. | [ ] approve · [ ] change |
| c209 | q12 | GDPR Art. 46 | 0 | Not relevant: the article concerns Trasferimento soggetto a garanzie adeguate. | [ ] approve · [ ] change |
| c210 | q13 | GDPR Art. 13 | 0 | Not relevant: the article concerns Informazioni da fornire qualora i dati personali siano raccolti presso l'interessato. | [ ] approve · [ ] change |
| c211 | q13 | GDPR Art. 7 | 0 | Not relevant: the article concerns Condizioni per il consenso. | [ ] approve · [ ] change |
| c212 | q13 | Code Art. 141 | 0 | Not relevant: the article concerns Reclamo al Garante. | [ ] approve · [ ] change |
| c213 | q13 | Code Art. 2-undecies | 1 | In the transcription: the rights of Arts. 15-22, objection included, cannot be exercised by request where this could prejudice the interests it lists; an exception to the right asked about. | **owner_reviewed** 2026-11-12: grade 1 |
| c214 | q13 | GDPR Art. 14 | 0 | Not relevant: the article concerns Informazioni da fornire qualora i dati personali non siano stati ottenuti presso l'interessato. | [ ] approve · [ ] change |
| c215 | q13 | GDPR Art. 80 | 0 | Not relevant: the article concerns Rappresentanza degli interessati. | [ ] approve · [ ] change |
| c216 | q13 | Code Art. 160-bis | 0 | Not relevant: the article concerns (Validità, efficacia e utilizzabilità nel procedimento giudiziario di atti, documenti e provvedimenti basati sul trattamento di dati personali non conforme a disposizioni di legge o di Regolamento). | [ ] approve · [ ] change |
| c217 | q14 | Code Art. 120 | 0 | Not relevant: the article concerns Sinistri. | [ ] approve · [ ] change |
| c218 | q14 | Code Art. 2-quinquies | 0 | Not relevant: the article concerns (Consenso del minore in relazione ai servizi della società dell'informazione). | [ ] approve · [ ] change |
| c219 | q14 | GDPR Art. 43 | 0 | Not relevant: the article concerns Organismi di certificazione. | [ ] approve · [ ] change |
| c220 | q14 | Code Art. 144-bis | 0 | Not relevant: the article concerns (Revenge porn). | [ ] approve · [ ] change |
| c221 | q14 | GDPR Art. 88 | 0 | Not relevant: the article concerns Trattamento dei dati nell'ambito dei rapporti di lavoro. | [ ] approve · [ ] change |
| c222 | q14 | Code Art. 130 | 0 | Not relevant: the article concerns Comunicazioni indesiderate. | [ ] approve · [ ] change |
| c223 | q14 | GDPR Art. 40 | 0 | Not relevant: the article concerns Codici di condotta. | [ ] approve · [ ] change |
| c224 | q14 | Code Art. 2-sexies | 0 | Not relevant: the article concerns Trattamento di categorie particolari di dati personali necessario per motivi di interesse pubblico rilevante. | [ ] approve · [ ] change |
| c225 | q14 | Code Art. 160-bis | 0 | Not relevant: the article concerns (Validità, efficacia e utilizzabilità nel procedimento giudiziario di atti, documenti e provvedimenti basati sul trattamento di dati personali non conforme a disposizioni di legge o di Regolamento). | [ ] approve · [ ] change |
| c226 | q14 | Code Art. 110-bis | 0 | Not relevant: the article concerns (Trattamento ulteriore da parte di terzi dei dati personali a fini di ricerca scientifica o a fini statistici). | [ ] approve · [ ] change |
| c227 | q14 | GDPR Art. 47 | 0 | Not relevant: the article concerns Norme vincolanti d'impresa. | [ ] approve · [ ] change |
| c228 | q14 | GDPR Art. 38 | 0 | Not relevant: the article concerns Posizione del responsabile della protezione dei dati. | [ ] approve · [ ] change |
| c229 | q14 | Code Art. 1 | 0 | Not relevant: the article concerns (Oggetto). | [ ] approve · [ ] change |
| c230 | q14 | GDPR Art. 45 | 0 | Not relevant: the article concerns Trasferimento sulla base di una decisione di adeguatezza. | [ ] approve · [ ] change |
| c231 | q15 | Code Art. 166 | 1 | In the transcription: which violations carry the fines of GDPR Art. 83, and the procedure for adopting corrective and sanctioning measures; a specification of the corrective powers asked about. | **owner_reviewed** 2026-11-12: grade 1 |
| c232 | q15 | Code Art. 144 | 0 | Not relevant: in the transcription, reports to the Garante and measures taken of its own motion; a procedure, not a power. | **owner_reviewed** 2026-11-12: grade 0 |
| c233 | q15 | Code Art. 168 | 0 | Not relevant: the article concerns (Falsità nelle dichiarazioni al Garante e interruzione dell'esecuzione dei compiti o dell'esercizio dei poteri del Garante). | [ ] approve · [ ] change |
| c234 | q15 | Code Art. 143 | 0 | Not relevant: in the transcription, the decision on a complaint, a procedure in which the Art. 58 powers are used; it adds no power. | **owner_reviewed** 2026-11-12: grade 0 |
| c235 | q15 | Code Art. 156 | 0 | Not relevant: the article concerns Ruolo organico e personale. | [ ] approve · [ ] change |
| c236 | q15 | Code Art. 144-bis | 0 | Not relevant: the article concerns (Revenge porn). | [ ] approve · [ ] change |
| c237 | q15 | Code Art. 154 | 0 | Not relevant: the article concerns Compiti. | [ ] approve · [ ] change |
| c238 | q15 | Code Art. 170 | 0 | Not relevant: the article concerns Inosservanza di provvedimenti del Garante. | [ ] approve · [ ] change |
| c239 | q15 | Code Art. 140-bis | 0 | Not relevant: the article concerns Forme alternative di tutela. | [ ] approve · [ ] change |
| c240 | q15 | Code Art. 2-quaterdecies.1 | 0 | Not relevant: the article concerns (Procedura di notifica delle violazioni di dati personali da parte di microimprese). | [ ] approve · [ ] change |
| c241 | q15 | Code Art. 154-ter | 0 | Not relevant: in the transcription, the Garante's standing to bring proceedings; neither an investigative nor a corrective power. | **owner_reviewed** 2026-11-12: grade 0 |
| c242 | q15 | Code Art. 153 | 0 | Not relevant: the article concerns Garante per la protezione dei dati personali. | [ ] approve · [ ] change |
| c243 | q15 | Code Art. 110-bis | 0 | Not relevant: the article concerns (Trattamento ulteriore da parte di terzi dei dati personali a fini di ricerca scientifica o a fini statistici). | [ ] approve · [ ] change |
| c244 | q15 | Code Art. 111 | 0 | Not relevant: the article concerns (Regole deontologiche per trattamenti nell'ambito del rapporto di lavoro). | [ ] approve · [ ] change |
| c245 | q15 | Code Art. 2-ter | 0 | Not relevant: the article concerns Base giuridica per il trattamento di dati personali effettuato per l'esecuzione di un compito di interesse pubblico o connesso all'esercizio di pubblici poteri. | [ ] approve · [ ] change |
| c246 | q16 | Code Art. 58 | 0 | Not relevant: the article concerns Trattamenti di dati personali per fini di sicurezza nazionale o difesa. | [ ] approve · [ ] change |
| c247 | q16 | Code Art. 144-bis | 0 | Not relevant: the article concerns (Revenge porn). | [ ] approve · [ ] change |
| c248 | q16 | Code Art. 106 | 0 | Not relevant: the article concerns (Regole deontologiche per trattamenti a fini statistici o di ricerca scientifica). | [ ] approve · [ ] change |
| c249 | q16 | Code Art. 132 | 0 | Not relevant: the article concerns (Conservazione di dati di traffico per altre finalità). | [ ] approve · [ ] change |
| c250 | q16 | Code Art. 140-bis | 0 | Not relevant: the article concerns Forme alternative di tutela. | [ ] approve · [ ] change |
| c251 | q16 | GDPR Art. 40 | 0 | Not relevant: the article concerns Codici di condotta. | [ ] approve · [ ] change |
| c252 | q16 | GDPR Art. 23 | 0 | Not relevant: the article concerns Limitazioni. | [ ] approve · [ ] change |
| c253 | q16 | Code Art. 2-octies | 0 | Not relevant: the article concerns Principi relativi al trattamento di dati relativi a condanne penali e reati. | [ ] approve · [ ] change |
| c254 | q16 | Code Art. 2-terdecies | 0 | Not relevant: the article concerns (Diritti riguardanti le persone decedute). | [ ] approve · [ ] change |
| c255 | q16 | Code Art. 2-septies | 0 | Not relevant: the article concerns (Misure di garanzia per il trattamento dei dati genetici, biometrici e relativi alla salute). | [ ] approve · [ ] change |
| c256 | q16 | Code Art. 78 | 0 | Not relevant: the article concerns Informazioni del medico di medicina generale o del pediatra. | [ ] approve · [ ] change |
| c257 | q17 | Code Art. 9 | 0 | Not relevant: the article is marked repealed in the transcription. | [ ] approve · [ ] change |
| c258 | q17 | Code Art. 50 | 0 | Not relevant: the article concerns Notizie o immagini relative a minori. | [ ] approve · [ ] change |
| c259 | q17 | Code Art. 2-terdecies | 0 | Not relevant: the article concerns (Diritti riguardanti le persone decedute). | [ ] approve · [ ] change |
| c260 | q17 | Code Art. 108 | 0 | Not relevant: the article concerns (Sistema statistico nazionale). | [ ] approve · [ ] change |
| c261 | q17 | GDPR Art. 17 | 0 | Not relevant: the article concerns Diritto alla cancellazione («diritto all'oblio»). | [ ] approve · [ ] change |
| c262 | q17 | Code Art. 183 | 0 | Not relevant: the article concerns Norme abrogate. | [ ] approve · [ ] change |
| c263 | q17 | Code Art. 106 | 0 | Not relevant: the article concerns (Regole deontologiche per trattamenti a fini statistici o di ricerca scientifica). | [ ] approve · [ ] change |
| c264 | q17 | Code Art. 75 | 0 | Not relevant: in the transcription, conditions for processing in the health sector; a sector rule the question does not ask about. | **owner_reviewed** 2026-11-12: grade 0 |
| c265 | q17 | Code Art. 92 | 0 | Not relevant: the article concerns Cartelle cliniche. | [ ] approve · [ ] change |
| c266 | q17 | Code Art. 82 | 0 | Not relevant: the article concerns Emergenze e tutela della salute e dell'incolumità fisica. | [ ] approve · [ ] change |
| c267 | q17 | Code Art. 110-bis | 0 | Not relevant: the article concerns (Trattamento ulteriore da parte di terzi dei dati personali a fini di ricerca scientifica o a fini statistici). | [ ] approve · [ ] change |
| c268 | q18 | Code Art. 130 | 0 | Not relevant: the article concerns Comunicazioni indesiderate. | [ ] approve · [ ] change |
| c269 | q18 | Code Art. 2-sexies | 0 | Not relevant: the article concerns Trattamento di categorie particolari di dati personali necessario per motivi di interesse pubblico rilevante. | [ ] approve · [ ] change |
| c270 | q18 | GDPR Art. 64 | 0 | Not relevant: the article concerns Parere del comitato europeo per la protezione dei dati. | [ ] approve · [ ] change |
| c271 | q18 | Code Art. 132-quater | 0 | Not relevant: the article concerns Informazioni sui rischi. | [ ] approve · [ ] change |
| c272 | q18 | GDPR Art. 20 | 0 | Not relevant: the article concerns Diritto alla portabilità dei dati. | [ ] approve · [ ] change |
| c273 | q18 | GDPR Art. 9 | 0 | Not relevant: the article concerns Trattamento di categorie particolari di dati personali. | [ ] approve · [ ] change |
| c274 | q18 | Code Art. 2-octies | 0 | Not relevant: the article concerns Principi relativi al trattamento di dati relativi a condanne penali e reati. | [ ] approve · [ ] change |
| c275 | q18 | GDPR Art. 12 | 0 | Not relevant: the article concerns Informazioni, comunicazioni e modalità trasparenti per l'esercizio dei diritti dell'interessato. | [ ] approve · [ ] change |
| c276 | q18 | Code Art. 52 | 0 | Not relevant: the article concerns Dati identificativi degli interessati. | [ ] approve · [ ] change |
| c277 | q18 | GDPR Art. 40 | 0 | Not relevant: the article concerns Codici di condotta. | [ ] approve · [ ] change |
| c278 | q19 | Code Art. 105 | 0 | Not relevant: the article concerns Modalità di trattamento. | [ ] approve · [ ] change |
| c279 | q19 | GDPR Art. 34 | 0 | Not relevant: the article concerns Comunicazione di una violazione dei dati personali all'interessato. | [ ] approve · [ ] change |
| c280 | q19 | Code Art. 115 | 0 | Not relevant: the article concerns Telelavoro, lavoro agile e lavoro domestico. | [ ] approve · [ ] change |
| c281 | q19 | Code Art. 82 | 0 | Not relevant: the article concerns Emergenze e tutela della salute e dell'incolumità fisica. | [ ] approve · [ ] change |
| c282 | q19 | GDPR Art. 9 | 0 | Not relevant: the article concerns Trattamento di categorie particolari di dati personali. | [ ] approve · [ ] change |
| c283 | q19 | GDPR Art. 12 | 0 | Not relevant: the procedure for answering requests under Arts. 15-22; the question asks who may exercise the rights, not how. | **owner_reviewed** 2026-11-12: grade 0 |
| c284 | q19 | Code Art. 93 | 0 | Not relevant: the article concerns Certificato di assistenza al parto. | [ ] approve · [ ] change |
| c285 | q19 | Code Art. 101 | 0 | Not relevant: the article concerns Modalità di trattamento. | [ ] approve · [ ] change |
| c286 | q19 | GDPR Art. 18 | 0 | Not relevant: the article concerns Diritto di limitazione di trattamento. | [ ] approve · [ ] change |
| c287 | q19 | GDPR Art. 22 | 0 | Not relevant: the article concerns Processo decisionale automatizzato relativo alle persone fisiche, compresa la profilazione. | [ ] approve · [ ] change |
| c288 | q19 | Code Art. 97 | 0 | Not relevant: the article concerns (Ambito applicativo). | [ ] approve · [ ] change |
| c289 | q19 | Code Art. 99 | 0 | Not relevant: the article concerns (Durata del trattamento). | [ ] approve · [ ] change |
| c290 | q19 | GDPR Art. 85 | 0 | Not relevant: the article concerns Trattamento e libertà d'espressione e di informazione. | [ ] approve · [ ] change |
| c291 | q20 | GDPR Art. 64 | 0 | Not relevant: the article concerns Parere del comitato europeo per la protezione dei dati. | [ ] approve · [ ] change |
| c292 | q20 | GDPR Art. 57 | 0 | Not relevant: the article concerns Compiti. | [ ] approve · [ ] change |
| c293 | q20 | Code Art. 154 | 0 | Not relevant: the article concerns Compiti. | [ ] approve · [ ] change |
| c294 | q20 | GDPR Art. 42 | 0 | Not relevant: the article concerns Certificazione. | [ ] approve · [ ] change |
| c295 | q20 | GDPR Art. 4 | 0 | Not relevant: the article concerns Definizioni. | [ ] approve · [ ] change |
| c296 | q20 | Code Art. 2-octies | 0 | Not relevant: the article concerns Principi relativi al trattamento di dati relativi a condanne penali e reati. | [ ] approve · [ ] change |
| c297 | q20 | GDPR Art. 33 | 0 | Not relevant: the article concerns Notifica di una violazione dei dati personali all'autorità di controllo. | [ ] approve · [ ] change |
| c298 | q20 | GDPR Art. 58 | 0 | Not relevant: paragraph 2, letter i), names the power to impose fines by reference to Art. 83, on which the answer relies. | **owner_reviewed** 2026-11-12: grade 0 |
| c299 | q20 | GDPR Art. 12 | 0 | Not relevant: the article concerns Informazioni, comunicazioni e modalità trasparenti per l'esercizio dei diritti dell'interessato. | [ ] approve · [ ] change |
| c300 | q20 | Code Art. 107 | 0 | Not relevant: the article concerns (Trattamento di categorie particolari di dati personali). | [ ] approve · [ ] change |
| c301 | q21 | Code Art. 57 | 0 | Not relevant: the article concerns Disposizioni di attuazione. | [ ] approve · [ ] change |
| c302 | q21 | Code Art. 167-ter | 0 | Not relevant: the article concerns (Acquisizione fraudolenta di dati personali oggetto di trattamento su larga scala). | [ ] approve · [ ] change |
| c303 | q21 | GDPR Art. 79 | 0 | Not relevant: the article concerns Diritto a un ricorso giurisdizionale effettivo nei confronti del titolare del trattamento o del responsabile del trattamento. | [ ] approve · [ ] change |
| c304 | q22 | Code Art. 111 | 0 | Not relevant: the article concerns (Regole deontologiche per trattamenti nell'ambito del rapporto di lavoro). | [ ] approve · [ ] change |
| c305 | q22 | GDPR Art. 88 | 0 | Not relevant: the article concerns Trattamento dei dati nell'ambito dei rapporti di lavoro. | [ ] approve · [ ] change |
| c306 | q22 | Code Art. 111-bis | 0 | Not relevant: the article concerns (Informazioni in caso di ricezione di curriculum). | [ ] approve · [ ] change |
| c307 | q22 | GDPR Art. 54 | 0 | Not relevant: the article concerns Norme sull'istituzione dell'autorità di controllo. | [ ] approve · [ ] change |
| c308 | q22 | Code Art. 2-undecies | 0 | Not relevant: the article concerns Limitazioni ai diritti dell'interessato. | [ ] approve · [ ] change |
| c309 | q22 | GDPR Art. 96 | 0 | Not relevant: the article concerns Rapporto con accordi precedentemente conclusi. | [ ] approve · [ ] change |
| c310 | q22 | GDPR Art. 82 | 0 | Not relevant: the article concerns Diritto al risarcimento e responsabilità. | [ ] approve · [ ] change |
| c311 | q22 | Code Art. 113 | 0 | Not relevant: the article concerns Raccolta di dati e pertinenza. | [ ] approve · [ ] change |
| c312 | q22 | Code Art. 82 | 0 | Not relevant: the article concerns Emergenze e tutela della salute e dell'incolumità fisica. | [ ] approve · [ ] change |
| c313 | q22 | Code Art. 52 | 0 | Not relevant: the article concerns Dati identificativi degli interessati. | [ ] approve · [ ] change |
| c314 | q23 | Code Art. 130 | 0 | Not relevant: the article concerns Comunicazioni indesiderate. | [ ] approve · [ ] change |
| c315 | q23 | GDPR Art. 88 | 0 | Not relevant: the article concerns Trattamento dei dati nell'ambito dei rapporti di lavoro. | [ ] approve · [ ] change |
| c316 | q23 | Code Art. 82 | 0 | Not relevant: the article concerns Emergenze e tutela della salute e dell'incolumità fisica. | [ ] approve · [ ] change |
| c317 | q23 | Code Art. 2-ter | 0 | Not relevant: the article concerns Base giuridica per il trattamento di dati personali effettuato per l'esecuzione di un compito di interesse pubblico o connesso all'esercizio di pubblici poteri. | [ ] approve · [ ] change |
| c318 | q23 | Code Art. 121 | 0 | Not relevant: the article concerns Servizi interessati e definizioni. | [ ] approve · [ ] change |
| c319 | q23 | GDPR Art. 34 | 0 | Not relevant: the article concerns Comunicazione di una violazione dei dati personali all'interessato. | [ ] approve · [ ] change |
| c320 | q23 | GDPR Art. 12 | 0 | Not relevant: the article concerns Informazioni, comunicazioni e modalità trasparenti per l'esercizio dei diritti dell'interessato. | [ ] approve · [ ] change |
| c321 | q23 | Code Art. 2-quaterdecies.1 | 0 | Not relevant: the article concerns (Procedura di notifica delle violazioni di dati personali da parte di microimprese). | [ ] approve · [ ] change |
| c322 | q24 | Code Art. 2-octies | 0 | Not relevant: the article concerns Principi relativi al trattamento di dati relativi a condanne penali e reati. | [ ] approve · [ ] change |
| c323 | q24 | GDPR Art. 83 | 0 | Not relevant: the article concerns Condizioni generali per infliggere sanzioni amministrative pecuniarie. | [ ] approve · [ ] change |
| c324 | q24 | GDPR Art. 84 | 0 | Not relevant: the article concerns Sanzioni. | [ ] approve · [ ] change |
| c325 | q24 | Code Art. 168 | 0 | Not relevant: the article concerns (Falsità nelle dichiarazioni al Garante e interruzione dell'esecuzione dei compiti o dell'esercizio dei poteri del Garante). | [ ] approve · [ ] change |
| c326 | q24 | Code Art. 2-bis | 0 | Not relevant: the article concerns (Autorità di controllo). | [ ] approve · [ ] change |
| c327 | q24 | Code Art. 141 | 0 | Not relevant: the article concerns Reclamo al Garante. | [ ] approve · [ ] change |
| c328 | q24 | Code Art. 156 | 0 | Not relevant: the article concerns Ruolo organico e personale. | [ ] approve · [ ] change |
| c329 | q24 | Code Art. 102 | 0 | Not relevant: the article concerns Regole deontologiche per il trattamento a fini di archiviazione nel pubblico interesse o di ricerca storica. | [ ] approve · [ ] change |
| c330 | q24 | Code Art. 127 | 0 | Not relevant: the article concerns Chiamate di disturbo e di emergenza. | [ ] approve · [ ] change |
| c331 | q24 | Code Art. 129 | 0 | Not relevant: the article concerns Elenchi dei contraenti. | [ ] approve · [ ] change |

### 2.5 Unchanged v1 records

356 judgments are carried over from legal-v1 unchanged, with their v1 provenance.
- **Reviewed:** q05 GDPR Art. 23, reviewed at Gate 2 (`owner_reviewed`; kept at 1). Only its
  review fields changed.
- **Not reviewed:** the other 355, which are candidates. You may approve them by question, or
  list exceptions.
- **Where to look:** their grades and rationales are in `judgments.jsonl`, and the AI
  pre-review of v1 discusses the borderline ones (`legal-v1-human-review.md`).

### 2.6 Gate 2 review changes, c332–c348

Each line has `decision` «review» and `basis` «owner». It is appended after the earlier lines;
no earlier line was edited.

| Change | Question | Article | Change | v2 rationale | Owner review |
|---|---|---|---|---|---|
| c332 | q06 | Code Art. 110 | grade 0 → 1 | In the transcription: paragraph 1 requires an impact assessment under GDPR Arts. 35 and 36 for medical research without consent, and Art. 166(1) sanctions failing to carry it out; a case where an assessment is required. | **owner_reviewed** 2026-11-12: grade 1 |
| c333 | q15 | Code Art. 154-bis | grade 1 → 0 | Not relevant: in the transcription, powers to adopt guidelines and approve deontological rules, cooperation, publication and simplification; not the investigative or corrective powers asked about. | **owner_reviewed** 2026-11-12: grade 0 |
| c334 | q15 | Code Art. 166 | rationale only | In the transcription: paragraphs 1-3 list the Code violations that carry the fines of GDPR Art. 83, and make the Garante the body competent for the corrective measures of Art. 58(2) and for the fines; a specification of the corrective powers asked about. | **owner_reviewed** 2026-11-12: grade 1 |
| c335 | q09 | GDPR Art. 23 | added, grade 1 | Paragraph 1: Union or Member State law may restrict the obligations of Arts. 12-22, the information of Art. 13 included; an exception to the obligation asked about. | **owner_reviewed** 2026-11-12: grade 1 |
| c336 | q10 | GDPR Art. 23 | added, grade 1 | Paragraph 1: Union or Member State law may restrict the rights of Arts. 12-22, the right of access included; an exception to the right asked about. | **owner_reviewed** 2026-11-12: grade 1 |
| c337 | q11 | GDPR Art. 23 | added, grade 1 | Paragraph 1: Union or Member State law may restrict the rights of Arts. 12-22, the right to erasure included; an exception to the right asked about. | **owner_reviewed** 2026-11-12: grade 1 |
| c338 | q12 | GDPR Art. 23 | added, grade 1 | Paragraph 1: Union or Member State law may restrict the rights of Arts. 12-22, the right to data portability included; an exception to the right asked about. | **owner_reviewed** 2026-11-12: grade 1 |
| c339 | q13 | GDPR Art. 23 | added, grade 1 | Paragraph 1: Union or Member State law may restrict the rights of Arts. 12-22, the right to object included; an exception to the right asked about. | **owner_reviewed** 2026-11-12: grade 1 |
| c340 | q10 | Code Art. 2-undecies | added, grade 1 | In the transcription: the rights of Arts. 15-22, access included, cannot be exercised by request where this could prejudice the interests it lists; an exception to the right asked about. | **owner_reviewed** 2026-11-12: grade 1 |
| c341 | q11 | Code Art. 2-undecies | added, grade 1 | In the transcription: the rights of Arts. 15-22, erasure included, cannot be exercised by request where this could prejudice the interests it lists; an exception to the right asked about. | **owner_reviewed** 2026-11-12: grade 1 |
| c342 | q12 | Code Art. 2-undecies | added, grade 1 | In the transcription: the rights of Arts. 15-22, data portability included, cannot be exercised by request where this could prejudice the interests it lists; an exception to the right asked about. | **owner_reviewed** 2026-11-12: grade 1 |
| c343 | q05 | Code Art. 2-duodecies | added, grade 1 | In the transcription: for processing for reasons of justice, the rights and obligations of Arts. 12-22 and 34, the communication of a breach included, are governed within the limits of the rules of those proceedings; an exception to the obligation asked about. | **owner_reviewed** 2026-11-12: grade 1 |
| c344 | q09 | Code Art. 2-duodecies | added, grade 1 | In the transcription: for processing for reasons of justice, the rights and obligations of Arts. 12-22 and 34, the information of Art. 13 included, are governed within the limits of the rules of those proceedings; an exception to the obligation asked about. | **owner_reviewed** 2026-11-12: grade 1 |
| c345 | q10 | Code Art. 2-duodecies | added, grade 1 | In the transcription: for processing for reasons of justice, the rights and obligations of Arts. 12-22 and 34, the right of access included, are governed within the limits of the rules of those proceedings; an exception to the right asked about. | **owner_reviewed** 2026-11-12: grade 1 |
| c346 | q11 | Code Art. 2-duodecies | added, grade 1 | In the transcription: for processing for reasons of justice, the rights and obligations of Arts. 12-22 and 34, the right to erasure included, are governed within the limits of the rules of those proceedings; an exception to the right asked about. | **owner_reviewed** 2026-11-12: grade 1 |
| c347 | q12 | Code Art. 2-duodecies | added, grade 1 | In the transcription: for processing for reasons of justice, the rights and obligations of Arts. 12-22 and 34, the right to data portability included, are governed within the limits of the rules of those proceedings; an exception to the right asked about. | **owner_reviewed** 2026-11-12: grade 1 |
| c348 | q13 | Code Art. 2-duodecies | added, grade 1 | In the transcription: for processing for reasons of justice, the rights and obligations of Arts. 12-22 and 34, the right to object included, are governed within the limits of the rules of those proceedings; an exception to the right asked about. | **owner_reviewed** 2026-11-12: grade 1 |

**At a later review, record:**
- the records approved (by change ID, by question, or as a list);
- the changes you want, as new grades or wording;
- the name to record in `reviewed_by`, and the date for `reviewed_on`.
