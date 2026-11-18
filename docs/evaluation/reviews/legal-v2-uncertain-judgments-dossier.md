# legal-v2: dossier on the 12 uncertain judgments (Gate 2 preparation)

*Prepared by Claude (AI assistant) in a Claude Code session on 2026-11-11, for the owner's
review at Gate 2. It was prepared read-only. It supports
[`legal-v2-review-checklist.md`](legal-v2-review-checklist.md), Part 2, §2.2.*

*Updated on 2026-11-12: the owner confirmed the decisions of §0 at Gate 2, and they have been
applied to `legal-v2`.*
- *28 judgments are now `owner_reviewed` (reviewer Simone Zanetti, 2026-11-12). The other 645
  judgments and all 24 questions remain `candidate`.*
- *Owner review is not expert legal validation. It establishes nothing about the validity or
  currency of the Privacy Code transcription, or of the 2016 GDPR text.*

**What this document is, and is not:**
- **Not a review.** It is not an owner review and not an expert legal review. The proposals
  below are an AI assistant's reading of the approved grade policy D1 and its five working rules
  (plan §2.0; guidelines, "Relevance grades"). Your decisions on them will be owner decisions;
  they will not be an expert legal validation.
- **Textual relevance only.** The grades concern the textual relevance of provisions in this
  corpus, for these questions. Presence in the corpus says nothing about validity or force.
- **The Privacy Code is an unverified user transcription**
  (`it-dlgs-2003-196@transcription-vigente-2026-11-05`; the label is its name, not a
  verification). The GDPR text is the 2016 original publication.
- **Sources.** Only `data/evaluation/legal-v2/` and the recorded build
  `build-f76ff6031f2fc82c4852f0a2bde27807`. No external source was used.
- **Nothing measured.** No metric was computed, and no ranking position is shown.
- **Quotations** reproduce the corpus text.
  - The «(( … ))» marks are the transcription's own amendment markers.
  - Where the GDPR text in the build has a line-break hyphen inside a word, it is shown as
    «- ».

**How each entry is laid out:** 1 question, 2 search query, 3 provision, 4 current grade, 5
current rationale, 6 passage, 7 relation to the question, 8 classification, 9 proposed grade,
10 uncertainty and dependencies.

**Classification used in field 8:**

| Class | Meaning |
|---|---|
| **A** | directly answers the question (grade 2) |
| **B** | contributes a necessary condition, an exception, a procedure, a prerequisite or a relevant specification (grade 1) |
| **C** | only indirectly related (grade 0) |
| **D** | not relevant (grade 0) |

## 0. Owner decisions at Gate 2 (confirmed and applied 2026-11-12)

**What these are.**
- **Confirmed.** These are the owner's decisions, taken after reading this dossier and
  confirmed at Gate 2 by Simone Zanetti on 2026-11-12.
- **Applied to `legal-v2`:**
  - as review lines c332–c348 in `changes.jsonl` (`decision` «review», `basis` «owner»), appended
    after the earlier lines, none of which was edited;
  - as the review status `owner_reviewed`, with `reviewed_by` and `reviewed_on`, on the 28 records
    named below. No other record was marked reviewed.
- **Not expert review.** They are owner decisions on textual relevance, not an expert legal
  review.

### 0.1 The 12 uncertain judgments (all `owner_reviewed`)

| Change | Q | Provision | Grade before Gate 2 | Final grade | Note |
|---|---|---|---|---|---|
| c141 | q06 | GDPR Art. 9 | 1 | **1** | rule 2 (entry 1) |
| c130 | q06 | Code Art. 110 | 0 | **1** | revised 0 → 1 (c332); the reading of rule 5 is now in the guidelines (§0.5) |
| c213 | q13 | Code Art. 2-undecies | 1 | **1** | kept, with Option A (§0.2) |
| c231 | q15 | Code Art. 166 | 1 | **1** | on paragraphs 1–3; rationale reworded to say so (c334, §0.3) |
| c232 | q15 | Code Art. 144 | 0 | **0** | procedure (§0.3) |
| c234 | q15 | Code Art. 143 | 0 | **0** | procedure (§0.3) |
| c241 | q15 | Code Art. 154-ter | 0 | **0** | standing in court (§0.3) |
| c103 | q04 | GDPR Art. 51 | 0 | **0** | — |
| c181 | q09 | Code Art. 111-bis | 0 | **0** | — |
| c264 | q17 | Code Art. 75 | 0 | **0** | — |
| c283 | q19 | GDPR Art. 12 | 0 | **0** | — |
| c298 | q20 | GDPR Art. 58 | 0 | **0** | — |

Only c130 changed grade among the 12.

### 0.2 Restrictions of data-subject rights: Option A, as revised (applied: 14 additions)

**Kept at 1, and `owner_reviewed`:** c213 (q13, Code Art. 2-undecies) and the existing q05 GDPR
Art. 23 judgment.

**Added at grade 1 and `owner_reviewed`: 14 judgments (c335–c348):**

| Provision | Questions | Count |
|---|---|---|
| GDPR Art. 23 | q09, q10, q11, q12, q13 | 5 |
| Code Art. 2-undecies | q10, q11, q12 | 3 |
| Code Art. 2-duodecies | q05, q09, q10, q11, q12, q13 | 6 |

**Resolved at Gate 2: GDPR Art. 23 is included for q09 (c335).**
- **The history.** A provisional version of this decision excluded q09 from GDPR Art. 23. That
  rested on reading q09's article (GDPR Art. 13) as outside Art. 23's scope.
- **The corpus text, which decided it.** Art. 23(1) covers «la portata degli obblighi e dei
  diritti di cui agli articoli da 12 a 22 e 34». Art. 13 lies within 12–22.
- **The provisions compared:**

  | Provision | Range it covers | Art. 13 within it |
  |---|---|---|
  | GDPR Art. 23(1) | Arts. 12–22 and 34 | yes |
  | Code Art. 2-duodecies | Arts. 12–22 and 34 | yes |
  | Code Art. 2-undecies | Arts. 15–22 | no |

  The provision whose scope excludes Art. 13 is Code Art. 2-undecies. That is why q09 is
  already left out of Code Art. 2-undecies (§4).
- **The consequence.** On the text, q09 falls within GDPR Art. 23 exactly as it falls within Code
  Art. 2-duodecies.
- **The final decision.** The owner applied the same text-based scope to both: GDPR Art. 23 is
  included for q09, which gives 14 additions.

### 0.3 q15: the strict reading

The question asks specifically about investigative and corrective powers («poteri di indagine
e correttivi»).

