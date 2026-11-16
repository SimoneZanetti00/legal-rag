# M1 review: compact sheets for five provisions

> **Preparation aid, not a review.** Prepared on 2026-11-12 by Claude Code (AI assistant) from the
> generated package [`m1-human-review-package.md`](m1-human-review-package.md) and the recorded build.
>
> - It records no decision, marks nothing as reviewed and changes no other file.
> - Every decision is yours. Write them in the dated record
>   [`m1-review-record-2026-11-09.md`](m1-review-record-2026-11-09.md), or give them in your reply.
>   Nothing is recorded until you decide.
> - Legal validity is not assessed here and stays `not_established`.
> - The full evidence for each provision is in the package section named on each sheet.

## Checks run for these sheets (2026-11-12)

| Check | Result |
|---|---|
| Package reproduced from the build (`python -m tools.review_package.generate --check`) | Byte-identical. sha256 `2f90fe52723f91c63f4414404c4ce880e5a37bfc61de00f2e3ec45568665ce56`, the hash the dated record expects. |
| Archived official sources (`python -m tools.review_package.official_texts`) | All five archived files match their recorded hashes. The five official texts extract to their recorded hashes, all `identical_after_normalisation`. |
| Stored article text in the recorded build (`ProvisionExplorer.lookup`) | All five texts match the package's SHA-256. The texts below were filled in from the build and checked against those hashes. |
| Review ledger | Empty (`[]`). All five entries are `pending_human_review`. |

## Summary

| # | Provision | Stored text: source and pages | Units | Official comparison | Anomalies (layout only) | Judgment points | Tier now → if confirmed |
|---|---|---|---|---|---|---|---|
| 1 | GDPR Art. 4 «Definizioni» (demo uses point 12) | OJ L 119, 4.5.2016, original publication, pp. 33–35 | 26 points; (16) a–b, (22) a–c, (23) a–b | EUR-Lex consolidated 2016-05-04: `identical_after_normalisation`, no word differs (point 12 alone also identical) | 14: 6 soft hyphens, 1 page join inside a sentence, 6 blank lines inside sentences, 1 footnote reference | Scope (whole article), hyphenation, footnote, 2 page joins, blank lines | `internal_only` → `primary` |
| 2 | GDPR Art. 33 «Notifica … all'autorità di controllo» | same source, p. 52 | 5 paragraphs; 3(a)–(d) | `identical_after_normalisation`, no word differs | 3: 1 soft hyphen, 2 blank lines | Hyphenation, blank lines, word-by-word reading of p. 52, Digital Omnibus note | `internal_only` → `primary` |
| 3 | GDPR Art. 34 «Comunicazione … all'interessato» | same source, pp. 52–53 | 4 paragraphs; 3(a)–(c) | `identical_after_normalisation`, no word differs | 3 blank lines | Page join 52→53, blank lines | `internal_only` → `primary` |
| 4 | GDPR Art. 55 «Competenza» | same source, p. 67 | 3 paragraphs | `identical_after_normalisation`, no word differs | none | Dependence on Art. 56 (excluded, pre-corrigendum) | `internal_only` → `primary` |
| 5 | Privacy Code Art. 2-bis «(Autorità di controllo)» | user transcription of the consolidated Code, p. 2 | 1 paragraph | Normattiva (text in force; no «vigente al» date): `identical_after_normalisation`, no word differs | none | Transcription as a source, amendment markers, title form, reference date | `internal_only` → `primary`, still qualified `unofficial_transcription` |

## What a review means, and what recording it does

**Who may review.** Only a person who has checked the entry against the source PDF may mark it `reviewed`. They are named in `checked_by`, and the date goes in `checked_on` (`YYYY-MM-DD`, not in the future). The ledger record must carry the same reviewer and date (`data/reference/README.md`, «Human review»).

**The five decisions per provision** (worksheet E of the package; they are independent):

