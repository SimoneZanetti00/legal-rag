"""Build the P1.2 candidate reference inventories from the source PDFs only.

    python -m tools.reference_inventory.build --output-dir <dir> [--generated-on YYYY-MM-DD]
                                              [--overwrite] [--discard-reviews]

Input: the two trial PDFs in data/raw/trial-2026-10-10/documents/, identified by
SHA-256; a different file is refused. The text layer is read with PyMuPDF
(page.get_text("dict") lines). Nothing from src.ingestion, src.chunking or any
chunk file is used: parser output is only a cross-check (crosscheck.py).

Safety:
- the output directory must be given; nothing is written anywhere else;
- an existing inventory file is replaced only with --overwrite, and one that
  holds any reviewed entry (or cannot be read) only with --discard-reviews too;
- both inventories are built, validated and checked against a second extraction
  of the same PDFs (plain page text) before anything is written. If any check
  fails, nothing is written;
- no temporary or intermediate file is written.

The document-specific rules and notes below are the ones used for the shipped
inventories. With PyMuPDF 1.28.2 and --generated-on 2026-11-07 the output is
byte-identical to data/reference/*.inventory.json.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
from collections import Counter
from importlib import metadata
from pathlib import Path

import pymupdf

from src.reference_inventory import (
    entry_id_for,
    missing_entry_id_for,
    serialize_inventory,
    validate_inventory,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCUMENTS_DIR = REPO_ROOT / "data/raw/trial-2026-10-10/documents"
DOCUMENTS_PATH = "data/raw/trial-2026-10-10/documents"  # as recorded in the inventories
TESTED_PYMUPDF = "1.28.2"


class BuildError(RuntimeError):
    """The build was refused or failed; nothing has been written."""


# --- Extraction and parsing of the text layer -----------------------------------------


def pdf_lines(path: Path) -> tuple[list[dict], int]:
    """Non-blank lines in reading order: dicts with page, bold, x and text (stripped)."""
    out = []
    with pymupdf.open(path) as doc:
        page_count = doc.page_count
        for pno, page in enumerate(doc, start=1):
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    spans = [s for s in line["spans"] if s["text"].strip()]
                    if not spans:
                        continue
                    text = "".join(s["text"] for s in line["spans"]).strip()
                    bold = all((s["flags"] & 16) or "Bold" in s["font"] for s in spans)
                    out.append(
                        {"page": pno, "bold": bold, "x": round(line["bbox"][0]), "text": text}
                    )
    return out, page_count


def _balanced(text: str) -> bool:
    return text.count("(") <= text.count(")")


def build_inventory(cfg: dict, pdf: Path, generated_on: str) -> dict:
    """The inventory for one source PDF, built and validated in memory."""
    data = pdf.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    all_lines, page_count = pdf_lines(pdf)
    header = re.compile(cfg["header"])
    lines = [ln for ln in all_lines if not header.match(ln["text"])]
    removed = len(all_lines) - len(lines)

    start = cfg["scope_start"](lines)
    end = cfg["scope_end"](lines)
    closing = next(
        (i for i in range(start, end) if lines[i]["text"].startswith(cfg["closing_starts"])), end
    )
    scope = lines[start:closing]

    art_re = re.compile(cfg["article"])
    div_re = re.compile(cfg["division"])
    levels = cfg["levels"]
    stack: dict[int, dict] = {}  # level -> open division
    divisions: list[dict] = []
    entries: list[dict] = []
    stats: Counter[str] = Counter()
    candidate_re = re.compile(
        r"^(?:\(\(\s*)?(?:Art\.|ART\.|art\.|Articolo|ARTICOLO|articolo)\s*\d"
    )
    prose_candidates = []
    current = None  # the entry whose text the current line belongs to
    i = 0
    while i < len(scope):
        ln = scope[i]
        text = ln["text"]
        dm = div_re.match(text)
        am = art_re.match(text)
        if dm:
            kind_word, numeral = dm.group("kind"), dm.group("num")
            kind = kind_word.lower()
            level = levels[kind]
            for lv in [lv for lv in stack if lv >= level]:
                del stack[lv]
            parent = stack[max(stack)] if stack else None
            segment = f"{kind}:{numeral}"
            division_id = (parent["division_id"] + "/" if parent else cfg["prefix"] + ":") + segment
            label = f"{kind_word} {numeral}"
            title_lines, marker, notes = [], None, []
            j = i + 1
            preamble_stop = cfg.get("preamble_stop", "\0")
            while j < len(scope) and len(title_lines) < 5:
                t = scope[j]["text"]
                if div_re.match(t) or art_re.match(t) or t.startswith(preamble_stop):
                    break
                if cfg["title_bold_only"] and not scope[j]["bold"]:
                    break
                if re.match(r"^\(\((TITOLO|CAPO|SEZIONE) ABROGAT", t):
                    marker = t
                else:
                    title_lines.append(t)
                j += 1
            if len(title_lines) >= 5:
                notes.append("REVIEW: title collection stopped after 5 lines")
            title = " ".join(title_lines) or None
            if title and "((...))" in title:
                notes.append(
                    "The printed title is followed by the line '((...))', an elision marker; "
                    "it is kept in the title as printed."
                )
            division = {
                "division_id": division_id,
                "kind": kind,
                "label": label,
                "heading_as_printed": text,
                "title": title,
                "status_marker": marker,
                "page": ln["page"],
                "parent_id": parent["division_id"] if parent else None,
                "notes": notes,
            }
            divisions.append(division)
            stack[level] = division
            current = None
            i = j
            continue
        if am:
            label = am.group("label")
            heading_page = ln["page"]
            title_lines, marker, notes = [], None, []
            j = i + 1
            nxt = scope[j]["text"] if j < len(scope) else ""
            if cfg["title_bold_only"]:
                while j < len(scope) and scope[j]["bold"] and not art_re.match(scope[j]["text"]):
                    title_lines.append(scope[j]["text"])
                    j += 1
            elif art_re.match(nxt) or div_re.match(nxt):
                notes.append(
                    f"No title or status text is printed: the next line is the heading {nxt!r}."
                )
            elif nxt.startswith("("):
                acc = []
                while j < len(scope) and len(acc) < 4:
                    acc.append(scope[j]["text"])
                    j += 1
                    if _balanced(" ".join(acc)):
                        break
                joined = " ".join(acc)
                if not _balanced(joined):
                    notes.append("REVIEW: parentheses of the title do not balance within 4 lines")
                if re.search(r"ARTICOLO (ABROGATO|NON PI)", joined):
                    marker = joined
                else:
                    title_lines = acc
            elif re.match(r"^\(?\(?\s*\d+[.)]", nxt):
                notes.append("No title is printed: the text starts directly after the heading.")
            else:
                title_lines = [nxt]
                j += 1
                notes.append(
                    f"The title {nxt!r} is printed without parentheses and in regular type, "
                    "unlike the other titles of this document; it is recorded as printed."
                )
            title = " ".join(title_lines) or None
            if title_lines and scope[i + 1]["page"] != heading_page:
                notes.append(
                    f"The heading is on page {heading_page} and the title starts on page "
                    f"{scope[i + 1]['page']}; the running header lies between them."
                )
            if title and ("­" in title or any(t.endswith("-") for t in title_lines[:-1])):
                notes.append("REVIEW: the title contains a soft hyphen or a hyphen at a line end.")
            current = {
                "entry_id": None,
                "document_id": "doc-" + sha[:16],
                "ordinal": None,
                "kind": "article",
                "heading_as_printed": text,
                "label": label,
                "title": title,
                "status_marker": marker,
                "page_start": heading_page,
                "page_end": scope[j - 1]["page"],
                "parent_id": stack[max(stack)]["division_id"] if stack else None,
                "parent_path": " > ".join(stack[lv]["label"] for lv in sorted(stack)) or None,
                "structural_status": "marked_repealed" if marker else "present",
                "review_status": "pending_human_review",
                "checked_by": None,
                "checked_on": None,
                "source_sha256": sha,
                "notes": notes,
                "_aggiornamento": 0,
                "_stray": 0,
            }
            entries.append(current)
            i = j
            continue
        # A line of text.
        if candidate_re.match(text):
            prose_candidates.append({"page": ln["page"], "text": text[:120]})
        if current is not None:
            current["page_end"] = max(current["page_end"], ln["page"])
            if text.startswith("AGGIORNAMENTO"):
                current["_aggiornamento"] += 1
            if text == ".":
                if scope[i - 1]["text"] == "((":
                    current["_stray"] += 1
                else:
                    current["notes"].append(
                        f"A line consisting only of '.' is printed inside the text on page "
                        f"{ln['page']}, after '...{scope[i - 1]['text'][-40:]}' and before "
                        f"'{scope[i + 1]['text'][:30]}...'."
                    )
        for name, pattern in cfg["counts"].items():
            if re.match(pattern, text):
                stats[name] += 1
        i += 1

    stats["marker_line_before_numbered_paragraph"] = sum(
        1
        for a, b in zip(scope, scope[1:])
        if a["text"] == "((" and re.match(r"^\d+(?:-[a-z]+)?\.\s", b["text"])
    )

    for e in entries:
        if e.pop("_aggiornamento"):
            e["notes"].append(
                "The article's text includes an editorial update note ('AGGIORNAMENTO (n)') "
                "of the transcription; it is not article text."
            )
        if e.pop("_stray"):
            e["notes"].append(
                "A stray line '.' (with '((' before it) is printed between the title and "
                "paragraph 1."
            )
    for suffix, note in cfg.get("division_notes", {}).items():
        for d in divisions:
            if d["division_id"] == cfg["prefix"] + ":" + suffix:
                d["notes"].append(note)
    for label, note in cfg["entry_notes"].items():
        for e in entries:
            if e["label"] == label:
                e["notes"].append(note)
    for label, (status, note) in cfg["overrides"].items():
        for e in entries:
            if e["label"] == label:
                e["structural_status"] = status
                e["notes"].append(note)

    label_counts = Counter(e["label"] for e in entries)
    for e in entries:
        if label_counts[e["label"]] > 1 and e["structural_status"] != "ambiguous":
            e["structural_status"] = "duplicate_label"
            e["notes"].append(
                f"The label {e['label']!r} is printed {label_counts[e['label']]} times."
            )

    bases = [int(re.match(r"\d+", e["label"]).group()) for e in entries]
    missing = sorted(set(range(1, max(bases) + 1)) - set(bases))
    for n in missing:
        pos = max(k for k, b in enumerate(bases) if b < n) + 1
        entries.insert(
            pos,
            {
                **{k: None for k in entries[0] if k != "notes"},
                "entry_id": missing_entry_id_for(cfg["prefix"], str(n)),
                "document_id": "doc-" + sha[:16],
                "kind": "article",
                "structural_status": "expected_missing",
                "review_status": "pending_human_review",
                "source_sha256": sha,
                "notes": [
                    f"No heading for article {n} is printed between articles {n - 1} and {n + 1}."
                ],
            },
        )
        bases.insert(pos, n)

    seen: Counter[str] = Counter()
    for k, e in enumerate(entries, start=1):
        e["ordinal"] = k
        if e["structural_status"] != "expected_missing":
            seen[e["label"]] += 1
            e["entry_id"] = entry_id_for(cfg["prefix"], e["label"], seen[e["label"]])

    inventory = {
        "schema_version": 1,
        "inventory_id": cfg["inventory_id"],
        "entry_id_prefix": cfg["prefix"],
        "document": {
            "doc_id": "doc-" + sha[:16],
            "path": f"{DOCUMENTS_PATH}/{cfg['file']}",
            "sha256": sha,
            "size_bytes": len(data),
            "page_count": page_count,
            "title_as_printed": cfg["title_as_printed"],
            "nature": cfg["nature"],
            "caveats": cfg["caveats"],
        },
        "scope": cfg["scope"],
        "provenance": {
            "generated_on": generated_on,
            "generated_by": (
                "Claude (AI assistant) in a Claude Code session, from the source PDF only. "
                "This is candidate generation, not a human review."
            ),
            "method": cfg["method"] + [f"Running-header lines removed before analysis: {removed}."],
            "parser_output_used": False,
            "human_review": (
                "No entry has been reviewed by a person yet: every entry is "
                "pending_human_review with checked_by and checked_on null."
            ),
        },
        "source_notes": cfg["source_notes"](stats, prose_candidates),
        "divisions": divisions,
        "entries": entries,
    }
    validate_inventory(inventory)
    return inventory


def check_against_page_text(inventory: dict, pdf: Path) -> list[str]:
    """Second extraction: compare every entry with the PDF's plain page text."""
    with pymupdf.open(pdf) as doc:
        pages = {i + 1: doc[i].get_text("text") for i in range(doc.page_count)}
    page_lines = {p: [ln.strip() for ln in t.split("\n")] for p, t in pages.items()}
    first, last = inventory["scope"]["first_page"], inventory["scope"]["last_page"]
    entries = inventory["entries"]
    problems = []

    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip()

    for k, e in enumerate(entries):
        if e["structural_status"] == "expected_missing":
            continue
        hits = [
            p for p, lines in page_lines.items()
            if first <= p <= last and e["heading_as_printed"] in lines
        ]
        if hits != [e["page_start"]]:
            problems.append(f"{e['entry_id']}: heading found on pages {hits}")
        for field in ("title", "status_marker"):
            if e[field]:
                window = norm(pages[e["page_start"]] + " " + pages.get(e["page_start"] + 1, ""))
                if norm(e[field]) not in window:
                    problems.append(f"{e['entry_id']}: {field} not found as printed")
        if k + 1 < len(entries) and entries[k + 1]["page_start"] is not None:
            nxt = entries[k + 1]["page_start"]
            if not e["page_end"] <= nxt <= e["page_end"] + 1:
                problems.append(f"{e['entry_id']}: page_end {e['page_end']} vs next heading {nxt}")
    for d in inventory["divisions"]:
        if d["heading_as_printed"] not in page_lines[d["page"]]:
            problems.append(f"{d['division_id']}: heading not on page {d['page']}")
    return problems


