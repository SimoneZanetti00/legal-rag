# GDPR Article 33: PDF text and project-extracted text, side by side

> **Comparison aid for the M1 human review, not a review.** Prepared on 2026-11-09 by an AI assistant (Claude Code).
>
> - It records no decision and marks nothing as reviewed or verified.
> - It establishes nothing about legal validity.
> - The reference is the printed page: PDF page 52 of the source file. Both text extractions below read the PDF's embedded text layer, so their agreement does not show that either matches the printed page.

## Sources

| Item | Value |
|---|---|
| Source PDF | `data/raw/trial-2026-10-10/documents/gdpr_2016_679_it.pdf` (sha256 `8f7504d289853f57647bd94d8926f4661e7b41a1204f4d74eca9d8685069427b`) |
| Page | PDF page 52, printed as «L 119/52» in the running header (OJ L 119, 4.5.2016). Article 33 starts and ends on this page. |
| Project-extracted text | `docs/reviews/m1-human-review-package.md` (sha256 `2f90fe52723f91c63f4414404c4ce880e5a37bfc61de00f2e3ec45568665ce56`), section 6 «B. Extracted text». It is the stored article text of build `build-f76ff6031f2fc82c4852f0a2bde27807` (text sha256 `17ad07bbee1cd8bef89280dd2d4847f0a71d6f6eb5097b0a0f0508b536c23a8f`). |

**How the texts are shown**

- `⟨SHY⟩` stands for the invisible soft-hyphen character U+00AD, in both A and B. It is the only character replaced for display.
- Line breaks are shown as they are, except that Poppler's Windows line endings (CR LF) are shown as plain line breaks.
- Spaces at the end of a line are present but cannot be seen.
- Nothing else has been normalised or corrected.

## A. Original PDF text

### A.1 Text layer of PDF page 52, extracted directly from the PDF

Extracted with **Poppler `pdftotext` 4.00** (`-f 52 -l 52 -layout -enc UTF-8`), a different program from the one the project uses (PyMuPDF). The lines run from «Articolo 33» to just before «Articolo 34». The `-layout` mode keeps the line breaks and the hanging indent of points a)–d).

This is the PDF's embedded text, not a reading of the printed page and not OCR. Poppler's `-raw` mode gives the same words, in the same order.

```text
                                                                  Articolo 33

                            Notifica di una violazione dei dati personali all'autorità di controllo

1. In caso di violazione dei dati personali, il titolare del trattamento notifica la violazione all'autorità di controllo
competente a norma dell'articolo 55 senza ingiustificato ritardo e, ove possibile, entro 72 ore dal momento in cui ne è
venuto a conoscenza, a meno che sia improbabile che la violazione dei dati personali presenti un rischio per i diritti e le
libertà delle persone fisiche. Qualora la notifica all'autorità di controllo non sia effettuata entro 72 ore, è corredata dei
motivi del ritardo.

2. Il responsabile del trattamento informa il titolare del trattamento senza ingiustificato ritardo dopo essere venuto a
conoscenza della violazione.

3. La notifica di cui al paragrafo 1 deve almeno:

a) descrivere la natura della violazione dei dati personali compresi, ove possibile, le categorie e il numero approssi⟨SHY⟩
   mativo di interessati in questione nonché le categorie e il numero approssimativo di registrazioni dei dati personali in
   questione;

b) comunicare il nome e i dati di contatto del responsabile della protezione dei dati o di altro punto di contatto presso
   cui ottenere più informazioni;

c) descrivere le probabili conseguenze della violazione dei dati personali;

d) descrivere le misure adottate o di cui si propone l'adozione da parte del titolare del trattamento per porre rimedio
   alla violazione dei dati personali e anche, se del caso, per attenuarne i possibili effetti negativi.

4. Qualora e nella misura in cui non sia possibile fornire le informazioni contestualmente, le informazioni possono
essere fornite in fasi successive senza ulteriore ingiustificato ritardo.

5. Il titolare del trattamento documenta qualsiasi violazione dei dati personali, comprese le circostanze a essa relative,
le sue conseguenze e i provvedimenti adottati per porvi rimedio. Tale documentazione consente all'autorità di controllo
di verificare il rispetto del presente articolo.
```

### A.2 What the rendered page shows (observations, not a review)

The assistant rendered page 52 as an image at 200 dpi and looked at it. These observations need to be checked by the reviewer against the PDF itself.

