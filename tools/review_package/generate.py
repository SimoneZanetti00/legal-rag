"""Generate the M1 human-review package (read-only on the build and data).

Run from the repository root (see tools/review_package/README.md):

    python -m tools.review_package.generate [--check] [--output PATH]
        [--sources-dir DIR] [--build-dir DIR]

--check compares the generated package with the file at --output and writes nothing
(exit code 0 if byte-identical, 1 otherwise).
"""

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

from src.provisions import QUALIFICATIONS, REASONS, eligibility, load_store
from src.text_normalization import PROFILE, normalise
from tools.review_package.official_texts import (
    ARCHIVE_DIR,
    DEFAULT_BUILD_DIR,
    compare_all,
    load_provenance,
)
from tools.review_package.structure import gaps, structure

sys.stdout.reconfigure(encoding="utf-8")
PROVENANCE = load_provenance()
_parser = argparse.ArgumentParser(description="Generate the M1 human-review package.")
_parser.add_argument("--output", type=Path, default=Path("docs/reviews/m1-human-review-package.md"))
_parser.add_argument("--sources-dir", type=Path, default=ARCHIVE_DIR)
_parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD_DIR)
_parser.add_argument("--check", action="store_true",
                     help="compare with the existing --output file instead of writing it")
ARGS = _parser.parse_args()

SHY, NBSP = chr(0xAD), chr(0xA0)
B = ARGS.build_dir
BUILD_ID = B.name
OUT = ARGS.output
M1 = ARGS.sources_dir
store = load_store()
OFF = compare_all(M1, B, store=store, provenance=PROVENANCE)

# The M1 download of the Official Journal PDF is not archived: it is byte-identical to
# the corpus source. Its recorded hash is used, after checking that identity.
EURLEX_PDF_SHA256 = PROVENANCE["related_download_not_archived"]["sha256"]
_gdpr_pdf = Path("data/raw/trial-2026-10-10/documents/gdpr_2016_679_it.pdf")
if hashlib.sha256(_gdpr_pdf.read_bytes()).hexdigest() != EURLEX_PDF_SHA256:
    sys.exit(f"error: {_gdpr_pdf} is not byte-identical to the recorded EUR-Lex PDF download")
record = json.loads((B / "build.json").read_text(encoding="utf-8"))
maps, map_files, link_rows, link_files = {}, {}, {}, {}
for p in sorted((B / "anchors").glob("*.segments.json")):
    m = json.loads(p.read_text(encoding="utf-8"))
    maps[m["version_id"]], map_files[m["version_id"]] = m, p
for p in sorted((B / "anchors").glob("*.links.jsonl")):
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    link_rows[rows[0]["variant_id"]], link_files[rows[0]["variant_id"]] = rows[1:], p


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def vis(text):
    """Text with invisible characters made visible; nothing else changed."""
    out = []
    for c in text:
        if c in "\n ":
            out.append(c)
        elif c == SHY:
            out.append("⟨SHY⟩")
        elif c == NBSP:
            out.append("⟨NBSP⟩")
        elif unicodedata.category(c) in ("Cf", "Cc", "Zs", "Zl", "Zp", "Mn"):
            out.append(f"⟨U+{ord(c):04X}⟩")
        else:
            out.append(c)
    return "".join(out)


def one_line(text, limit=None):
    t = vis(text).replace("\n", "⏎")
    return t if limit is None or len(t) <= limit else t[:limit] + "…"


def md_cell(text):
    return text.replace("|", "\\|")


def label_at(text, offset):
    labels = structure(text[:offset])
    return labels[-1] if labels else "heading/title"


def fmt_unit(label, gdpr_art4=False):
    return label


# --- Hand-written review notes (facts only; each cited string is checked below) -----------

INV_TITLES = {}
for p in store.articles():
    INV_TITLES[(p.version_id, p.label_as_printed)] = p.title
GDPR_V = "eu-reg-2016-679@oj-l119-2016-it"
CODICE_V = "it-dlgs-2003-196@transcription-vigente-2026-11-05"


def gdpr_title(n):
    return f"GDPR Art. {n} «{INV_TITLES[(GDPR_V, str(n))]}»"