# --- Document-specific rules (used for the shipped inventories) ----------------------


def _first_index(pred):
    def find(lines):
        return next(i for i, ln in enumerate(lines) if pred(ln["text"]))

    return find


CODICE_METHOD = [
    "Text: PyMuPDF page.get_text('dict') lines of the source PDF, stripped of leading and "
    "trailing whitespace; nothing else in a line is changed.",
    "Article heading: a line consisting only of 'Art. ' plus an identifier (a number, an "
    "optional hyphenated Latin suffix, an optional '.n' sub-number), as printed.",
    "Division heading: a line consisting only of PARTE, TITOLO, CAPO or SEZIONE plus a roman "
    "numeral (optionally '0.'), optionally preceded by '(('. Parent paths follow the printed "
    "order (a PARTE closes the open TITOLO, CAPO and SEZIONE, and so on).",
    "Article title: the bracketed text after the heading, up to the line where the brackets "
    "balance, joined with single spaces. A '((ARTICOLO ABROGATO ...))' text in that place is "
    "recorded as status_marker instead.",
    "Pages: page_start is the heading's page; page_end the page of the article's last line "
    "before the next heading, the closing formula or the scope end.",
    "No parser, chunker or chunk file was used. The parser cross-check is a separate report "
    "(data/reference/parser_crosscheck.md) and did not change this file.",
]


