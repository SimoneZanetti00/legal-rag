# Benchmark answers-v0: owner review sheet

> **Review record.** Decisions by Simone Zanetti (owner) on 2026-11-18, applied the same day
> to `questions.jsonl` and `expectations.jsonl` as `owner_reviewed`. An AI assistant (Claude,
> claude.ai) gave a second opinion on each row; the decisions are the owner's. a01–a13 are
> reviewed; a14–a22 are not reviewed yet and stay `candidate`. The SHA-256 values below are
> those of the files the sheet was generated from, before the review.
>
> - Generated on 2026-11-16 by Claude Code (AI assistant) from the two files below. It changes neither file.
> - `data/evaluation/answers-v0/questions.jsonl`: 22 questions, SHA-256 `67a206011d4d4fa66b61dd05f73ef6fce079ed5377f1ac098e25984c2c6d0648`
> - `data/evaluation/answers-v0/expectations.jsonl`: 81 rows, SHA-256 `e2915ad8fa06940a0da4b46239d98d5c333a712911b20045fc80ad9790276fc3`
> - Every question and row is currently `candidate`. The scorer counts only `owner_reviewed` or `expert_reviewed`.

## How to fill it in

- **Row** is the line number in `expectations.jsonl`. Decisions are applied by that number, so do not renumber.
- **Decision column**, one of:
  - `ok`: the row becomes `owner_reviewed` as it is;
  - `change: …`: say what changes (role, unit, article, rationale); the row is then applied and marked `owner_reviewed`;
  - `remove`: the row is deleted;
  - `unsure: …`: the row stays `candidate`, with your reason recorded in `REVIEW_SHEET.md`.
- **Question decision** (above each table): `ok`, `change: …` (for example the expected outcome or reason) or `unsure: …`.
- **Add a row:** write it under the table as `add: <instrument> <article> <unit> <role> — <rationale>`.
- A question is scored only when the question and all its rows are reviewed.

Instruments: **GDPR** = `eu-reg-2016-679` (2016 OJ original, not consolidated); **Codice** = `it-dlgs-2003-196` (user transcription, unverified). Unit «—» means the whole article. Roles: **core** = a complete answer must rest on it; **supporting** = useful, not required.

## Questions

### a01 · dev · breach

**Question:** When is a personal data breach required to be notified to the Italian Data Protection Authority?

**Expected outcome:** `answer`

**Time-sensitive:** valid as of 2026-11-08; basis: Digital Omnibus COM(2025) 837, procedure 2025/0360(COD): not adopted (EP procedure file: awaiting committee decision). Re-check before every benchmark run; if adopted, rewrite the expectation and the expected answer

**Question decision:** ok

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 1 | GDPR | 33 | par. 1 | core | Duty, 72-hour deadline, risk exception, competent authority under Art. 55 | ok |
| 2 | GDPR | 55 | par. 1 | supporting | Competent supervisory authority: territorial competence; supporting: it does not say when notification is due | ok |
| 3 | Codice | 2-bis | — | supporting | In Italy the supervisory authority is the Garante; supporting, as in a10: the question names the authority, and when notification is due is answered by GDPR Art. 33(1). Privacy Code: user transcription, not verified against an official text. | ok |
| 4 | GDPR | 4 | point 12 | supporting | Definition of personal data breach | ok |
| 5 | GDPR | 33 | par. 2 | supporting | Processor informs the controller, does not notify the authority | ok |
| 6 | GDPR | 34 | — | supporting | Separate duty towards data subjects (high risk) | ok |

### a02 · dev · definition

**Question:** Che cos'è una violazione dei dati personali?

**Expected outcome:** `answer`

**Question decision:** ok

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 7 | GDPR | 4 | point 12 | core | Legal definition | ok |

### a03 · dev · breach

**Question:** Quando il titolare deve comunicare una violazione dei dati personali agli interessati?

**Expected outcome:** `answer`

**Question decision:** ok

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 8 | GDPR | 34 | par. 1 | core | High-risk threshold, without undue delay | ok |
| 9 | GDPR | 34 | par. 3 | core | Exemptions: encryption, subsequent measures, disproportionate effort | ok |
| 10 | GDPR | 33 | — | supporting | Distinct from notification to the authority | ok |

add: GDPR 34 par. 4 supporting — the supervisory authority may require the communication or decide that a condition of par. 3 is met (applied as row 82)

### a04 · dev · authority

**Question:** Quale autorità di controllo è competente in Italia?

**Expected outcome:** `answer`

**Notes:** Code Art. 2-bis is core because its text names the Garante as the supervisory authority of GDPR Art. 51; Code Art. 153 concerns the Garante as an institution and GDPR Art. 55 its competence, so both are supporting.