| Decision | Meaning |
|---|---|
| 1. Structure | The article starts and ends in the right place, the heading and title belong to it, the numbering is as printed, and context (running headers, footnotes, the next heading) is excluded. |
| 2. Extraction fidelity | The stored text matches the printed page word for word; the anomalies are layout only. |
| 3. Completeness | Every paragraph and point is present, with nothing truncated or duplicated. |
| 4. Source-status markers | Status and amendment markers are recorded as the source prints them. This is not a legal status. |
| 5. Primary-citation eligibility | Your view of whether it should be citable as primary evidence. **The system computes the tier; this answer does not change it.** |

**Ledger outcome.**
- `confirmed`: nothing changed; the provision's structural status becomes `auto_verified`.
- `corrected`: each changed field is listed with its value before and after, and the inventory is edited to hold the new values; the status becomes `manually_curated`.
- Or no record yet: the provision stays `internal_only`.

**Official-source check (optional).** The candidate `official_check` object in each package section C can be recorded as computed, recomputed from your own extraction, or left out.
- A `differs` result keeps a provision out of primary citations.
- A match changes nothing else. It doesn't make the text authentic: EUR-Lex consolidated texts and Normattiva are official but not authentic.

**What a confirmed record changes.** A provision becomes `primary` when it is reviewed, its text is anchored, its structure isn't ambiguous, no official check says `differs`, and the source doesn't mark it repealed. All five meet every other condition today, so **confirming a provision makes it citable**.
- Its qualifications stay attached to every use of it, for example `original_publication_not_consolidated` and `unofficial_transcription`.
- To keep a provision out of primary citations, the only route today is **not to record its review yet**.

**What it does not change.** The anchors and the recorded build stay valid, and legal validity stays `not_established`.

**Changes that go with recording.** These need your approval as part of G4:
- the inventory entries (`review_status`, `checked_by`, `checked_on`) and one ledger record each;
- two tests that assume an empty ledger, in `tests/test_provisions.py`:
  - `test_shipped_files_load_and_the_ledger_is_empty`;
  - `test_nothing_is_primary_while_the_ledger_is_empty`;
- the README sentences saying the ledger is empty.

Afterwards, the generated package's `--check` will report a difference, because it documents the state before review. Whether to make a new recorded build afterwards is a separate policy decision (TECHNICAL_DEBT.md TD-062), not needed for the demo.

**Already handled in code.** Answer quotations are checked with the same normalisation as the official comparison (`answer_generation.quote_problem`, profile `ws-markers-softhyphen-v1`). So soft hyphens, line breaks, typographic apostrophes and spacing cannot make a correct quotation fail.

## Decisions that apply to all five

| ID | Decision | Options |
|---|---|---|
| G1 | Reviewer name and review date for `checked_by` and `checked_on`. It must be the person who checked the PDF pages. | name; `YYYY-MM-DD` |
| G2 | Record the official-source checks. | as computed in the package (C) · with my own extraction · not recorded |
| G3 | May a user transcription (the Privacy Code file) become `primary` at all? It is an open policy question (ROADMAP, «Record the M1 review»). If not, leave Art. 2-bis unrecorded. | yes · no, not now |
| G4 | Make the accompanying changes listed above (inventory entries, ledger records, two tests, README lines) in one step, then run the full suite. | yes · no |
| G5 | A new recorded build after the review (TD-062). | not now (recommended for the demo) · yes |

---

## 1. GDPR Article 4: «Definizioni»; the demo uses point 12

Full evidence: package section 5. Worksheet: dated record section 3.

**1. Sources and versions**
- **Stored text:**
  - Regulation (EU) 2016/679 as published in the Official Journal, L 119 of 4 May 2016 (Italian): the original publication, not consolidated.
  - File `data/raw/trial-2026-10-10/documents/gdpr_2016_679_it.pdf` (sha256 `8f7504d2…9427b`), pages 33–35.
  - Byte-identical to the EUR-Lex PDF for CELEX 32016R0679. It has no digital signature, so its authenticity is not established.
  - The corrigenda R(01)–R(03) do not change Art. 4.