def _codice_notes(stats, prose):
    hidden = stats["paragraph_number_after_marker"] + stats["marker_line_before_numbered_paragraph"]
    return [
        "Running header 'D.Lgs. 30 giugno 2003, n. 196 — testo trascritto' and 'Pagina N' on "
        "every page (N equals the PDF page number); removed before analysis.",
        "Amended paragraphs whose number directly follows the amendment marker '((': "
        f"{hidden}"
        f" in the main body ({stats['paragraph_number_after_marker']} printed on one line as "
        f"'((1. ...', {stats['marker_line_before_numbered_paragraph']} with '((' on a text-layer "
        "line of its own directly before the numbered line). How the number reaches the parser "
        "depends on the text extraction mode. Paragraph level only; no article boundary depends "
        f"on them. Numbered paragraph lines in the main body: {stats['numbered_paragraph_lines']}.",
        f"Editorial update notes ('AGGIORNAMENTO (n)') in the main body: "
        f"{stats['aggiornamento_lines']}, each inside an article's text.",
        f"Lines in the main body starting with 'Art.'/'art.'/'Articolo' that are not headings: "
        f"{len(prose)}.",
        "Every article heading is printed on a line of its own as 'Art. <identifier>' with no "
        "trailing full stop; no heading in the main body is preceded by '(('.",
        "The CAPO I of PARTE III, TITOLO I (page 38) is followed by the line '((...))'; SEZIONE "
        "III is printed on page 40 but no SEZIONE I or II heading is printed in that CAPO.",
    ]