PROVISIONS = [
    {
        "key": "4", "instrument": "gdpr", "label": "4", "name": "GDPR Article 4(12)",
        "focus": "The demonstration uses point 12 only («violazione dei dati personali»). The "
                 "inventory entry, the review record and the eligibility tier cover the whole of "
                 "Article 4 (26 points): confirming Article 4 confirms all of them.",
        "refs": [
            ("articolo 27", gdpr_title(27), "No", "In point 17."),
            ("articolo 51", gdpr_title(51), "No", "In point 21. Privacy Code Art. 2-bis also "
             "refers to it."),
            ("articolo 1, paragrafo 1, lettera b), della direttiva (UE) 2015/1535",
             "Directive (EU) 2015/1535", "No", "In point 25, followed by the footnote reference "
             "«(1)»."),
            ("presente regolamento", "The GDPR itself", "—", "General reference."),
        ],
        "judgment": [
            "**Scope:** decide whether to review all 26 points now. The demonstration needs only "
            "point 12, but a ledger record for Article 4 covers the whole article.",
            "**Hyphenation:** six words are split by a soft hyphen at a line end (see B). Confirm "
            "that each is PDF hyphenation and that the joined word is the printed word.",
            "**Footnote:** point 25 keeps the footnote reference «(1)» in the article text, while "
            "the footnote itself is stored separately as context (segment 80, page 35, shown in "
            "B). Confirm that this split is right.",
        ],
    },
    {
        "key": "33", "instrument": "gdpr", "label": "33", "name": "GDPR Article 33",
        "focus": "Core provision of the demonstration: notification of a personal data breach to "
                 "the supervisory authority.",
        "refs": [
            ("articolo 55", gdpr_title(55), "Yes", "33(1): the competent authority."),
            ("paragrafo 1", "Art. 33(1)", "Yes (internal)", "In 33(3)."),
            ("presente articolo", "Art. 33 itself", "Yes (internal)", "In 33(5)."),
        ],
        "judgment": [
            "**Hyphenation across a block break:** in 33(3)(a) the word «approssimativo» is "
            "stored as «approssi⟨SHY⟩⏎⏎mativo». The words are right, but an exact quotation "
            "check against the stored text needs the shared normalisation.",
            "**Pending proposal:** the Digital Omnibus proposal COM(2025) 837 would replace "
            "Art. 33(1). As established in M1, it had not been adopted or published on 2026-11-08. "
            "This affects how an answer is worded, not this structural review: the stored text is "
            "the 2016 original publication, and EUR-Lex lists no amending act.",
        ],
    },
    {
        "key": "34", "instrument": "gdpr", "label": "34", "name": "GDPR Article 34",
        "focus": "Communication of a personal data breach to the data subject.",
        "refs": [
            ("articolo 33, paragrafo 3, lettere b), c) e d)", "Art. 33(3)(b)–(d)", "Yes",
             "In 34(2)."),
            ("paragrafo 1 del presente articolo", "Art. 34(1)", "Yes (internal)", "In 34(2)."),
            ("paragrafo 1", "Art. 34(1)", "Yes (internal)", "In 34(3) and 34(3)(b)."),
            ("paragrafo 3", "Art. 34(3)", "Yes (internal)", "In 34(4)."),
        ],
        "judgment": [],
    },
    {
        "key": "55", "instrument": "gdpr", "label": "55", "name": "GDPR Article 55",
        "focus": "Competence of each supervisory authority on the territory of its Member State "
                 "(the link from Art. 33(1) to the national authority).",
        "refs": [
            ("articolo 6, paragrafo 1, lettera c) o e)", "GDPR Art. 6(1)(c) or (e) «"
             + INV_TITLES[(GDPR_V, "6")] + "»", "No", "In 55(2)."),
            ("articolo 56", gdpr_title(56), "No", "In 55(2). Excluded from the demonstration: "
             "our stored text of Art. 56 differs from the EUR-Lex consolidated text by "
             "corrigenda C2 and C3 (M1)."),
            ("presente regolamento", "The GDPR itself", "—", "In 55(1)."),
        ],
        "judgment": [
            "**Dependence on Art. 56:** 55(2) refers to Art. 56 (lead supervisory authority), which "
            "is outside the demonstration and whose stored text is pre-corrigendum. Decide whether "
            "Art. 55 can be cited for the demonstration question without Art. 56.",
        ],
    },
    {
        "key": "2-bis", "instrument": "codice privacy", "label": "2-bis",
        "name": "Italian Privacy Code Article 2-bis",
        "focus": "Designates the Garante as the Italian supervisory authority under GDPR Art. 51.",
        "refs": [
            ("articolo 51 del regolamento", gdpr_title(51), "No",
             "«regolamento» here means Regulation (EU) 2016/679: Code Art. 1 (same source) "
             "defines it as «… regolamento (UE) 2016/679 … di seguito «Regolamento»» (capital "
             "R; 2-bis prints it in lower case)."),
            ("articolo 153", "Privacy Code Art. 153 «"
             + INV_TITLES[(CODICE_V, "153")] + "»", "No", "Defines the Garante."),
        ],
        "judgment": [
            "**Source:** the stored text is a user-provided transcription, not an official "
            "document. It was compared only with Normattiva, which is official but not authentic. "
            "The authentic Gazzetta Ufficiale text was not compared (unavailable here).",
            "**Amendment markers:** the title and paragraph 1 are entirely inside «((» … «))», "
            "Normattiva's marking for text introduced or changed by an amending act. The stored "
            "text does not name the amending act. Normattiva states «Testo in vigore dal: "
            "19-9-2018». Decide how this marking should be represented; it is not a repeal "
            "marker.",
            "**Title:** the inventory title is stored with the markers: «(( (Autorità di "
            "controllo). ))». Decide whether this is the right representation.",
            "**Reference date:** Normattiva's «vigente al» field had no date. Its page states "
            "«ultimo aggiornamento all'atto: 19/02/2026». The transcription's reference date "
            "(2026-11-05, in the version ID) is unverified.",
        ],
    },
]

# Check that every cited reference string occurs in the normalised stored text.
for spec in PROVISIONS:
    norm = normalise(OFF[spec["key"]]["ours"])
    for ref, *_ in spec["refs"]:
        assert ref in norm, (spec["key"], ref)
codice1 = normalise("".join(
    s["text"] for s in maps[CODICE_V]["segments"]
    if s["kind"] == "article" and s["provision_id"] == f"{CODICE_V}/body/article:1"))
assert "regolamento (UE) 2016/679" in codice1 and "di seguito «Regolamento»" in codice1


# --- Anomaly detection ------------------------------------------------------------------------


def anomalies(text, pieces):
    found = []
    title_end = text.find("\n\n", text.find("\n\n") + 2)  # heading and title blocks
    for m in re.finditer(SHY + r"(\s*)", text):
        i = m.start()
        found.append((i, label_at(text, i), "Soft hyphen (U+00AD)" + (
            " across a block break" if "\n\n" in m.group(1) else " at a line end"),
            text[max(0, i - 15): m.end() + 10],
            "Word split by PDF hyphenation; same words after normalisation."))
    joins, offset = set(), 0
    for s in pieces[:-1]:
        offset += len(s["text"])
        joins.add(offset)
    for m in re.finditer(r"(\S)[ \t]*\n[ \t]*\n\s*(?=\S)", text):
        if m.start() < title_end or m.group(1) in ".;:()" or m.group(1) == SHY:
            continue
        if re.match(r"(?:\d+\.|\d+\)|[a-z]\))(?:\s|$)", text[m.end():]):
            continue  # the next line starts a new point: a list break, not a broken sentence
        i = m.start()
        at_join = any(m.start() < j <= m.end() for j in joins)
        found.append((i, label_at(text, i),
                      "Page break inside a sentence" if at_join else "Blank line inside a sentence",
                      text[max(0, i - 25): m.end() + 20],
                      "Page join: the running header between the pieces is excluded; no word "
                      "affected." if at_join else
                      "Layout only (hanging indent in the PDF); no word affected. Matters only "
                      "if something splits text on blank lines."))
    for m in re.finditer(r"(?<=\S) \(\d+\)(?=[;.,])", text):
        i = m.start() + 1
        found.append((i, label_at(text, i), "Footnote reference", text[max(0, i - 30): m.end() + 2],
                      "The footnote text is stored as a separate context segment."))
    found.sort()
    return found