- **Comparison source:**
  - EUR-Lex consolidated text, CELEX 02016R0679-20160504 (consolidation date 2016-05-04; no amending act listed).
  - Retrieved on 2026-11-08 by the assistant during M1; archived as `official-sources/gdpr_consolidated_it.html` (sha256 `90d07101…ad8d260`).
  - Official, not authentic.

**2. Text and structure.** The opening sentence, then 26 numbered points; point 16 has a)–b), point 22 a)–c) and point 23 a)–b). No units are missing and the numbering has no gaps. The full stored text (9,791 characters) is in package section 5 B, and on PDF pages 33–35. **The ledger record covers the whole article, not only point 12.** Point 12, exactly as stored (page 34):

```text
12) «violazione dei dati personali»: la violazione di sicurezza che comporta accidentalmente o in modo illecito la 
distruzione, la perdita, la modifica, la divulgazione non autorizzata o l'accesso ai dati personali trasmessi, conservati 
o comunque trattati;
```

**3. Correspondence with the corpus and the anchors**

| Item | Value |
|---|---|
| Provision | `eu-reg-2016-679@oj-l119-2016-it/body/article:4`, printed path «CAPO I > Articolo 4» |
| Inventory entry | `gdpr-2016-679-oj-it:art:4` in `data/reference/gdpr_2016_679_it.inventory.json`; `present`, `pending_human_review`, no status marker |
| Anchors | 3 article segments (72, 74, 76): chars 181738–185161, 185225–189528 and 189592–191657, pages 33, 34 and 35. The running headers between them are context. |
| Chunks | 10 (chunk indices 208–217) |
| Stored text sha256 | `c51bc38c149752871af6c92948ca344654d27570a6a521482c8d02ba8179d5c7` (matches the build, 2026-11-12) |
| Official text sha256 | `2053253a4edb5c7693a4dcb39c87ba8018858cb9148745ed625a852f414a394b` (9,707 chars) |

**4. Discrepancies and normalisation**
- **Words:** none differ from the official text after normalisation, and none is missing or extra.
- **Layout anomalies (14).** Soft hyphens at line ends (6) are in points 1, 2, 9 (twice), 11 and 16(b). One page join falls inside point 9. Blank lines inside sentences (6) are in 16(a), 16(b), 22(a), 22(b), 23(a) and 23(b). Point 25 keeps the footnote reference «(1)»; the footnote text is a separate context segment.
- **What normalisation changed.** Ours: soft hyphens, whitespace and line breaks. Official: whitespace and line breaks, and spacing before punctuation (« : » becomes «:»). For point 12 alone, the official text has a line break after «12)» and a space before «:».

**5. Decisions for you**
- [ ] **A4-1 Scope:** review all 26 points now, or leave Art. 4 unrecorded. Without it, «violazione dei dati personali» cannot be cited as a definition.
- [ ] **A4-2:** the six soft-hyphen splits are PDF hyphenation, and each joined word is the printed word.
- [ ] **A4-3:** keeping the footnote reference «(1)» in point 25 while the footnote is stored as context is right.
- [ ] **A4-4:** nothing is lost or duplicated at the page joins 33→34 (inside point 9: «…degli Stati» / «membri non sono considerate…») and 34→35 (between points 21 and 22).
- [ ] **A4-5:** the six blank lines inside sentences are layout only.
- [ ] Worksheet decisions 1–5, official check (G2), ledger outcome.

---

## 2. GDPR Article 33: «Notifica di una violazione dei dati personali all'autorità di controllo»

Full evidence: package section 6, and the side-by-side extraction in [`m1-article-33-comparison.md`](m1-article-33-comparison.md). Worksheet: dated record section 4.