| Provision | Final grade | Why |
|---|---|---|
| Code Art. 166 (c231) | **1** | Paragraphs 1–3 specify the Garante's competence for corrective measures and fines, and the Code violations that carry the Art. 83 fines. The rationale now says so (c334). |
| Code Arts. 143 (c234) and 144 (c232) | **0** | Procedural: how and when the Art. 58 powers are used. They add no investigative or corrective power. |
| Code Art. 154-ter (c241) | **0** | Standing to bring legal proceedings is neither an investigative nor a corrective power. |
| Code Art. 154-bis (not one of the 12; graded 1 before Gate 2) | **0** (c333) | Its powers are not the investigative or corrective powers asked about: guidelines, deontological rules, cooperation, publication, simplification. |

**Code Art. 154-bis was inherited from v1.**
- v1 graded it 1 as «Further powers of the Garante under GDPR Art. 58(6)».
- legal-v2 kept that grade unchanged («checked and kept», plan §2.5).
- It was never re-examined against the strict reading of q15, and it is not retained merely for
  backward consistency.
- Applied as review line c333, for a record carried over from v1: q15, Code Art. 154-bis,
  1 → 0. The record is now `owner_reviewed`.

**Unchanged under this reading:** GDPR Art. 58 (2), GDPR Art. 83 (1, the fining power) and Code
Arts. 157 and 158 (1, investigative powers). These records were not part of the Gate 2 review,
and they remain `candidate`.

### 0.4 legal-v2 after Gate 2 (applied)

| | Before Gate 2 | After Gate 2 |
|---|---|---|
| Judgments | 659 | 673 |
| Grade 2 | 23 | 23 |
| Grade 1 | 33 | 47 |
| Grade 0 | 603 | 603 |
| `owner_reviewed` judgments | 0 | 28 |
| `candidate` judgments | 659 | 645 |

- **Grade 1:** c130 went up (+1, c332), q15 Code Art. 154-bis went down (−1, c333), and the 14
  additions are all at grade 1 (c335–c348).
- **The pool.** The 14 additions are `judge_added` entries in `pool.jsonl`.
- **The 28 reviewed records:**
  - the 12 uncertain judgments;
  - q15 Code Art. 154-bis;
  - q05 GDPR Art. 23;
  - the 14 additions.

### 0.5 Remaining dependencies and uncertainties

- **c130 and rule 5.** The grade 1 rests on reading a question that asks for all cases (q06)
  as including sector cases. That reading is now written into the guidelines (working rule 5).
- **c141 and rule 2.** A stricter reading would give 0. GDPR Art. 10 stays unjudged for q06:
  Art. 35(3)(b) names that category in words (§5).
- **c213 and Option A.** Kept at 1 with Option A, as revised. The restrictions policy is now
  written into the guidelines (working rule 6).
- **Code Art. 166.** It is graded on paragraphs 1–3. If it were graded for its procedure
  (paragraphs 4–7), Code Arts. 143 and 144 would have to follow.
- **Not judged, not proposed:**
  - Code Art. 160, which Code Art. 2-undecies(3) refers to for exercising the rights through the
    Garante;
  - GDPR Art. 56, which Code Art. 143 refers to;
  - Code Art. 132, a sector rule (§4).
- **Missing context.** The national list of processing that requires an impact assessment
  (Art. 35(4)) is not in the corpus.
- **The Privacy Code is an unverified transcription.** Every Code judgment grades its text, not
  its validity.

## Summary of the analysis

The table below, and entries 1–14, are the analysis as first prepared. Their «current» grade is
the grade before Gate 2. Where the Gate 2 decisions of §0 differ, §0 prevails: the q15
decisions, Option A as revised, and Code Art. 154-bis.

| Change | Q | Provision | Current | Proposed | Class | Confidence | Depends on |
|---|---|---|---|---|---|---|---|
| c141 | q06 | GDPR Art. 9 | 1 | **1** | B | medium | rule 2; see GDPR Art. 10 (§5) |
| c130 | q06 | Code Art. 110 | 0 | **1 (revised)** | B | medium-low | the reading of rule 5 (§5) |
| c213 | q13 | Code Art. 2-undecies | 1 | **1** | B | medium | the restrictions issue (§0.2, §4) |
| c231 | q15 | Code Art. 166 | 1 | **1** | B | medium-high | graded on paragraphs 1–3 (§0.3) |
| c232 | q15 | Code Art. 144 | 0 | **0** | C | medium | c231 graded on paragraphs 1–3 (§0.3) |
| c234 | q15 | Code Art. 143 | 0 | **0** | C | medium | c231 graded on paragraphs 1–3 (§0.3) |
| c241 | q15 | Code Art. 154-ter | 0 | **0** | C | medium | the strict reading of q15 (§0.3) |
| c103 | q04 | GDPR Art. 51 | 0 | **0** | C | high | — |
| c181 | q09 | Code Art. 111-bis | 0 | **0** | C | high | — |
| c264 | q17 | Code Art. 75 | 0 | **0** | C | high | D5 (Code Art. 107) |
| c283 | q19 | GDPR Art. 12 | 0 | **0** | C | high | rule 4 |
| c298 | q20 | GDPR Art. 58 | 0 | **0** | C | high | — |

- **Changed proposal.** One proposal differs from the current candidate grade: **c130, from 0 to
  1**. Reading the text closely, Code Art. 166(1) sanctions the failure to carry out the
  assessment of Art. 110(1). The transcription therefore treats it as a case where an assessment
  is required, and q06 asks for those cases (entry 2).
- **Decisions beyond the 12 records,** taken at Gate 2 (§0):
  - the **restrictions of data-subject rights** (§4): Option A, as revised (§0.2), with 14
    additions, GDPR Art. 23 for q09 included;
  - the **q15 group**: the strict reading (§0.3), including Code Art. 154-bis → 0;
  - **GDPR Art. 10 for q06**: no addition (§5).

## 1. c141 — q06, GDPR Art. 9 (current 1; proposed 1)

1. **Question** (q06, test split, `obligation`): «In quali casi è obbligatoria una valutazione
   d'impatto sulla protezione dei dati?»
2. **Search query:**
   - retrieved by the natural query «trattamenti ad alto rischio che richiedono un'analisi
     preventiva» (dense and hybrid);
   - pooled through the natural dense list;
   - not in the technical pool.
3. **Provision:** `eu-reg-2016-679`, Art. 9 (article level; no point).
4. **Current grade:** 1 (`candidate`).
5. **Current rationale:** «Art. 35(3)(b) names large-scale processing of the special categories
   «di cui all'articolo 9, paragrafo 1» as a case that requires an assessment; only Art. 9(1)
   says which data those are.»
   - *Change reason:* «Uncertain: rule 2 (the scope of one listed case is fixed by reference).
     Under a stricter reading, 0: the question is answered by Art. 35.»