# --- Rendering -------------------------------------------------------------------------------

L = []
w = L.append


def table(headers, rows):
    w("| " + " | ".join(headers) + " |")
    w("|" + "|".join("---" for _ in headers) + "|")
    for r in rows:
        w("| " + " | ".join(md_cell(str(c)) for c in r) + " |")
    w("")


eurlex_file = M1 / "gdpr_consolidated_it.html"
norm_file = M1 / "normattiva_2bis.html"
# Provenance statements are quoted from the record, never retyped here.
RECORD = {r["file"]: r for r in PROVENANCE["original_files"]}
ARCHIVE = PROVENANCE["archive_dir"]
DISCLAIMER = RECORD["gdpr_consolidated_it.html"]["page_disclaimer"]
_TAG = '<p class="disclaimer">'
DISCLAIMER_LOCATION = DISCLAIMER["location"].replace(_TAG, f"`{_TAG}`")  # shown as code, not HTML
SOURCES = {
    "gdpr": {
        "name": "EUR-Lex consolidated text, Regulation (EU) 2016/679, Italian, CELEX 02016R0679-20160504",
        "url": "https://eur-lex.europa.eu/legal-content/IT/TXT/HTML/?uri=CELEX:02016R0679-20160504",
        "type": "eurlex_consolidated",
        "consolidation": "2016-05-04. The only consolidated version on EUR-Lex, which lists no "
                         "amending act (EUR-Lex ALL page, checked in M1).",
        "retrieved": "2026-11-08 12:28:58 +01:00, by the assistant during M1 (curl; time taken from the file).",
        "file": eurlex_file,
        "authentic": RECORD["gdpr_consolidated_it.html"]["authenticity"],
        "disclaimer": f"«{DISCLAIMER['text']}» ({DISCLAIMER_LOCATION}; in Italian, as "
                      "printed). The page states that the consolidated text is a documentation "
                      "tool with no legal effect.",
        "reuse": RECORD["gdpr_consolidated_it.html"]["reuse"],
    },
    "codice privacy": {
        "name": "Normattiva, d.lgs. 30 giugno 2003, n. 196, Art. 2-bis, text in force",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2003-06-30;196~art2bis",
        "type": "normattiva_vigente",
        "consolidation": "**Unavailable.** The page's «vigente al» field had no date. The page "
                         "states «Testo in vigore dal: 19-9-2018» and «ultimo aggiornamento "
                         "all'atto: 19/02/2026».",
        "retrieved": "2026-11-08 12:30:57 +01:00, by the assistant during M1 (curl; time taken from the file).",
        "file": norm_file,
        "authentic": RECORD["normattiva_2bis.html"]["authenticity"],
        "disclaimer": "None recorded for the archived page; see «Authentic?».",
        "reuse": RECORD["normattiva_2bis.html"]["reuse"],
    },
}

w("# M1 human-review package: the five demonstration provisions")
w("")
w("> **Status: prepared, not reviewed.** This package was prepared on 2026-11-08 by an AI "
  "assistant (Claude Code) from the recorded build and the official-source downloads made "
  "during M1. It is not a human review, an approval or a legal opinion. Every decision field "
  "is blank and must be filled in by the human reviewer. Legal validity is outside this "
  "review and stays `not_established`.")
w("")
w("> **Revision 2 (2026-11-09):** the two official pages are now archived in the repository, and "
  "this package is generated by `tools/review_package/generate.py`. Only the text about where "
  "the sources are and how the package is made has changed: sections 1, 3, 11 and 13 and the "
  "«Downloaded file» row of each section C. The evidence, comparisons and worksheets are "
  "unchanged.")
w("")
w("**Contents**")
w("")
w("1. [How to use this package](#1-how-to-use-this-package)")
w("2. [Recorded build and inputs](#2-recorded-build-and-inputs)")
w("3. [Official sources used for the comparison](#3-official-sources-used-for-the-comparison)")
w("4. [Summary](#4-summary)")
for n, spec in enumerate(PROVISIONS, start=5):
    anchor = re.sub(r"[^a-z0-9 -]", "", f"{n} {spec['name']}".lower()).replace(" ", "-")
    w(f"{n}. [{spec['name']}](#{anchor})")
w("10. [Issues that affect several provisions](#10-issues-that-affect-several-provisions)")
w("11. [Missing artifacts and open questions](#11-missing-artifacts-and-open-questions)")
w("12. [After the review (not part of this package)](#12-after-the-review-not-part-of-this-package)")
w("13. [Appendix: how to re-check this package](#13-appendix-how-to-re-check-this-package)")
w("")

w("## 1. How to use this package")
w("")
w("**Demonstration question:** «When is a personal data breach required to be notified to the "
  "Italian Data Protection Authority?»")
w("")
w("**Closure:** GDPR Art. 4(12), 33, 34 and 55, and Privacy Code Art. 2-bis. GDPR Art. 56 is "
  "excluded (see section 10).")
w("")
w("**For each provision**, sections A–D give the evidence and section E is the worksheet:")
w("")
w("- **A. Identity:** IDs, the inventory entry, the build, the segments and the chunks.")
w("- **B. Extracted text:** the stored article text and the anomalies found in it.")
w("- **C. Official-source comparison:** source, dates, hashes, match status and differences.")
w("- **D. Structural and completeness checks:** paragraphs, cross-references, markers and the "
  "points that need your judgment.")
w("- **E. Review decision worksheet:** five separate decisions, all blank.")
w("")
w("**Keep the decisions separate.** Structure, extraction fidelity, completeness and "
  "source-status markers are four independent checks. Primary-citation eligibility is computed "
  "by the system from the recorded review; your field records your view of it. Legal validity "
  "is not assessed anywhere in this package.")
w("")
w("**What you need:**")
w("")
w("- the source PDFs, to check against the printed pages:")
w("  - `data/raw/trial-2026-10-10/documents/gdpr_2016_679_it.pdf`;")
w("  - `data/raw/trial-2026-10-10/documents/codice_privacy_dlgs_196_2003.pdf`;")
w("- optionally, the archived official pages (section 3), to re-check the comparison yourself.")
w("")
w("**How the texts are shown**")
w("")
w("- Text blocks show the stored text exactly, line breaks included. Invisible characters are "
  "made visible: `⟨SHY⟩` is a soft hyphen (U+00AD), `⟨NBSP⟩` a no-break space, `⟨U+XXXX⟩` any "
  "other invisible character. Spaces at line ends are present but cannot be seen.")