**1. Sources and versions.** As for Art. 4: the stored text is the 2016 Official Journal original, p. 52, and the comparison source is EUR-Lex consolidated (2016-05-04). No corrigendum changes Art. 33.

**2. Text and structure.** Paragraphs 1–5; paragraph 3 has points a)–d). The text exactly as stored follows. `⟨SHY⟩` is an invisible soft hyphen, and spaces at line ends are present but cannot be seen.

```text
Articolo 33

Notifica di una violazione dei dati personali all'autorità di controllo

1.
In caso di violazione dei dati personali, il titolare del trattamento notifica la violazione all'autorità di controllo 
competente a norma dell'articolo 55 senza ingiustificato ritardo e, ove possibile, entro 72 ore dal momento in cui ne è 
venuto a conoscenza, a meno che sia improbabile che la violazione dei dati personali presenti un rischio per i diritti e le 
libertà delle persone fisiche. Qualora la notifica all'autorità di controllo non sia effettuata entro 72 ore, è corredata dei 
motivi del ritardo.

2.
Il responsabile del trattamento informa il titolare del trattamento senza ingiustificato ritardo dopo essere venuto a 
conoscenza della violazione.

3.
La notifica di cui al paragrafo 1 deve almeno:

a) descrivere la natura della violazione dei dati personali compresi, ove possibile, le categorie e il numero approssi⟨SHY⟩

mativo di interessati in questione nonché le categorie e il numero approssimativo di registrazioni dei dati personali in 
questione;

b)  comunicare il nome e i dati di contatto del responsabile della protezione dei dati o di altro punto di contatto presso

cui ottenere più informazioni;

c)  descrivere le probabili conseguenze della violazione dei dati personali;

d)  descrivere le misure adottate o di cui si propone l'adozione da parte del titolare del trattamento per porre rimedio

alla violazione dei dati personali e anche, se del caso, per attenuarne i possibili effetti negativi.

4.
Qualora e nella misura in cui non sia possibile fornire le informazioni contestualmente, le informazioni possono 
essere fornite in fasi successive senza ulteriore ingiustificato ritardo.

5.
Il titolare del trattamento documenta qualsiasi violazione dei dati personali, comprese le circostanze a essa relative, 
le sue conseguenze e i provvedimenti adottati per porvi rimedio. Tale documentazione consente all'autorità di controllo 
di verificare il rispetto del presente articolo.
```

**3. Correspondence with the corpus and the anchors**

| Item | Value |
|---|---|
| Provision | `eu-reg-2016-679@oj-l119-2016-it/body/article:33`, printed path «CAPO IV > Sezione 2 > Articolo 33» |
| Inventory entry | `gdpr-2016-679-oj-it:art:33`; `present`, `pending_human_review`, no status marker |
| Anchors | 1 article segment (148): chars 253118–255125, page 52 |
| Chunks | 2 |
| Stored text sha256 | `17ad07bbee1cd8bef89280dd2d4847f0a71d6f6eb5097b0a0f0508b536c23a8f` (matches the build, 2026-11-12) |
| Official text sha256 | `35ad52b17f064957bddf880c32e094841e7e9142c112dc0a1906e07315a420b2` (1,979 chars) |

**4. Discrepancies and normalisation**
- **Words:** none differ.
- **Two programs agree.** A second program (Poppler `pdftotext`) reads the same 299 tokens, in the same order, from the PDF's text layer. Both read the text layer, though, so only reading the printed page confirms the words.
- **Layout anomalies (3).**
  - In 3(a), «approssimativo» is stored as «approssi⟨SHY⟩», a blank line, then «mativo».
  - Blank lines inside sentences in 3(b) and 3(d).
  - The assistant's look at the rendered page 52 (comparison aid, A.2) found no blank line printed at any of these three places. You should confirm this yourself.
