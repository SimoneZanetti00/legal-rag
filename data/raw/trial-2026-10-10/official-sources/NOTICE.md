# Official sources: notice and attribution

This directory holds two web pages from official portals. They were downloaded on 2026-11-08 to compare our corpus text with official texts during the M1 human review. They are kept exactly as downloaded: not edited, not reformatted, with no line-ending conversion.

**Neither file is an authentic text.** Neither is a legal opinion, and neither establishes that any provision is valid or in force. Their full provenance (hashes, sizes, how the article texts are extracted) is in [official_sources.json](official_sources.json).

## `gdpr_consolidated_it.html`: EUR-Lex

| | |
|---|---|
| Content | Regulation (EU) 2016/679 (GDPR), consolidated text, Italian, CELEX 02016R0679-20160504 (consolidated to 2016-05-04) |
| Source | EUR-Lex, https://eur-lex.europa.eu/legal-content/IT/TXT/HTML/?uri=CELEX:02016R0679-20160504 |
| Retrieved | 2026-11-08 12:28:58 +01:00 |
| SHA-256 | `90d0710134489e08fc26f142c416028d2ee6f3cf049f83c084e772da3ac8d260` |

**Attribution:** Source: EUR-Lex (https://eur-lex.europa.eu), © European Union. The consolidated text is reused under the [Creative Commons Attribution 4.0 International licence (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/). The EUR-Lex legal notice (https://eur-lex.europa.eu/content/legal-notice/legal-notice.html, read 2026-11-08) states that the reuse policy "is based on Decision 2011/833/EU" and that "you can re-use the content provided you acknowledge the source and indicate any changes you have made".

**Changes:**
- The file itself: none.
- Texts derived from it (the article extracts compared in the M1 review package): markup removed, lines stripped of surrounding whitespace, and the articles cut out, as recorded in `official_sources.json` → `extraction`.

**Authenticity:** not authentic. The EUR-Lex legal notice states: "Only European Union documents published in the Official Journal of the European Union are deemed authentic."

## `normattiva_2bis.html`: Normattiva

| | |
|---|---|
| Content | Decreto legislativo 30 giugno 2003, n. 196 (Codice in materia di protezione dei dati personali), Art. 2-bis, text in force as shown by Normattiva («Testo in vigore dal: 19-9-2018»; «ultimo aggiornamento all'atto: 19/02/2026»; the «vigente al» date is not shown) |
| Source | Normattiva, https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2003-06-30;196~art2bis |
| Retrieved | 2026-11-08 12:30:57 +01:00 |
| SHA-256 | `f95c865efdc99dedd1993e993b343d1d31dbc902b72ae6992a5f3d4dcd4435ce` |

**Required qualification:** Fonte: Normattiva (www.normattiva.it). **Testo non autentico e gratuito**: a non-authentic text, provided free of charge.

Normattiva's legal notes (saved copy: `data/raw/trial-2026-10-10/source-pages/normattiva_note_legali.html`) state:

> I testi presenti nella banca dati "Normattiva" non hanno carattere di ufficialità. L'unico testo ufficiale e definitivo è quello pubblicato sulla Gazzetta Ufficiale Italiana a mezzo stampa, che prevale in casi di discordanza. La riproduzione dei testi forniti nel formato elettronico è consentita purchè venga menzionata la fonte, il carattere non autentico e gratuito.

**Changes:**
- The file itself: none.
- Texts derived from it: as for the EUR-Lex file above.
