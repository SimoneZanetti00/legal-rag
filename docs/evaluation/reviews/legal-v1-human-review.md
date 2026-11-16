# `legal-v1`: review package for the human reviewer

> **This is an AI assistant's pre-review, not a human review, and not legal validation.**
> - **Who wrote it:** Claude, in a Claude Code session on 2026-11-11.
> - **What it is:** it prepares the human review of the candidate benchmark in
>   `data/evaluation/legal-v1/`. Every record there is still `candidate`.
> - **What it changed:** nothing. No grade, question, provenance or review status was edited.
> - **What it used:** the benchmark files and the article text of the recorded corpus
>   (`build-f76ff6031f2fc82c4852f0a2bde27807`). It used no external legal source.
> - **What it did not look at:** any test-split metric.

Labels used below:

| Label | Meaning |
|---|---|
| `DEFENSIBLE` | the grade follows the guidelines on the corpus text |
| `REVIEW_REQUIRED` | a reasonable judge could grade it differently; a decision is needed |
| `LIKELY_INCONSISTENT` | it conflicts with how a comparable case is graded elsewhere in the benchmark |
| `INSUFFICIENT_CORPUS_EVIDENCE` | the corpus cannot settle the point |

The grade definitions are those of [docs/evaluation/guidelines.md](../guidelines.md):
- **2:** directly relevant evidence, needed to answer the question;
- **1:** partially relevant, or useful contextual evidence;
- **0:** not relevant.

## 1. Executive summary

- **All 23 grade-2 judgments are supported by the corpus text,** which this review read for
  each one. Grade 2 is reserved for the provision that states the answer, with one possible
  exception to discuss (q18, GDPR Art. 8).
- **Grade 1 is applied inconsistently.** That is the main finding. Some questions give 1 to
  related obligations and consequences (q02, q05, q06, q11, q20). Others give the same kind
  of provision 0 (q04, q08). The reviewer should fix one rule for "useful contextual
  evidence" (decision D1). About ten judgments depend on it.
- **There are four likely inconsistencies:** q11 Art. 12; q20 Art. 84 against Code Art. 167;
  q04 Art. 34 against q05 Art. 33; q02 Art. 32 against Art. 5 and Code Art. 132-ter.
- **Of the 10 borderline judgments examined,** 7 are `DEFENSIBLE` as they stand, 1 is
  `LIKELY_INCONSISTENT` (q02 Art. 32), and 1 is `DEFENSIBLE` with
  `INSUFFICIENT_CORPUS_EVIDENCE` (q04 Code Art. 2-quaterdecies.1). One `DEFENSIBLE` grade,
  q08 Art. 38, also depends on D1.
- **There is one probable pool gap.** GDPR Art. 55 is referred to by Art. 33(1), but was never
  pooled or judged for q04.
- **The search queries are the biggest methodological risk.** Most answerable questions have
  at least one query that repeats the target article's heading, or its defining wording,
  almost word for word. BM25 results will therefore look better than they would with neutral
  queries (decision D2). The pools come from the same queries.
- **The questions themselves are clear and correctly classified.** Four answerable questions
  ask about Italy or the Garante, and their answers rest on the Privacy Code transcription,
  whose legal validity the corpus cannot establish.

## 2. Borderline judgments

### 2.1 q02, GDPR Art. 32, grade 1: `LIKELY_INCONSISTENT`

| | |
|---|---|
| Question | «Quando si verifica una violazione dei dati personali?» (dev). Need: *the definition of a personal data breach.* |
| Provision | `eu-reg-2016-679@oj-l119-2016-it/body/article:32`, article `32` |
| Corpus excerpt | 32(2): «Nel valutare l'adeguato livello di sicurezza, si tiene conto in special modo dei rischi presentati dal trattamento che derivano in particolare dalla distruzione, dalla perdita, dalla modifica, dalla divulgazione non autorizzata o dall'accesso, in modo accidentale o illegale, a dati personali …» |
| Current grade | **1**: "Security of processing: names the same risks (destruction, loss, alteration, unauthorised disclosure or access) that the definition covers." |
| Assessment | Art. 32 shares the definition's vocabulary, but does not define a breach. The answer is GDPR Art. 4 point 12, graded 2. Two provisions graded 0 in the same question share that vocabulary equally: GDPR Art. 5(1)(f) («dalla perdita, dalla distruzione o dal danno accidentali», «integrità e riservatezza») and Code Art. 132-ter(4). Grading Art. 32 at 1 and those two at 0 is inconsistent. |
| Proposed grade | **0**. Otherwise raise Art. 5 and Code Art. 132-ter to 1 as well. |
| Basis in the guidelines | Shared terminology is not relevance: "do not assign grade 2 merely because similar terminology", and by extension 1. A definition question needs the definition. |