- **Character form.** The printed page uses typographic apostrophes (’), while the stored text and the EUR-Lex text use the ASCII apostrophe ('). The normalisation treats them as equal.
- **What normalisation changed:** the soft hyphen, whitespace and line breaks.

**5. Decisions for you**
- [ ] **A33-1:** the printed page 52 matches the stored text word for word: paragraphs 1–5 and points a)–d). This is the one check the comparison aid could not do.
- [ ] **A33-2:** the hyphenated «approssi-/mativo» is the printed word «approssimativo», and the blank lines in 3(b) and 3(d) are layout only.
- [ ] **A33-3 (noted, not part of the structural review):** the Digital Omnibus proposal COM(2025) 837 would replace Art. 33(1). M1 found it neither adopted nor published as of 2026-11-08, and it has not been re-checked since. It affects how an answer about Art. 33(1) should be worded, not this review.
- [ ] Worksheet decisions 1–5, official check (G2), ledger outcome.

---

## 3. GDPR Article 34: «Comunicazione di una violazione dei dati personali all'interessato»

Full evidence: package section 7. Worksheet: dated record section 5.

**1. Sources and versions.** As for Art. 4: Official Journal original, pp. 52–53; EUR-Lex consolidated (2016-05-04). No corrigendum changes Art. 34.

**2. Text and structure.** Paragraphs 1–4; paragraph 3 has points a)–c). The text exactly as stored follows. The line `⟦ … ⟧` marks the page join and is not part of the text.

```text
Articolo 34

Comunicazione di una violazione dei dati personali all'interessato

1.
Quando la violazione dei dati personali è suscettibile di presentare un rischio elevato per i diritti e le libertà delle 
persone fisiche, il titolare del trattamento comunica la violazione all'interessato senza ingiustificato ritardo.

⟦ end of piece 1 (page 52) · start of piece 2 (page 53) ⟧
2.
La comunicazione all'interessato di cui al paragrafo 1 del presente articolo descrive con un linguaggio semplice e 
chiaro la natura della violazione dei dati personali e contiene almeno le informazioni e le misure di cui all'articolo 33, 
paragrafo 3, lettere b), c) e d).

3.
Non è richiesta la comunicazione all'interessato di cui al paragrafo 1 se è soddisfatta una delle seguenti condizioni:

a)  il titolare del trattamento ha messo in atto le misure tecniche e organizzative adeguate di protezione e tali misure

erano state applicate ai dati personali oggetto della violazione, in particolare quelle destinate a rendere i dati personali 
incomprensibili a chiunque non sia autorizzato ad accedervi, quali la cifratura;

b)  il titolare del trattamento ha successivamente adottato misure atte a scongiurare il sopraggiungere di un rischio

elevato per i diritti e le libertà degli interessati di cui al paragrafo 1;

c)  detta comunicazione richiederebbe sforzi sproporzionati. In tal caso, si procede invece a una comunicazione pubblica

o a una misura simile, tramite la quale gli interessati sono informati con analoga efficacia.

4.
Nel caso in cui il titolare del trattamento non abbia ancora comunicato all'interessato la violazione dei dati 
personali, l'autorità di controllo può richiedere, dopo aver valutato la probabilità che la violazione dei dati personali 
presenti un rischio elevato, che vi provveda o può decidere che una delle condizioni di cui al paragrafo 3 è soddisfatta.
```

**3. Correspondence with the corpus and the anchors**

| Item | Value |
|---|---|
| Provision | `eu-reg-2016-679@oj-l119-2016-it/body/article:34`, printed path «CAPO IV > Sezione 2 > Articolo 34» |
| Inventory entry | `gdpr-2016-679-oj-it:art:34`; `present`, `pending_human_review`, no status marker |
| Anchors | 2 article segments (149, 151): chars 255125–255446 (page 52) and 255510–257015 (page 53). The running header between them is context. |
| Chunks | 2 |
| Stored text sha256 | `c9ce5d93754c678cdd1f8f3f1f3dd2ffe584e5da085206fbce38976f119091e6` (matches the build, 2026-11-12) |
| Official text sha256 | `7ca3656e2b8e999733da88d3329f772969f667d722dd77c3a9a8c758555ffc88` (1,805 chars) |

