# Reference inventories (P1.2)

A reference inventory lists the articles of one source document **as that document prints them**: label, title, pages, parent divisions and a structural status. It is built from the source PDF, independently of the parser and of chunking, and P1.3 will use it to build and check the provision store.

Every entry is a **candidate awaiting human review**. Nothing here has been checked by a person yet.

## Files

| File | Source document | Scope |
|---|---|---|
| `gdpr_2016_679_it.inventory.json` | `gdpr_2016_679_it.pdf`: GDPR, Official Journal L 119 of 4.5.2016, Italian. The original publication, **not a consolidated text**. | Enacting terms: Articles 1–99 |
| `codice_privacy_dlgs_196_2003.main_body.inventory.json` | `codice_privacy_dlgs_196_2003.pdf`: a **user-provided transcription** of d.lgs. 196/2003. **Not an official Normattiva document.** | Main body only, ending before the line `ALLEGATO A.1` (page 53); the annexes are excluded |
| `parser_crosscheck.md` | — | The parser's article labels compared with both inventories |
| `instruments.json` | — | Instrument registry (P1.3): instruments, versions, source hashes and segmentation rules |
| `review_ledger.json` | — | Review ledger (P1.3): how each human review ended, with corrections; empty so far |

The source PDFs are in `data/raw/trial-2026-10-10/documents/`, which is git-ignored. Each inventory records the source file's path, SHA-256 and page count, and every entry repeats the SHA-256 so that it can be traced back to its source.

## Format

The inventories are JSON (UTF-8, 2-space indent, fixed key order, LF line endings), written by `src.reference_inventory.serialize_inventory`. Writing a valid inventory twice gives the same text. The repository's `.gitattributes` keeps the JSON and Markdown files in this folder LF in every checkout, whatever `core.autocrlf` says, so their recorded SHA-256 values hold on every platform.

**Top level**

| Key | Content |
|---|---|
| `schema_version` | `1` |
| `inventory_id`, `entry_id_prefix` | the inventory's name; the prefix of every entry ID |
| `document` | `doc_id` (the ingestion `doc-` ID of the file), `path`, `sha256`, `size_bytes`, `page_count`, `title_as_printed`, `nature`, `caveats` |
| `scope` | what part of the document is inventoried, where it starts and ends, and what is excluded |
| `provenance` | when and how the candidates were produced; `parser_output_used` is `false` |
| `source_notes` | observations about the document as a whole (running headers, amendment markers, editorial notes) |
| `divisions` | the printed divisions (PARTE, TITOLO, CAPO, SEZIONE; CAPO and Sezione in the GDPR) in source order |
| `entries` | one entry per article heading, in source order |

**Division:** `division_id`, `kind`, `label` (for example `CAPO II`), `heading_as_printed` (for example `(( CAPO II`), `title`, `status_marker` (for example `((CAPO ABROGATO DAL D.LGS. 10 AGOSTO 2018, N. 101))`), `page`, `parent_id`, `notes`.

**Entry**

| Key | Content |
|---|---|
| `entry_id` | `<entry_id_prefix>:art:<label>` (see IDs below) |
| `document_id` | the document's `doc_id` |
| `ordinal` | position in source order, from 1 |
| `kind` | `article` |
| `heading_as_printed` | the heading line exactly as printed, for example `Art. 2-quaterdecies.1` or `Articolo 1` |
| `label` | the article identifier exactly as printed: the end of the heading line |
| `title` | the printed title, or `null` if none is printed |
| `status_marker` | printed status text in place of a title, for example `((ARTICOLO ABROGATO DAL D.LGS. 10 AGOSTO 2018, N. 101))`, or `null` |
| `page_start`, `page_end` | PDF pages (1-based) from the heading to the article's last line |
| `parent_id`, `parent_path` | the innermost printed division, and the printed path, for example `PARTE I > TITOLO I > CAPO IV`; `null` if the source prints none |
| `structural_status` | see below |
| `review_status`, `checked_by`, `checked_on` | see Human review below |
| `source_sha256` | the source file's SHA-256 |
| `notes` | anything a reviewer should know about this entry |