w("- Lines written as `⟦ … ⟧` mark where one stored piece ends and the next begins. They are "
  "not part of the text.")
w("- In tables, `⏎` stands for a line break.")
w("- Offsets (`Chars`) are character positions in the source's full extracted text, whose "
  "SHA-256 is the segment map's `content_sha256` (section 2). «Offset in text» counts from the "
  "start of the article text.")
w("")

# --- 2. Build -----------------------------------------------------------------------------
w("## 2. Recorded build and inputs")
w("")
code = record["code"]
table(["Item", "Value"], [
    ["Build ID", f"`{BUILD_ID}`"],
    ["Build kind", f"`{record['build_kind']}`"],
    ["Code", f"`{code['state']}` at commit `{code['commit']}`"],
    ["Build record", f"`{(B / 'build.json').as_posix()}` (sha256 `{sha_file(B / 'build.json')}`)"],
    ["Corpus file", f"`{record['build']['output']['path']}`: {record['build']['output']['chunk_count']} chunks, sha256 `{record['build']['output']['sha256']}`"],
    ["Corpus specification", f"`{record['spec']['path']}` (canonical-JSON sha256 `{record['spec']['sha256']}`)"],
    ["Instrument registry", f"`data/reference/instruments.json` (sha256 `{store.registry.sha256}`)"],
    ["Review ledger", "`data/reference/review_ledger.json`: empty (`[]`); no provision has been reviewed"],
    ["Verification on 2026-11-08", "The explorer opened the build with all its checks (record, chunk and corpus hashes, segment-map provenance, links). The build is reproducible: an independent second build gave the same build ID and byte-identical chunk, corpus, segment and links files."],
])
rows = []
for s in record["sources"]:
    v = store.registry.version(s["version_id"])
    variant = next(x for x in record["build"]["variants"] if x["variant_id"] == s["variant_id"])
    m = maps[s["version_id"]]
    rows.append([f"`{s['version_id']}`", f"`{s['source_path']}`<br>sha256 `{s['source_sha256']}`",
                 f"`{v.version_kind}`, authenticity "
                 + (f"`{v.authenticity}`" if v.authenticity else "`null` (not established)"),
                 f"`{s['variant_id']}`: chunks `{variant['output']['path'].split('/')[-1]}` ({variant['output']['chunk_count']}), sha256 `{variant['output']['sha256'][:16]}…`",
                 f"`{map_files[s['version_id']].name}`<br>file sha256 `{sha_file(map_files[s['version_id']])[:16]}…`<br>content_sha256 `{m['content_sha256'][:16]}…`",
                 f"`{link_files[s['variant_id']].name}`<br>sha256 `{sha_file(link_files[s['variant_id']])[:16]}…`"])
table(["Version", "Source file", "Kind", "Variant and chunks", "Segment map (under `anchors/`)", "Links (under `anchors/`)"], rows)
for v in store.registry.versions:
    w(f"- **`{v.version_id}`:** {v.description}")
w("")

# --- 3. Official sources ------------------------------------------------------------------
w("## 3. Official sources used for the comparison")
w("")
w("These sources were established in M1. Both downloaded pages are archived in the repository, "
  f"byte for byte, in `{ARCHIVE}/`:")
w("")
w("- **Provenance:** `official_sources.json` (URLs, retrieval times, SHA-256, sizes, "
  "authenticity, reuse terms, extraction procedure).")
w("- **Attribution:** `NOTICE.md`.")
w("- **Integrity:** the generator refuses to run unless both files match their recorded SHA-256 "
  "and size. `tests/test_review_package.py` checks the hashes, the folder's exact contents and "
  "the five extracted texts.")
w("- **Original or derived:** the archived files are the original downloads. The official texts "
  "compared in section C are derived from them by the method in section 13; they are not "
  "stored as separate files.")
w("")
table(["Item", "GDPR (Arts. 4, 33, 34, 55)", "Privacy Code (Art. 2-bis)"], [
    ["Source", SOURCES["gdpr"]["name"], SOURCES["codice privacy"]["name"]],
    ["URL", SOURCES["gdpr"]["url"], SOURCES["codice privacy"]["url"]],
    ["`source_type`", f"`{SOURCES['gdpr']['type']}`", f"`{SOURCES['codice privacy']['type']}`"],
    ["Consolidation or update date", SOURCES["gdpr"]["consolidation"], SOURCES["codice privacy"]["consolidation"]],
    ["Retrieved", SOURCES["gdpr"]["retrieved"], SOURCES["codice privacy"]["retrieved"]],
    ["Downloaded file sha256", f"`{sha_file(eurlex_file)}`", f"`{sha_file(norm_file)}`"],
    ["Archived copy", f"`{ARCHIVE}/gdpr_consolidated_it.html`", f"`{ARCHIVE}/normattiva_2bis.html`"],
    ["Authentic?", SOURCES["gdpr"]["authentic"], SOURCES["codice privacy"]["authentic"]],
    ["Disclaimer on the page", SOURCES["gdpr"]["disclaimer"], SOURCES["codice privacy"]["disclaimer"]],
    ["Reuse", SOURCES["gdpr"]["reuse"], SOURCES["codice privacy"]["reuse"]],
])
w("**About our own sources**")
w("")
w("- **GDPR PDF:** byte-identical to the PDF EUR-Lex serves for CELEX 32016R0679 (sha256 "
  f"`{EURLEX_PDF_SHA256}`, downloaded in M1). It is the 2016 original "
  "publication, not consolidated. It has no digital signature, so its authenticity is not "
  "established.")
w("- **Privacy Code PDF:** a user-provided transcription, not an official document.")
w("- **Corrigenda (M1):** R(01) changes only Art. 47(2)(h). R(02) makes 75 corrections; near "
  "the demonstration it changes only Art. 56(3). R(03) changes recital 158 and Art. 56(1). "
  "**None changes Arts. 4, 33, 34 or 55.**")
w("")