CODICE = {
    "file": "codice_privacy_dlgs_196_2003.pdf",
    "sha256": "0d264a29f564b4baec978b1786898c09329e1d4de0d57cfad9673bda9116ffe5",
    "out": "codice_privacy_dlgs_196_2003.main_body.inventory.json",
    "inventory_id": "dlgs-196-2003-transcription-main-body",
    "prefix": "dlgs-196-2003-transcription:body",
    "header": r"^(D\.Lgs\. 30 giugno 2003, n\. 196 — testo trascritto|Pagina \d+)$",
    "scope_start": lambda lines: 0,
    "scope_end": _first_index(lambda t: t == "ALLEGATO A.1"),
    "closing_starts": "Il presente decreto, munito del sigillo dello Stato",
    "preamble_stop": "IL PRESIDENTE DELLA REPUBBLICA",
    "article": r"^Art\. (?P<label>\d+(?:-[a-z]+(?:-[a-z]+)?)?(?:\.\d+)?)$",
    "division": r"^(?:\(\(\s*)?(?P<kind>PARTE|TITOLO|CAPO|SEZIONE) (?P<num>(?:0\.)?[IVXLC]+)$",
    "levels": {"parte": 0, "titolo": 1, "capo": 2, "sezione": 3},
    "title_bold_only": False,
    "counts": {
        "numbered_paragraph_lines": r"^(?:\(\(\s*)?\d+(?:-[a-z]+)?\.\s",
        "paragraph_number_after_marker": r"^\(\(\s*\d+(?:-[a-z]+)?\.\s",
        "marker_only_lines": r"^\(\($",
        "aggiornamento_lines": r"^AGGIORNAMENTO",
    },
    "title_as_printed": (
        "DECRETO LEGISLATIVO 30 giugno 2003 , n. 196 / Codice in materia di protezione dei dati "
        "personali ((, recante disposizioni per l'adeguamento dell'ordinamento nazionale al "
        "regolamento (UE) n. 2016/679 del Parlamento europeo e del Consiglio, del 27 aprile 2016, "
        "relativo alla protezione delle persone fisiche con riguardo al trattamento dei dati "
        "personali, nonchè alla libera circolazione di tali dati e che abroga la direttiva "
        "95/46/CE))."
    ),
    "nature": (
        "User-provided transcription of the Italian Personal Data Protection Code (d.lgs. 30 "
        "giugno 2003, n. 196), converted to PDF. Its running header reads 'D.Lgs. 30 giugno "
        "2003, n. 196 — testo trascritto'. It is not an official Normattiva document and has not "
        "been verified against an official text."
    ),
    "caveats": [
        "The date 'Vigente al: 5-11-2026' printed on page 1 is the transcription's claim and is "
        "unverified.",
        "Errors of transcription cannot be told apart from the official text: labels and titles "
        "are recorded as this file prints them, including amendment markers '((' and '))'.",
        "Article status (for example repeal) is recorded only as this file prints it.",
    ],
    "scope": {
        "description": "Main body of the Code only (Parts I-III and the closing formula); the "
        "annexes are excluded.",
        "first_page": 1,
        "last_page": 53,
        "starts_at": "the first line of the document (page 1)",
        "ends_before": "the line 'ALLEGATO A.1' (page 53, bold), the only line equal to that "
        "text; the same boundary as the P0 ingestion option --end-before \"ALLEGATO A.1\". "
        "The closing formula from 'Il presente decreto, munito del sigillo dello Stato' to "
        "'Visto, il Guardasigilli: CASTELLI' (page 53) is in the main body but belongs to no "
        "article.",
        "excluded": [
            "Allegato A.1 to A.7, B and C (pages 53-101), with their own article numbering",
        ],
    },
    "method": CODICE_METHOD,
    "source_notes": _codice_notes,
    "entry_notes": {
        "1": (
            "The headings PARTE I, TITOLO I and CAPO I are printed on page 1 before the "
            "enacting formula ('IL PRESIDENTE DELLA REPUBBLICA ... EMANA il seguente decreto "
            "legislativo:'); they are recorded as this article's parents in that printed order."
        ),
    },
    "division_notes": {
        "parte:III/titolo:I/capo:I/sezione:III": (
            "No SEZIONE I or SEZIONE II heading is printed in this CAPO: Articles 141 to 144-bis "
            "follow the CAPO I heading directly, and this SEZIONE III is the only section "
            "printed. The source does not show whether earlier sections were removed or elided "
            "(compare the '((...))' line after the CAPO I heading)."
        ),
    },
    "overrides": {
        "2-quindecies": (
            "ambiguous",
            "Page 9 prints 'Art. 2-quindecies' immediately followed by 'Art. 2-quinquiesdecies' "
            "and then a single repeal marker. This file does not settle whether these are two "
            "articles (this one with no title or text) or one article printed with two spellings "
            "of the same ordinal (both mean 'fifteenth'). Supporting observation, not used as "
            "the source: the Normattiva HTML saved on 2026-10-10 (source-pages/"
            "normattiva_esporta_attoCompleto.out) marks up 'Art. 2-quindecies' as the heading "
            "and has 'Art. 2-quinquiesdecies' as the first line of that article's text.",
        ),
        "2-quinquiesdecies": (
            "ambiguous",
            "See the entry for 2-quindecies: printed directly after 'Art. 2-quindecies' on page "
            "9; the repeal marker below it may belong to one article or to both labels. If it is "
            "a separate article, its status would be marked_repealed.",
        ),
    },
}