6. **Passages:**
   - GDPR Art. 35(3), the grade-2 article for q06: «La valutazione d'impatto sulla protezione dei
     dati di cui al paragrafo 1 è richiesta in particolare nei casi seguenti: […] b) il
     trattamento, su larga scala, di categorie particolari di dati personali di cui all'articolo
     9, paragrafo 1, o di dati relativi a condanne penali e a reati di cui all'articolo 10; o c) la
     sorveglianza sistematica su larga scala di una zona accessibile al pubblico.»
   - GDPR Art. 9(1): «È vietato trattare dati personali che rivelino l'origine razziale o etnica,
     le opinioni politiche, le convinzioni religiose o filosofiche, o l'appartenenza sindacale,
     nonché trattare dati genetici, dati biometrici intesi a identificare in modo univoco una
     persona fisica, dati relativi alla salute o alla vita sessuale o all'orientamento sessuale
     della persona.»
7. **Relation to the question.**
   - One of the three cases that Art. 35(3) lists is defined by reference: «categorie
     particolari di dati personali di cui all'articolo 9, paragrafo 1».
   - Art. 35 names the label, «categorie particolari», but not its content. Which data make
     processing fall in that case is stated only in Art. 9(1).
   - Art. 9 is otherwise about something else: a prohibition and its exceptions.
8. **Classification:** B, a relevant specification of one listed case.
9. **Proposed grade: 1.** Rule 2 grades a referenced provision 1 when the answer needs what only
   it says, «for example when it fixes the scope of the rule asked about».
   - Here the referenced text fixes the scope of case (b).
   - This matches q17, where the definitions of genetic, biometric and health data (Art. 4
     points 13–15) are graded 1 for the categories Art. 9 names.
10. **Uncertainty and dependencies.**
    - **The stricter reading.** «Categorie particolari» is itself stated in words, and an
      answer could name the case (large-scale processing of special categories) without listing
      them. On that reading, 0. That is the ground of the uncertainty.
    - **GDPR Art. 10 (§5).** The same case also refers to «dati relativi a condanne penali e a
      reati di cui all'articolo 10». GDPR Art. 10 is not judged for q06; it was not pooled.
    - **The national list.** Art. 35(4) says the supervisory authority publishes a list of
      processing types that require an assessment. No such list is in the corpus, so the
      national cases it would add cannot be judged.

## 2. c130 — q06, Code Art. 110 (current 0; proposed 1, a revision)

1. **Question:** q06, as in entry 1.
2. **Search query:**
   - retrieved by «quando è obbligatoria la DPIA» (BM25);
   - pooled through the natural BM25 list.
3. **Provision:** `it-dlgs-2003-196` (the transcription), Art. 110, paragraph 1.
4. **Current grade:** 0 (`candidate`).
5. **Current rationale:** «Not relevant: in the transcription, an impact assessment as a
   condition for medical research without consent; a sector rule the question does not ask
   about.»
   - *Change reason:* «Uncertain: rule 5 (a narrow sector rule), as D5 decided for Code
     Art. 107. It does name one case where an assessment is required.»
6. **Passages** (in the transcription):
   - Code Art. 110(1): «Il consenso dell'interessato per il trattamento dei dati relativi alla
     salute, a fini di ricerca scientifica in campo medico, biomedico o epidemiologico, non è
     necessario quando la ricerca è effettuata in base a disposizioni di legge o di regolamento o
     al diritto dell'Unione europea in conformità all'articolo 9, paragrafo 2, lettera j), del
     Regolamento, ivi incluso il caso in cui la ricerca rientra in un programma di ricerca
     biomedica o sanitaria previsto ai sensi dell'articolo 12-bis del decreto legislativo 30
     dicembre 1992, n. 502, ed è condotta e resa pubblica una valutazione d'impatto ai sensi
     degli articoli 35 e 36 del Regolamento.»
   - Code Art. 166(1), second sentence: «Alla medesima sanzione amministrativa è soggetto colui
     che non effettua la valutazione di impatto di cui all'articolo 110, comma 1, primo periodo,
     […]»
7. **Relation to the question.**
   - **As drafted in Phase 2:** Art. 110(1) was read as making the assessment a *condition* of
     an exemption from consent in medical research, a narrow sector rule.
   - **Art. 166(1) changes that reading.** It attaches an administrative sanction to failing to
     carry out «la valutazione di impatto di cui all'articolo 110, comma 1, primo periodo». In the
     transcription, Art. 110(1) thus describes a case in which an assessment must be carried out.
   - **The question asks for cases.** q06 asks «in quali casi è obbligatoria» an assessment,
     without limiting itself to the GDPR.
   - **Search result.** The Code's articles were searched for «valutazione d'impatto»,
     «valutazione di impatto» and «valutazione dell'impatto». Only Art. 110 and Art. 166 match,
     once each; Art. 166's match is the sentence quoted.
8. **Classification:** B, a relevant specification: a national case where an assessment is
   required, in the transcription.
9. **Proposed grade: 1, revising the current 0.**
   - **Rule 5.** Its second sentence excludes «a national rule for a narrow sector *that the
     question does not ask about*». q06 asks for all cases, so a sector case is within it.
   - **D5 differs.** D5 (Code Art. 107 at 0 for q17) concerned a question about the content of
     one GDPR article, which a sector rule does not answer. q06 is not limited to one article.
10. **Uncertainty and dependencies.**
    - **The literal reading.** If rule 5 is read literally (any narrow-sector rule is 0 unless
      the question names the sector), the grade stays 0. The owner's reading of rule 5 decides
      this, and it would be worth writing into the guidelines either way.
    - **Code Art. 166 is not judged for q06.** It is not needed under D1: it is the sanction, a
      consequence. Its paragraph 1 is used here only as textual evidence about Art. 110.
    - **The text.** Art. 110's text in the transcription carries amendment markers. Its
      correctness and currency are not verified.

## 3. c213 — q13, Code Art. 2-undecies (current 1; proposed 1)

1. **Question** (q13, dev split, `rights`): «Quando l'interessato può opporsi al trattamento dei
   suoi dati, ad esempio per il marketing diretto?»
2. **Search query:**
   - retrieved by «opposizione dell'interessato al marketing» (BM25);
   - pooled through the natural BM25 list.
3. **Provision:** `it-dlgs-2003-196` (the transcription), Art. 2-undecies, paragraphs 1 and 3.
4. **Current grade:** 1 (`candidate`).
5. **Current rationale:** «In the transcription: the rights of Arts. 15-22, objection included,
   cannot be exercised by request where this could prejudice the interests it lists; an
   exception to the right asked about.»
   - *Change reason:* «Uncertain: an exception under D1, like GDPR Art. 23 for q05.
     Consistency: this article and GDPR Art. 23 are not in the pools of q10-q12, and GDPR
     Art. 23 is not judged for q13.»