**Exactness.**
- Text is taken from the PDF's text layer. Each line has its leading and trailing whitespace removed, and a title printed over several lines is joined with single spaces. Nothing else is changed.
- Labels, titles and amendment markers `((` `))` are kept as printed. Spelling variants, hyphens and suffixes (`bis`, `ter`, `quindecies` or `quinquiesdecies`, `sex-decies`) are never normalised or treated as equal.

**IDs.**
- An entry ID is derived from the printed label, so it does not change when entries are added before it.
- If a label is printed a second time in the same inventory, that entry's ID gets the suffix `~2` (then `~3`, and so on).
- An `expected_missing` entry has the ID `<prefix>:missing:art:<number>`.
- Division IDs are the printed path, for example `…:body:parte:I/titolo:I/capo:IV`.

## Structural status

The structural status says what the source document shows. It is separate from human review.

| Status | Meaning |
|---|---|
| `present` | The heading is printed on its own line, its label is legible, and its title (if any) is identified. |
| `marked_repealed` | The heading is printed and, in place of a title, the source prints a repeal marker (`status_marker`). This records what the source prints, not the legal status. |
| `duplicate_label` | The same label is printed for more than one article heading within the inventory's scope. |
| `uncertain` | The heading is printed, but an element of it (label reading, title, boundary or page) cannot be established from the source. |
| `ambiguous` | The source supports more than one structural reading, for example one article or two. |
| `expected_missing` | The numbering implies an article that the source does not print. Such an entry has no label, heading or page. |

Entries with `uncertain`, `ambiguous` or `duplicate_label`, and every `expected_missing` entry, must explain why in `notes`.

## Human review

- `review_status` is `pending_human_review` or `reviewed`.
- **Pending:** a pending entry must have `checked_by` and `checked_on` null. Every entry is pending in the files as generated.
- **Recording a review:** only a person who has checked an entry against the source PDF may set `reviewed`. They must fill in `checked_by` (their name) and `checked_on`: the review date written exactly as `YYYY-MM-DD`, for example `2026-11-10`, and not later than the day the file is validated.
- **Corrections:** if they correct a field, they add a note saying what was changed and why.
- **Independent fields:** an entry can be `present` and still `pending_human_review`. Review never changes the structural status by itself.
- **The review ledger (P1.3):** every reviewed entry also needs one record in `review_ledger.json`, with the same reviewer and date, saying how the review ended. The provision store refuses to build otherwise:

  ```json
  {"inventory_id": "gdpr-2016-679-oj-it", "entry_id": "gdpr-2016-679-oj-it:art:33",
   "outcome": "confirmed", "checked_by": "<reviewer>", "checked_on": "YYYY-MM-DD",
   "corrections": [], "note": null}
  ```

  - `confirmed`: nothing was changed. The provision becomes `auto_verified`.
  - `corrected`: list every changed field as `{"field", "before", "after"}`, and edit the inventory so that it holds the `after` values. The provision becomes `manually_curated`, never `auto_verified`.
  - A record for an entry that is not marked reviewed, or a reviewed entry without a record, fails the build. Records must describe real reviews by named people; none exists yet.

The validator, `src.reference_inventory.validate_inventory`, rejects:
- a `reviewed` entry without `checked_by`, or without a `checked_on` that is a real `YYYY-MM-DD` date not in the future;
- a pending entry that has either;
- unknown status values;
- a `present` entry whose `status_marker` is a repeal marker, and a `marked_repealed` entry without one;
- a `parent_path` that is not the printed path of `parent_id`, built from the division labels (for example `CAPO III > Sezione 1`);
- an `expected_missing` entry with a label, heading, title, marker, page or parent;
- missing or extra fields, and values of the wrong type (reported as `InventoryError`, never as a crash);
- duplicate IDs;
- an ID that doesn't follow the label;
- an entry whose SHA-256 differs from the document's.

The tests in `tests/test_reference_inventory.py` validate both files on every run.

## How the candidates were produced

- **Generation:** on 2026-11-07, by an AI assistant, from the PDFs alone, using the rules recorded in each file's `provenance.method`. No parser, chunker or chunk file was used.
- **Second extraction:** each entry was then checked against a second extraction of the same PDF (plain page text). Each heading is printed on its stated page; each title or marker is printed as recorded; page ranges are consistent with the next heading.
- **Parser cross-check:** done afterwards, in `parser_crosscheck.md`. It did not change the inventories.