GDPR_METHOD = [
    "Text: PyMuPDF page.get_text('dict') lines of the source PDF, stripped of leading and "
    "trailing whitespace; nothing else in a line is changed.",
    "Article heading: a line consisting only of 'Articolo ' plus a number.",
    "Division heading: a line consisting only of 'CAPO <roman numeral>' or 'Sezione <number>'. "
    "A CAPO closes the open Sezione.",
    "Article and division titles: the bold lines directly after the heading, joined with "
    "single spaces.",
    "Pages: page_start is the heading's page; page_end the page of the article's last line "
    "before the next heading or the closing formula.",
    "No parser, chunker or chunk file was used. The parser cross-check is a separate report "
    "(data/reference/parser_crosscheck.md) and did not change this file.",
]


def _gdpr_notes(stats, prose):
    return [
        "Running header '4.5.2016', 'L 119/N', 'Gazzetta ufficiale dell'Unione europea' and "
        "'IT' on every page; removed before analysis.",
        f"Footnote lines starting '(n) ' inside the enacting terms: {stats['footnote_lines']} "
        "(for example references to the Official Journal); they are not article text.",
        f"Lines in the enacting terms starting with 'Articolo'/'Art.' that are not headings: "
        f"{len(prose)}.",
        "Paragraph numbers ('1.', '2.' ...) are printed on lines of their own.",
    ]