**4. Discrepancies and normalisation**
- **Words:** none differ.
- **Layout anomalies (3):** blank lines inside sentences in 3(a), 3(b) and 3(c).
- **What normalisation changed:** whitespace and line breaks only.

**5. Decisions for you**
- [ ] **A34-1:** nothing is lost or duplicated at the page join between paragraph 1 (page 52) and paragraph 2 (page 53).
- [ ] **A34-2:** the three blank lines in 3(a)–(c) are layout only.
- [ ] Worksheet decisions 1–5, official check (G2), ledger outcome.

---

## 4. GDPR Article 55: «Competenza»

Full evidence: package section 8. Worksheet: dated record section 6.

**1. Sources and versions.** As for Art. 4: Official Journal original, p. 67; EUR-Lex consolidated (2016-05-04). No corrigendum changes Art. 55.

**2. Text and structure.** Paragraphs 1–3, with no points. The text exactly as stored:

```text
Articolo 55

Competenza

1.
Ogni autorità di controllo è competente a eseguire i compiti assegnati e a esercitare i poteri a essa conferiti a 
norma del presente regolamento nel territorio del rispettivo Stato membro.

2.
Se il trattamento è effettuato da autorità pubbliche o organismi privati che agiscono sulla base dell'articolo 6, 
paragrafo 1, lettera c) o e), è competente l'autorità di controllo dello Stato membro interessato. In tal caso, non si 
applica l'articolo 56.

3.
Le autorità di controllo non sono competenti per il controllo dei trattamenti effettuati dalle autorità giurisdizionali 
nell'esercizio delle loro funzioni giurisdizionali.
```

**3. Correspondence with the corpus and the anchors**

| Item | Value |
|---|---|
| Provision | `eu-reg-2016-679@oj-l119-2016-it/body/article:55`, printed path «CAPO VI > Sezione 2 > Articolo 55» |
| Inventory entry | `gdpr-2016-679-oj-it:art:55`; `present`, `pending_human_review`, no status marker |
| Anchors | 1 article segment (206): chars 314231–314889, page 67 |
| Chunks | 1 |
| Stored text sha256 | `8d10a5c3289f0c5dbd423d534a5f1b696f07b59cffac248cd33165596c2ee606` (matches the build, 2026-11-12) |
| Official text sha256 | `c782e12897b6fe7cde260f76ff478177b32c6792290c5588c6767183d8ab1a54` (649 chars) |

**4. Discrepancies and normalisation.** No word differs and there are no anomalies. Normalisation changed only whitespace and line breaks.

**5. Decisions for you**
- [ ] **A55-1:** Art. 55 may be cited without Art. 56, the lead supervisory authority. 55(2) ends «non si applica l'articolo 56». Art. 56 is excluded because our stored text predates corrigenda C2 and C3.
- [ ] Worksheet decisions 1–5, official check (G2), ledger outcome.

---

## 5. Privacy Code Article 2-bis: «(Autorità di controllo)»

Full evidence: package section 9. Worksheet: dated record section 7.

**1. Sources and versions**
- **Stored text:**
  - A user-provided transcription of the consolidated Code (d.lgs. 30 giugno 2003, n. 196), main body only, page 2.
  - File `data/raw/trial-2026-10-10/documents/codice_privacy_dlgs_196_2003.pdf` (sha256 `0d264a29…16ffe5`).
  - Version `it-dlgs-2003-196@transcription-vigente-2026-11-05`: its reference date, 2026-11-05, is unverified.
  - Not an official document.