**Question decision:** ok

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 11 | Codice | 2-bis | — | core | Garante identified as the supervisory authority. Privacy Code: user transcription, not verified against an official text. | ok |
| 12 | GDPR | 51 | par. 1 | supporting | Member States provide one or more supervisory authorities | ok |
| 13 | Codice | 153 | — | supporting | Garante per la protezione dei dati personali (institution). Privacy Code: user transcription, not verified against an official text. | ok |
| 14 | GDPR | 55 | — | supporting | Competence | ok |

### a05 · dev · overview

**Question:** What are the main principles governing the processing of personal data under the GDPR?

**Expected outcome:** `answer`

**Question decision:** ok

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 15 | GDPR | 5 | par. 1 | core | Six principles (a)-(f) | ok |
| 16 | GDPR | 5 | par. 2 | core | Accountability | ok |

### a06 · dev · overview

**Question:** What rights do individuals have regarding their personal data under the GDPR?

**Expected outcome:** `answer`

**Notes:** Information duties (GDPR Arts. 12-14) are kept supporting: they are the controller's duties through which the data subject is informed, not rights the data subject exercises. GDPR Art. 7(3), the right to withdraw consent, is supporting because it exists only where consent is the legal basis.

**Question decision:** ok

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 17 | GDPR | 15 | — | core | Access | ok |
| 18 | GDPR | 16 | — | core | Rectification | ok |
| 19 | GDPR | 17 | — | core | Erasure | ok |
| 20 | GDPR | 18 | — | core | Restriction | ok |
| 21 | GDPR | 20 | — | core | Portability | ok |
| 22 | GDPR | 21 | — | core | Objection | ok |
| 23 | GDPR | 22 | — | core | Automated decisions, profiling | ok |
| 24 | GDPR | 12 | — | supporting | Modalities, deadlines, free of charge | ok |
| 25 | GDPR | 13 | — | supporting | Information (collected from the data subject) | ok |
| 26 | GDPR | 14 | — | supporting | Information (not collected from the data subject) | ok |
| 27 | GDPR | 19 | — | supporting | Notification of rectification/erasure/restriction | ok |
| 28 | GDPR | 77 | — | supporting | Complaint to a supervisory authority | ok |
| 29 | GDPR | 79 | — | supporting | Judicial remedy against controller/processor | ok |
| 30 | GDPR | 82 | — | supporting | Compensation | ok |
| 31 | GDPR | 7 | par. 3 | supporting | Right to withdraw consent at any time, where consent is the legal basis | ok |

### a07 · dev · overview

**Question:** What are the main obligations of a data controller under the GDPR?

**Expected outcome:** `answer`

