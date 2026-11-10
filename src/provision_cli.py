"""Provision CLI (P1.3): a development interface to the corpus explorer, and `ask`.

    python -m src.provision_cli build [--spec PATH] [--output-root DIR] [--allow-dirty]
    python -m src.provision_cli build-anchors [--build-dir DIR]
    python -m src.provision_cli link [--build-dir DIR]
    python -m src.provision_cli lookup INSTRUMENT LABEL [--build-dir DIR] [--json]
    python -m src.provision_cli search QUESTION [--top-k N] [--build-dir DIR] [--json] [--full]
    python -m src.provision_cli ask QUESTION [--build-dir DIR] [--json]

`python -m src.cli` runs the same commands. `--build-dir` defaults to the only recorded
build in data/processed/builds/; temporary verification builds must be named explicitly.

`ask` answers from citable evidence or abstains (src.answer_generation). It sends the
question and the citable evidence to the LLM provider configured by LLM_PROVIDER, which
must be a real provider: the default "mock" answers nothing outside tests.

Exit codes: 0 success (for ask: an answer or an abstention was printed); 1 no such
instrument or article; 2 refused, missing, damaged or stale build, anchors or links,
invalid arguments, or missing LLM configuration; 3 the LLM provider request failed.
Error messages say what to run.

All results come from src.provision_explorer and src.answer_generation, which a chat or
web interface can call directly; --json prints exactly what they return.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src import corpus_build
from src.answer_generation import (
    MODEL_NOTES_LABEL,
    AnswerResult,
    Outcome,
    SourceReference,
    answer_question,
)
from src.config import PROJECT_ROOT, ConfigError, Settings, load_settings
from src.corpus_build import CorpusBuildError
from src.corpus_identity import CodeVersionError, detect_code_version
from src.llm import LLMClient, LLMConfigError, LLMTransportError, make_llm
from src.models import VerificationStatus
from src.provision_anchors import AnchorError, write_passage_links, write_segment_maps
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.provisions import ProvisionError, load_store
from src.query_analysis import QueryAnalysisError

EXCERPT_CHARS = 400
FAILURES = (AnchorError, CorpusBuildError, CodeVersionError, ExplorerError, ProvisionError)
MOCK_PROVIDER_MESSAGE = (
    "ask needs a real LLM provider, but LLM_PROVIDER is 'mock' (the default), which answers "
    "nothing outside tests. Set LLM_PROVIDER=anthropic, LLM_MODEL and ANTHROPIC_API_KEY in "
    "the environment or a local .env file (see .env.example). The question and the citable "
    "evidence are then sent to that provider."
)


def _parser(prog: str = "python -m src.provision_cli") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Explore the provision store: article lookup and BM25 question search, and "
        "ask a question answered only from citable evidence. BM25 scores are uncalibrated; "
        "running headers inside chunk text can affect them (TECHNICAL_DEBT.md TD-061). Nothing "
        "here establishes legal validity, and nothing here is legal advice.",
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
    ask = sub.add_parser("ask", help="answer a question from citable evidence, or abstain "
                         "(sends it to the configured LLM provider)")
    ask.add_argument("question")
    for cmd in (lookup, search, ask):
        cmd.add_argument("--build-dir", type=Path)
        cmd.add_argument("--json", action="store_true", help="print the result as JSON")
    return parser


def main(argv: list[str] | None = None, *, prog: str = "python -m src.provision_cli",
         llm: LLMClient | None = None, settings: Settings | None = None) -> int:
    """`llm` and `settings` replace the configured ones (tests); `ask` uses them."""
    args = _parser(prog).parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # source text may not fit the console encoding
        sys.stdout.reconfigure(errors="replace")
    if args.command == "build":
        forwarded = (["--spec", str(args.spec)] if args.spec else []) + (
            ["--output-root", str(args.output_root)] if args.output_root else []) + (
            ["--allow-dirty"] if args.allow_dirty else [])
        return corpus_build.main(forwarded)
    if args.command == "ask":
        try:
            settings = settings or load_settings()
            llm = llm or _configured_llm(settings)
        except (ConfigError, LLMConfigError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
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
    if args.command == "ask":
        return _ask(args, explorer, llm, settings)
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


# --- ask ---------------------------------------------------------------------------------------


def _configured_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "mock":
        raise LLMConfigError(MOCK_PROVIDER_MESSAGE)
    return make_llm(settings)


def _ask(args: argparse.Namespace, explorer: ProvisionExplorer, llm: LLMClient,
         settings: Settings) -> int:
    try:
        result = answer_question(args.question, llm, explorer, settings=settings)
    except (QueryAnalysisError, LLMConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except LLMTransportError as exc:
        print(f"error: the LLM provider request failed: {exc}", file=sys.stderr)
        return 3
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) if args.json
          else render_answer(result))
    return 0


def _source_line(ref: SourceReference) -> str:
    title = f" {ref.title}" if ref.title else ""
    pages = (f"page {ref.page_start}" if ref.page_start == ref.page_end
             else f"pages {ref.page_start}-{ref.page_end}")
    extent = "" if ref.whole_provision else (
        f", point {ref.point} only" if ref.point else ", excerpt")
    return f"[{ref.evidence_id}] {ref.instrument_id} {ref.heading}{title} ({pages}{extent})"


def render_answer(result: AnswerResult) -> str:
    """The result as text: outcome first, then the answer, its sources and its limits."""
    outcome = result.outcome.value.replace("_", " ").upper()
    lines = [f"question: {result.question}"]
    if result.outcome == Outcome.ABSTAIN:
        lines += [f"outcome: {outcome} ({result.abstention_reason})",
                  f"  {result.abstention_detail}"]
    else:
        lines.append(f"outcome: {outcome}")
    lines.append("Experimental prototype. Not legal advice.")

    if result.question_references:
        lines += ["", "legal references in the question (only resolved ones are looked up):"]
        lines += [f"  «{r.reference.raw_text}» {r.status.value}: {_resolution_text(r)}"
                  for r in result.question_references]

    analysis = result.analysis
    if analysis is not None:
        lines += ["", "issues found by the query analysis (questions written by the model, not "
                  f"answers; {analysis.provenance.prompt_version}):"]
        lines += [f"  {issue.id}  {issue.question}" for issue in analysis.issues]
        if analysis.search_queries_it:
            lines.append("  search queries: " + "; ".join(analysis.search_queries_it))

    if result.claims:
        checked = ("support was assessed by a model, which is not legal validation"
                   if result.verification else "the claims themselves are not verified")
        lines += ["", "answer (each claim with its quotations; quotations are checked against "
                  f"the evidence, {checked}):"]
        for claim in result.claims:
            kind = claim.kind.replace("_", " ")
            support = ("" if claim.verification == VerificationStatus.NOT_VERIFIED
                       else f"; support: {claim.verification.value.lower().replace('_', ' ')}")
            lines.append(f"  {claim.claim_id} [{', '.join(claim.issue_ids)}] ({kind}{support}) "
                         f"{claim.text}")
            lines += [f"      {quote.evidence_id}: «{' '.join(quote.text.split())}»"
                      for quote in claim.quotes]
        lines += ["", "citations (citable provisions):"]
        for ref in result.citations:
            lines.append(f"  {_source_line(ref)}")
            lines.append(f"      {ref.provision_id}; legal validity {ref.legal_validity}")
            if ref.qualifications:
                lines.append(f"      qualifications: {', '.join(ref.qualifications)}")

    if result.unanswered_issues:
        lines += ["", "unanswered issues:"]
        lines += [f"  {u.issue_id}  {u.reason}" for u in result.unanswered_issues]
    if result.rejected_claims:
        lines += ["", f"removed by validation: {len(result.rejected_claims)} claim(s), not "
                  "part of the answer:"]
        lines += [f"  - {', '.join(r.reasons)}" for r in result.rejected_claims]
    if result.non_authoritative:
        lines += ["", "non-authoritative references (NOT citations: not eligible to be cited; "
                  "for inspection only):"]
        for ref in result.non_authoritative:
            why = ", ".join(ref.reasons) or "not primary"
            lines.append(f"  {_source_line(ref)}; tier {ref.tier}: {why}")
            lines.append(f"      inspect: python -m src.cli lookup {ref.instrument_id} "
                         f"{ref.label}")
    if result.model_notes:
        lines += ["", MODEL_NOTES_LABEL,
                  "  (written by the model; checked only for references to provisions outside "
                  "the evidence)"]
        lines += [f"  - {note}" for note in result.model_notes]

    lines += ["", "qualifications:"]
    lines += [f"  - {q}" for q in result.qualifications]
    preflight = result.preflight
    corpus_lines = []  # one blank line before whichever of the two comes first
    if preflight is not None:
        tiers = ", ".join(f"{count} {tier}" for tier, count in preflight.article_tiers)
        corpus_lines.append(f"corpus preflight: build {preflight.build_id}; articles: {tiers}; "
                            f"{preflight.citable_articles} citable")
    if result.evidence is not None:
        ev = result.evidence
        corpus_lines.append(f"evidence: build {ev.build_id}; {len(ev.items)} items "
                            f"({len(ev.citable_items)} citable); about {ev.total_tokens} tokens")
    if corpus_lines:
        lines += ["", *corpus_lines]
    if result.warnings:
        lines.append("warnings: " + "; ".join(result.warnings))
    if preflight is not None and not preflight.passed:
        lines.append("models: none called (no citable article in the corpus)")
        return "\n".join(lines)
    models = []
    if analysis is not None:
        models.append(_model_line("analysis", analysis.provenance))
    models.append(_model_line("generation", result.generation) if result.generation
                  else "generation: not run")
    if result.verification is not None:
        models.append(_model_line("support check", result.verification))
    lines.append("models: " + "; ".join(models))
    return "\n".join(lines)


def _provision_name(provision_id: str) -> str:
    """'eu-reg-2016-679@…/body/article:33' -> 'eu-reg-2016-679 art. 33'."""
    return f"{provision_id.split('@', 1)[0]} art. {provision_id.rsplit(':', 1)[-1]}"


def _resolution_text(resolution: Any) -> str:
    ref = resolution.reference
    if resolution.provision_id:
        how = f" (act named: {ref.instrument_text})" if ref.instrument_text else (
            f" (by {ref.basis.value})")
        text = _provision_name(resolution.provision_id) + how
        return text if resolution.reason == "found" else f"{text}; {resolution.explanation}"
    if resolution.candidates:
        names = ", ".join(_provision_name(c) for c in resolution.candidates)
        return f"{resolution.explanation}. Candidates, not looked up: {names}"
    return resolution.explanation


def _model_line(task: str, provenance: Any) -> str:
    served = ("" if provenance.served_by == provenance.model and not provenance.fallback_used
              else f", served by {provenance.served_by} (fallback)")
    return (f"{task} {provenance.provider}/{provenance.model}{served}, "
            f"{provenance.attempts} attempt(s)")


if __name__ == "__main__":
    sys.exit(main())