6. **Passages** (in the transcription):
   - Code Art. 2-undecies(1): «I diritti di cui agli articoli da 15 a 22 del Regolamento non
     possono essere esercitati con richiesta al titolare del trattamento ovvero con reclamo ai
     sensi dell'articolo 77 del Regolamento qualora dall'esercizio di tali diritti possa derivare
     un pregiudizio effettivo e concreto: a) agli interessi tutelati in base alle disposizioni in
     materia di riciclaggio; b) […] sostegno alle vittime di richieste estorsive; c) all'attività
     di Commissioni parlamentari d'inchiesta […]; d) alle attività svolte da un soggetto pubblico
     […] per esclusive finalità inerenti alla politica monetaria e valutaria […]; e) allo
     svolgimento delle investigazioni difensive o all'esercizio di un diritto in sede
     giudiziaria; ((f) alla riservatezza dell'identità della persona che segnala violazioni […]))
     f-bis) agli interessi tutelati in materia tributaria e allo svolgimento delle attività di
     prevenzione e contrasto all'evasione fiscale.»
   - Code Art. 2-undecies(3), extract: «L'esercizio dei medesimi diritti può, in ogni caso, essere
     ritardato, limitato o escluso con comunicazione motivata e resa senza ritardo all'interessato
     […]. In tali casi, i diritti dell'interessato possono essere esercitati anche tramite il
     Garante con le modalità di cui all'articolo 160.»
   - GDPR Art. 21(1), the grade-2 article for q13: «L'interessato ha il diritto di opporsi in
     qualsiasi momento, per motivi connessi alla sua situazione particolare, al trattamento dei
     dati personali che lo riguardano ai sensi dell'articolo 6, paragrafo 1, lettere e) o f) […]»
7. **Relation to the question.** Art. 21 falls within «articoli da 15 a 22». Art. 2-undecies
   says when, in the transcription, the right to object cannot be exercised by request, or may
   be delayed, limited or excluded. That is an exception to the right the question asks about.
8. **Classification:** B, an exception.
9. **Proposed grade: 1.**
   - D1 lists «an exception» as grade-1 information.
   - Rule 5's first sentence also applies: the article fills an option the GDPR leaves to
     Member States (GDPR Art. 23(1), §4).
   - This is consistent with q05, where GDPR Art. 23, the Union-level clause permitting such
     restrictions, is graded 1 as an exception to Art. 34.
10. **Uncertainty and dependencies.**
    - **Breadth.** The exception is bound to listed contexts (anti-money laundering, judicial
      claims, tax, and others). Read as «a national rule for a narrow sector» (rule 5, second
      sentence), it would be 0.
    - **Code Art. 160.** The procedure through the Garante refers to it, but Art. 160 is not
      judged anywhere.
    - **Consistency.** The grade cannot be settled alone without leaving the other rights
      questions inconsistent; see §4.
    - **Gate 2 decision (§0.2):** kept at 1, with Option A as revised.

## 4. Cross-cutting issue: restrictions of data-subject rights (q05, q09–q13)

**Provisions in the corpus that restrict the rights and obligations of Arts. 12–22 and 34:**

