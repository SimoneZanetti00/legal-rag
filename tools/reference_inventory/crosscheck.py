"""Compare parser output with the P1.2 reference inventories; write a Markdown report.

    python -m tools.reference_inventory.crosscheck --report <path.md>
                                                   [--generated-on YYYY-MM-DD] [--overwrite]

The inventories are the reference; the parser is what is checked. The script
reads the inventories and never writes them (it verifies their hashes before and
after). Inputs:
- Privacy Code: the trial's existing chunk file
  data/processed/trial-2026-10-10/codice_privacy_main_body.jsonl (git-ignored);
- GDPR: no current chunk file exists, so the parser's heading detection
  (src.ingestion.load_document, src.chunking._split_blocks/_group_units) runs in
  memory on the source PDF. No chunk is generated and nothing else is written.

The report must be a Markdown (.md) file and can never be one of the
inventories. An existing report is replaced only with --overwrite. The report records the
commit and whether the parser code (src/ingestion.py, src/chunking.py,
src/models.py) differs from it.
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

from src.chunking import _group_units, _split_blocks
from src.ingestion import load_document
from src.reference_inventory import load_inventory, serialize_inventory

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE = REPO_ROOT / "data/reference"
GDPR_INV = REFERENCE / "gdpr_2016_679_it.inventory.json"
CODICE_INV = REFERENCE / "codice_privacy_dlgs_196_2003.main_body.inventory.json"
CODICE_CHUNKS = REPO_ROOT / "data/processed/trial-2026-10-10/codice_privacy_main_body.jsonl"
PARSER_FILES = ("src/ingestion.py", "src/chunking.py", "src/models.py")
_DIVISION_LINE = re.compile(r"^\(\(\s*(PARTE|TITOLO|CAPO|SEZIONE) ")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha(path: Path) -> str:
    """SHA-256 of the inventory's canonical (LF) text; equals the file's when it is canonical."""
    return _sha(serialize_inventory(load_inventory(path)).encode("utf-8"))


def _git(*args: str) -> str:
    run = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, check=True
    )
    return run.stdout.strip()


def runs_from_chunks(path: Path):
    """Article runs (consecutive chunks with the same article label) and unlabeled chunks."""
    runs, unlabeled, chunks = [], [], []
    for raw in path.read_text(encoding="utf-8").splitlines():
        chunk = json.loads(raw)
        chunks.append(chunk)
        loc = chunk["location"]
        label = loc["article"]
        if label is None:
            unlabeled.append(chunk)
            continue
        last = runs[-1] if runs else None
        if last and last["label"] == label and last["last_index"] == chunk["chunk_index"] - 1:
            last["last_index"] = chunk["chunk_index"]
        else:
            runs.append(
                {
                    "label": label,
                    "page": loc["page"],
                    "first_index": chunk["chunk_index"],
                    "last_index": chunk["chunk_index"],
                    "section": loc["section"],
                }
            )
    return runs, unlabeled, chunks


def runs_from_parser(pdf: Path):
    """Article heading blocks found by the parser, in memory."""
    document, _ = load_document(pdf)
    runs = []
    for unit in _group_units(_split_blocks(document.content)):
        for block in unit.blocks:
            if block.kind == "article":
                runs.append(
                    {"label": block.label, "page": document.page_at(block.start),
                     "section": unit.section}
                )
    return runs


def compare(inventory, runs):
    entries = [e for e in inventory["entries"] if e["structural_status"] != "expected_missing"]
    a, b = [e["label"] for e in entries], [r["label"] for r in runs]
    matched, page_mismatch, not_found, parser_only, mismatches = [], [], [], [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            for e, r in zip(entries[i1:i2], runs[j1:j2]):
                (matched if r["page"] == e["page_start"] else page_mismatch).append((e, r))
        elif op == "replace":
            pairs = list(zip(entries[i1:i2], runs[j1:j2]))
            mismatches.extend(pairs)
            not_found.extend(entries[i1 + len(pairs) : i2])
            parser_only.extend(runs[j1 + len(pairs) : j2])
        elif op == "delete":
            not_found.extend(entries[i1:i2])
        elif op == "insert":
            parser_only.extend(runs[j1:j2])
    counts = Counter(b)
    return {
        "entries": entries,
        "matched": matched,
        "page_mismatch": page_mismatch,
        "not_found": not_found,
        "parser_only": parser_only,
        "mismatches": mismatches,
        "duplicates": {label: n for label, n in counts.items() if n > 1},
        "unknown_labels": sorted(set(b) - set(a)),
    }


def section_differences(inventory, pairs):
    division = {d["division_id"]: d for d in inventory["divisions"]}
    agree, differ = 0, []
    for e, r in pairs:
        innermost = division[e["parent_id"]]["heading_as_printed"] if e["parent_id"] else None
        if r["section"] == innermost:
            agree += 1
        else:
            differ.append((e, r, innermost))
    return agree, differ


def _labels(items, key=lambda e: e["label"]):
    return ", ".join(f"`{key(x)}`" for x in items) if items else "none"


def build_report(generated_on: str) -> str:
    gdpr, codice = load_inventory(GDPR_INV), load_inventory(CODICE_INV)
    commit = _git("rev-parse", "HEAD")
    parser_changed = _git("status", "--porcelain", "--", *PARSER_FILES)
    code_state = f"commit `{commit}`" + (
        f", with uncommitted changes in {', '.join(PARSER_FILES)}" if parser_changed else
        f"; {', '.join(f'`{p}`' for p in PARSER_FILES)} identical to that commit"
    )
    codice_runs, unlabeled, chunks = runs_from_chunks(CODICE_CHUNKS)
    gdpr_runs = runs_from_parser(REPO_ROOT / gdpr["document"]["path"])
    results = {"gdpr": compare(gdpr, gdpr_runs), "codice": compare(codice, codice_runs)}

    # Division headings with the '((' marker that ended up inside chunk text.
    absorbed = []
    for chunk in chunks:
        for line in chunk["text"].split("\n"):
            s = line.strip()
            if _DIVISION_LINE.match(s) and "ABROGAT" not in s:
                absorbed.append((chunk, s))

    first_article_chunk = codice_runs[0]["first_index"]
    causes = defaultdict(list)
    for chunk in unlabeled:
        if any(line.strip().startswith("Art. ") for line in chunk["text"].split("\n")):
            causes["contains an 'Art. ' line (would be a missed heading)"].append(chunk)
        elif chunk["chunk_index"] < first_article_chunk:
            causes["before the first article heading (title, PARTE I / TITOLO I / CAPO I "
                   "headings, enacting formula)"].append(chunk)
        elif chunk["location"]["section"] is not None:
            causes["a division heading and its title (a recognised PARTE/TITOLO/CAPO/SEZIONE "
                   "heading clears the current article in the chunker)"].append(chunk)
        else:
            causes["other"].append(chunk)

    out = []
    w = out.append
    w("# Parser cross-check of the P1.2 reference inventories")
    w("")
    w(f"*Generated {generated_on} by `python -m tools.reference_inventory.crosscheck`, which "
      "reads the inventories and never writes them. The inventories were built from the source "
      "PDFs first; this report checks the parser against them, not the other way round.*")
    w("")
    w("## Inputs")
    w("")
    w("| Item | Path | SHA-256 |")
    w("|---|---|---|")
    w(f"| GDPR inventory | `data/reference/{GDPR_INV.name}` | `{_canonical_sha(GDPR_INV)}` |")
    w(f"| Privacy Code inventory | `data/reference/{CODICE_INV.name}` | "
      f"`{_canonical_sha(CODICE_INV)}` |")
    w(f"| Privacy Code parser output | `{CODICE_CHUNKS.relative_to(REPO_ROOT).as_posix()}` | "
      f"`{_sha(CODICE_CHUNKS.read_bytes())}` |")
    w("")
    w("- **Inventory hashes** are those of the canonical serialization (UTF-8, LF line "
      "endings). `.gitattributes` keeps these files LF in every checkout, so the hashes equal "
      "the files' bytes.")
    w("- **Privacy Code parser output:** the trial's existing chunk file (main body, boundary "
      "`ALLEGATO A.1`, CHUNK_SIZE 1200, CHUNK_OVERLAP 150; see the trial manifest). An article "
      "*run* is a sequence of consecutive chunks with the same `location.article`; its page is "
      "the page of its first chunk.")
    w("- **GDPR parser output:** no current chunk file exists (the only GDPR chunks are in the "
      "stale `chunks.jsonl`). The parser's heading detection (`load_document`, `_split_blocks`, "
      f"`_group_units`) was run in memory at {code_state}. No chunk was generated and no file "
      "was written. Each article heading block is one run; its page is the heading's page.")
    w("- **Alignment:** the inventory's label sequence and the parser's run sequence are "
      "aligned with `difflib.SequenceMatcher`; equal labels in aligned positions are matches, "
      "aligned different labels are label mismatches.")
    w("")
    for key, title, runs, inventory in (
        ("gdpr", "GDPR", gdpr_runs, gdpr),
        ("codice", "Privacy Code (main body)", codice_runs, codice),
    ):
        r = results[key]
        statuses = Counter(e["structural_status"] for e in r["entries"])
        w(f"## {title}")
        w("")
        w("| Measure | Value |")
        w("|---|---|")
        status_text = ", ".join(f"{k} {v}" for k, v in sorted(statuses.items()))
        w(f"| Inventory entries | {len(r['entries'])} ({status_text}) |")
        w(f"| Parser article headings / runs | {len(runs)} |")
        w(f"| Matched: same label, same page | {len(r['matched'])} |")
        w(f"| Same label, different page | {len(r['page_mismatch'])} |")
        w(f"| Inventory entries not found by the parser | {len(r['not_found'])} |")
        w(f"| Parser-only labels | {len(r['parser_only'])} |")
        w(f"| Label mismatches (aligned, different label) | {len(r['mismatches'])} |")
        w(f"| Labels the parser assigns more than once | {len(r['duplicates'])} |")
        agree, differ = section_differences(inventory, r["matched"] + r["page_mismatch"])
        w(f"| Wrong section assigned by the parser | {len(differ)} |")
        w("")
        w(f"- **Matched entries ({len(r['matched'])}):** {_labels([e for e, _ in r['matched']])}.")
        w("- **Same label, different page:** " + (", ".join(
            f"`{e['label']}` (inventory p. {e['page_start']}, parser p. {x['page']})"
            for e, x in r["page_mismatch"]) or "none") + ".")
        w(f"- **Not found by the parser:** {_labels(r['not_found'])}.")
        w(f"- **Parser-only labels:** {_labels(r['parser_only'])}.")
        w("- **Label mismatches:** " + (", ".join(
            f"inventory `{e['label']}` vs parser `{x['label']}` (p. {x['page']})"
            for e, x in r["mismatches"]) or "none") + ".")
        w("- **Labels assigned to more than one parser run:** " + (", ".join(
            f"`{k}` ({v})" for k, v in sorted(r["duplicates"].items())) or "none") + ".")
        unknown = _labels(r["unknown_labels"], key=str)
        w(f"- **Parser labels absent from the inventory:** {unknown}.")
        w(f"- **Section:** the parser's `section` equals the innermost printed division for "
          f"{agree} of {agree + len(differ)} matched articles"
          + (f"; **{len(differ)} articles receive a wrong section** (see below)." if differ
             else "."))
        w("")

    _, differ = section_differences(
        codice, results["codice"]["matched"] + results["codice"]["page_mismatch"]
    )
    if differ:
        groups = defaultdict(list)
        for e, x, inner in differ:
            groups[(x["section"], inner)].append(e["label"])
        w("## Parser defect: division headings marked with `((` are not recognised")
        w("")
        w(f"{len(differ)} Privacy Code articles receive an incorrect section assignment. This is "
          "a parser/chunking defect, not an expected difference between the two "
          "representations.")
        w("")
        w("- **Cause:** the chunker's section rule only accepts a line that starts with the "
          "division word. The printed headings below begin with the amendment marker `((`, so "
          "the parser does not recognise them as headings. The previous section therefore "
          "stays in force for the following articles.")
        w("- **Wrong sections:**")
        for (parser_section, inner), labels in groups.items():
            plural = "s" if len(labels) != 1 else ""
            w(f"  - printed division `{inner}`, parser section `{parser_section}`: "
              f"{len(labels)} article{plural} ({_labels(labels, key=str)}).")
        w("- **Heading text in the wrong place:** an unrecognised heading line, with the title "
          "printed after it, is treated as ordinary text. It therefore becomes part of the chunk "
          "before it:")
        for chunk, line in absorbed:
            article = chunk["location"]["article"]
            owner = f"labelled article `{article}`" if article else "with no article label"
            w(f"  - `{line}` is inside chunk {chunk['chunk_index']} (page "
              f"{chunk['location']['page']}), {owner}, section "
              f"`{chunk['location']['section']}`.")
        w("- **Effect:** passages near these headings carry a wrong `section`. Where the chunk "
          "belongs to an article, the chunk text attributed to that article also contains a "
          "division heading and title that are not part of the article. Article labels are not "
          "affected.")
        w("- **Status:** recorded here only. The chunker is not changed in P1.2.")
        w("")

    w("## Privacy Code chunks without an article label")
    w("")
    w(f"{len(unlabeled)} of {len(chunks)} chunks have `location.article` null. By position:")
    w("")
    w("| Cause | Chunks | Pages |")
    w("|---|---|---|")
    for cause, items in sorted(causes.items(), key=lambda kv: -len(kv[1])):
        pages = sorted({c["location"]["page"] for c in items})
        w(f"| {cause} | {len(items)} | {', '.join(map(str, pages))} |")
    w("")
    if causes.get("contains an 'Art. ' line (would be a missed heading)"):
        w("**Some unlabeled chunks contain an article heading line: see the table.**")
    else:
        w("No unlabeled chunk contains an article heading line, so none of them is a missed "
          "article. They hold division headings with their titles, and the opening text before "
          "Art. 1. The chunker deliberately keeps these outside any article.")
    w("")
    w("## Cases for manual inspection")
    w("")
    w("- **`2-quindecies` / `2-quinquiesdecies` (page 9):** `ambiguous` in the inventory. The "
      "parser recognises both heading lines, but the first has no text of its own, so both "
      "lines and the repeal marker form one chunk labelled `2-quinquiesdecies`; the label "
      "`2-quindecies` is never assigned. This is the one entry 'not found' above. It is a "
      "consequence of the chunker's grouping, not evidence for either reading.")
    w("- **Art. 120 (page 27):** title `Sinistri` printed without parentheses; the parser does "
      "not read titles, so the cross-check cannot confirm it.")
    w("- **Closing formula of the Privacy Code (page 53):** the parser attributes it to the last "
      "article run (`186`); the inventory records it as main-body text belonging to no article.")
    w("- **Depth of the division path:** separately from the defect above, the parser keeps "
      "only the most recent division heading line as `section`, while the inventory records "
      "the full printed path (for example `PARTE I > TITOLO I > CAPO IV`). This is a design "
      "limit of the chunk format, not counted as a wrong section here.")
    return "\n".join(out).rstrip("\n") + "\n"


def _date(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise argparse.ArgumentTypeError("use YYYY-MM-DD")
    datetime.date.fromisoformat(value)
    return value


def report_path_problem(path: Path) -> str | None:
    """Why `path` cannot be the report, or None. Inventories are never a valid target."""
    target = os.path.normcase(str(path.resolve()))
    if any(target == os.path.normcase(str(inv.resolve())) for inv in (GDPR_INV, CODICE_INV)):
        return f"{path} is a reference inventory; the cross-check never writes inventories."
    if path.suffix.lower() != ".md":
        return f"{path} is not a Markdown (.md) file; the report is Markdown."
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.reference_inventory.crosscheck",
        description="Check the parser against the P1.2 reference inventories.",
    )
    parser.add_argument("--report", type=Path, required=True, help="Markdown file to write")
    parser.add_argument(
        "--generated-on", type=_date, default=datetime.date.today().isoformat(),
        help="date written in the report (default: today)",
    )
    parser.add_argument("--overwrite", action="store_true", help="replace an existing report")
    args = parser.parse_args(argv)
    problem = report_path_problem(args.report)
    if problem:
        print(f"error: {problem} Nothing was written.", file=sys.stderr)
        return 2
    if args.report.exists() and not args.overwrite:
        print(f"error: {args.report} exists; pass --overwrite to replace it.", file=sys.stderr)
        return 2
    if not CODICE_CHUNKS.is_file():
        print(f"error: parser output not found: {CODICE_CHUNKS}", file=sys.stderr)
        return 2
    before = {p: _sha(p.read_bytes()) for p in (GDPR_INV, CODICE_INV)}
    report = build_report(args.generated_on)
    if {p: _sha(p.read_bytes()) for p in before} != before:
        print("error: an inventory changed during the cross-check", file=sys.stderr)
        return 2
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8", newline="\n")
    print(f"wrote {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