GDPR = {
    "file": "gdpr_2016_679_it.pdf",
    "sha256": "8f7504d289853f57647bd94d8926f4661e7b41a1204f4d74eca9d8685069427b",
    "out": "gdpr_2016_679_it.inventory.json",
    "inventory_id": "gdpr-2016-679-oj-it",
    "prefix": "gdpr-2016-679-oj-it",
    "header": r"^(4\.5\.2016|L 119/\d+|Gazzetta ufficiale dell'Unione europea|IT)$",
    "scope_start": _first_index(lambda t: t == "HANNO ADOTTATO IL PRESENTE REGOLAMENTO:"),
    "scope_end": lambda lines: len(lines),
    "closing_starts": "Il presente regolamento è obbligatorio in tutti i suoi elementi",
    "article": r"^Articolo (?P<label>\d+)$",
    "division": r"^(?P<kind>CAPO|Sezione) (?P<num>[IVXLC]+|\d+)$",
    "levels": {"capo": 0, "sezione": 1},
    "title_bold_only": True,
    "counts": {"footnote_lines": r"^\(\d+\)\s"},
    "title_as_printed": (
        "REGOLAMENTO (UE) 2016/679 DEL PARLAMENTO EUROPEO E DEL CONSIGLIO del 27 aprile 2016 "
        "relativo alla protezione delle persone fisiche con riguardo al trattamento dei dati "
        "personali, nonché alla libera circolazione di tali dati e che abroga la direttiva "
        "95/46/CE (regolamento generale sulla protezione dei dati) (Testo rilevante ai fini del "
        "SEE)"
    ),
    "nature": (
        "Original publication of Regulation (EU) 2016/679 in the Official Journal of the "
        "European Union, L 119 of 4.5.2016, pages 1-88, Italian language version (running "
        "header '4.5.2016 / L 119/N / Gazzetta ufficiale dell'Unione europea / IT'). Reported "
        "by the user as obtained from EUR-Lex; the download URL is not recorded."
    ),
    "caveats": [
        "This is the text as published on 4.5.2016, not a consolidated text: later corrigenda "
        "or amendments are not reflected, and this inventory does not describe the current "
        "text of the GDPR.",
        "The document carries no status markers, so no entry is marked_repealed; that says "
        "nothing about the later status of any article.",
    ],
    "scope": {
        "description": "Enacting terms: Chapters I-XI, Articles 1-99. Citations, recitals and "
        "the closing formula are excluded.",
        "first_page": 32,
        "last_page": 87,
        "starts_at": "the line 'HANNO ADOTTATO IL PRESENTE REGOLAMENTO:' (page 32)",
        "ends_before": "the closing formula 'Il presente regolamento è obbligatorio in tutti i "
        "suoi elementi ...' (page 88), printed indented after Article 99 and followed by "
        "'Fatto a Bruxelles, il 27 aprile 2016' and the signatures.",
        "excluded": [
            "Title, citations and recitals (pages 1-32)",
            "Closing formula and signatures (page 88)",
        ],
    },
    "method": GDPR_METHOD,
    "source_notes": _gdpr_notes,
    "entry_notes": {
        "99": (
            "The unnumbered sentence 'Il presente regolamento è obbligatorio in tutti i suoi "
            "elementi e direttamente applicabile in ciascuno degli Stati membri.' on page 88 is "
            "treated as the closing formula, not as part of this article (it is indented "
            "differently from the article's text, x=119 against 67/89)."
        ),
    },
    "overrides": {},
}