**Notes:** Overview criterion (owner's decision, 2026-11-16): core = accountability and the controller's main obligations, whether they bind every controller (Arts. 5(2), 24, 25, 30, 32) or are triggered by a condition (Art. 33 on a breach, Art. 34 on a breach likely to result in a high risk to data subjects, Art. 35 on likely high risk, Art. 37 in the listed cases). This v0 overview question does not require exhaustive coverage of every controller obligation. Supporting: the information duties (Arts. 12-14), which an answer may name but need not, and Arts. 26 and 28, which govern how the controller's responsibility is shared with joint controllers or delegated to processors. Obligations not listed are neither required nor penalised. See REVIEW_SHEET.md, 'Core in overview questions'.

**Question decision:** ok

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 32 | GDPR | 5 | par. 2 | core | Accountability | ok |
| 33 | GDPR | 24 | — | core | Responsibility, technical and organisational measures | ok |
| 34 | GDPR | 25 | — | core | Data protection by design and by default | ok |
| 35 | GDPR | 30 | — | core | Records of processing activities | ok |
| 36 | GDPR | 32 | — | core | Security of processing | ok |
| 37 | GDPR | 33 | — | core | Breach notification to the authority | ok |
| 38 | GDPR | 34 | — | core | Communication to data subjects; core: a conditional obligation (a breach likely to result in a high risk), like Art. 33 | ok |
| 39 | GDPR | 35 | — | core | DPIA | ok |
| 40 | GDPR | 37 | — | core | DPO designation | ok |
| 41 | GDPR | 26 | — | supporting | Joint controllers | ok |
| 42 | GDPR | 28 | — | supporting | Choice of and contract with processors | ok |
| 43 | GDPR | 12 | — | supporting | Facilitating data subject rights | ok |
| 44 | GDPR | 13 | — | supporting | Information to be provided where personal data are collected from the data subject; supporting: a v0 overview answer may name it but is not required to | ok |
| 45 | GDPR | 14 | — | supporting | Information to be provided where personal data have not been obtained from the data subject; supporting: a v0 overview answer may name it but is not required to | ok |

### a08 · dev · lawfulness

**Question:** Can a company process personal data without the consent of the data subject?

**Expected outcome:** `answer`

**Question decision:** ok

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 46 | GDPR | 6 | par. 1 | core | Six legal bases; consent is one of them; (b) contract is key for companies | ok |
| 47 | GDPR | 9 | par. 2 | supporting | Special categories: separate conditions | ok |
| 48 | GDPR | 10 | — | supporting | Criminal convictions data | ok |
| 49 | GDPR | 7 | — | supporting | Conditions where consent is the basis | ok |
| 50 | GDPR | 21 | — | supporting | Right to object, e.g. against (e)/(f) | ok |

### a09 · dev · out_of_scope

**Question:** What are the legal requirements for establishing a company in Germany?

**Expected outcome:** `abstain (out_of_scope)`

**Question decision:** ok

*No expectation rows (no provision is expected).*

### a10 · dev · breach

**Question:** Entro quanto tempo va notificata una violazione dei dati personali al Garante?

**Expected outcome:** `answer`

**Time-sensitive:** valid as of 2026-11-08; basis: Digital Omnibus COM(2025) 837, procedure 2025/0360(COD): not adopted (EP procedure file: awaiting committee decision). Re-check before every benchmark run; if adopted, rewrite the expectation and the expected answer

**Question decision:** ok

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 51 | GDPR | 33 | par. 1 | core | Without undue delay and, where feasible, within 72 hours; reasons for delay | ok |
| 52 | Codice | 2-bis | — | supporting | The authority is the Garante. Privacy Code: user transcription, not verified against an official text. | ok |

### a11 · dev · false_premise

**Question:** Il responsabile del trattamento deve notificare la violazione al Garante?

**Expected outcome:** `answer`

**Notes:** False premise: the processor informs the controller (GDPR Art. 33(2)) and assists it (Art. 28(3)(f)); notification to the authority is the controller's duty (Art. 33(1)).

**Question decision:** ok

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 53 | GDPR | 33 | par. 2 | core | No: the processor informs the controller without undue delay | ok |
| 54 | GDPR | 33 | par. 1 | supporting | Notification is the controller's duty | ok |
| 55 | GDPR | 28 | par. 3, letter f | supporting | The processor assists the controller with the obligations of Arts. 32-36, breach notification included; it does not notify the authority itself | ok |

### a12 · dev · false_premise

**Question:** Il GDPR prevede un termine di 96 ore per notificare una violazione dei dati personali?

**Expected outcome:** `answer`

**Notes:** False premise: the text in force sets 72 hours (GDPR Art. 33(1)); 96 hours appears only in the Digital Omnibus proposal, which the answer must not present as law.

**Time-sensitive:** valid as of 2026-11-08; basis: Digital Omnibus COM(2025) 837, procedure 2025/0360(COD): not adopted (EP procedure file: awaiting committee decision). Re-check before every benchmark run; if adopted, rewrite the expectation and the expected answer

**Question decision:** ok

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 56 | GDPR | 33 | par. 1 | core | Text in force: 72 hours. 96 hours appears only in the Digital Omnibus proposal COM(2025) 837, not adopted; the answer must say so without presenting it as law | ok |

### a13 · test · definition

**Question:** Che cos'è un dato personale secondo il GDPR?

**Expected outcome:** `answer`

**Question decision:** ok

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 57 | GDPR | 4 | point 1 | core | Definition of personal data and data subject | ok |

### a14 · test · obligations

**Question:** Quando è obbligatoria una valutazione d'impatto sulla protezione dei dati?

**Expected outcome:** `answer`

**Notes:** The Garante's own list of processing operations requiring a DPIA (adopted under GDPR Art. 35(4)) is not in the corpus.

**Question decision:** not reviewed yet (2026-11-18); stays `candidate`

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 58 | GDPR | 35 | par. 1 | core | Likely high risk |  |
| 59 | GDPR | 35 | par. 3 | core | Cases where it is required in particular |  |
| 60 | GDPR | 35 | par. 4 | supporting | Lists by the supervisory authority; the Garante's own list is not in the corpus |  |
| 61 | GDPR | 36 | — | supporting | Prior consultation |  |

### a15 · test · obligations

**Question:** Quando un'azienda deve designare un responsabile della protezione dei dati (DPO)?

**Expected outcome:** `answer`

**Question decision:** not reviewed yet (2026-11-18); stays `candidate`

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 62 | GDPR | 37 | par. 1 | core | Three cases (a)-(c) |  |
| 63 | GDPR | 38 | — | supporting | Position of the DPO |  |
| 64 | GDPR | 39 | — | supporting | Tasks of the DPO |  |

### a16 · test · rights

**Question:** Posso chiedere a un'azienda di cancellare i miei dati? In quali casi?

**Expected outcome:** `answer`

**Question decision:** not reviewed yet (2026-11-18); stays `candidate`

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 65 | GDPR | 17 | par. 1 | core | Grounds (a)-(f) |  |
| 66 | GDPR | 17 | par. 3 | core | Exceptions |  |
| 67 | GDPR | 12 | par. 3 | supporting | One-month deadline |  |

### a17 · test · italian_specific

**Question:** A partire da quale età un minore può prestare da solo il consenso ai servizi della società dell'informazione in Italia?

**Expected outcome:** `answer`

**Notes:** Tests use of the Privacy Code where it changes the answer (14 years in Italy).

**Question decision:** not reviewed yet (2026-11-18); stays `candidate`

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 68 | GDPR | 8 | par. 1 | core | 16 years, Member States may lower to not below 13 |  |
| 69 | Codice | 2-quinquies | — | core | Italy: 14 years. Privacy Code: user transcription, not verified against an official text. |  |

### a18 · test · historical

**Question:** Qual era la disciplina applicabile alla notifica di una violazione dei dati personali avvenuta nel 2017?

**Expected outcome:** `answer_limited`

**Notes:** Historical question. The corpus states the GDPR's application date (Art. 99(2): from 25 May 2018), so a correct answer can say the GDPR did not govern a breach in 2017. It cannot establish the regime then in force (the pre-2018 Privacy Code and the Garante's measures are not in the corpus), so the expected outcome is answer_limited.

