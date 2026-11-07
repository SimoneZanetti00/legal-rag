# Parser cross-check of the P1.2 reference inventories

*Generated 2026-11-07 by `python -m tools.reference_inventory.crosscheck`, which reads the inventories and never writes them. The inventories were built from the source PDFs first; this report checks the parser against them, not the other way round.*

## Inputs

| Item | Path | SHA-256 |
|---|---|---|
| GDPR inventory | `data/reference/gdpr_2016_679_it.inventory.json` | `e6fbaba9a996dfd0329501bc636bdaa1d54c52d5a8f21b6264a1247538efd25f` |
| Privacy Code inventory | `data/reference/codice_privacy_dlgs_196_2003.main_body.inventory.json` | `6e4b06ddf1797ea5b2fbf4bd6b59b2338d03894292814e24406f835db598af24` |
| Privacy Code parser output | `data/processed/trial-2026-10-10/codice_privacy_main_body.jsonl` | `e2c443d550e6dbf99225ec09ff7d5f35aaf90bb880c976bca0dd91513202689f` |

- **Inventory hashes** are those of the canonical serialization (UTF-8, LF line endings). `.gitattributes` keeps these files LF in every checkout, so the hashes equal the files' bytes.
- **Privacy Code parser output:** the trial's existing chunk file (main body, boundary `ALLEGATO A.1`, CHUNK_SIZE 1200, CHUNK_OVERLAP 150; see the trial manifest). An article *run* is a sequence of consecutive chunks with the same `location.article`; its page is the page of its first chunk.
- **GDPR parser output:** no current chunk file exists (the only GDPR chunks are in the stale `chunks.jsonl`). The parser's heading detection (`load_document`, `_split_blocks`, `_group_units`) was run in memory at commit `a2697db8974a262b2d0e310f0adb568b13bdbad0`; `src/ingestion.py`, `src/chunking.py`, `src/models.py` identical to that commit. No chunk was generated and no file was written. Each article heading block is one run; its page is the heading's page.
- **Alignment:** the inventory's label sequence and the parser's run sequence are aligned with `difflib.SequenceMatcher`; equal labels in aligned positions are matches, aligned different labels are label mismatches.

## GDPR

| Measure | Value |
|---|---|
| Inventory entries | 99 (present 99) |
| Parser article headings / runs | 99 |
| Matched: same label, same page | 99 |
| Same label, different page | 0 |
| Inventory entries not found by the parser | 0 |
| Parser-only labels | 0 |
| Label mismatches (aligned, different label) | 0 |
| Labels the parser assigns more than once | 0 |
| Wrong section assigned by the parser | 0 |

- **Matched entries (99):** `1`, `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`, `10`, `11`, `12`, `13`, `14`, `15`, `16`, `17`, `18`, `19`, `20`, `21`, `22`, `23`, `24`, `25`, `26`, `27`, `28`, `29`, `30`, `31`, `32`, `33`, `34`, `35`, `36`, `37`, `38`, `39`, `40`, `41`, `42`, `43`, `44`, `45`, `46`, `47`, `48`, `49`, `50`, `51`, `52`, `53`, `54`, `55`, `56`, `57`, `58`, `59`, `60`, `61`, `62`, `63`, `64`, `65`, `66`, `67`, `68`, `69`, `70`, `71`, `72`, `73`, `74`, `75`, `76`, `77`, `78`, `79`, `80`, `81`, `82`, `83`, `84`, `85`, `86`, `87`, `88`, `89`, `90`, `91`, `92`, `93`, `94`, `95`, `96`, `97`, `98`, `99`.
- **Same label, different page:** none.
- **Not found by the parser:** none.
- **Parser-only labels:** none.
- **Label mismatches:** none.
- **Labels assigned to more than one parser run:** none.
- **Parser labels absent from the inventory:** none.
- **Section:** the parser's `section` equals the innermost printed division for 99 of 99 matched articles.

## Privacy Code (main body)

| Measure | Value |
|---|---|
| Inventory entries | 222 (ambiguous 2, marked_repealed 114, present 106) |
| Parser article headings / runs | 221 |
| Matched: same label, same page | 221 |
| Same label, different page | 0 |
| Inventory entries not found by the parser | 1 |
| Parser-only labels | 0 |
| Label mismatches (aligned, different label) | 0 |
| Labels the parser assigns more than once | 0 |
| Wrong section assigned by the parser | 21 |