SOURCES = (GDPR, CODICE)


# --- Command line ------------------------------------------------------------------------


def check_targets(targets: list[Path], overwrite: bool, discard_reviews: bool) -> None:
    """Refuse to replace existing inventories unless explicitly allowed (see the module doc)."""
    for target in targets:
        if not target.exists():
            continue
        if not overwrite:
            raise BuildError(f"{target} exists; pass --overwrite to replace it.")
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
            reviewed = sum(
                1 for e in existing["entries"] if e.get("review_status") != "pending_human_review"
            )
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            reviewed = None
        if reviewed != 0 and not discard_reviews:
            what = (
                "cannot be read as an inventory, so it may hold reviews"
                if reviewed is None
                else f"holds {reviewed} entries that are not pending_human_review"
            )
            raise BuildError(
                f"{target} {what}; rebuilding would discard them. Pass --discard-reviews as "
                "well only if that is intended."
            )


def check_sources(documents_dir: Path) -> None:
    """Refuse unless each source PDF exists with its expected SHA-256."""
    for cfg in SOURCES:
        pdf = documents_dir / cfg["file"]
        if not pdf.is_file():
            raise BuildError(f"source PDF not found: {pdf}")
        actual = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if actual != cfg["sha256"]:
            raise BuildError(
                f"{pdf} has SHA-256 {actual}, not the expected {cfg['sha256']}; the rules in "
                "this builder are written for that exact file."
            )