| Provision | Text (extract) | What it covers |
|---|---|---|
| GDPR Art. 23(1) | «Il diritto dell'Unione o dello Stato membro […] può limitare, mediante misure legislative, la portata degli obblighi e dei diritti di cui agli articoli da 12 a 22 e 34 […] qualora tale limitazione rispetti l'essenza dei diritti e delle libertà fondamentali e sia una misura necessaria e proporzionata […] per salvaguardare: a) la sicurezza nazionale; […]» | Arts. 12–22 and 34 (and Art. 5, as far as it corresponds) |
| Code Art. 2-undecies (transcription) | quoted in entry 3 | the rights of Arts. 15–22, in listed contexts |
| Code Art. 2-duodecies(1) (transcription) | «(( 1. In applicazione dell'articolo 23, paragrafo 1, lettera f), del Regolamento, in relazione ai trattamenti di dati personali effettuati per ragioni di giustizia […] i diritti e gli obblighi di cui agli articoli da 12 a 22 e 34 del Regolamento sono disciplinati nei limiti e con le modalità previste dalle disposizioni di legge o di Regolamento che regolano tali procedimenti […]» | the rights and obligations of Arts. 12–22 and 34, for processing for reasons of justice |
| Code Art. 132 (transcription), not proposed | «Rispetto ai dati conservati per le finalità indicate al comma 1 i diritti di cui agli articoli da 12 a 22 del Regolamento possono essere esercitati con le modalità di cui all'articolo 2-undecies, comma 3 […]» | a narrow sector (retained traffic data): routes the exercise of the rights to Art. 2-undecies(3). Not proposed for any question. |

**How the corpus was searched:**
- **The ranges.** All articles were searched for the ranges «articoli da 12 a 22» and «articoli
  da 15 a 22», with 21 as an end too.
  - GDPR hits: Arts. 12, 23 and 83.
  - Code hits: Arts. 2-undecies, 2-duodecies, 2-terdecies, 130, 132 and 142.
- **Art. 23.** The Code's articles were searched for any mention of «articolo 23». The hits are
  Arts. 2-undecies, 2-duodecies and 45-bis.
- **What else turned up.** The other hits are not restrictions:
  - GDPR Arts. 12 and 83;
  - Code Art. 2-terdecies (deceased persons);
  - Code Art. 130 (already graded 1 for q13);
  - Code Art. 142 (the complaint procedure);
  - Code Art. 45-bis (the legal basis of Part II).

**Where they stand in legal-v2.** The questions are those whose grade-2 article falls within
these provisions' scope.

| Question (grade-2 article) | GDPR Art. 23 | Code Art. 2-undecies (Arts. 15–22) | Code Art. 2-duodecies (Arts. 12–22, 34) |
|---|---|---|---|
| q05 (GDPR Art. 34) | **1** (kept from v1) | out of scope (Art. 34) | not judged |
| q09 (GDPR Art. 13) | not judged | out of scope (Art. 13) | not judged |
| q10 (GDPR Art. 15) | not judged | not judged | not judged |
| q11 (GDPR Art. 17) | not judged | not judged | not judged |
| q12 (GDPR Art. 20) | not judged | not judged | not judged |
| q13 (GDPR Art. 21) | not judged | **1** (c213) | not judged |

- **Where they are judged elsewhere.** GDPR Art. 23 is judged 0 for q15, q16 and q19. Code
  Art. 2-undecies is judged 0 for q22. Code Art. 2-duodecies is judged 0 for q01, q16 and q22.
  All of these are questions outside these provisions' scope, or out of scope altogether.
- **q19** (deceased persons; Code Art. 2-terdecies, grade 2) is not included: it asks *who* may
  exercise the rights, not whether they can be exercised.
- **Why the gaps exist.** The «not judged» cells are not mistakes in the pooling: these articles
  were never retrieved for those questions. Leaving them unjudged makes them count as not
  relevant there. Leaving c213 at 1 next to them is inconsistent: the same kind of provision gets
  different grades in questions of the same kind (rule 4).

**Options for the owner.** Each option uses the scopes in the corpus text:
- GDPR Art. 23 and Code Art. 2-duodecies cover Arts. 12–22 and 34;
- Code Art. 2-undecies covers Arts. 15–22.

| Option | Rule | Changes at Gate 2 (as `review` lines) | Consequence |
|---|---|---|---|
| **A, as revised (applied at Gate 2, §0.2)** | Restrictions count as exceptions wherever the right or obligation asked about is in their scope | Add 14 judgments at grade 1: GDPR Art. 23 for q09–q13 (5); Code Art. 2-undecies for q10–q12 (3); Code Art. 2-duodecies for q05 and q09–q13 (6). Keep c213 and q05 GDPR Art. 23 at 1. | Consistent with D1's «exception» and with q05. More judge-added records. |
| **B** | Only exceptions specific to the right asked about count | c213 → 0, and q05 GDPR Art. 23 → 0 (a kept v1 record). No additions. | Consistent, but stricter than the current q05 grade. |
| **D** | The GDPR's own clause counts; sector-bound national restrictions do not (rule 5, second sentence) | GDPR Art. 23 → 1 for q10–q13 (4 additions), and for q09 on the text's scope (5 in all). c213 → 0. Code Arts. 2-undecies and 2-duodecies not added. | A middle way. It treats the Code articles as sector rules. |
| C | Status quo | none | Inconsistent; not recommended. |

**First proposed in this dossier:** Option A.
- D1 names exceptions as grade-1 information, and the approved q05 grade already applies that
  to GDPR Art. 23.
- The two Code articles are what fills Art. 23's option in Italy, in the transcription (rule 5,
  first sentence).
- If the owner reads them as sector rules, Option D is the consistent alternative.

**Gate 2 decision:** Option A, as revised, with 14 additions (§0.2), applied as c335–c348.

**Not covered by any option:** the exceptions written inside the rights' own articles, such as
Art. 17(3) for erasure. They are part of the grade-2 articles, not separate provisions.

## 5. Other consistency points raised by these entries

- **q06, GDPR Art. 10 (not judged).** Art. 35(3)(b) also refers to «dati relativi a condanne
  penali e a reati di cui all'articolo 10». GDPR Art. 10: «Il trattamento dei dati personali
  relativi alle condanne penali e ai reati o a connesse misure di sicurezza sulla base dell'ar-
  ticolo 6, paragrafo 1, deve avvenire soltanto sotto il controllo dell'autorità pubblica […]».
  - Unlike Art. 9(1), Art. 35(3)(b) already states this category in words. Art. 10 adds only
    «o a connesse misure di sicurezza».
  - Under rule 2 («when the referring article states the condition in its own words, the
    referenced one stays 0»), **0 is the consistent grade**, so no addition is proposed.
  - This difference is also the main reason to keep c141 (GDPR Art. 9) at 1. If the owner sets
    c141 to 0, Art. 10 stays unjudged at no cost.
- **q15, the procedure group (c231, c232, c234).** Code Art. 166 contains both specifications of
  the powers and procedure:
  - **Specifications:** paragraphs 1–2 list the Code violations that carry the fines of Art. 83,
    and paragraph 3 makes the Garante «l'organo competente ad adottare i provvedimenti
    correttivi di cui all'articolo 58, paragrafo 2, del Regolamento, nonché ad irrogare le
    sanzioni di cui all'articolo 83».
  - **Procedure:** paragraphs 4–7.
  - **Gate 2 decision (§0.3):** c231 is graded 1 on paragraphs 1–3 (its rationale reworded in
    c334), so Code Arts. 143 and 144 (procedure only) stay 0. Grading Art. 166 for its procedure
    would require 143 and 144 at 1 as well.
- **q15, Code Arts. 154-bis and 154-ter.**
  - **The tension.** 154-bis is graded 1, kept from v1 under the plan's reading «National
    specifications of the Garante's powers» (plan §2.5). Its powers are not investigative or
    corrective, though: guidelines, deontological rules, cooperation, publication,
    simplification. 154-ter (standing in court) is at 0.
  - **Gate 2 decision (§0.3): the strict reading.** 154-bis → 0, applied as review line c333 to
    a record carried over from v1. 154-ter stays 0.
  - **Why.** 154-bis's grade 1 was inherited from v1 and is not retained merely for backward
    consistency.
  - Code Arts. 157 and 158 (graded 1) are investigative powers, and stay 1.

## 6. c231 — q15, Code Art. 166 (current 1; proposed 1)

1. **Question** (q15, test split, `authority`): «Quali poteri di indagine e correttivi ha
   l'autorità di controllo?»
2. **Search query:** retrieved by both natural queries, «poteri ispettivi del Garante privacy»
   and «provvedimenti che il Garante può adottare contro un'azienda» (BM25, dense and hybrid).
   Pooled through all three natural lists.
3. **Provision:** `it-dlgs-2003-196` (the transcription), Art. 166, paragraphs 1–4.
4. **Current grade:** 1 (`candidate`).
5. **Current rationale:** «In the transcription: which violations carry the fines of GDPR
   Art. 83, and the procedure for adopting corrective and sanctioning measures; a specification
   of the corrective powers asked about.»
   - *Change reason:* «Uncertain: a specification of the fining power, as GDPR Art. 83 is graded
     1 for q15. Under a stricter reading, 0: a procedure, not a power.»
6. **Passages** (in the transcription):
   - Art. 166(1), first sentence: «Sono soggette alla sanzione amministrativa di cui all'articolo
     83, paragrafo 4, del Regolamento le violazioni delle disposizioni di cui agli articoli
     2-quinquies, comma 2, ((...)), 92, comma 1, 93, comma 1, 123, comma 4, 128, 129, comma 2, e
     132-ter.»
   - Art. 166(3): «Il Garante è l'organo competente ad adottare i provvedimenti correttivi di cui
     all'articolo 58, paragrafo 2, del Regolamento, nonché ad irrogare le sanzioni di cui
     all'articolo 83 del medesimo Regolamento e di cui ai commi 1 e 2.»
   - Art. 166(4): «Il procedimento per l'adozione dei provvedimenti e delle sanzioni indicati al
     comma 3 può essere avviato […] a seguito di reclamo ai sensi dell'articolo 77 del Regolamento
     o di attività istruttoria d'iniziativa del Garante, nell'ambito dell'esercizio dei poteri
     d'indagine di cui all'articolo 58, paragrafo 1, del Regolamento, nonché in relazione ad
     accessi, ispezioni e verifiche […]»
7. **Relation to the question.**
   - Paragraph 3 states, in the transcription, which body holds the corrective powers of
     Art. 58(2) and the fining power of Art. 83.
   - Paragraphs 1–2 extend the fining power to violations of Code provisions.
   - Paragraph 4 ties the procedure to the investigative powers of Art. 58(1).
   - The question asks generally about «l'autorità di controllo». The grade-2 answer is GDPR
     Art. 58.
8. **Classification:** B, a relevant specification of the corrective (fining) power, and of who
   exercises it.
9. **Proposed grade: 1,** on paragraphs 1–3 (Gate 2 decision, §0.3; rationale reworded in c334). It parallels the q15
   grades of GDPR Art. 83 (the conditions and amounts of the fining power) and Code Arts. 157 and
   158 (investigative powers), which are 1.
10. **Uncertainty and dependencies.**
    - **The stricter reading.** The question asks which powers exist, and the article mostly
      allocates them and sets procedure. On that reading, 0.
    - **The procedure group:** see §5. The grade rests on paragraphs 1–3, not on the procedure
      of paragraphs 4–7.
    - **Code Art. 166 elsewhere.** It is graded 2 for q20 and 0 for q04, q05, q16 and q24.

## 7. c232 — q15, Code Art. 144 (current 0; proposed 0)

1. **Question:** q15, as in entry 6.
2. **Search query:**
   - retrieved by «provvedimenti che il Garante può adottare contro un'azienda» (BM25, dense,
     hybrid) and by «poteri ispettivi del Garante privacy» (BM25, hybrid);
   - pooled through all three natural lists.