### 2.2 q05, GDPR Art. 23, grade 1: `DEFENSIBLE`

| | |
|---|---|
| Question | «Quando il titolare deve avvisare le persone coinvolte in una violazione dei loro dati?» (dev). Need: *when a breach must be communicated to the data subjects, and the exceptions.* |
| Provision | `eu-reg-2016-679@oj-l119-2016-it/body/article:23`, article `23` |
| Corpus excerpt | 23(1): «Il diritto dell'Unione o dello Stato membro … può limitare, mediante misure legislative, la portata degli obblighi e dei diritti di cui agli articoli da 12 a 22 e 34 …» |
| Current grade | **1**: "Union or Member State law may restrict the obligations of Art. 34." |
| Assessment | The stated need includes the exceptions. Art. 23 is the general basis for restricting the Art. 34 obligation. It is not the answer, which is Art. 34, graded 2, but it is a condition on it. |
| Proposed grade | 1 (no change) |
| Basis in the guidelines | Grade 1 covers "a provision that covers only part of the question": here, the exceptions. |

### 2.3 q05, GDPR Art. 58, grade 1: `DEFENSIBLE`

| | |
|---|---|
| Question | as in 2.2 |
| Provision | `eu-reg-2016-679@oj-l119-2016-it/body/article:58`, article `58` |
| Corpus excerpt | 58(2): «Ogni autorità di controllo ha tutti i poteri correttivi seguenti: … e) ingiungere al titolare del trattamento di comunicare all'interessato una violazione dei dati personali; …» |
| Current grade | **1**: "Paragraph 2, letter e): the authority may order the controller to communicate a breach to the data subject." |
| Assessment | It is one way the communication becomes required: by order of the authority. That is partial evidence for "when". Art. 34(4) states the same power, and Art. 34 is already graded 2. The grade is defensible, but under a strict rule for grade 1 (D1) it would remain 1 only if powers that trigger the obligation count. |
| Proposed grade | 1 (no change), subject to D1 |
| Basis in the guidelines | Partially relevant: it covers one case of the obligation. |

### 2.4 q03, GDPR Art. 9, grade 0: `DEFENSIBLE`

| | |
|---|---|
| Question | «Quali requisiti deve avere il consenso dell'interessato per essere valido?» (test). Need: *what makes consent valid: its definition and the conditions for it.* |
| Provision | `eu-reg-2016-679@oj-l119-2016-it/body/article:9`, article `9` |
| Corpus excerpt | 9(2): «Il paragrafo 1 non si applica se si verifica uno dei seguenti casi: a) l'interessato ha prestato il proprio consenso esplicito al trattamento di tali dati personali per una o più finalità specifiche …» |
| Current grade | **0**: "Not relevant: the article concerns Trattamento di categorie particolari di dati personali." |
| Assessment | Art. 9 uses explicit consent as one exception to its prohibition. It does not state what makes consent valid. The validity requirements are Art. 4 point 11 and Art. 7, both graded 2. A reviewer could argue that «esplicito» is a stricter validity requirement for special categories, and give 1. The corpus text does not support more. The rationale should name the reason rather than the title. |
| Proposed grade | 0 (no change). Option: 1, if specific forms of consent are counted (see D5). |
| Basis in the guidelines | Grade 1 needs useful evidence for the question. A mention of consent in another context is not. |

### 2.5 q08, GDPR Arts. 38 and 39, grade 0: `DEFENSIBLE` (Art. 39), depends on D1 (Art. 38)