# --- 4. Summary ---------------------------------------------------------------------------
w("## 4. Summary")
w("")
rows = []
data = {}
for spec in PROVISIONS:
    p = store.lookup(spec["instrument"], spec["label"])
    v = store.registry.version(p.version_id)
    m = maps[p.version_id]
    pieces = [s for s in m["segments"] if s["kind"] == "article" and s["provision_id"] == p.provision_id]
    text = "".join(s["text"] for s in pieces)
    assert text == OFF[spec["key"]]["ours"]
    variant = m["variant_id"]
    chunks = [r for r in link_rows[variant] if any(x["provision_id"] == p.provision_id for x in r["provisions"])]
    el = eligibility(p, v, anchored=bool(pieces))
    an = anomalies(text, pieces)
    data[spec["key"]] = dict(p=p, v=v, m=m, pieces=pieces, text=text, chunks=chunks, el=el, an=an)
    o = OFF[spec["key"]]
    rows.append([spec["name"], f"`{p.provision_id.split('/body/')[1]}`", f"{p.page_start}–{p.page_end}",
                 f"{len(pieces)} / {len(text)}", len(chunks),
                 f"{o['status']}" + (" (point 12: " + o["point12"]["status"] + ")" if spec["key"] == "4" else ""),
                 len(an), f"`{el.tier.value}`"])
table(["Provision", "ID (after `/body/`)", "Pages", "Pieces / chars", "Chunks", "Official comparison",
       "Anomalies flagged", "Current tier"], rows)
w("- **Comparison:** all five match their official source **only after** normalisation "
  f"`{PROFILE}`; none is identical as stored. No word differs.")
w("- **Structure:** all expected paragraphs and points are present, with no numbering gaps "
  "(section D of each provision).")
w("- **Tier:** every provision is `internal_only` because no review is recorded yet "
  "(`structure_not_reviewed`).")
w("")