3. **Provision:** `it-dlgs-2003-196` (the transcription), Art. 144.
4. **Current grade:** 0 (`candidate`).
5. **Current rationale:** «Not relevant: in the transcription, reports to the Garante and
   measures taken of its own motion; a procedure, not a power.»
   - *Change reason:* «Uncertain: 1 if procedural specifications of the powers count.»
6. **Passage** (in the transcription), Art. 144: «(( . 1. Chiunque può rivolgere una
   segnalazione che il Garante può valutare anche ai fini dell'emanazione dei provvedimenti di
   cui all'articolo 58 del Regolamento. 2. I provvedimenti del Garante di cui all'articolo 58 del
   Regolamento possono essere adottati anche d'ufficio. ))»
7. **Relation to the question.** It concerns how the exercise of the Art. 58 powers can be
   triggered: by a report from anyone, or of the Garante's own motion. It names no power and
   specifies none.
8. **Classification:** C, indirectly related (a procedural trigger).
9. **Proposed grade: 0.**
10. **Uncertainty and dependencies.** 1 only if procedural provisions on the powers' exercise
    count as «a procedure» useful to the answer. If so, Code Art. 143 and Code Art. 166(4)–(7)
    should be read the same way (§5). Gate 2 decision (§0.3): 0.

## 8. c234 — q15, Code Art. 143 (current 0; proposed 0)

1. **Question:** q15, as in entry 6.
2. **Search query:**
   - retrieved by «provvedimenti che il Garante può adottare contro un'azienda» (BM25, dense,
     hybrid);
   - pooled through the natural BM25 and hybrid lists.
3. **Provision:** `it-dlgs-2003-196` (the transcription), Art. 143, paragraph 1.
4. **Current grade:** 0 (`candidate`).
5. **Current rationale:** «Not relevant: in the transcription, the decision on a complaint, a
   procedure in which the Art. 58 powers are used; it adds no power.»
   - *Change reason:* «Uncertain: 1 if procedural specifications of the powers count.»
6. **Passage** (in the transcription), Art. 143(1): «Esaurita l'istruttoria preliminare, se il
   reclamo non è manifestamente infondato e sussistono i presupposti per adottare un
   provvedimento, il Garante, anche prima della definizione del procedimento può adottare i
   provvedimenti di cui all'articolo 58 del Regolamento nel rispetto delle disposizioni di cui
   all'articolo 56 dello stesso.»
   - Paragraphs 2–4 cover publication, time limits for deciding the complaint, and judicial
     remedy.
7. **Relation to the question.** It concerns when, in the complaint procedure, the Art. 58
   measures may be adopted (even before the procedure ends). It adds no power.
8. **Classification:** C, indirectly related (procedure).
9. **Proposed grade: 0.**
10. **Uncertainty and dependencies.**
    - As for entry 7; the two should get the same grade. Gate 2 decision (§0.3): 0.
    - It also refers to GDPR Art. 56 (the lead authority), which is not judged for q15.

## 9. c241 — q15, Code Art. 154-ter (current 0; proposed 0)

1. **Question:** q15, as in entry 6.
2. **Search query:**
   - retrieved by «poteri ispettivi del Garante privacy» (BM25, dense, hybrid) and by
     «provvedimenti che il Garante può adottare contro un'azienda» (dense, hybrid);
   - pooled through the natural dense and hybrid lists.
3. **Provision:** `it-dlgs-2003-196` (the transcription), Art. 154-ter, paragraph 1.
4. **Current grade:** 0 (`candidate`).
5. **Current rationale:** «Not relevant: in the transcription, the Garante's standing to bring
   proceedings; neither an investigative nor a corrective power.»
   - *Change reason:* «Uncertain: a power, but not of the two kinds the question names.»
6. **Passages:**
   - Code Art. 154-ter(1), in the transcription: «Il Garante è legittimato ad agire in giudizio
     nei confronti del titolare o del responsabile del trattamento in caso di violazione delle
     disposizioni in materia di protezione dei dati personali.»
   - Paragraphs 2–3 concern representation in court.
   - GDPR Art. 58(5): «Ogni Stato membro dispone per legge che la sua autorità di controllo
     abbia il potere di intentare un'azione o di agire in sede giudiziale o, ove del caso,
     stragiudiziale in caso di violazione del presente regolamento per far rispettare le
     disposizioni dello stesso.»
7. **Relation to the question.**
   - It gives the Garante a power: to bring proceedings, the subject of GDPR Art. 58(5).
   - The question names two kinds of power, «di indagine e correttivi», which are Art. 58(1)
     and 58(2). Standing in court is neither.
8. **Classification:** C, indirectly related (a power of another kind).
9. **Proposed grade: 0.**
10. **Uncertainty and dependencies.**
    - **The broad reading.** If the owner reads the question as asking about the authority's
      powers in general, this is a national specification of a power, and 1.
    - **An inconsistency with Code Art. 154-bis (graded 1 for q15, kept from v1), not resolved
      here.**
      - 154-bis adds powers «ai sensi dell'articolo 58, paragrafo 6» of other kinds:
        - paragraph 1: adopting guidelines and approving deontological rules;
        - paragraphs 2–4: cooperation with other authorities, publishing its decisions, and
          simplification for small firms.
      - None of these is an investigative or a corrective power.
      - Under the strict reading used for 154-ter, 154-bis would also be 0. Under the broad
        reading, both would be 1.
      - Grading 154-ter at 0 and 154-bis at 1 is consistent only with a stated distinction, for
        example between powers attached to the supervisory function and standing in court. That
        distinction is weak. See §5.
    - **Gate 2 decision (§0.3): the strict reading.** 154-ter stays 0, and 154-bis went to 0
      (c333). Its grade 1 had been inherited from v1, not re-examined.

## 10. c103 — q04, GDPR Art. 51 (current 0; proposed 0)

1. **Question** (q04, dev split, `procedure`): «Entro quanto tempo il titolare deve notificare al
   Garante una violazione dei dati personali?»
2. **Search query:**
   - retrieved by «ritardo nella segnalazione di una fuga di dati all'autorità» (BM25, hybrid);
   - pooled through the natural BM25 list.
3. **Provision:** `eu-reg-2016-679`, Art. 51, paragraph 1.
4. **Current grade:** 0 (`candidate`).
5. **Current rationale:** «Not relevant: it requires Member States to provide supervisory
   authorities; it adds nothing to the notification or its deadline.»
   - *Change reason:* «Uncertain: low. Related to Code Art. 2-bis, which is graded 1 for q04.»
6. **Passages:**
   - GDPR Art. 51(1): «Ogni Stato membro dispone che una o più autorità pubbliche indipendenti
     siano incaricate di sorvegliare l'appli- cazione del presente regolamento […] (l'«autorità di
     controllo»).»
   - Code Art. 2-bis, in the transcription: «(( 1. L'Autorità di controllo di cui all'articolo 51
     del regolamento è individuata nel Garante per la protezione dei dati personali, di seguito
     «Garante», di cui all'articolo 153. ))»
7. **Relation to the question.**
   - The deadline is in GDPR Art. 33 (grade 2).
   - The question names the Garante, and Code Art. 2-bis (graded 1) identifies it as the
     authority of Art. 51.
   - Art. 51 itself only requires that such authorities exist. The answer does not need it.
8. **Classification:** C, indirectly related.
9. **Proposed grade: 0.**
10. **Uncertainty and dependencies.**
    - Low.
    - GDPR Art. 51 is 1 for q14, which asks which authority supervises in Italy; there it is a
      prerequisite.
    - GDPR Art. 55, graded 1 for q04 (c11), is the provision Art. 33(1) refers to. Art. 51 is
      not referred to.

## 11. c181 — q09, Code Art. 111-bis (current 0; proposed 0)

1. **Question** (q09, test split, `obligation`): «Quali informazioni deve fornire il titolare
   quando raccoglie i dati direttamente presso l'interessato?»
2. **Search query:**
   - retrieved by «cosa indicare nell'informativa al momento della raccolta» (BM25, dense,
     hybrid);
   - pooled through the natural dense and hybrid lists.
3. **Provision:** `it-dlgs-2003-196` (the transcription), Art. 111-bis.
4. **Current grade:** 0 (`candidate`).
5. **Current rationale:** «Not relevant: in the transcription, when the Art. 13 information is
   given for unsolicited CVs; a narrow case, not the content asked about.»
   - *Change reason:* «Uncertain: low. Rule 5 (a narrow case).»
6. **Passages:**
   - Code Art. 111-bis, in the transcription: «(( 1. Le informazioni di cui all'articolo 13 del
     Regolamento, nei casi di ricezione dei curricula spontaneamente trasmessi dagli interessati
     al fine della instaurazione di un rapporto di lavoro, vengono fornite al momento del primo
     contatto utile, successivo all'invio del curriculum medesimo. Nei limiti delle finalità di
     cui all'articolo 6, paragrafo 1, lettera b), del Regolamento, il consenso al trattamento dei
     dati personali presenti nei curricula non è dovuto. ))»
   - GDPR Art. 13(1), the grade-2 article for q09: «In caso di raccolta presso l'interessato di
     dati che lo riguardano, il titolare del trattamento fornisce all'interessato, nel momento in
     cui i dati personali sono ottenuti, le seguenti informazioni: […]»
7. **Relation to the question.**
   - It changes *when* the Art. 13 information is given, for one case: unsolicited CVs. It does
     not change *what* information is given.
   - The question asks what information. «quando raccoglie» there states the situation, not the
     timing.
8. **Classification:** C, indirectly related (a timing exception in a narrow case).
9. **Proposed grade: 0.**
10. **Uncertainty and dependencies.** Low. It is an exception, but to the timing and in a narrow
    case the question does not ask about (rule 5, second sentence).

## 12. c264 — q17, Code Art. 75 (current 0; proposed 0)

1. **Question** (q17, dev split, `explicit_citation`): «Cosa stabilisce l'articolo 9 del GDPR
   sulle categorie particolari di dati?»
2. **Search query:**
   - retrieved by «divieto di trattare dati sanitari e relative eccezioni» (dense, hybrid) and by
     «art. 9 GDPR dati sensibili» (BM25);
   - pooled through the natural dense and hybrid lists.
3. **Provision:** `it-dlgs-2003-196` (the transcription), Art. 75.
4. **Current grade:** 0 (`candidate`).
5. **Current rationale:** «Not relevant: in the transcription, conditions for processing in the
   health sector; a sector rule the question does not ask about.»
   - *Change reason:* «Uncertain: low. Rule 5, as D5 decided for Code Art. 107.»
6. **Passages:**
   - Code Art. 75, in the transcription: «(( 1. Il trattamento dei dati personali effettuato per
     finalità di tutela della salute e incolumità fisica dell'interessato o di terzi o della
     collettività deve essere effettuato ai sensi dell'articolo 9, paragrafi 2, lettere h) ed i),
     e 3 del regolamento, dell'articolo 2-septies del presente codice, nonché nel rispetto delle
     specifiche disposizioni di settore. ))»
   - GDPR Art. 9(2)(h), extract: «il trattamento è necessario per finalità di medicina preventiva
     o di medicina del lavoro, […] diagnosi, assistenza o terapia sanitaria o sociale […], fatte
     salve le condizioni e le garanzie di cui al paragrafo 3».
7. **Relation to the question.**
   - The question asks what GDPR Art. 9 establishes.
   - Code Art. 75 refers health-sector processing back to Art. 9(2)(h) and (i) and 9(3), and to
     Code Art. 2-septies. It adds no condition to Art. 9 itself.
8. **Classification:** C, indirectly related (a sector routing rule).
9. **Proposed grade: 0.** This is the same situation as D5's Code Art. 107 (0 for q17): a sector
   rule, for a question about the content of one GDPR article.
10. **Uncertainty and dependencies.**
    - Low.
    - Code Art. 2-septies (graded 1 for q17, U5) is the national specification Art. 75 points to.
      Art. 75 adds only the sector routing.

## 13. c283 — q19, GDPR Art. 12 (current 0; proposed 0)

1. **Question** (q19, dev split, `rights`): «Chi può esercitare i diritti sui dati personali di
   una persona deceduta?»
2. **Search query:**
   - retrieved by «chi può esercitare i diritti privacy dopo la morte di una persona» (BM25,
     hybrid), one of the owner's Gate 1 edits;
   - pooled through the natural BM25 list.
3. **Provision:** `eu-reg-2016-679`, Art. 12, paragraphs 2–3.
4. **Current grade:** 0 (`candidate`).
5. **Current rationale:** «Not relevant: the procedure for answering requests under Arts. 15-22;
   the question asks who may exercise the rights, not how.»
   - *Change reason:* «Uncertain: low. Rule 4 grades Art. 12 at 1 in questions about exercising
     the rights (q10-q13); this question asks who.»
6. **Passages:**
   - GDPR Art. 12(2)–(3): «Il titolare del trattamento agevola l'esercizio dei diritti
     dell'interessato ai sensi degli articoli da 15 a 22. […] 3. Il titolare del trattamento
     fornisce all'interessato le informazioni relative all'azione intrapresa riguardo a una
     richiesta ai sensi degli articoli da 15 a 22 senza ingiustificato ritardo e, comunque, al più
     tardi entro un mese dal ricevimento della richiesta stessa.»
   - Code Art. 2-terdecies(1), in the transcription (grade 2 for q19): «I diritti di cui agli
     articoli da 15 a 22 del Regolamento riferiti ai dati personali concernenti persone decedute
     possono essere esercitati da chi ha un interesse proprio, o agisce a tutela dell'interessato,
     in qualità di suo mandatario, o per ragioni familiari meritevoli di protezione.»
7. **Relation to the question.** Who may act is answered by Code Art. 2-terdecies. Art. 12
   governs how and within what time the controller answers a request, which the question does not
   ask.
8. **Classification:** C, indirectly related.
9. **Proposed grade: 0.**
10. **Uncertainty and dependencies.**
    - Low.
    - Rule 4 grades Art. 12 at 1 for q10–q13, which ask when or how a right is exercised. q19 is a
      different kind of question.

## 14. c298 — q20, GDPR Art. 58 (current 0; proposed 0)

1. **Question** (q20, dev split, `cross_instrument`): «Come si applicano in Italia le sanzioni
   amministrative pecuniarie previste dal GDPR?»
2. **Search query:**
   - retrieved by «quantificazione delle sanzioni privacy» (dense);
   - pooled through the natural dense list.
3. **Provision:** `eu-reg-2016-679`, Art. 58, paragraph 2, letter i).
4. **Current grade:** 0 (`candidate`).
5. **Current rationale:** «Not relevant: paragraph 2, letter i), names the power to impose fines
   by reference to Art. 83, on which the answer relies.»
   - *Change reason:* «Uncertain: low. GDPR Art. 83 answers the question; Art. 58 adds only that
     the power exists.»
