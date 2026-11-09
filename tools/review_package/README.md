# M1 human-review package: generator and source checks

This tool reproduces [docs/reviews/m1-human-review-package.md](../../docs/reviews/m1-human-review-package.md) and verifies its official-text comparison. It only reads: it never changes the corpus, inventories, ledger, builds or the archived sources, and it records no review.

## Original files and derived results

| Kind | What | Where |
|---|---|---|
| **Original files** | The two official HTML pages downloaded in M1, kept byte for byte (no line-ending conversion: `.gitattributes`) | [data/raw/trial-2026-10-10/official-sources/](../../data/raw/trial-2026-10-10/official-sources/) |
| **Provenance and attribution** | For each file: URL, retrieval time, SHA-256, size, source type, authenticity and reuse terms. Also the extraction procedure and the expected derived hashes | [official_sources.json](../../data/raw/trial-2026-10-10/official-sources/official_sources.json) and [NOTICE.md](../../data/raw/trial-2026-10-10/official-sources/NOTICE.md), in the same folder |
| **Derived results** | The extracted official texts, their `official_text_sha256`, the comparisons and the package | Computed by the scripts below; only the package is stored |

Neither source is authentic: only the Official Journal and the Gazzetta Ufficiale are.

The M1 download of the Official Journal PDF is not archived. It is byte-identical to the corpus source `data/raw/trial-2026-10-10/documents/gdpr_2016_679_it.pdf`. Its hash is in the provenance record, and the generator checks it.

## Scripts

| File | Role |
|---|---|
| `official_texts.py` | Checks the archived files against their recorded size and SHA-256, extracts the five articles, and compares them with the anchored text of the build |
| `structure.py` | Reads paragraph and point labels from line starts |
| `generate.py` | Writes the Markdown package, or checks it with `--check` |

These are the scripts that generated the package on 2026-11-08. They now read the archived sources instead of a temporary folder; the generated text is unchanged.

## Running

From the repository root, with the project's virtual environment:

```powershell
# Verify the archived files and the five official_text_sha256 values (writes nothing; exit 1 on any mismatch).
.\.venv\Scripts\python.exe -m tools.review_package.official_texts

# Check that the package is reproduced byte for byte (writes nothing).
.\.venv\Scripts\python.exe -m tools.review_package.generate --check

# Write the package (default: docs/reviews/m1-human-review-package.md; --output to choose another path).
.\.venv\Scripts\python.exe -m tools.review_package.generate --output <path>
```

Both scripts accept `--sources-dir` (default: the archive folder) and `--build-dir` (default: `data/processed/builds/build-f76ff6031f2fc82c4852f0a2bde27807`). They refuse to run if an archived file is missing or differs from its recorded SHA-256.

**Test:** `tests/test_review_package.py` checks the two file hashes and the five extraction hashes against values written in the test. It also checks that the archive folder holds exactly the files the provenance record lists, plus the record itself and `NOTICE.md`, and that a changed file is refused. It skips, giving the reason, only when the archived sources are absent. It needs no build.

## Inputs

| Input | Tracked by Git? | Needed by |
|---|---|---|
| This folder, `src/provisions.py`, `src/text_normalization.py` | Yes | both scripts |
| Archived HTML files, `official_sources.json` | Yes | both scripts, the test |
| Instrument registry, inventories, review ledger (`data/reference/`) | Yes | both scripts |
| Recorded build `build-f76ff6031f2fc82c4852f0a2bde27807` (`data/processed/builds/`) | **No** (`data/processed/*` is ignored) | `generate`; the comparison in `official_texts` |
| Corpus source PDF `data/raw/trial-2026-10-10/documents/gdpr_2016_679_it.pdf` | **No** | `generate` (hash check only) |

No network access and no temporary paths are needed.

## Limits of reproducibility

- **Untracked inputs:** the recorded build and the source PDFs are not in Git. A fresh clone can verify the sources and their extraction hashes (the test does this), but it cannot regenerate the package or compare with the anchored text until those inputs are copied in.
- **Build identity:** the build ID includes the code commit (`e29a1b4`), so `provision_cli build` at a later commit makes a different build. Reproducing this one needs either the existing build directory or a checkout of `e29a1b4`.
- **Current data is read:** the package shows the current inventories and ledger. Once a review is recorded, `--check` will report a difference. That is expected: the package describes the state before review.
- **Re-downloading is not reproducing:** the pages at the same URLs may have changed since 2026-11-08. The archived files are the reference.
- **Re-extracting by hand:** extracting the text another way (for example, copying from a browser) gives a different `official_text_sha256`. The procedure is in `official_sources.json` → `extraction`.