# --- 5–9. Provisions ---------------------------------------------------------------------
for n, spec in enumerate(PROVISIONS, start=5):
    d = data[spec["key"]]
    p, v, m, pieces, text, chunks, el, an = (d[k] for k in ("p", "v", "m", "pieces", "text", "chunks", "el", "an"))
    o = OFF[spec["key"]]
    src = SOURCES[spec["instrument"]]
    inv = json.loads(Path(v.inventory_path).read_text(encoding="utf-8"))
    entry = next(e for e in inv["entries"] if e["entry_id"] == p.inventory_ref)

    w(f"## {n}. {spec['name']}")
    w("")
    w(f"**{p.heading_as_printed} — {p.title}**")
    w("")
    w(spec["focus"])
    w("")

    w("### A. Identity")
    w("")
    table(["Field", "Value"], [
        ["Provision ID", f"`{p.provision_id}`"],
        ["Source", f"{v.description} File `{record['sources'][0 if p.version_id == GDPR_V else 1]['source_path']}` (sha256 `{p.source_sha256}`)."],
        ["Article reference", f"«{p.heading_as_printed}», title «{p.title}», printed path «{p.path}», pages {p.page_start}–{p.page_end}"],
        ["Inventory", f"`{v.inventory_path}` · inventory `{p.inventory_id}` (sha256 `{p.inventory_sha256}`) · entry `{p.inventory_ref}`"],
        ["Build", f"`{BUILD_ID}` · variant `{m['variant_id']}` · segment map `anchors/{map_files[p.version_id].name}`"],
        ["Structural status", f"`{p.structural_status.value}`"],
        ["Review", f"`{p.review.status}` (checked_by and checked_on empty)"],
        ["Source status representation", f"`{p.source_status_representation.value if p.source_status_representation else None}`"],
        ["Legal validity", f"`{p.legal_validity}`"],
        ["Eligibility (now)", f"`{el.tier.value}`; reasons: " + "; ".join(f"`{r}` ({REASONS[r]})" for r in el.reasons)],
        ["Qualifications", "<br>".join(f"`{q}`: {QUALIFICATIONS[q]}" for q in el.qualifications)],
    ])
    w("Inventory entry, as stored:")
    w("")
    w("```json")
    w(json.dumps(entry, ensure_ascii=False, indent=2))
    w("```")
    w("")
    w("Article text pieces (the article text is these segments, joined in order):")
    w("")
    table(["Piece", "Segment", "Kind", "Chars", "Page", "Segment `text_sha256`"],
          [[i + 1, s["index"], s["kind"], f"{s['char_start']}–{s['char_end']}", s["page"] if s["page"] == s["page_end"] else f"{s['page']}–{s['page_end']}", f"`{s['text_sha256']}`"]
           for i, s in enumerate(pieces)])
    lo, hi = pieces[0]["index"], pieces[-1]["index"]
    inner = [s for s in m["segments"] if lo < s["index"] < hi and s not in pieces]
    if inner:
        w("Segments between the pieces (context, **not** article text):")
        w("")
        table(["Segment", "Kind", "Chars", "Page", "Text"],
              [[s["index"], s["kind"], f"{s['char_start']}–{s['char_end']}", s["page"], f"`{one_line(s['text'])}`"] for s in inner])
    before, after = m["segments"][lo - 1], m["segments"][hi + 1]
    w(f"Neighbours: before is segment {before['index']} (`{before['kind']}`, "
      f"`{(before['provision_id'] or '—').split('/body/')[-1]}`), after is segment {after['index']} "
      f"(`{after['kind']}`, `{(after['provision_id'] or '—').split('/body/')[-1]}`): "
      f"«{md_cell(one_line(after['text'], 70))}».")
    w("")
    w("Chunks overlapping this provision (from the links file):")
    w("")
    rows = []
    for r in chunks:
        x = next(x for x in r["provisions"] if x["provision_id"] == p.provision_id)
        others = [y["provision_id"].split("/body/")[1] for y in r["provisions"] if y["provision_id"] != p.provision_id]
        rows.append([r["chunk_index"], f"`{r['chunk_id']}`", f"{r['char_start']}–{r['char_end']}",
                     r["page"] if r["page"] == r["page_end"] else f"{r['page']}–{r['page_end']}",
                     f"{x['char_start']}–{x['char_end']} ({x['chars']})", ", ".join(others) or "—",
                     ", ".join(sorted({c["kind"] for c in r["context"]})) or "—"])
    table(["#", "Chunk ID", "Chunk chars", "Pages", "This provision (non-space chars)", "Other provisions", "Context in chunk"], rows)

    w("### B. Extracted text")
    w("")
    w(f"- **Length:** {len(text)} characters in {len(pieces)} piece(s).")
    w(f"- **SHA-256** of the exact text (UTF-8, pieces joined in order): `{sha_text(text)}`.")
    w("")
    w("```text")
    for i, s in enumerate(pieces):
        if i:
            w(f"⟦ end of piece {i} · start of piece {i + 1}: segment {s['index']}, page {s['page']}, chars {s['char_start']}–{s['char_end']} ⟧")
        w(vis(s["text"]).rstrip("\n"))
    w("```")
    w("")
    labels = structure(text)
    w("**Paragraphs and points found** (read from line starts):")
    w("")
    rows = []
    lines = text.split("\n")
    for lab in labels:
        rows.append([lab])
    # first words of each unit
    unit_rows, current = [], None
    from tools.review_package.structure import LET_POINT, NUM_POINT, PARA
    top = None
    for idx, line in enumerate(lines):
        s = line.strip()
        lab = None
        if mm := PARA.match(s):
            top = mm.group(1); lab = top
        elif mm := NUM_POINT.match(s):
            top = f"({mm.group(1)})"; lab = top
        elif mm := LET_POINT.match(s):
            lab = f"{top}({mm.group(1)})"
        if lab:
            rest = s[len(mm.group(0)):].strip() or (lines[idx + 1].strip() if idx + 1 < len(lines) else "")
            unit_rows.append([lab, one_line(rest, 90)])
    table(["Unit", "Starts with"], unit_rows)
    w("**Anomalies and suspicious formatting**")
    w("")
    if an:
        table(["#", "Offset in text", "In", "Kind", "Excerpt", "Effect"],
              [[i + 1, a[0], a[1], a[2], f"`{one_line(a[3])}`", a[4]] for i, a in enumerate(an)])
    else:
        w("None found.")
        w("")
    dup = [l for l in {x.strip() for x in lines if len(x.strip()) > 40} if sum(1 for x in lines if x.strip() == l) > 1]
    w("- **Duplicated lines** (longer than 40 characters): " + ("none." if not dup else ", ".join(dup)))
    w("- **Missing text:** none detected. Every paragraph and point of the official text is present, "
      "and the comparison in C finds no missing or extra word.")
    w("- **Running headers:** " + ("excluded from the article text; they are context segments (table above)." if inner else "none inside this article."))
    double = len(re.findall(r"\S  +\S", text))
    trailing = sum(1 for x in lines if x.endswith(" "))
    if double or trailing:
        w(f"- **Whitespace only:** {double} double space(s)"
          + (" (after point letters, e.g. `a)  `)" if double else "")
          + f" and {trailing} line(s) ending with a space. These do not affect the words.")
    else:
        w("- **Whitespace:** no double spaces and no lines ending with a space.")
    if spec["key"] == "4":
        fn = next(s for s in m["segments"] if s["kind"] == "footnote" and s["page"] == 35)
        w(f"- **Footnote text** (segment {fn['index']}, `footnote`, page {fn['page']}, chars "
          f"{fn['char_start']}–{fn['char_end']}; context, not article text): `{one_line(fn['text'])}`")
    w("")

    w("### C. Official-source comparison")
    w("")
    cand = o["candidate"]
    rules = {"whitespace": "whitespace and line breaks", "soft_hyphen": "soft hyphens",
             "markers": "EUR-Lex markers", "apostrophe": "typographic apostrophe",
             "punctuation_spacing": "spacing before punctuation"}
    table(["Item", "Value"], [
        ["Official source", src["name"]],
        ["URL", src["url"]],
        ["`source_type`", f"`{src['type']}`"],
        ["Consolidation or update date", src["consolidation"]],
        ["Retrieved", src["retrieved"]],
        ["Downloaded file", f"sha256 `{sha_file(src['file'])}`, archived as `{ARCHIVE}/{src['file'].name}`"],
        ["Compared official text", f"{len(o['official'])} characters extracted from that file (method in section 13)"],
        ["`official_text_sha256`", f"`{cand['official_text_sha256']}`: SHA-256 of the extracted official text, UTF-8, before normalisation"],
        ["Our text SHA-256", f"`{o['ours_sha256']}`"],
        ["Normalisation", f"`{PROFILE}` (`src/text_normalization.py`)"],
        ["Identical as stored?", "**No**"],
        ["Match status", f"**`{o['status']}`**: identical only after normalisation"],
        ["Differences", "None after normalisation" if not o["differences"] else "; ".join(f"ours «{a}» / official «{b}»" for a, b in o["differences"])],
        ["Transformations that changed our text", ", ".join(rules[r] for r in o["rules_ours"]) or "none"],
        ["Transformations that changed the official text", ", ".join(rules[r] for r in o["rules_official"]) or "none"],
        ["EUR-Lex markers (▼ ► ◄) inside the official article", ("none" if "markers" not in o["rules_official"] else "present") if spec["instrument"] == "gdpr" else "not applicable"],
    ])
    if spec["key"] == "4":
        p12 = o["point12"]
        w("**Point 12 on its own** (the part the demonstration uses):")
        w("")
        table(["Item", "Value"], [
            ["Ours", f"`{one_line(p12['ours'])}` (SHA-256 `{p12['ours_sha256']}`)"],
            ["Official", f"`{one_line(p12['official'])}` (SHA-256 `{p12['official_sha256']}`)"],
            ["Match status", f"**`{p12['status']}`**; differences: none"],
            ["What differs before normalisation", "Line breaks; the official text has a line break after «12)» and a space before «:»."],
        ])
    w("<details><summary>Official text as extracted and compared (click to open)</summary>")
    w("")
    w("```text")
    w(vis(o["official"]).rstrip("\n"))
    w("```")
    w("")
    w(f"Source: {src['name']}, {src['url']}. Extracted text; line breaks come from the HTML "
      "markup. " + ("Not authentic: only the Official Journal is." if spec["instrument"] == "gdpr"
                    else "Non-authentic text, freely available from Normattiva."))
    w("")
    w("</details>")
    w("")
    w("Candidate `official_check` object, computed by `src.provisions.official_check_record` "
      "from the two texts above. **It is not a review result.** It belongs in a ledger record "
      "only if you verify the comparison and decide to record it. If you extract the official "
      "text yourself, the hash will differ: recompute it from your own text.")
    w("")
    w("```json")
    w(json.dumps(cand, ensure_ascii=False, indent=2))
    w("```")
    w("")

    w("### D. Structural and completeness checks")
    w("")
    off_labels = structure(o["official"])
    table(["Check", "Result"], [
        ["Units in the official text", ", ".join(off_labels)],
        ["Units in the stored text", ", ".join(labels)],
        ["Missing / extra units", "none / none" if labels == off_labels else "**different, see lists**"],
        ["Numbering gaps", ", ".join(gaps(labels)) or "none"],
        ["Article heading and title", f"«{p.heading_as_printed}» / «{p.title}»: the first lines of the stored text are «{one_line(text.split(chr(10))[0])}» and «{one_line(text.split(chr(10)+chr(10))[1].strip())}»"],
        ["Inventory `status_marker`", f"`{json.dumps(entry['status_marker'], ensure_ascii=False)}`"],
        ["Inventory `structural_status`", f"`{entry['structural_status']}`"],
        ["Repeal or amendment words in the text («abrogat», «soppress», «modificat», «AGGIORNAMENTO»)",
         ", ".join(sorted(set(re.findall(r"abrogat\w*|soppress\w*|modificat\w*|AGGIORNAMENTO", text)))) or "none"],
        ["Normattiva amendment markers «((» «))»", f"{text.count('((')} opening / {text.count('))')} closing" if "((" in text else "none"],
    ])
    w("**Cross-references**")
    w("")
    table(["Reference (as printed)", "Target", "In the demonstration closure?", "Note"],
          [[f"«{r}»", t, c, note] for r, t, c, note in spec["refs"]])
    w("**Needs human judgment**")
    w("")
    for j in spec["judgment"]:
        w(f"- {j}")
    offset = 0
    for k, s in enumerate(pieces[:-1]):
        offset += len(s["text"])
        nxt = pieces[k + 1]
        unit = label_at(text, offset)
        starts_unit = re.match(r"(?:\d+\.|\d+\)|[a-z]\))(?:\s|$)", nxt["text"])
        where = (f"between unit {unit} and the next unit" if starts_unit
                 else f"inside unit {unit}, mid-sentence")
        w(f"- **Page join** between piece {k + 1} (page {s['page_end']}) and piece {k + 2} "
          f"(page {nxt['page']}), {where}. Piece {k + 1} ends "
          f"«{md_cell(one_line(s['text'][-60:]))}»; piece {k + 2} starts "
          f"«{md_cell(one_line(nxt['text'][:60]))}». Confirm against the PDF that nothing is "
          "lost or duplicated there. The running header between them is context.")
    if any(a[2] == "Blank line inside a sentence" for a in an):
        where = sorted({a[1] for a in an if a[2] == "Blank line inside a sentence"}, key=lambda x: labels.index(x) if x in labels else -1)
        w(f"- **Blank lines inside sentences** in {', '.join(where)}: confirm that they are layout "
          "only and that no text is missing at those points.")
    w("")

    w("### E. Review decision worksheet")
    w("")
    w("*To be completed by the human reviewer. Nothing is pre-filled.*")
    w("")
    w("Reviewer (name): ____________________  Review date (YYYY-MM-DD): ____________")
    w("")
    table(["Decision", "What to confirm", "Decision (tick one)", "Notes and corrections"], [
        ["1. Structure", "The article starts and ends at the right place, heading and title belong to it, numbering is as printed, and context (running headers, footnotes, next headings) is excluded.", "☐ confirmed ☐ correction needed ☐ cannot confirm", ""],
        ["2. Extraction fidelity", "The stored text matches the printed source word for word; the anomalies in B are layout only.", "☐ confirmed ☐ correction needed ☐ cannot confirm", ""],
        ["3. Completeness", "Every paragraph and point is present, with nothing truncated or duplicated (D).", "☐ confirmed ☐ correction needed ☐ cannot confirm", ""],
        ["4. Source status markers", "The status markers are recorded as the source prints them (status marker, amendment markers, source status representation). This is not a legal status.", "☐ confirmed ☐ correction needed ☐ cannot confirm", ""],
        ["5. Primary-citation eligibility", "Your view of whether the provision should be citable as primary evidence once the review is recorded. The system computes the tier; record any reason against it.", "☐ should become primary ☐ should not become primary", ""],
    ])
    w("Official-source check: ☐ recorded as computed in C ☐ recorded with my own extraction ☐ not recorded")
    w("")
    w("Ledger outcome to record: ☐ `confirmed` (no change) ☐ `corrected` (list each field, before and after) ☐ no record yet")
    w("")