6. **Passages:**
   - GDPR Art. 58(2)(i): «infliggere una sanzione amministrativa pecuniaria ai sensi
     dell'articolo 83, in aggiunta alle misure di cui al presente paragrafo, o in luogo di tali
     misure, in funzione delle circostanze di ogni singolo caso».
   - GDPR Art. 83(2), the grade-2 article for q20: «Le sanzioni amministrative pecuniarie sono
     inflitte, in funzione delle circostanze di ogni singolo caso, in aggiunta alle misure di cui
     all'articolo 58, paragrafo 2, lettere da a) a h) e j), o in luogo di tali misure. Al momento
     di decidere se infliggere una sanzione amministrativa pecuniaria e di fissare l'ammontare
     della stessa in ogni singolo caso si tiene debito conto dei seguenti elementi: […]»
7. **Relation to the question.**
   - What Art. 58(2)(i) says about fines (imposed «in aggiunta … o in luogo» of the other
     measures) is restated in Art. 83(2).
   - Who applies the fines in Italy is in Code Art. 166(3) (graded 2 for q20), in the
     transcription.
   - Art. 58 adds nothing the answer needs.
8. **Classification:** C, indirectly related.
9. **Proposed grade: 0.**
10. **Uncertainty and dependencies.**
    - Low.
    - Art. 58 is 2 for q15, which asks about the powers. The difference in grade follows the
      question.