def _date(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise argparse.ArgumentTypeError("use YYYY-MM-DD")
    datetime.date.fromisoformat(value)
    return value


def main(argv: list[str] | None = None, *, documents_dir: Path = DOCUMENTS_DIR) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.reference_inventory.build",
        description="Build the P1.2 reference inventories from the source PDFs.",
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="where to write")
    parser.add_argument(
        "--generated-on",
        type=_date,
        default=datetime.date.today().isoformat(),
        help="provenance.generated_on (default: today; 2026-11-07 reproduces the shipped files)",
    )
    parser.add_argument("--overwrite", action="store_true", help="replace existing files")
    parser.add_argument(
        "--discard-reviews",
        action="store_true",
        help="with --overwrite, also replace files that hold reviewed entries",
    )
    args = parser.parse_args(argv)
    targets = [args.output_dir / cfg["out"] for cfg in SOURCES]
    try:
        check_targets(targets, args.overwrite, args.discard_reviews)
        check_sources(documents_dir)
        installed = metadata.version("PyMuPDF")
        if installed != TESTED_PYMUPDF:
            print(
                f"warning: PyMuPDF {installed} (the shipped files were built with "
                f"{TESTED_PYMUPDF}); the output may differ.",
                file=sys.stderr,
            )
        texts = {}
        for cfg, target in zip(SOURCES, targets):
            pdf = documents_dir / cfg["file"]
            inventory = build_inventory(cfg, pdf, args.generated_on)
            problems = check_against_page_text(inventory, pdf)
            if problems:
                raise BuildError(f"{cfg['out']} fails the page-text check: {problems}")
            texts[target] = serialize_inventory(inventory)
            counts = Counter(e["structural_status"] for e in inventory["entries"])
            print(f"{cfg['out']}: {len(inventory['entries'])} entries, {dict(counts)}")
    except BuildError as exc:
        print(f"error: {exc} Nothing was written.", file=sys.stderr)
        return 2
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for target, text in texts.items():
        target.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