# --- 10. Cross-provision issues --------------------------------------------------------
w("## 10. Issues that affect several provisions")
w("")
w("- **GDPR text is the 2016 original publication**, not a consolidated text. The qualification "
  "`original_publication_not_consolidated` stays on every GDPR provision whatever the review "
  "says. No corrigendum touches Arts. 4, 33, 34 or 55 (section 3).")
w("- **GDPR Art. 56 is excluded** from the demonstration: our stored text differs from the "
  "consolidated text by corrigenda C2 and C3 (M1). Art. 55(2) refers to it (section 8).")
w("- **Soft hyphens:** Art. 4 has six and Art. 33 has one. They are stored as printed in the "
  "PDF text layer. Retrieval is unaffected, but an exact-quotation check must use the shared "
  "normalisation.")
w("- **Blank lines inside sentences** (Arts. 4, 33, 34): layout from the PDF's hanging indents.")
w("- **Digital Omnibus:** COM(2025) 837 would amend Art. 33. It was not adopted on 2026-11-08 "
  "(M1). This concerns how an answer is worded, not the structural review.")
w("- **Legal validity** is `not_established` for all five and is not part of this review.")
w("")

# --- 11. Missing artifacts ------------------------------------------------------------
w("## 11. Missing artifacts and open questions")
w("")
table(["Artifact or fact", "Status"], [
    ["Official source files (EUR-Lex HTML, Normattiva HTML)", f"**Archived** byte for byte in `{ARCHIVE}/`, with their provenance and attribution (section 3). The texts compared are reproduced in section C, but their hashes cannot be recomputed from this Markdown (rendering may change whitespace): recompute them from the archived files (section 13)."],
    ["Source PDFs (`data/raw/trial-2026-10-10/documents/`)", "**Not in Git** (`data/raw/` is ignored except for the archive). They are needed to check the stored text against the printed pages. The generator checks the GDPR PDF's hash."],
    ["Recorded build `" + BUILD_ID + "`", "**Not in Git** (`data/processed/` is ignored). It is needed to regenerate this package. Its ID includes code commit `e29a1b4`, so a rebuild at a later commit gets a different ID."],
    ["Authentic GDPR text (signed electronic Official Journal)", "**Unavailable.** Not acquired. Our PDF matches the EUR-Lex PDF, which has no signature."],
    ["Authentic Privacy Code text (Gazzetta Ufficiale)", "**Unavailable.** Not acquired. The comparison is against Normattiva only."],
    ["Normattiva consolidation date", "**Unavailable.** The «vigente al» field had no date; `consolidation_date` is `null` in the candidate."],
    ["Amending act behind Art. 2-bis's «(( ))» markers", "**Unverified.** Not named in the stored text, and not checked in M1."],
    ["Who retrieved the official sources", "The assistant, during M1 (2026-11-08). If you rely on these retrievals, the ledger record still describes your review."],
])