- **Comparison source:**
  - Normattiva, Art. 2-bis, text in force: «Testo in vigore dal: 19-9-2018», «ultimo aggiornamento all'atto: 19/02/2026». The «vigente al» field had no date.
  - Retrieved on 2026-11-08 by the assistant; archived as `official-sources/normattiva_2bis.html` (sha256 `f95c865e…dcd4435ce`).
  - Official, not authentic. Normattiva states that only the Gazzetta Ufficiale is official and definitive.
- **Provenance evidence:**
  - The archive also holds Gazzetta Ufficiale n. 205 of 4 September 2018, with D.Lgs. 10 agosto 2018, n. 101. According to the archive's `NOTICE.md`, its art. 2, comma 1, lettera e) inserts Art. 2-bis.
  - Also archived: an errata corrige and a rettifica notice, which concern other articles.
  - These were downloaded on 2026-11-09. Their authenticity is not verified, because the IPZS verification tool was not run, and the package does not compare Art. 2-bis with them.

**2. Text and structure.** One paragraph. The title and the paragraph are each inside Normattiva's amendment markers «((» … «))». The text exactly as stored:

```text
Art. 2-bis

(( (Autorità di controllo). ))

((

1. L'Autorità di controllo di cui all'articolo 51 del regolamento è individuata nel Garante per la protezione dei
dati personali, di seguito «Garante», di cui all'articolo 153.

))
```

**3. Correspondence with the corpus and the anchors**

| Item | Value |
|---|---|
| Provision | `it-dlgs-2003-196@transcription-vigente-2026-11-05/body/article:2-bis`, printed path «PARTE I > TITOLO I > CAPO I > Art. 2-bis» |
| Inventory entry | `dlgs-196-2003-transcription:body:art:2-bis` in `data/reference/codice_privacy_dlgs_196_2003.main_body.inventory.json`; `present`, `pending_human_review`, no status marker, title stored as «(( (Autorità di controllo). ))» |
| Anchors | 1 article segment (10): chars 3948–4178, page 2 |
| Chunks | 1 |
| Stored text sha256 | `db01a28beee7de84853c55e51c1bea397620c6f34cbd08cd25900c60f2e6294a` (matches the build, 2026-11-12) |
| Official text sha256 | `73c7c3bd222f87bf114e18e1c8ab1a04f5722ce888104572de4b1c85f8acc988` (225 chars) |
| Qualifications that stay attached | `unofficial_transcription`, `reference_date_unverified`, `legal_validity_not_established` |

**4. Discrepancies and normalisation**
- **Words:** none differ, and there are no anomalies.
- **What normalisation changed:** whitespace, and the spaces inside the markers (`(( (Autorità` and `). ))` close up). The markers themselves count in the comparison and match.
- **Cross-references:**
  - «articolo 51 del regolamento» is GDPR Art. 51. Code Art. 1 defines «Regolamento» as Regulation (EU) 2016/679, and the system already follows this one-hop reference. Art. 51 is not in the review set, so it would be shown as non-citable evidence.
  - «articolo 153» is Code Art. 153, the Garante.

**5. Decisions for you**
- [ ] **A2bis-1 (G3):** a user transcription may be a primary citation, with the `unofficial_transcription` qualification. Or leave Art. 2-bis unrecorded for now.
- [ ] **A2bis-2:** the amendment markers «((» «))» are recorded as the source prints them. They mark amended text, not a repeal, and the amending act is not named in the stored text.
- [ ] **A2bis-3:** the inventory title «(( (Autorità di controllo). ))», with markers, is the right representation. Or correct it to «(Autorità di controllo)» or «Autorità di controllo», which would be a `corrected` outcome with the change listed. Titles do not affect the anchors.
- [ ] **A2bis-4:** accept that the transcription's reference date (2026-11-05) stays unverified. It remains a qualification, not a blocker.
- [ ] Worksheet decisions 1–5, official check (G2), ledger outcome.
