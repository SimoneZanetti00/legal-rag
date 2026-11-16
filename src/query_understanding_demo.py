"""Demo: one question through the query understanding layer and the fused article search.

    python -m src.query_understanding_demo --scripted          offline, scripted reading
    python -m src.query_understanding_demo                     needs a configured model
    python -m src.query_understanding_demo --no-reformulation  the original question alone

It prints the original question, the structured reading, the queries searched, the articles
retrieved (with the queries that found each one), and for the top articles their source and
the exact article text found. It draws no conclusion and answers nothing: it shows what was
retrieved, with each article's eligibility tier and legal-validity status as the build records
them.

--scripted replaces the model with MockLLM and a reply written by hand for the default
question (SCRIPTED_REPLY). The reading is checked exactly like a model's, but it is not model
output, and the demo says so every time it runs. Without --scripted, the model comes from
LLM_PROVIDER, LLM_MODEL and ANTHROPIC_API_KEY; with LLM_PROVIDER=mock (the default) the demo
stops and says what to set.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.config import ConfigError, load_settings
from src.llm import LLMClient, LLMError, MockLLM, make_llm
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.query_fusion import FusedSearch, query_variants, search_variants
from src.query_understanding import (
    TASK,
    QueryUnderstanding,
    QueryUnderstandingError,
    UnderstandingCache,
    understand,
)

DEFAULT_QUESTION = "Can a company keep the personal data of a former employee?"
DEFAULT_TOP = 5
EXCERPT_CHARS = 320

SCRIPTED_LABEL = ("SCRIPTED MOCK REPLY: the reading below was written by hand for this demo, "
                  "not produced by a model. It shows how the layer checks and uses a reading, "
                  "not how well a model reads questions.")

# A stand-in for a model reply to DEFAULT_QUESTION (not model output). It passes the same
# checks as a model reply.
SCRIPTED_REPLY: dict[str, Any] = {
    "legal_query": ("conservazione dei dati personali di un ex dipendente da parte del "
                    "titolare del trattamento dopo la cessazione del rapporto di lavoro"),
    "semantic_query": "un'azienda può tenere i dati personali di un ex lavoratore",
    "legal_concepts": ["conservazione dei dati personali", "limitazione della conservazione",
                       "liceità del trattamento", "titolare del trattamento",
                       "trattamento dei dati nell'ambito del rapporto di lavoro"],
    "entities": [
        {"mention": "a company", "type": "organisation"},
        {"mention": "the personal data", "type": "personal_data"},
        {"mention": "a former employee", "type": "natural_person"},
    ],
    "relationships": [
        {"subject": "a company", "relation": "asks whether it may keep", "object":
         "the personal data", "evidence": "a company keep the personal data"},
        {"subject": "the personal data", "relation": "concern", "object": "a former employee",
         "evidence": "the personal data of a former employee"},
    ],
    "conditions": [
        {"condition": "the employment relationship has ended", "evidence": "former employee"},
    ],
    "ambiguities": [
        {"issue": "whether the company is the person's former employer",
         "interpretations": ["the company employed the person",
                             "another company holds the person's data"]},
        {"issue": "which data, and for what purpose they would be kept",
         "interpretations": ["data kept to comply with an obligation",
                             "data kept for another purpose of the company",
                             "no purpose stated: the question asks in general"]},
        {"issue": "whether the question asks if keeping is allowed at all, or for how long",
         "interpretations": ["whether any keeping is allowed", "for how long keeping is allowed"]},
    ],
    "clarification_needed": False,
}

NOTES = (
    "Retrieved text only. Nothing here answers the question or states a legal conclusion.",
    "An article may be cited only if its eligibility tier is 'primary'; the M1 review is not "
    "recorded, so no article of the real corpus is citable yet.",
    "The Privacy Code text is a user transcription, not an official text. Nothing here "
    "establishes that a provision is legally valid or in force.",
    "RRF scores rank; they are not probabilities or confidence.",
)


def scripted_llm() -> MockLLM:
    return MockLLM({TASK: [SCRIPTED_REPLY]}, model="scripted-demo")


def run_demo(question: str, explorer: ProvisionExplorer, llm: LLMClient | None, *,
             top: int = DEFAULT_TOP, semantic: bool = True,
             cache: UnderstandingCache | None = None, scripted: bool = False) -> dict[str, Any]:
    """Everything the demo shows, as data. `llm` None means no reformulation."""
    reading: QueryUnderstanding | None = None
    if llm is None:
        source = {"kind": "none", "note": "reformulation switched off: the original alone"}
    else:
        source = {"kind": "scripted" if scripted else "model",
                  "provider": getattr(llm, "provider", ""), "model": getattr(llm, "model", "")}
        if scripted:
            source["label"] = SCRIPTED_LABEL
        try:
            reading = understand(question, llm, cache=cache)
        except LLMError as exc:
            source["failure"] = {"type": type(exc).__name__, "message": str(exc),
                                 "fallback": "the original question alone"}
    fused = search_variants(explorer, query_variants(question, reading, semantic=semantic))
    return {
        "question": question,
        "reading_source": source,
        "understanding": reading.to_dict() if reading else None,
        "search": fused.summary(),
        "articles": [_article(fused, a, n) for n, a in enumerate(fused.articles[:top], 1)],
        "articles_found": len(fused.articles),
        "build": explorer.identity()["build_id"],
        "notes": list(NOTES),
    }


def _article(fused: FusedSearch, article, position: int) -> dict[str, Any]:
    best = min(article.contributions, key=lambda c: (c.chunk_rank, c.variant))
    search = fused.searches[best.variant - 1]
    entry = next(p for p in search["provisions"] if p["provision_id"] == article.provision_id)
    evidence = None
    for result in search["results"]:
        if result["rank"] != best.chunk_rank:
            continue
        for item in result["evidence"]:
            if item["provision_id"] == article.provision_id and item["pieces"]:
                piece = item["pieces"][0]
                evidence = {"query": fused.variants[best.variant - 1].kind,
                            "chunk_rank": result["rank"], "chunk_id": result["chunk_id"],
                            "source_path": result["source_path"],
                            "version_id": result["version_id"], "page": piece["page"],
                            "char_start": piece["char_start"], "char_end": piece["char_end"],
                            "text": piece["text"]}
                break
        if evidence:
            break
    return {
        "position": position,
        "provision_id": article.provision_id,
        "instrument_id": article.instrument_id,
        "label": article.label,
        "heading": entry["heading"],
        "title": entry["title"],
        "rrf_score": article.score,
        "found_by": [{"query": c.kind, "chunk_rank": c.chunk_rank} for c in article.contributions],
        "tier": entry["eligibility"]["tier"],
        "legal_validity": entry["legal_validity"],
        "structural_status": entry["structural_status"],
        "evidence": evidence,
    }


def format_demo(data: dict[str, Any]) -> str:
    lines = ["QUERY UNDERSTANDING DEMO: retrieval only, no answer", ""]
    lines.append(f"Original question (unchanged): {data['question']}")
    source = data["reading_source"]
    if source["kind"] == "scripted":
        lines += ["", "*** " + source["label"] + " ***"]
    elif source["kind"] == "model":
        lines.append(f"Reading by: {source['provider']}/{source['model']}")
    else:
        lines.append(f"Reading: {source['note']}")
    if "failure" in source:
        f = source["failure"]
        lines.append(f"Reading failed ({f['type']}: {f['message']}); searched with "
                     f"{f['fallback']}.")
    u = data["understanding"]
    if u:
        lines += ["", "Structured understanding",
                  f"  legal_query:    {u['legal_query']}",
                  f"  semantic_query: {u['semantic_query']}",
                  "  legal_concepts: " + "; ".join(u["legal_concepts"])]
        lines.append("  entities:       " + "; ".join(f"{e['mention']} ({e['type']})"
                                                     for e in u["entities"]))
        for r in u["relationships"]:
            lines.append(f"  relationship:   {r['subject']} -> {r['relation']} -> {r['object']}"
                         f"  [«{r['evidence']}»]")
        for c in u["conditions"]:
            lines.append(f"  condition:      {c['condition']}  [«{c['evidence']}»]")
        for a in u["ambiguities"]:
            lines.append(f"  ambiguity:      {a['issue']}")
            lines += [f"                    - {i}" for i in a["interpretations"]]
        lines.append(f"  clarification_needed: {u['clarification_needed']}")
        p = u["provenance"]
        lines.append(f"  provenance:     {p['task']} {p['prompt_version']}, {p['provider']}/"
                     f"{p['served_by']}, attempts {p['attempts']}, cache {p['cache']}")
    lines += ["", f"Queries searched (BM25, {data['search']['chunk_depth']} chunks each, RRF "
                  f"k={data['search']['rrf_k']})"]
    for n, v in enumerate(data["search"]["variants"], 1):
        lines.append(f"  {n}. [{v['kind']}] {v['query']}  ({v['articles']} articles)")
    for v in data["search"]["dropped_variants"]:
        lines.append(f"  -  [{v['kind']}] {v['query']}  (not searched: {v['reason']})")
    lines += ["", f"Retrieved articles (top {len(data['articles'])} of "
                  f"{data['articles_found']})"]
    for a in data["articles"]:
        found = ", ".join(f"{f['query']}@{f['chunk_rank']}" for f in a["found_by"])
        title = f" {a['title']}" if a["title"] else ""
        lines.append(f"  {a['position']}. {a['instrument_id']} {a['heading']}{title}")
        lines.append(f"     RRF {a['rrf_score']:.4f}; found by {found}; tier {a['tier']}; "
                     f"legal validity {a['legal_validity']}")
    lines += ["", "Sources and evidence (exact article text in the best chunk)"]
    for a in data["articles"]:
        e = a["evidence"]
        lines.append(f"  [{a['position']}] {a['instrument_id']} {a['heading']}")
        if e is None:
            lines.append("      no article text located")
            continue
        text = " ".join(e["text"].split())
        if len(text) > EXCERPT_CHARS:
            text = text[:EXCERPT_CHARS - 1] + "…"
        lines.append(f"      {e['source_path']}, page {e['page']}, chars {e['char_start']}-"
                     f"{e['char_end']} (chunk {e['chunk_id']}, {e['query']} query, rank "
                     f"{e['chunk_rank']})")
        lines.append(f"      «{text}»")
    lines += ["", "Notes"] + [f"  - {n}" for n in data["notes"]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.query_understanding_demo",
        description="Show the query understanding layer and the fused article search on one "
                    "question. Retrieval only: no answer is generated.")
    parser.add_argument("--question", default=DEFAULT_QUESTION,
                        help=f"the question (default: {DEFAULT_QUESTION!r})")
    parser.add_argument("--scripted", action="store_true",
                        help="use the hand-written reading of the default question instead of "
                             "a model (offline)")
    parser.add_argument("--no-reformulation", action="store_true",
                        help="search with the original question alone; no model call")
    parser.add_argument("--no-semantic", action="store_true",
                        help="leave the semantic restatement out of the search")
    parser.add_argument("--cache-dir", type=Path,
                        help="cache readings in this directory (default: no cache; the files "
                             "contain the question)")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP, help="articles shown")
    parser.add_argument("--build-dir", type=Path,
                        help="corpus build (default: the recorded build in data/processed/builds/)")
    parser.add_argument("--json", action="store_true", help="print JSON, not text")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if args.scripted and args.no_reformulation:
        parser.error("--scripted and --no-reformulation exclude each other")
    if args.scripted and args.question != DEFAULT_QUESTION:
        parser.error("--scripted has a reading for the default question only")
    try:
        llm: LLMClient | None = None
        if args.scripted:
            llm = scripted_llm()
        elif not args.no_reformulation:
            settings = load_settings()
            if settings.llm_provider == "mock":
                print("error: no model configured (LLM_PROVIDER=mock). Set LLM_PROVIDER="
                      "anthropic, LLM_MODEL and ANTHROPIC_API_KEY, or use --scripted or "
                      "--no-reformulation.", file=sys.stderr)
                return 2
            llm = make_llm(settings)
        explorer = ProvisionExplorer.open(args.build_dir or find_recorded_build())
        data = run_demo(args.question, explorer, llm, top=args.top,
                        semantic=not args.no_semantic,
                        cache=UnderstandingCache(args.cache_dir) if args.cache_dir else None,
                        scripted=args.scripted)
    except (ConfigError, ExplorerError, QueryUnderstandingError, LLMError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(data, ensure_ascii=False, indent=2) if args.json else format_demo(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