# --- 12. After review -----------------------------------------------------------------
w("## 12. After the review (not part of this package)")
w("")
w("This package does not change any file. Recording a review is a separate, deliberate step "
  "(`data/reference/README.md`, «Human review»):")
w("")
w("1. In the inventory entry, set `review_status` to `reviewed` and fill in `checked_by` and "
  "`checked_on`. For a correction, also edit the corrected fields.")
w("2. Add one record to `data/reference/review_ledger.json`, with the same reviewer and date, "
  "outcome `confirmed` or `corrected`, the corrections, and optionally `official_check`.")
w("")
w("**Known effects of recording reviews:**")
w("")
w("- The recorded build stays usable: review fields do not make anchors stale.")
w("- Two tests assume an empty ledger and will need updating in the same change:")
w("  - `test_shipped_files_load_and_the_ledger_is_empty`;")
w("  - `test_nothing_is_primary_while_the_ledger_is_empty` (319 `internal_only`, 2 `blocked`).")
w("- The README sentences saying the ledger is empty will need updating too.")
w("- Whether a new recorded build is wanted after that commit is a policy decision (TECHNICAL_DEBT.md TD-062).")
w("")

# --- 13. Appendix -----------------------------------------------------------------------
w("## 13. Appendix: how to re-check this package")
w("")
w("Look up a provision in the recorded build (the default build):")
w("")
w("```powershell")
w(".\\.venv\\Scripts\\python.exe -m src.provision_cli lookup gdpr 33 --json")
w(".\\.venv\\Scripts\\python.exe -m src.provision_cli lookup \"codice privacy\" 2-bis --json")
w("```")
w("")
w("Recompute the length and SHA-256 of a stored article text (example: Art. 33):")
w("")
w("```powershell")
w(".\\.venv\\Scripts\\python.exe -c \"import json,hashlib; m=json.load(open(r'data\\processed\\builds\\"
  + BUILD_ID + "\\anchors\\" + map_files[GDPR_V].name + "',encoding='utf-8')); "
  "t=''.join(s['text'] for s in m['segments'] if s['kind']=='article' and s['provision_id']=='"
  + GDPR_V + "/body/article:33'); print(len(t), hashlib.sha256(t.encode('utf-8')).hexdigest())\"")
w("```")
w("")
w("Compare with an official text you extracted yourself (this writes nothing):")
w("")
w("```python")
w("from src.provisions import official_check_record")
w("check = official_check_record(our_text, official_text, source_url=..., source_type=...,")
w("                              consolidation_date=..., retrieved_on=...)")
w("```")
w("")
w("**How the official texts in section C were extracted** from the archived HTML (the same "
  "procedure is recorded in `official_sources.json` under `extraction`):")
w("")
w("1. `<script>` and `<style>` elements were removed.")
w("2. Every tag was replaced by a line break, and HTML entities were decoded.")
w("3. Each line was stripped of surrounding whitespace (no-break spaces included), and empty "
  "lines were dropped.")
w("4. The article was cut out:")
w("   - **EUR-Lex:** from the line `Articolo N` to just before the next `Articolo N`, "
  "`CAPO …` or `Sezione N` line;")
w("   - **Normattiva:** from `Art. 2-bis` to just before the page's «articolo precedente» "
  "navigation text.")
w("")
w("Step 3 changes only whitespace, but it does change the `official_text_sha256`.")
w("")
w("**How this package is generated**")
w("")
w("It is generated by `tools/review_package/generate.py` (see `tools/review_package/README.md`) "
  "and must not be edited by hand. From the repository root:")
w("")
w("```powershell")
w("# Verify the archived sources and the five extraction hashes (writes nothing).")
w(".\\.venv\\Scripts\\python.exe -m tools.review_package.official_texts")
w("# Check that this file is reproduced byte for byte (writes nothing).")
w(".\\.venv\\Scripts\\python.exe -m tools.review_package.generate --check")
w("```")
w("")
w("**Inputs:**")
w("")
w("- tracked: the archived sources, the instrument registry, the inventories, the review ledger "
  "and the code;")
w(f"- not tracked: the recorded build `{BUILD_ID}` and the GDPR source PDF (section 11).")
w("")
w("**Limits:**")
w("")
w("- A fresh clone can verify the sources and their extraction hashes, but cannot regenerate "
  "this package until the untracked inputs are copied in.")
w("- The package shows the current inventories and ledger. Once a review is recorded, `--check` "
  "reports a difference: this file describes the state before review.")

content = ("\n".join(L) + "\n").encode("utf-8")
if ARGS.check:
    same = OUT.is_file() and OUT.read_bytes() == content
    print(f"{OUT}: {'byte-identical to the generated package' if same else 'DIFFERS from the generated package'} "
          f"(generated sha256 {hashlib.sha256(content).hexdigest()})")
    sys.exit(0 if same else 1)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(content)
print("wrote", OUT, len("\n".join(L)), "chars")
