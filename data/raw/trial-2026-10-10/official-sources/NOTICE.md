# Official sources: notice and attribution

This directory holds documents from official portals, kept exactly as downloaded: not edited, not reformatted, with no line-ending conversion. Their full provenance (hashes, sizes, how the article texts are extracted) is in [official_sources.json](official_sources.json).

- **Two web pages**, downloaded on 2026-11-08 to compare our corpus text with official texts during the M1 human review. **Neither is an authentic text.**
- **Three complete Gazzetta Ufficiale issues**, downloaded on 2026-11-09 as provenance evidence for Privacy Code Art. 2-bis. **Their authenticity has not been verified** (see the last section).

None of these files is a legal opinion. None establishes that any provision is legally valid, in force, or applicable at any date.

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

## Gazzetta Ufficiale issues: D.Lgs. 101/2018 and its two corrigenda

These are three complete online issues of the Gazzetta Ufficiale della Repubblica Italiana, Serie Generale. They were downloaded on 2026-11-09 from www.gazzettaufficiale.it.

| File | Issue | Content | Downloaded from | SHA-256 |
|---|---|---|---|---|
| `gu_sg_2018-09-04_n205_dlgs_101_2018.pdf` | n. 205, 4 September 2018 | D.Lgs. 10 agosto 2018, n. 101 (18G00129). Its art. 2, comma 1, lettera e), on page 2, inserts Art. 2-bis into the Privacy Code. | https://www.gazzettaufficiale.it/eli/gu/2018/09/04/205/sg/pdf | `baa9b2eeea6f97591a0927a44ee0f2df5265466d56e471cb2f08010ba1213e97` |
| `gu_sg_2018-09-12_n212_errata_corrige_18A05889.pdf` | n. 212, 12 September 2018 | ERRATA-CORRIGE for D.Lgs. 101/2018 (18A05889, page 25). It concerns Privacy Code art. 166, not Art. 2-bis. | https://www.gazzettaufficiale.it/eli/gu/2018/09/12/212/sg/pdf | `1c2757c6e7a80a13156b94cdf040f1af353148fe92bb9f93c05c57f7e4d3adf9` |
| `gu_sg_2018-09-27_n225_avviso_rettifica_18A06204.pdf` | n. 225, 27 September 2018 | AVVISO DI RETTIFICA for D.Lgs. 101/2018 (18A06204, page 28). It concerns Privacy Code art. 130 and art. 166, not Art. 2-bis. | https://www.gazzettaufficiale.it/eli/gu/2018/09/27/225/sg/pdf | `1a676f49520d06cd4c93f56c648e69ddba78768f74c4237e3888be34ff5e7593` |

**Authenticity: not verified.**
- **What the site describes:** the Gazzetta website states that, since 2 January 2009, the authenticity of its online edition is attested by a process using a digital stamp («timbro digitale», a two-dimensional code on each page) and a digital signature («firma digitale»). It also states that an IPZS application verifies the stamp, both offline and against the copy held on the IPZS servers. The exact statements are quoted in `official_sources.json`, under `authenticity_verification`.
- **What was observed:** pages 1 and 6 of the D.Lgs. 101/2018 issue carry such two-dimensional codes. The files contain no embedded PDF digital signature.
- **What was not done:** **the IPZS verification application was not run.** The authenticity of these downloaded copies has therefore not been independently verified.

**Why they are archived:** as provenance evidence for the wording of Art. 2-bis as introduced in 2018, and for the corrigenda check. They are not archived as a claim that any provision is legally valid, in force, or applicable at a particular date. Later amendments are outside these documents.

**Reuse:** the reuse terms of www.gazzettaufficiale.it were not examined during this acquisition.

**Changes:** none. The files are as downloaded.