## Rebuilding and re-running the cross-check

The tools are in `tools/reference_inventory/`. Both need the project's virtual environment (`requirements.txt`; PyMuPDF 1.28.2) and run from the repository root.

```powershell
# Rebuild the candidates into a separate directory, then compare.
.\.venv\Scripts\python.exe -m tools.reference_inventory.build --output-dir <new-dir> --generated-on 2026-11-07

# Re-run the parser cross-check.
.\.venv\Scripts\python.exe -m tools.reference_inventory.crosscheck --report data\reference\parser_crosscheck.md --overwrite
```

**The builder (`build.py`):**
- **Input:** it reads only the two source PDFs in `data/raw/trial-2026-10-10/documents/`, and refuses any file whose SHA-256 differs from the expected one. Its document-specific rules and notes are written for those exact files.
- **Output:** it writes only into `--output-dir`, which is required, and it writes no temporary or intermediate files.
- **Checks before writing:** both inventories are validated and checked against the PDFs' plain page text first. If any check fails, nothing is written.
- **Reproducibility:** with PyMuPDF 1.28.2 and `--generated-on 2026-11-07`, the output is byte-identical to the files here. With another PyMuPDF version it prints a warning, and the output may differ.

**Protecting review work:**
- An existing inventory file is replaced only with `--overwrite`.
- A file that holds any entry not `pending_human_review`, or that cannot be read, is replaced only with `--discard-reviews` as well.
- After a person has reviewed entries, edit these files by hand rather than rebuilding them.

**The cross-check (`crosscheck.py`):**
- **What it compares:** the parser against the inventories. It never writes an inventory, and fails if one changes during the run.
- **Privacy Code:** it reads the trial's existing chunk file (git-ignored).
- **GDPR:** no chunk file exists, so it runs the parser's heading detection in memory.
- **Report:** `--report` must be a Markdown (`.md`) file. A path that resolves to one of the inventories is refused, even with `--overwrite`. An existing report is replaced only with `--overwrite`. The report records the commit, and whether the parser code differs from it.
- **Limitation:** both git-ignored inputs, the source PDFs and the Privacy Code chunk file, must be present locally. They are not in the repository.

## Open items for review

- **Privacy Code `2-quindecies` / `2-quinquiesdecies` (page 9):** `ambiguous`. They may be two articles, or one article printed with two spellings of "fifteenth".
- **Privacy Code Art. 120 (page 27):** the title `Sinistri` is printed without parentheses and in regular type. It is recorded as printed, with status `present`.
- **Privacy Code PARTE III, TITOLO I, CAPO I (pages 38–40):**
  - the CAPO heading is followed by a `((...))` line;
  - SEZIONE III is printed with no SEZIONE I or II.
- **GDPR Art. 99 (page 87):** the unnumbered sentence on page 88 is treated as the closing formula, not part of the article.

Each entry's `notes` give the details.

## Instrument registry (P1.3)

`instruments.json` lists the instruments (ID, type, jurisdiction, lookup aliases, official identifiers, left null when unknown) and their versions:
- the version kind (the GDPR file is the 2016 Official Journal original publication, not a consolidated text; the Privacy Code file is a user transcription);
- authenticity, the reference date with its basis, and what the source says about the status of its provisions;
- the inventory and the SHA-256 of the source file;
- the segmentation rules used by `src/provision_anchors.py`: running-header patterns, region markers (preamble, recitals, enacting formula, closing formula), editorial notes and footnotes. Each rule states how often it must match, and any other count fails. See TECHNICAL_DEBT.md TD-063 for what the rules assume.

The registry's SHA-256 is recorded in every segment map, so editing it makes existing anchors stale.

## Still open

These validator checks are not implemented yet (deferred from P1.2; not part of the P1.3 scope):
- **V5:** page order across entries, and pages within the inventory's `scope`, are not checked. Neither is the heading's prefix word (`Art.` or `Articolo`).
- **V7:** a division's `kind` is not restricted to a fixed list.

Text that belongs to no article (front matter, recitals, enacting and closing formulas, division headings, editorial notes, footnotes, running headers) now has its own segment kinds in the P1.3 segment maps; see the root README, "Provision store and corpus explorer".
