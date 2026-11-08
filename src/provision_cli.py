"""Provision CLI (P1.3): a development interface to the corpus explorer.

    python -m src.provision_cli build [--spec PATH] [--output-root DIR] [--allow-dirty]
    python -m src.provision_cli build-anchors [--build-dir DIR]
    python -m src.provision_cli link [--build-dir DIR]
    python -m src.provision_cli lookup INSTRUMENT LABEL [--build-dir DIR] [--json]
    python -m src.provision_cli search QUESTION [--top-k N] [--build-dir DIR] [--json] [--full]

`--build-dir` defaults to the only recorded build in data/processed/builds/;
temporary verification builds must be named explicitly.

Exit codes: 0 success; 1 no such instrument or article; 2 refused, missing, damaged
or stale build, anchors or links, or invalid arguments. Error messages say what to run.

All results come from src.provision_explorer, which a chat or web interface can call
directly; --json prints exactly what it returns.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src import corpus_build
from src.config import PROJECT_ROOT
from src.corpus_build import CorpusBuildError
from src.corpus_identity import CodeVersionError, detect_code_version
from src.provision_anchors import AnchorError, write_passage_links, write_segment_maps
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.provisions import ProvisionError, load_store

EXCERPT_CHARS = 400
FAILURES = (AnchorError, CorpusBuildError, CodeVersionError, ExplorerError, ProvisionError)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.provision_cli",
        description="Explore the provision store: article lookup and BM25 question search. "
        "BM25 scores are uncalibrated; running headers inside chunk text can affect them "
        "(TECHNICAL_DEBT.md TD-061). Nothing here establishes legal validity.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="build the corpus (same as python -m src.corpus_build)")
    build.add_argument("--spec", type=Path)
    build.add_argument("--output-root", type=Path)
    build.add_argument("--allow-dirty", action="store_true")
    for name, text in (("build-anchors", "write the segment maps of a build"),
                       ("link", "write the passage links of a build")):
        cmd = sub.add_parser(name, help=text)
        cmd.add_argument("--build-dir", type=Path)
    lookup = sub.add_parser("lookup", help="show one article: exact text, status, eligibility")
    lookup.add_argument("instrument", help="instrument name or alias, e.g. gdpr, 'codice privacy'")
    lookup.add_argument("label", help="article label as printed, e.g. 33, 2-bis, 2-quaterdecies.1")
    search = sub.add_parser("search", help="BM25 question search mapped to provisions")
    search.add_argument("question")
    search.add_argument("--top-k", type=int, default=5, help="results (default: 5)")
    search.add_argument("--full", action="store_true", help="print whole chunks, not excerpts")
    for cmd in (lookup, search):
        cmd.add_argument("--build-dir", type=Path)
        cmd.add_argument("--json", action="store_true", help="print the result as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # source text may not fit the console encoding
        sys.stdout.reconfigure(errors="replace")
    if args.command == "build":
        forwarded = (["--spec", str(args.spec)] if args.spec else []) + (
            ["--output-root", str(args.output_root)] if args.output_root else []) + (
            ["--allow-dirty"] if args.allow_dirty else [])
        return corpus_build.main(forwarded)
    try:
        build_dir = args.build_dir or find_recorded_build()
        store = load_store()
        if args.command == "build-anchors":
            paths = write_segment_maps(build_dir, store=store, registry=store.registry,
                                       detect_code=lambda: detect_code_version(PROJECT_ROOT))
            for path in paths:
                print(f"wrote {path}")
            return 0
        if args.command == "link":
            for path in write_passage_links(build_dir, store=store, registry=store.registry):
                print(f"wrote {path}")
            return 0
        if args.command == "search" and args.top_k < 1:
            print("error: --top-k must be at least 1", file=sys.stderr)
            return 2
        explorer = ProvisionExplorer.open(build_dir, store=store)
    except FAILURES as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        if args.command == "lookup":
            result = explorer.lookup(args.instrument, args.label)
            text = render_lookup(result)
        else:
            result = explorer.search(args.question, top_k=args.top_k)
            text = render_search(result, full=args.full)
    except ProvisionError as exc:
        print(f"error: {exc}. Labels are matched exactly as printed (e.g. 33, 2-bis); "
              "instruments by ID or alias.", file=sys.stderr)
        return 1
    except (TypeError, ValueError) as exc:  # e.g. a blank question
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else text)
    return 0


# --- Text rendering --------------------------------------------------------------------------


def _range(item: dict[str, Any]) -> str:
    pages = (f"page {item['page']}" if item["page"] == item["page_end"]
             else f"pages {item['page']}-{item['page_end']}")
    return f"{pages}, characters {item['char_start']}-{item['char_end']}"


def _eligibility_lines(eligibility: dict[str, Any], indent: str = "  ") -> list[str]:
    lines = [f"{indent}tier: {eligibility['tier']}"]
    for reason in eligibility["reasons"]:
        lines.append(f"{indent}not primary because {reason['code']}: {reason['message']}")
    for q in eligibility["qualifications"]:
        lines.append(f"{indent}qualification {q['code']}: {q['message']}")
    return lines


def _build_line(build: dict[str, Any]) -> str:
    code = build["code"]
    state = code["state"] + (f", fingerprint {code['fingerprint'][:12]}" if code["fingerprint"]
                             else "")
    warning = "" if build["build_kind"] == "recorded" else " (verification build, not recorded)"
    return (f"build {build['build_id']}{warning}; code {code['commit'][:12]} ({state}); "
            f"corpus sha256 {build['corpus_sha256'][:16]}")


def render_lookup(result: dict[str, Any]) -> str:
    p = result["provision"]
    v = p["version"]
    review = p["review"]
    reviewed = (f"reviewed by {review['checked_by']} on {review['checked_on']} "
                f"({review['outcome']})" if review["status"] == "reviewed"
                else "pending human review")
    lines = [
        f"{v['instrument_id']} — {p['heading']}" + (f": {p['title']}" if p["title"] else ""),
        f"  provision:      {p['provision_id']}",
        f"  path:           {p['path']}",
        f"  version:        {v['version_id']} ({v['version_kind']}; authenticity "
        f"{v['authenticity'] or 'not established'})",
        f"                  {v['description']}",
        f"  pages:          {p['page_start']}-{p['page_end']}",
        f"  structure:      {p['structural_status']}; {reviewed}",
        "  source says:    " + (p["source_status_representation"]
                                or "not established (ambiguous structure)"),
    ]
    if p["status_marker"]:
        lines.append(f"  printed marker: {p['status_marker']}")
    lines.append(f"  legal validity: {p['legal_validity']} (not established by this system)")
    lines.append("  eligibility:")
    lines += _eligibility_lines(p["eligibility"], "    ")
    prov = p["provenance"]
    lines += [
        f"  provenance:     inventory {prov['inventory_ref']}; source sha256 "
        f"{prov['source_sha256'][:16]}; {prov['doc_id']}; variant {prov['variant_id']}",
        f"  {_build_line(result['build'])}",
        "--- exact source text (article segments only; running headers and footnotes "
        "between pieces are left out) ---",
    ]
    for piece in p["text"]:
        lines += [f"[{_range(piece)}]", piece["text"].rstrip()]
    if p["context"]:
        lines.append("--- context inside the article (not article text) ---")
        for piece in p["context"]:
            lines += [f"[{piece['kind']}, {_range(piece)}]", piece["text"].rstrip()]
    return "\n".join(lines)


def _excerpt(text: str, full: bool) -> str:
    if full or len(text) <= EXCERPT_CHARS:
        return text
    return text[:EXCERPT_CHARS] + f" … [{len(text) - EXCERPT_CHARS} more characters; --full]"


def render_search(result: dict[str, Any], *, full: bool = False) -> str:
    retriever = result["retriever"]
    lines = [
        f"search: {result['query']['question']!r} (BM25 over {retriever['indexed_chunks']} "
        f"chunks, top {result['query']['top_k']})",
        _build_line(result["build"]),
        f"note: {retriever['score_note']}",
    ]
    if not result["results"]:
        lines.append("no chunk contains any of the query terms")
    for r in result["results"]:
        role = "article evidence" if r["role"] == "article_evidence" else (
            "CONTEXT ONLY: no article text, never a citation")
        lines.append("")
        lines.append(f"#{r['rank']}  score {r['score']:.3f} (uncalibrated)  {r['version_id']}  "
                     f"{_range(r)}  [{role}]")
        lines.append(f"    chunk {r['chunk_id']} ({r['variant_id']})")
        for e in r["evidence"]:
            reasons = ", ".join(e["reasons"]) or "none"
            lines.append(f"    evidence: {e['heading']}" + (f" — {e['title']}" if e["title"]
                                                             else "")
                         + f" [{e['tier']}; reasons: {reasons}]")
            for piece in e["pieces"]:
                lines.append(f"      exact article text, {_range(piece)}")
        for c in r["context"]:
            owner = f" of {c['label']}" if c["label"] else ""
            lines.append(f"    context:  {c['kind']}{owner} ({c['chars']} characters, "
                         f"characters {c['char_start']}-{c['char_end']})")
        lines.append("    chunk text: " + _excerpt(r["text"], full).replace("\n", "\n      "))
    lines.append("")
    lines.append("provisions found (best rank first):")
    if not result["provisions"]:
        lines.append("  none: no retrieved chunk contains article text")
    for p in result["provisions"]:
        reasons = ", ".join(x["code"] for x in p["eligibility"]["reasons"]) or "none"
        lines.append(f"  {p['heading']} ({p['provision_id']}): ranks {p['ranks']}; "
                     f"{p['eligibility']['tier']}; reasons: {reasons}")
    if result["primary_citations"]:
        lines.append("primary citations: " + ", ".join(result["primary_citations"]))
    else:
        lines.append("primary citations: none. No retrieved provision is eligible; the "
                     "reasons above say why.")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