- **Headings:** «Articolo 33» is printed in italics, centred. The title «Notifica di una violazione dei dati personali all’autorità di controllo» is printed in bold, centred.
- **Paragraph numbers:** each of «1.» to «5.» is printed on the same line as the start of its paragraph, followed by a wide gap.
- **Point 3(a):** the line ends with «approssi-», with a visible hyphen, and the next line begins «mativo di interessati…». There is no blank line between the two lines.
- **Point 3(b):** the line ends with «presso»; the next line, «cui ottenere più informazioni;», follows directly with a hanging indent. There is no blank line.
- **Point 3(d):** the line ends with «rimedio»; the next line, «alla violazione dei dati personali e anche, …», follows directly with a hanging indent. There is no blank line.
- **Spacing:** there is extra vertical space between paragraphs 1, 2, 3, 4 and 5, and between points a)–d).
- **Apostrophes:** they are printed as typographic apostrophes (’), as in «all’autorità», «dell’articolo», «l’adozione».

## B. Project-extracted text

Copied verbatim from the review package, section 6 «B. Extracted text». It is the text stored in the recorded build, extracted by the project with PyMuPDF.

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

## C. Potential discrepancies and points requiring human verification

**Automated comparison of A.1 and B.** Both texts were split at whitespace only, with no other normalisation:

- Both contain **299 tokens, identical and in the same order**: words, punctuation, paragraph numbers «1.»–«5.», point letters «a)»–«d)», and the two halves «approssi⟨SHY⟩» and «mativo».
- No word, punctuation mark, paragraph number or point letter is missing, duplicated or altered **between the two extractions**.
- All the differences between A.1 and B are whitespace and line structure; they are listed below.

**What this does not show:** both extractions read the same embedded text layer. If that layer differed from the printed glyphs, neither would reveal it. Only a reading of the printed page can confirm the words.

| # | Where | PDF: printed page (A.2) and text layer (A.1) | Project text (B) | Kind | To verify on PDF page 52 |
|---|---|---|---|---|---|
| 1 | 3(a), «approssimativo» | Printed: «approssi-» at the end of a line, then «mativo» on the next line. Text layer: «approssi» + U+00AD + one line break + «mativo». | «approssi» + U+00AD + **a blank line** + «mativo». | Extra blank line inside a hyphenated word; same characters otherwise. | The printed word is «approssimativo», hyphenated across a line break, with nothing printed between the two halves. |
| 2 | 3(b), «presso / cui» | Printed: «… punto di contatto presso» / «cui ottenere più informazioni;» on consecutive lines. Text layer: one line break. | «presso» + **a blank line** + «cui ottenere più informazioni;». | Extra blank line inside a sentence. | Nothing is printed between «presso» and «cui», and point (b) is a single sentence. |
| 3 | 3(d), «rimedio / alla» | Printed: «… per porre rimedio» / «alla violazione dei dati personali e anche, …» on consecutive lines. Text layer: one line break. | «rimedio» + **a blank line** + «alla violazione …». | Extra blank line inside a sentence. | Nothing is printed between «rimedio» and «alla», and point (d) is a single sentence. |
| 4 | Paragraph numbers 1.–5. | Printed: each number on the same line as its paragraph text. Text layer: «1. In caso…», on one line. | Each number on its own line: «1.» / «In caso…». | Line structure only. | Each number belongs to the paragraph that follows it, and no number is missing or repeated (1, 2, 3, 4, 5). |
| 5 | Points b), c), d) | Poppler output (A.1): one space after the letter (Poppler may collapse spaces). | Two spaces after «b)», «c)» and «d)»; one after «a)». | Whitespace only. | Nothing is printed between each letter and its text. |
| 6 | Line ends | Poppler output (A.1): no spaces at line ends (Poppler may trim them). | 9 lines end with a space. Apart from the separate paragraph-number lines and the blank lines, the line breaks fall at the same places as in A.1 (23 lines each). | Whitespace only. | — |
| 7 | Apostrophes | Printed: typographic apostrophe (’). Text layer: ASCII apostrophe (U+0027). | ASCII apostrophe (U+0027), as in the text layer. | Character form: both extractions differ from the printed glyph in the same way. | Whether quotations need the printed form (’). The official EUR-Lex text compared in the package uses U+0027 for this article. |
| 8 | Heading and title | Printed: italics (heading) and bold (title), centred. | Plain text, same words, each on its own line. | Formatting not carried by plain text. | The heading «Articolo 33» and the title are the ones printed. |
| 9 | Every other word | Text layer identical to B (299 tokens). | — | Not checked against the printed page. | Read paragraphs 1, 2, 3, 3(a)–3(d), 4 and 5 against the printed page, word by word. |

**Not done here:** no correction, normalisation or decision. The stored text, the package, the review record and the ledger are unchanged. For the comparison with the official EUR-Lex text, see the package, section 6 C.