- **Matched entries (221):** `1`, `2`, `2-bis`, `2-ter`, `2-quater`, `2-quinquies`, `2-sexies`, `2-septies`, `2-octies`, `2-novies`, `2-decies`, `2-undecies`, `2-duodecies`, `2-terdecies`, `2-quaterdecies`, `2-quaterdecies.1`, `2-quinquiesdecies`, `2-sex-decies`, `2-septies-decies`, `3`, `4`, `5`, `6`, `7`, `8`, `9`, `10`, `11`, `12`, `13`, `14`, `15`, `16`, `17`, `18`, `19`, `20`, `21`, `22`, `23`, `24`, `25`, `26`, `27`, `28`, `29`, `30`, `31`, `32`, `32-bis`, `33`, `34`, `35`, `36`, `37`, `38`, `39`, `40`, `41`, `42`, `43`, `44`, `45`, `45-bis`, `46`, `47`, `48`, `49`, `50`, `51`, `52`, `53`, `54`, `55`, `56`, `57`, `58`, `59`, `60`, `61`, `62`, `63`, `64`, `65`, `66`, `67`, `68`, `69`, `70`, `71`, `72`, `73`, `74`, `75`, `76`, `77`, `78`, `79`, `80`, `81`, `82`, `83`, `84`, `85`, `86`, `87`, `88`, `89`, `89-bis`, `90`, `91`, `92`, `93`, `94`, `95`, `96`, `97`, `98`, `99`, `100`, `101`, `102`, `103`, `104`, `105`, `106`, `107`, `108`, `109`, `110`, `110-bis`, `111`, `111-bis`, `112`, `113`, `114`, `115`, `116`, `117`, `118`, `119`, `120`, `121`, `122`, `123`, `124`, `125`, `126`, `127`, `128`, `129`, `130`, `131`, `132`, `132-bis`, `132-ter`, `132-quater`, `133`, `134`, `135`, `136`, `137`, `138`, `139`, `140`, `140-bis`, `141`, `142`, `143`, `144`, `144-bis`, `145`, `146`, `147`, `148`, `149`, `150`, `151`, `152`, `153`, `154`, `154-bis`, `154-ter`, `155`, `156`, `157`, `158`, `159`, `160`, `160-bis`, `161`, `162`, `162-bis`, `162-ter`, `163`, `164`, `164-bis`, `165`, `166`, `167`, `167-bis`, `167-ter`, `168`, `169`, `170`, `171`, `172`, `173`, `174`, `175`, `176`, `177`, `178`, `179`, `180`, `181`, `182`, `183`, `184`, `185`, `186`.
- **Same label, different page:** none.
- **Not found by the parser:** `2-quindecies`.
- **Parser-only labels:** none.
- **Label mismatches:** none.
- **Labels assigned to more than one parser run:** none.
- **Parser labels absent from the inventory:** none.
- **Section:** the parser's `section` equals the innermost printed division for 200 of 221 matched articles; **21 articles receive a wrong section** (see below).

## Parser defect: division headings marked with `((` are not recognised

21 Privacy Code articles receive an incorrect section assignment. This is a parser/chunking defect, not an expected difference between the two representations.

- **Cause:** the chunker's section rule only accepts a line that starts with the division word. The printed headings below begin with the amendment marker `((`, so the parser does not recognise them as headings. The previous section therefore stays in force for the following articles.
- **Wrong sections:**
  - printed division `(( CAPO II`, parser section `CAPO I`: 8 articles (`2-ter`, `2-quater`, `2-quinquies`, `2-sexies`, `2-septies`, `2-octies`, `2-novies`, `2-decies`).
  - printed division `(( CAPO III`, parser section `CAPO I`: 3 articles (`2-undecies`, `2-duodecies`, `2-terdecies`).
  - printed division `(( CAPO IV`, parser section `CAPO I`: 9 articles (`2-quaterdecies`, `2-quaterdecies.1`, `2-quinquiesdecies`, `2-sex-decies`, `2-septies-decies`, `3`, `4`, `5`, `6`).
  - printed division `(( CAPO 0.I`, parser section `TITOLO I`: 1 article (`140-bis`).
- **Heading text in the wrong place:** an unrecognised heading line, with the title printed after it, is treated as ordinary text. It therefore becomes part of the chunk before it:
  - `(( CAPO II` is inside chunk 8 (page 2), labelled article `2-bis`, section `CAPO I`.
  - `(( CAPO III` is inside chunk 33 (page 7), labelled article `2-decies`, section `CAPO I`.
  - `(( CAPO IV` is inside chunk 42 (page 8), labelled article `2-terdecies`, section `CAPO I`.
  - `(( CAPO 0.I` is inside chunk 300 (page 38), with no article label, section `TITOLO I`.
- **Effect:** passages near these headings carry a wrong `section`. Where the chunk belongs to an article, the chunk text attributed to that article also contains a division heading and title that are not part of the article. Article labels are not affected.
- **Status:** recorded here only. The chunker is not changed in P1.2.

## Privacy Code chunks without an article label

74 of 412 chunks have `location.article` null. By position:

| Cause | Chunks | Pages |
|---|---|---|
| a division heading and its title (a recognised PARTE/TITOLO/CAPO/SEZIONE heading clears the current article in the chunker) | 68 | 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22, 23, 26, 27, 36, 37, 38, 40, 41, 44, 46, 48, 49, 51, 52, 53 |
| before the first article heading (title, PARTE I / TITOLO I / CAPO I headings, enacting formula) | 6 | 1 |

No unlabeled chunk contains an article heading line, so none of them is a missed article. They hold division headings with their titles, and the opening text before Art. 1. The chunker deliberately keeps these outside any article.

## Cases for manual inspection

- **`2-quindecies` / `2-quinquiesdecies` (page 9):** `ambiguous` in the inventory. The parser recognises both heading lines, but the first has no text of its own, so both lines and the repeal marker form one chunk labelled `2-quinquiesdecies`; the label `2-quindecies` is never assigned. This is the one entry 'not found' above. It is a consequence of the chunker's grouping, not evidence for either reading.
- **Art. 120 (page 27):** title `Sinistri` printed without parentheses; the parser does not read titles, so the cross-check cannot confirm it.
- **Closing formula of the Privacy Code (page 53):** the parser attributes it to the last article run (`186`); the inventory records it as main-body text belonging to no article.
- **Depth of the division path:** separately from the defect above, the parser keeps only the most recent division heading line as `section`, while the inventory records the full printed path (for example `PARTE I > TITOLO I > CAPO IV`). This is a design limit of the chunk format, not counted as a wrong section here.