| | |
|---|---|
| Question | «Quando è obbligatorio designare un responsabile della protezione dei dati?» (dev). Need: *when a data protection officer must be designated.* |
| Provisions | `…/article:38` (`38`) and `…/article:39` (`39`) of `eu-reg-2016-679@oj-l119-2016-it` |
| Corpus excerpts | 38(1): «Il titolare del trattamento e il responsabile del trattamento si assicurano che il responsabile della protezione dei dati sia tempestivamente e adeguatamente coinvolto …». 39(1): «Il responsabile della protezione dei dati è incaricato almeno dei seguenti compiti: a) informare e fornire consulenza …» |
| Current grade | **0** each, with the generic title rationale |
| Assessment | Neither article says when designation is mandatory: that is Art. 37(1), graded 2. Both are defensible at 0 under a strict reading of grade 1. They are inconsistent, however, with the looser reading used in q02, q05, q06, q11 and q20, where related provisions about the same subject got 1. |
| Proposed grade | 0 (no change). Move to 1 only if D1 adopts the looser rule. |
| Basis in the guidelines | Grade 1: useful contextual evidence for this question. The position and tasks of a DPO do not answer "when". |

### 2.6 q09, GDPR Art. 14, grade 0: `DEFENSIBLE`

| | |
|---|---|
| Question | «Quali informazioni deve fornire il titolare quando raccoglie i dati direttamente presso l'interessato?» (test). Need: *the information to give when data are collected from the data subject.* |
| Provision | `eu-reg-2016-679@oj-l119-2016-it/body/article:14`, article `14` |
| Corpus excerpt | 14(1): «Qualora i dati non siano stati ottenuti presso l'interessato, il titolare del trattamento fornisce all'interessato le seguenti informazioni: …» |
| Current grade | **0**: "Not relevant: the article concerns Informazioni da fornire qualora i dati personali non siano stati ottenuti presso l'interessato." |
| Assessment | The question explicitly restricts itself to direct collection, and Art. 14 governs the opposite case. Its list largely overlaps with Art. 13's, so a retrieval system confusing them is a realistic error. Grading it 0 measures that error correctly. |
| Proposed grade | 0 (no change) |
| Basis in the guidelines | Not relevant to the stated need. |

### 2.7 q09, Code Art. 80, grade 0: `DEFENSIBLE`

| | |
|---|---|
| Question | as in 2.6 |
| Provision | `it-dlgs-2003-196@transcription-vigente-2026-11-05/body/article:80`, article `80` |
| Corpus excerpt | 80(1): «Nel fornire le informazioni di cui agli articoli 13 e 14 del Regolamento, … possono avvalersi della facoltà di fornire un'unica informativa per una pluralità di trattamenti … i competenti servizi o strutture di altri soggetti pubblici … operanti in ambito sanitario o della protezione e sicurezza sociale.» |
| Current grade | **0**, with the generic title rationale |
| Assessment | It is a sector-specific simplification of how certain public bodies give the information. It says nothing about what information to give. |
| Proposed grade | 0 (no change) |
| Basis in the guidelines | Not relevant to the content asked about. |

### 2.8 q14, GDPR Art. 51, grade 1: `DEFENSIBLE`

| | |
|---|---|
| Question | «Quale autorità controlla in Italia l'applicazione della normativa sulla protezione dei dati personali?» (dev). Need: *which body is Italy's supervisory authority.* |
| Provision | `eu-reg-2016-679@oj-l119-2016-it/body/article:51`, article `51` |
| Corpus excerpt | 51(1): «Ogni Stato membro dispone che una o più autorità pubbliche indipendenti siano incaricate di sorvegliare l'applicazione del presente regolamento … (l'«autorità di controllo»).» |
| Current grade | **1**: "Each Member State provides for supervisory authorities: the rule Code Art. 2-bis applies." |
| Assessment | It answers part of the question ("an independent public authority, designated by the Member State") but not "which". The answer is Code Art. 2-bis («individuata nel Garante»), graded 2. Grade 2 for Art. 51 would overstate it. |
| Proposed grade | 1 (no change) |
| Basis in the guidelines | Grade 1: covers only part of the question. |