**Question decision:** not reviewed yet (2026-11-18); stays `candidate`

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 70 | GDPR | 99 | par. 2 | core | The GDPR applies from 25 May 2018, so it did not govern a breach in 2017 |  |

### a19 · test · out_of_scope

**Question:** Quali sono i requisiti per il licenziamento per giusta causa in Italia?

**Expected outcome:** `abstain (out_of_scope)`

**Question decision:** not reviewed yet (2026-11-18); stays `candidate`

*No expectation rows (no provision is expected).*

### a20 · test · transfers

**Question:** Si possono trasferire dati personali verso un paese terzo senza una decisione di adeguatezza?

**Expected outcome:** `answer`

**Question decision:** not reviewed yet (2026-11-18); stays `candidate`

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 71 | GDPR | 46 | — | core | Appropriate safeguards |  |
| 72 | GDPR | 49 | — | core | Derogations for specific situations |  |
| 73 | GDPR | 45 | — | supporting | Adequacy decisions |  |
| 74 | GDPR | 44 | — | supporting | General principle |  |
| 75 | GDPR | 47 | — | supporting | Binding corporate rules |  |

### a21 · test · sanctions

**Question:** Qual è la sanzione massima per la violazione dell'obbligo di notificare una violazione dei dati personali?

**Expected outcome:** `answer`

**Question decision:** not reviewed yet (2026-11-18); stays `candidate`

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 76 | GDPR | 83 | par. 4 | core | Up to EUR 10 million or, for an undertaking, up to 2% of total worldwide annual turnover of the preceding year, whichever is higher; covers obligations under Arts. 8, 11, 25-39, 42, 43. The answer must keep the maximum apart from the criteria for setting the actual fine (Art. 83(2)) |  |
| 77 | GDPR | 83 | par. 2 | supporting | Criteria for setting the fine |  |

### a22 · test · italian_specific

**Question:** Come si presenta un reclamo al Garante e cosa prevede il Codice privacy?

**Expected outcome:** `answer`

**Notes:** Tests use of the Privacy Code: Art. 141 gives the route, Art. 142 how to lodge the complaint, Art. 143 how it is decided.

**Question decision:** not reviewed yet (2026-11-18); stays `candidate`

| Row | Instrument | Article | Unit | Role | Rationale | Decision |
|---|---|---|---|---|---|---|
| 78 | GDPR | 77 | — | core | Right to lodge a complaint |  |
| 79 | Codice | 141 | — | core | Reclamo al Garante: the route, by reference to GDPR Art. 77. Privacy Code: user transcription, not verified against an official text. |  |
| 80 | Codice | 142 | — | core | Proposizione del reclamo: its content, signature and attachments, i.e. how to lodge the complaint. Privacy Code: user transcription, not verified against an official text. |  |
| 81 | Codice | 143 | — | supporting | Decisione del reclamo: how the Garante decides the complaint. Privacy Code: user transcription, not verified against an official text. |  |