## Gate 2 outcome (2026-11-12)

**All items settled:**

| Item | Outcome |
|---|---|
| q09 and GDPR Art. 23 | included (c335), on the text's scope; 14 additions in all |
| Rule 5 | written into the guidelines: a question that asks for every case of a rule includes sector cases (it decides c130) |
| The restrictions policy | written into the guidelines as working rule 6 |
| The decisions of §0 | confirmed by the owner, Simone Zanetti, and applied on 2026-11-12 |

**What was applied to `legal-v2`:**
- **Review lines c332–c348**, appended to `changes.jsonl`:
  - two grade changes: c130 0 → 1, and q15 Code Art. 154-bis 1 → 0;
  - one rationale change: Code Art. 166 for q15, on paragraphs 1–3;
  - 14 added judgments.
- **`owner_reviewed`**, with `reviewed_by` «Simone Zanetti» and `reviewed_on` 2026-11-12, on the
  28 records listed in §0.4. Every other record keeps its earlier provenance.
- **Totals:** 673 judgments: 23 at grade 2, 47 at grade 1, 603 at grade 0.

**After Gate 2:**
- **The freeze (Gate 3), done on 2026-11-12.**
  - legal-v2 is frozen, with its six files pinned, and it is the default benchmark.
  - The first technical and natural results are in
    [`../legal-v2-first-evaluation.md`](../legal-v2-first-evaluation.md).
- **The rest of the review.** The other 645 judgments and the 24 questions remain candidates.
  Because v2 is frozen, any further review change would make legal-v3.