### 2.9 q04, Code Art. 2-quaterdecies.1, grade 1: `DEFENSIBLE` for relevance; `INSUFFICIENT_CORPUS_EVIDENCE` for its status

| | |
|---|---|
| Question | «Entro quanto tempo il titolare deve notificare al Garante una violazione dei dati personali?» (dev). Need: *the deadline and conditions for notifying a breach to the supervisory authority.* |
| Provision | `it-dlgs-2003-196@transcription-vigente-2026-11-05/body/article:2-quaterdecies.1`, article `2-quaterdecies.1` |
| Corpus excerpt | «1. ((Le imprese con meno di cinque dipendenti si avvalgono, per l'adempimento dell'obbligo di cui all'articolo 33 del regolamento, di una specifica procedura di notifica.)) 2. ((La procedura di cui al comma 1 è disciplinata dal Garante con proprio provvedimento …))» |
| Current grade | **1**: "In this transcription: a specific notification procedure under GDPR Art. 33 for firms with fewer than five employees." |
| Assessment | For the question's "conditions", a special procedure for some controllers is partial evidence. It does not change the deadline, which comes from Art. 33, graded 2. As relevance, the grade is defensible. Whether this provision is actually part of the Code in force cannot be established from the corpus: it appears only in an unverified user transcription. This review did not check it against any official source. |
| Proposed grade | 1 (no change). The reviewer should decide whether provisions not yet checked against an official text may carry grade 1 or 2 (D6). |
| Basis in the guidelines | Judge the text in the corpus; relevance is not validity. |

## 3. Other grade 1 and grade 2 judgments

**Basis.** The candidate README said some GDPR grades rested on titles and well-known
content. This review then read the corpus text behind each of them:
- Art. 7(1)–(4); Art. 13(1); Art. 15(1); Art. 17(1) and (3); Art. 19; Art. 20(1);
- Art. 21(2)–(3); Art. 30(1) and (5); Art. 35(1) and (3); Art. 36(1); Art. 37(1);
- Art. 12(3); Art. 6(3); Art. 83(1); Art. 58(2)(e) and (i); Art. 34(3); Art. 33(1).

All of them support the subject the grade claims. Not re-read in this review: Art. 6(1)(a)
(q03) and Art. 83(4)–(6), the fine amounts mentioned in the q20 rationale.

**Grade 2 is reserved for the provision that answers.** All 23 grade-2 judgments are the
article that states the answer, or the definition the question asks for. One case for
discussion:

| Judgment | Label | Note |
|---|---|---|
| q18, GDPR Art. 8, grade 2 | `REVIEW_REQUIRED` | The age asked about («in Italia») comes from Code Art. 2-quinquies («il minore che ha compiuto i quattordici anni»). Art. 8 gives the default of 16 and the option, with a floor of 13, that the Code uses. Grade 2 is defensible if the answer must explain the derogation; otherwise it is a 1. |

**Likely inconsistencies:**

| Judgment | Label | The inconsistency | Proposal |
|---|---|---|---|
| q11, GDPR Art. 12, **0** | `LIKELY_INCONSISTENT` | Art. 12(3) sets how and when requests "ai sensi degli articoli da 15 a 22" are answered, Art. 17 included. It is graded 1 for access (q10) and portability (q12), but 0 for erasure (q11). | 1 |
| q20, GDPR Art. 84, **1**, against Code Art. 167, **0** | `LIKELY_INCONSISTENT` | Art. 84 covers the "altre sanzioni" set by Member States. Code Art. 167 is such a penalty (criminal, «reclusione»). The question asks about administrative fines, so neither answers it. | Art. 84 → 0, keeping Art. 167 at 0. Otherwise both 1. |
| q04, GDPR Art. 34, **0**, against q05, GDPR Art. 33, **1** | `LIKELY_INCONSISTENT` | Two symmetric cases: each question asks about one breach obligation, and the other obligation is graded differently. q02 grades both at 1. | One rule from D1: 0 in both under a strict rule, 1 in both under a loose one |
| q02, GDPR Art. 32, **1**, against Art. 5 and Code 132-ter, **0** | `LIKELY_INCONSISTENT` | See 2.1 | Art. 32 → 0 |

**Judgments that depend on the grade-1 rule (D1).** Each gives 1 to a related provision or a
consequence, not to a condition, exception, definition or procedure needed for the answer:

| Judgment | Label | Under a strict rule |
|---|---|---|
| q02 Arts. 33 and 34, grade 1 ("context, not the definition") | `REVIEW_REQUIRED` | 0 |
| q05 Art. 33, grade 1 ("the related obligation") | `REVIEW_REQUIRED` | 0 |
| q06 Art. 36, grade 1 (prior consultation follows the assessment) | `REVIEW_REQUIRED` | 0: it does not say when an assessment is mandatory |
| q11 Art. 19, grade 1 (notifying recipients) | `REVIEW_REQUIRED` | 0: a consequence, not a ground for erasure |
| q20 Art. 84, grade 1 | `LIKELY_INCONSISTENT` | 0 (above) |
| q13 GDPR Art. 6, grade 0 | `REVIEW_REQUIRED` | 1: Art. 21(1) limits objection to processing on the bases of Art. 6(1)(e) and (f), so Art. 6 conditions "quando" one can object |

**Other points:**

| Judgment | Label | Note |
|---|---|---|
| q17, Code Art. 107, grade 0 | `REVIEW_REQUIRED` | It implements Art. 9 for one sector: simplified consent for statistics and research. Code Arts. 2-sexies and 2-septies, which implement Art. 9 generally, are graded 1. Defensible at 0 if only general implementing provisions count. |
| q17, GDPR Art. 4, grade 1 at article level | `REVIEW_REQUIRED` (form) | The rationale cites points 13–15. Elsewhere Art. 4 is judged by point (q01, q02, q03, q04, q14). For consistency, record points 13, 14 and 15. The metric is unchanged. |
| q04, GDPR Art. 55, not judged | `REVIEW_REQUIRED` (pool gap) | Art. 33(1) sends the notification to «l'autorità di controllo competente a norma dell'articolo 55». Art. 55 was not in any top-10 list for q04, so it is unjudged and counts as not relevant. Candidate grade: 1. |
| q04 Code Art. 2-bis and Art. 4 point 12; q14 Code Art. 153; q15 Code Arts. 154-bis, 157 and 158 (all judge-added, grade 1) | `DEFENSIBLE` | Each was read in the corpus: Art. 2-bis names the Garante; Art. 153 establishes it; Arts. 154-bis, 157 and 158 implement the Art. 58 powers. Being judge-added, they are counted as relevant although no retriever found them in its top 10. That is intended, but it lowers BM25 recall for those questions. |
| The 334 grade-0 rationales | note | They name the article's title, not why it does not answer. Acceptable as a provisional record. A reviewer may want a short reason where a grade-0 article looks related (for example q04 Art. 34, q09 Art. 14, q13 Art. 6). |

## 4. Question quality

| Finding | Label | Questions |
|---|---|---|
| **Search queries repeat the target article's wording.** At least one query reproduces the heading or defining sentence of the article graded 2 almost word for word. Examples: q09 «informazioni da fornire qualora i dati personali siano raccolti presso l'interessato» = the heading of Art. 13; q19 «diritti riguardanti le persone decedute» = the heading of Code Art. 2-terdecies; q01 «informazione riguardante una persona fisica identificata o identificabile» = Art. 4 point 1. Lexical retrieval scores will be optimistic. Pools built from the same queries inherit the bias. | `REVIEW_REQUIRED` (D2) | q01, q02, q05, q06, q07, q08, q09, q10, q11, q12, q13, q16, q17, q18, q19, q20 |
| **Answers that rest on the unverified transcription.** These questions ask about Italy or the Garante. Their answers rest on the Privacy Code transcription: Arts. 2-bis, 2-quinquies, 166 and 2-quaterdecies.1. A user would expect current law, which the corpus cannot establish. Relevance can be judged; validity cannot. | `INSUFFICIENT_CORPUS_EVIDENCE` (for validity) | q04, q14, q18, q20 |
| **More than one need.** q07 asks who keeps the record *and* what it contains. q15 asks about investigative *and* corrective powers. Each pair is answered by a single article, so the effect is small. | `DEFENSIBLE` | q07, q15 |
| **Category labels.** q03 asks for the conditions of valid consent, which is more `obligation` than `definition`. q19 is answered by the Privacy Code alone, since the GDPR has no article on deceased persons, so `cross_instrument` is debatable. | `REVIEW_REQUIRED` (D7) | q03, q19 |
| **Expected outcomes.** They are correctly set. q21 and q22 are outside data protection. q23 (AI regulation) and q24 (the Garante's 2025 decisions) need sources the corpus lacks. q22 is out of scope even though the corpus has employment-related data protection provisions, because it asks about dismissal requirements. | `DEFENSIBLE` | q21–q24 |
| **Explicit citations.** Only BM25 is measured. In `ask`, the citation resolver would look up the named article directly, and that path is not measured here. | note | q16, q17 |

**Coverage gaps** (for a later version; the questions are not changed here):
- no `needs_clarification` question;
- no question in English, although `ask` accepts any language;
- no multi-hop question;
- no question on principles (Art. 5), processors (Art. 28), transfers (Chapter V), security
  (Art. 32), rectification or restriction (Arts. 16 and 18), automated decisions (Art. 22),
  remedies and damages (Arts. 77–82; Code Arts. 140-bis–143), employment (Art. 88; Code
  Arts. 113–115), research (Art. 89; Code Art. 110), journalism (Code Arts. 136–139), cookies
  (Code Art. 122) or telemarketing rules as an answerable question (Code Art. 130);
- `explicit_citation` appears in dev only.

## 5. Decisions for the human reviewer, in order of priority

| | Decision | Judgments affected |
|---|---|---|
| **D1** | Fix the rule for grade 1. **Recommended:** grade 1 only for a definition, condition, exception or procedure that an answer would need to cite. A related obligation or a consequence is 0. | q02 Arts. 33, 34; q05 Art. 33; q06 Art. 36; q11 Art. 19; q20 Art. 84; q04 Art. 34; q08 Arts. 38, 39; q13 Art. 6. About ten in all |
| **D2** | Search-query policy: keep queries that mirror the corpus's wording (an idealised query analysis), or write neutral paraphrases. Either way, state the choice in the README. For version 2, consider a neutral query set alongside. | most answerable questions; BM25 numbers |
| **D3** | Resolve the four likely inconsistencies. | q11 Art. 12; q20 Arts. 84 and 167; q04 Art. 34 and q05 Art. 33; q02 Arts. 32, 5 and 132-ter |
| **D4** | Fill the pool gap. | q04 GDPR Art. 55 |
| **D5** | Decide the remaining borderline grades. | q03 Art. 9 (0 or 1); q18 Art. 8 (2 or 1); q17 Code Art. 107 (0 or 1) |
| **D6** | Decide whether transcription provisions not checked against an official text (such as Code Art. 2-quaterdecies.1) may carry grade 1 or 2. | — |
| **D7** | Category labels. | q03, q19 |
| **D8** | Record the outcome. Mark each checked record `owner_reviewed`, with reviewer and date, and publish any change as version 2. The review must not be described as expert or legal validation. | all records |

## 6. Limitations of this review

- **Not a human review, and not legal advice.** Its proposals are suggestions. No record's
  status changes until a person reviews it.
- **Corpus only.** It judges against the text of the recorded corpus: the GDPR as published
  in 2016 and an unverified Code transcription. It does not say what the law in force is, and
  it did not check any provision against an official source.
- **Coverage.** It read every grade-1 and grade-2 judgment, and the grade-0 judgments named
  above. It did not review each of the 334 grade-0 judgments individually.
- **Pool gaps.** These are found only where the corpus text points to them (q04 Art. 55).
  Other unpooled relevant articles may exist.
- **No metrics.** It neither inspected nor reports any test-split metric. It ran no retrieval
  experiment and changed no configuration.
- **Unverified points.** It did not re-read Art. 6(1)(a) or Art. 83(4)–(6) in the corpus.
