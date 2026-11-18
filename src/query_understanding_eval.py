"""Dev-split experiment: does the query understanding layer help the BM25 article search?

    python -m src.query_understanding_eval [--strategies A,B,C,D] [--output FILE]
    python -m src.query_understanding_eval --check | --smoke

--check validates the configuration and prints what a run would do (model, prompt, cached
readings, requests needed) without sending any request. Exit status: 0 done; 1 nothing scored,
or some readings failed (the report is written and lists them); 2 error, no report written.
A wrong key, a forbidden or rejected request or an unknown model is an error (FATAL_ERRORS),
not a per-question failure.

--smoke sends exactly one short test request to the configured model (no retry, no fallback
model, no benchmark question) and reports success, authentication or access failure, an
unknown model, a timeout or another API error. Exit status: 0 success; 1 the request failed
or the reply was not the expected text; 2 configuration error, no request sent. It never
falls back to the mock provider, and it does not run the experiment.

Strategies, all through ProvisionExplorer.search (BM25, chunk depth 20), several queries fused
by query_fusion (article-level RRF, k = 60):

    A  the original question                       baseline; no model call
    B  the legal restatement only                  query_understanding
    C  original + legal restatement
    D  original + legal + semantic restatements

E, the original question through hybrid retrieval (dense + BM25), is not run: scoring it per
article needs the build's chunk-to-article links, which ProvisionExplorer keeps private (see
NOT_RUN). B-D need a model; without one (LLM_PROVIDER=mock) they are listed as not run.

References and controls, with no model call:
- ref-technical, ref-natural: the benchmark's handwritten queries of each scenario, interleaved
  by provision_eval.rank_articles, as the frozen evaluator ranks them (dev only);
- ctl-technical, ctl-natural: the same queries RRF-fused instead of interleaved, which
  separates the effect of the fusion method from the effect of adding the original;
- ctl-original+*: the original question RRF-fused with those handwritten queries, as
  stand-ins for restatements. They test the fusion, not the layer, and the queries were
  written with the corpus in view, so they flatter it.
A-D use the question text, which both scenarios share, so they have no per-scenario variant;
the per-scenario rows are the references and controls.

Only dev questions are read: test questions are never searched, sent to a model or scored
(they stay held out). The benchmark files are read, never written. Judgments were pooled
from the handwritten queries, not from the question text or from restatements, so articles
these strategies find may be unjudged; they count as not relevant, and each strategy reports
how many of its top 10 are unjudged.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Mapping, Sequence
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

from src.config import PROJECT_ROOT, ConfigError, Settings, load_settings
from src.corpus_identity import CodeVersionError, detect_code_version
from src.hybrid_retrieval import DEFAULT_RRF_K
from src.llm import (
    LLMAuthenticationError,
    LLMClient,
    LLMConfigError,
    LLMError,
    LLMOutputError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMRequestError,
    LLMTimeoutError,
    LLMTransportError,
    make_llm,
)
from src.provision_eval import (
    DEFAULT_BENCHMARK,
    DEFAULT_CHUNK_DEPTH,
    METRICS,
    RELEVANT_GRADE,
    SHOWN,
    Benchmark,
    Question,
    load_benchmark,
    rank_articles,
    resolve_judgments,
)
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.provisions import ProvisionError
from src.query_fusion import FusedSearch, QueryVariant, search_variants
from src.query_understanding import (
    PROMPT_VERSION,
    TASK,
    QueryUnderstanding,
    QueryUnderstandingError,
    UnderstandingCache,
    generation_settings,
    prompt_sha256,
    readings_summary,
    understand,
)
from src.retrieval_eval import EvaluationDataError

REPORT = "query-understanding-experiment/1"
SPLIT = "dev"  # the only split read; "test" stays held out
LABEL = ("DEV SPLIT ONLY. Ranking quality of article search strategies against the legal-v2 "
         "judgments (mostly unreviewed candidates). Retrieval quality, not legal correctness.")

STRATEGIES: dict[str, tuple[str, tuple[str, ...]]] = {
    "A": ("original question (baseline)", ("original",)),
    "B": ("legal restatement only", ("legal",)),
    "C": ("original + legal restatement", ("original", "legal")),
    "D": ("original + legal + semantic restatements", ("original", "legal", "semantic")),
}
NEEDS_MODEL = frozenset({"B", "C", "D"})
# Errors that say the model setup is wrong, not one question: they stop the run.
FATAL_ERRORS = (LLMConfigError, LLMAuthenticationError, LLMRequestError)
NOT_RUN = {
    "E": ("not run: hybrid retrieval (dense + BM25) can be scored per article only through the "
          "build's chunk-to-article links, which ProvisionExplorer keeps private (_by_doc). "
          "Running it needs a public read-only accessor on ProvisionExplorer, or a search that "
          "takes a retriever; neither exists, and this experiment does not reach around them."),
}
# name -> (description, merge, query kinds)
CONTROLS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "ref-technical": ("handwritten technical queries, interleaved (frozen evaluator)",
                      "interleave", ("technical",)),
    "ref-natural": ("handwritten natural queries, interleaved (frozen evaluator)",
                    "interleave", ("natural",)),
    "ctl-technical": ("handwritten technical queries, RRF (the fusion alone)",
                      "rrf", ("technical",)),
    "ctl-natural": ("handwritten natural queries, RRF (the fusion alone)",
                    "rrf", ("natural",)),
    "ctl-original+technical": ("original + handwritten technical queries, RRF",
                               "rrf", ("original", "technical")),
    "ctl-original+natural": ("original + handwritten natural queries, RRF",
                             "rrf", ("original", "natural")),
    "ctl-original+technical+natural": ("original + both handwritten query sets, RRF",
                                       "rrf", ("original", "technical", "natural")),
}


def dev_questions(benchmark: Benchmark) -> tuple[Question, ...]:
    return tuple(q for q in benchmark.questions if q.split == SPLIT)


def read_questions(questions: Sequence[Question], llm: LLMClient, *,
                   cache: UnderstandingCache | None = None) -> dict[str, dict[str, Any]]:
    """query_id -> {"status": "ok", "reading": QueryUnderstanding} or {"status": "failed",
    "error": ...}.

    A failure of one question (timeout, rate limit, connection, refusal, malformed or invalid
    reply) is recorded, not raised: that question falls back to the original query, and the
    report lists it. A configuration failure (FATAL_ERRORS: a rejected key, a forbidden or
    malformed request, an unknown model) would fail every question alike, so it is raised and
    the run stops before any report is written."""
    out: dict[str, dict[str, Any]] = {}
    for q in questions:
        if q.split != SPLIT:
            raise ValueError(f"{q.query_id} is a {q.split} question; only {SPLIT} is read")
        try:
            out[q.query_id] = {"status": "ok", "reading": understand(q.question, llm,
                                                                    cache=cache)}
        except FATAL_ERRORS:
            raise
        except LLMError as exc:
            out[q.query_id] = {"status": "failed",
                               "error": {"type": type(exc).__name__, "message": str(exc)}}
    return out


def evaluate_strategies(questions: Sequence[Question], grades: Mapping[str, Mapping[str, int]],
                        explorer: Any, *, strategies: Sequence[str],
                        readings: Mapping[str, Mapping[str, Any]] | None = None,
                        controls: Sequence[str] = tuple(CONTROLS),
                        chunk_depth: int = DEFAULT_CHUNK_DEPTH,
                        rrf_k: int = DEFAULT_RRF_K) -> dict[str, Any]:
    """Score each strategy and control on `questions` (dev only). `explorer` needs `search`
    and `store.get` (ProvisionExplorer, or a stand-in in tests)."""
    for q in questions:
        if q.split != SPLIT:
            raise ValueError(f"{q.query_id} is a {q.split} question; only {SPLIT} is scored")
    unknown = [s for s in strategies if s not in STRATEGIES]
    if unknown:
        raise ValueError(f"unknown strategies {unknown}; use {list(STRATEGIES)}")
    unknown = [c for c in controls if c not in CONTROLS]
    if unknown:
        raise ValueError(f"unknown controls {unknown}; use {list(CONTROLS)}")
    readings = readings or {}
    results: dict[str, Any] = {}
    not_run: dict[str, str] = {}
    for name in strategies:
        if name in NEEDS_MODEL and not readings:
            not_run[name] = "not run: no model reading (LLM_PROVIDER=mock, or no model given)"
            continue
        description, kinds = STRATEGIES[name]
        results[name] = _score(description, "rrf", kinds, questions, grades, explorer,
                               readings, chunk_depth, rrf_k)
    controls_out = {name: _score(CONTROLS[name][0], CONTROLS[name][1], CONTROLS[name][2],
                                 questions, grades, explorer, readings, chunk_depth, rrf_k)
                    for name in controls}
    checks = {}
    if "A" in results:
        checks["A_equals_rank_articles"] = all(
            _ids(rank_articles(explorer, (q.question,), chunk_depth)[0])
            == [r["provision_id"] for r in entry["full_ranking"]]
            for q, entry in zip(questions, results["A"]["per_query"]))
    for block in (*results.values(), *controls_out.values()):
        for entry in block["per_query"]:
            del entry["full_ranking"]
    return {
        "strategies": results,
        "not_run": {**not_run, **NOT_RUN},
        "controls": controls_out,
        "comparison_with_A": _compare(results, controls_out),
        "checks": checks,
    }


def _score(description: str, merge: str, kinds: Sequence[str], questions: Sequence[Question],
           grades: Mapping[str, Mapping[str, int]], explorer: Any,
           readings: Mapping[str, Mapping[str, Any]], chunk_depth: int,
           rrf_k: int) -> dict[str, Any]:
    per_query = []
    for q in questions:
        judged = grades.get(q.query_id, {})
        relevant = sum(1 for g in judged.values() if g >= RELEVANT_GRADE)
        reading = readings.get(q.query_id, {}).get("reading")
        entry: dict[str, Any] = {"query_id": q.query_id, "category": q.category,
                                 "expected_outcome": q.expected_outcome,
                                 "judged_articles": len(judged), "relevant_articles": relevant}
        if merge == "interleave":
            queries = [text for kind in kinds for text in q.queries(kind)]
            ranking, _ = rank_articles(explorer, queries, chunk_depth)
            entry["variants"] = [{"kind": kind, "query": text}
                                 for kind in kinds for text in q.queries(kind)]
            entry["fallback"] = None
            full = [{"provision_id": r.provision_id, "label": r.label, "score": None,
                     "found_by": [{"query": r.query, "chunk_rank": r.chunk_rank}]}
                    for r in ranking]
        else:
            variants, fallback = _variants(kinds, q, reading,
                                           readings.get(q.query_id, {}).get("status"))
            fused: FusedSearch = search_variants(explorer, variants, chunk_depth=chunk_depth,
                                                 rrf_k=rrf_k)
            entry["variants"] = fused.summary()["variants"]
            entry["dropped_variants"] = fused.summary()["dropped_variants"]
            entry["fallback"] = fallback
            full = [{"provision_id": a.provision_id, "label": a.label, "score": a.score,
                     "found_by": [{"kind": c.kind, "variant": c.variant,
                                   "chunk_rank": c.chunk_rank} for c in a.contributions]}
                    for a in fused.articles]
        ranked = [r["provision_id"] for r in full]
        entry["ranking_length"] = len(ranked)
        entry["ranking"] = [{"position": n, **r, "grade": judged.get(r["provision_id"])}
                            for n, r in enumerate(full[:SHOWN], 1)]
        entry["unjudged_in_top10"] = sum(1 for pid in ranked[:10] if pid not in judged)
        entry["full_ranking"] = full
        if relevant == 0:
            entry["skipped"] = ("no judgment with grade >= 1" if judged
                                else "no judgments for this question")
        else:
            entry["metrics"] = {name: metric(ranked, judged, k) for name, metric, k in METRICS}
        per_query.append(entry)
    scored = [e for e in per_query if "metrics" in e]
    return {
        "description": description,
        "merge": merge,
        "query_kinds": list(kinds),
        "means": mean_metrics(scored),
        "questions_scored": len(scored),
        "questions_skipped": [e["query_id"] for e in per_query if "skipped" in e],
        "unjudged_in_top10": sum(e["unjudged_in_top10"] for e in scored),
        "fallbacks": [e["query_id"] for e in per_query if e.get("fallback")],
        "per_query": per_query,
    }


def _variants(kinds: Sequence[str], q: Question, reading: QueryUnderstanding | None,
              status: str | None) -> tuple[list[QueryVariant], str | None]:
    variants: list[QueryVariant] = []
    missing = False
    for kind in kinds:
        if kind == "original":
            variants.append(QueryVariant("original", q.question))
        elif kind in ("legal", "semantic"):
            if reading is None:
                missing = True
            else:
                variants.append(QueryVariant(kind, reading.legal_query if kind == "legal"
                                             else reading.semantic_query))
        else:  # a benchmark scenario's handwritten queries
            variants.extend(QueryVariant(kind, text) for text in q.queries(kind))
    fallback = None
    if missing:
        fallback = f"no reading ({status or 'not generated'}): restatements left out"
    if not variants:
        variants = [QueryVariant("original", q.question)]
        fallback = f"no reading ({status or 'not generated'}): the original query alone"
    return variants, fallback


def mean_metrics(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    if not entries:
        return None
    return {"questions": len(entries),
            **{name: sum(e["metrics"][name] for e in entries) / len(entries)
               for name, _, _ in METRICS}}


def _compare(results: Mapping[str, Any], controls: Mapping[str, Any]) -> dict[str, Any]:
    """Each strategy and control against A: mean differences, and per question nDCG@10."""
    if "A" not in results or results["A"]["means"] is None:
        return {}
    base = results["A"]
    base_ndcg = {e["query_id"]: e["metrics"]["ndcg@10"] for e in base["per_query"]
                 if "metrics" in e}
    out = {}
    for name, block in (*results.items(), *controls.items()):
        if name == "A" or block["means"] is None:
            continue
        deltas = {metric: block["means"][metric] - base["means"][metric]
                  for metric, _, _ in METRICS}
        better = worse = same = 0
        for e in block["per_query"]:
            if "metrics" not in e or e["query_id"] not in base_ndcg:
                continue
            diff = e["metrics"]["ndcg@10"] - base_ndcg[e["query_id"]]
            if abs(diff) < 1e-12:
                same += 1
            elif diff > 0:
                better += 1
            else:
                worse += 1
        out[name] = {"mean_difference": deltas,
                     "ndcg@10_per_question": {"better": better, "worse": worse, "same": same}}
    return out


def _ids(ranking: Sequence[Any]) -> list[str]:
    return [r.provision_id for r in ranking]


# --- Run ---------------------------------------------------------------------------------------


def run(benchmark_dir: Path = DEFAULT_BENCHMARK, build_dir: Path | None = None, *,
        strategies: Sequence[str] = tuple(STRATEGIES), llm: LLMClient | None = None,
        cache: UnderstandingCache | None = None, chunk_depth: int = DEFAULT_CHUNK_DEPTH,
        controls: Sequence[str] = tuple(CONTROLS)) -> dict[str, Any]:
    """Load the benchmark and the build, read the dev questions with `llm` if a strategy needs
    it, and score every strategy and control on the dev split."""
    benchmark = load_benchmark(benchmark_dir)
    questions = dev_questions(benchmark)
    explorer = ProvisionExplorer.open(build_dir or find_recorded_build())
    grades = resolve_judgments(benchmark.judgments, explorer)
    wanted_model = [s for s in strategies if s in NEEDS_MODEL]
    readings: dict[str, dict[str, Any]] = {}
    if wanted_model and llm is not None:
        readings = read_questions(questions, llm, cache=cache)
    results = evaluate_strategies(questions, grades, explorer, strategies=strategies,
                                  readings=readings, controls=controls,
                                  chunk_depth=chunk_depth)
    identity = explorer.identity()
    ok = [r["reading"] for r in readings.values() if r["status"] == "ok"]
    return {
        "report": REPORT,
        "label": LABEL,
        "split": SPLIT,
        "held_out": "test questions: not searched, not sent to a model, not scored",
        "benchmark": {"benchmark_id": benchmark.benchmark_id, "version": benchmark.version,
                      "schema_version": benchmark.schema_version, "files": benchmark.files,
                      "dev_questions": len(questions)},
        "corpus": {"build_id": identity["build_id"], "corpus_sha256": identity["corpus_sha256"],
                   "registry_sha256": explorer.store.registry.sha256},
        "code": _code(),
        "retrieval": {"function": "src.provision_explorer.ProvisionExplorer.search",
                      "method": "bm25", "chunk_depth": chunk_depth, "fusion": "rrf",
                      "rrf_k": DEFAULT_RRF_K,
                      "rrf_rank": "the article's best chunk rank in each query's search",
                      "ties": "the order provision_eval.rank_articles gives the same queries"},
        "experiment": {"strategies_requested": list(strategies), "controls": list(controls),
                       "split": SPLIT, "fatal_errors": [e.__name__ for e in FATAL_ERRORS],
                       "on_other_failures": "the question falls back to the original query "
                                            "and is listed in understanding.failures"},
        "understanding": _understanding_record(llm, cache, wanted_model, readings, ok),
        "representations": [
            {"query_id": qid, "status": r["status"],
             **({"understanding": r["reading"].to_dict()} if r["status"] == "ok"
                else {"error": r["error"]})}
            for qid, r in readings.items()],
        "metrics": {"names": [name for name, _, _ in METRICS],
                    "relevant": f"grade >= {RELEVANT_GRADE}", "unjudged": "not relevant"},
        **results,
    }


def _understanding_record(llm, cache, wanted, readings, ok) -> dict[str, Any]:
    if not wanted:
        return {"status": "not requested"}
    if llm is None:
        return {"status": "not run: no model configured (LLM_PROVIDER=mock)"}
    provider = getattr(llm, "provider", "")
    generated = [r for r in ok if r.provenance.cache != "hit"]
    return {"status": "run", **_model_record(llm),
            "cache": str(cache.directory) if cache is not None else "disabled",
            "failures": [qid for qid, r in readings.items() if r["status"] == "failed"],
            "generated_this_run": len(generated),
            "requests_for_generated": sum(r.provenance.attempts for r in generated),
            "real_model_calls_this_run": provider != "mock" and bool(
                generated or any(r["status"] == "failed" for r in readings.values())),
            **readings_summary(ok)}


def model_source(provider: str) -> str:
    """Where readings come from, in words a report reader cannot mistake."""
    if provider == "mock":
        return "mock provider: scripted replies, not model output"
    if provider == "anthropic":
        return "Anthropic API: real model calls"
    return f"{provider}: real model calls"


def _model_record(llm: LLMClient) -> dict[str, Any]:
    """Provider, model, prompt and client settings. Never a credential: LLMClient exposes none,
    and only the attributes read by generation_settings are recorded."""
    provider = getattr(llm, "provider", "")
    record = {"task": TASK, "prompt_version": PROMPT_VERSION, "prompt_sha256": prompt_sha256(),
              "provider": provider, "model": getattr(llm, "model", ""),
              "real_model": provider != "mock", "source": model_source(provider),
              "generation": generation_settings(llm)}
    if provider == "anthropic":
        try:
            record["sdk"] = {"anthropic": importlib_metadata.version("anthropic")}
        except importlib_metadata.PackageNotFoundError:
            record["sdk"] = {"anthropic": "not installed"}
    return record


def preflight(benchmark_dir: Path, llm: LLMClient | None, cache: UnderstandingCache | None,
              strategies: Sequence[str]) -> dict[str, Any]:
    """What a run would do, without sending any request or opening the build: the benchmark
    files and their hashes, the model setup, and how many readings are cached."""
    benchmark = load_benchmark(benchmark_dir)
    questions = dev_questions(benchmark)
    wanted = [s for s in strategies if s in NEEDS_MODEL]
    out: dict[str, Any] = {
        "check": "preflight only: no request was sent",
        "benchmark": {"benchmark_id": benchmark.benchmark_id, "version": benchmark.version,
                      "files": benchmark.files, "dev_questions": len(questions),
                      "test_questions": "held out: not sent to a model, searched or scored"},
        "build": find_recorded_build().name,
        "strategies": list(strategies),
    }
    if not wanted:
        out["understanding"] = {"status": "not requested"}
    elif llm is None:
        out["understanding"] = {"status": "would not run: no model configured "
                                          "(LLM_PROVIDER=mock); B-D would be listed as not run"}
    else:
        provider, model = getattr(llm, "provider", ""), getattr(llm, "model", "")
        cached = sum(1 for q in questions
                     if cache is not None and cache.path(q.question, provider, model).is_file())
        attempts = getattr(llm, "max_attempts", None)
        out["understanding"] = {
            "status": "would run", **_model_record(llm),
            "cache": str(cache.directory) if cache is not None else "disabled",
            "cached_readings_found": cached,
            "readings_to_generate": len(questions) - cached,
            "max_requests": (len(questions) - cached) * attempts if attempts else None,
        }
    return out


def _code() -> dict[str, Any]:
    try:
        return {"available": True, **detect_code_version(PROJECT_ROOT).to_record()}
    except CodeVersionError as exc:
        return {"available": False, "reason": str(exc)}


def format_summary(report: Mapping[str, Any]) -> str:
    names = report["metrics"]["names"]
    lines = ["QUERY UNDERSTANDING EXPERIMENT (dev split only)", report["label"],
             f"benchmark: {report['benchmark']['benchmark_id']} "
             f"v{report['benchmark']['version']}; {report['benchmark']['dev_questions']} dev "
             f"questions; test held out",
             f"build: {report['corpus']['build_id']}",
             f"understanding: {report['understanding']['status']}"]
    u = report["understanding"]
    if u["status"] == "run":
        lines.append(f"  readings from: {u['source'].upper()}")
        lines.append(f"  model {u['provider']}/{u['model']}, prompt {u['prompt_version']}, "
                     f"cache {u['cache']}; generated now {u['generated_this_run']}, from cache "
                     f"{u['from_cache']}, failed {len(u['failures'])}"
                     + (f" ({', '.join(u['failures'])}: original query only)"
                        if u["failures"] else ""))
    lines += ["", f"{'':<32}{'n':>4}" + "".join(f"{n:>11}" for n in names) + f"{'unjudged':>10}"]

    def row(name: str, block: Mapping[str, Any]) -> None:
        means = block["means"]
        if means is None:
            lines.append(f"{name:<32}   - nothing scored")
            return
        lines.append(f"{name:<32}{means['questions']:>4}"
                     + "".join(f"{means[n]:>11.3f}" for n in names)
                     + f"{block['unjudged_in_top10']:>10}")

    for name, block in report["strategies"].items():
        row(name, block)
    for name, reason in report["not_run"].items():
        lines.append(f"{name:<32}   {reason[:90]}")
    lines.append("")
    for name, block in report["controls"].items():
        row(name, block)
    if report["comparison_with_A"]:
        lines += ["", "difference from A (mean; nDCG@10 per question better/worse/same):"]
        for name, c in report["comparison_with_A"].items():
            d, p = c["mean_difference"], c["ndcg@10_per_question"]
            lines.append(f"  {name:<30}" + "".join(f"{d[n]:>+11.3f}" for n in names)
                         + f"   {p['better']}/{p['worse']}/{p['same']}")
    if report["checks"]:
        lines += ["", "checks: " + ", ".join(f"{k}={v}" for k, v in report["checks"].items())]
    return "\n".join(lines)


# --- Smoke test --------------------------------------------------------------------------------

SMOKE_TASK = "smoke_test"
SMOKE_TOKEN = "ANTHROPIC_CONNECTION_OK"
SMOKE_SYSTEM = "This is a connectivity test of an application. Follow the instruction exactly."
SMOKE_USER = f'Set the field "reply" to exactly {SMOKE_TOKEN} and nothing else.'
SMOKE_SCHEMA: dict[str, Any] = {
    "type": "object", "additionalProperties": False, "required": ["reply"],
    "properties": {"reply": {"type": "string"}},
}
# (outcome, hint) per error class; the first match wins, so subclasses come first.
_SMOKE_FAILURES: tuple[tuple[type[LLMError], str, str], ...] = (
    (LLMAuthenticationError, "authentication_failed",
     "check ANTHROPIC_API_KEY: it must be a Claude Console API key"),
    (LLMRequestError, "request_rejected", "the API rejected the request; see the message"),
    (LLMTimeoutError, "timeout", "no response within LLM_TIMEOUT_SECONDS"),
    (LLMRateLimitError, "rate_limited", "a rate or spend limit of the account was reached"),
    (LLMTransportError, "api_error", "a connection failure or a server error"),
    (LLMRefusalError, "refused", "the model declined the request"),
    (LLMOutputError, "invalid_response",
     "the reply was malformed, cut off or did not match the schema"),
)


def smoke_settings(settings: Settings) -> Settings:
    """The configured settings with one attempt (no schema retry) and no fallback model, so
    the smoke test is one request to the configured model. The SDK itself never retries."""
    return dataclasses.replace(settings, max_generation_retries=0, llm_refusal_fallback=False)


def smoke_test(llm: LLMClient) -> dict[str, Any]:
    """Send one short request through `llm` and classify the outcome. No benchmark question,
    corpus text or reading is involved. LLM errors are returned as outcomes, not raised."""
    attempts = getattr(llm, "max_attempts", None)
    if attempts != 1:
        raise ValueError(f"the smoke test needs a client that sends one attempt (got {attempts})")
    record = {"provider": getattr(llm, "provider", ""), "model": getattr(llm, "model", ""),
              "requests_allowed": 1}
    try:
        result = llm.complete_json(SMOKE_TASK, SMOKE_SYSTEM, SMOKE_USER, SMOKE_SCHEMA)
    except LLMError as exc:
        outcome, hint = "llm_error", ""
        for cls, name, text in _SMOKE_FAILURES:
            if isinstance(exc, cls):
                outcome, hint = name, text
                break
        status = getattr(exc, "status_code", None)
        if outcome == "authentication_failed" and status == 403:
            outcome, hint = "access_denied", "the key may not make this request or use this model"
        elif outcome == "request_rejected" and status == 404:
            outcome, hint = "model_not_accessible", ("check LLM_MODEL: the model ID is unknown "
                                                     "or not available to this key")
        elif outcome == "api_error" and isinstance(status, int) and 300 <= status < 400:
            outcome, hint = "redirect_refused", ("the request was not sent again; check "
                                                 "ANTHROPIC_BASE_URL and any proxy settings")
        return {**record, "ok": False, "outcome": outcome, "hint": hint,
                "error": type(exc).__name__, "message": str(exc), "status_code": status,
                "request_id": getattr(exc, "request_id", None)}
    reply = result.data["reply"].strip()
    ok = reply == SMOKE_TOKEN
    return {**record, "ok": ok, "outcome": "success" if ok else "unexpected_reply",
            "served_by": result.served_by, "attempts": result.attempts,
            "request_ids": list(result.request_ids), "reply": reply[:200]}


def format_smoke(result: Mapping[str, Any]) -> str:
    lines = ["SMOKE TEST: one request, no retry; no benchmark question is sent",
             f"provider/model: {result['provider']}/{result['model']}"]
    if result["ok"]:
        lines += ["result: SUCCESS. The key was accepted, the model answered, and the reply "
                  f"was valid JSON with the expected text ({SMOKE_TOKEN}).",
                  f"served by: {result['served_by']}; request id: "
                  f"{', '.join(result['request_ids']) or 'none'}"]
    elif result["outcome"] == "unexpected_reply":
        lines += ["result: FAILED (unexpected_reply). The key was accepted and the model "
                  "answered with valid JSON, but not with the expected text.",
                  f"reply: {result['reply']!r}; served by: {result['served_by']}"]
    else:
        lines += [f"result: FAILED ({result['outcome']}): {result['message']}",
                  f"hint: {result['hint']}" if result["hint"] else "",
                  f"HTTP status: {result['status_code']}; request id: {result['request_id']}"]
    return "\n".join(line for line in lines if line)


def _run_smoke(as_json: bool) -> int:
    """--smoke: 0 success; 1 the request failed or the reply was wrong; 2 configuration error,
    no request sent. It never falls back to the mock provider."""
    try:
        settings = load_settings()
        if settings.llm_provider == "mock":
            print("error: --smoke needs a real provider (LLM_PROVIDER=anthropic); with "
                  "LLM_PROVIDER=mock there is nothing to test.", file=sys.stderr)
            print("no request was sent", file=sys.stderr)
            return 2
        llm = make_llm(smoke_settings(settings))  # builds the client; sends nothing
        if getattr(llm, "provider", "mock") == "mock":
            raise ValueError("the configured client is the mock provider")
        result = smoke_test(llm)
    except (ConfigError, LLMError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("no request was sent", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2) if as_json else format_smoke(result))
    return 0 if result["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.query_understanding_eval",
        description="Compare article search strategies with and without the query "
                    "understanding layer, on the dev split of a benchmark (test held out).")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK,
                        help="benchmark directory (default: data/evaluation/legal-v2)")
    parser.add_argument("--build-dir", type=Path,
                        help="corpus build (default: the recorded build in data/processed/builds/)")
    parser.add_argument("--strategies", default=",".join(STRATEGIES),
                        help="comma-separated, from A,B,C,D (default: all; B-D need a model)")
    parser.add_argument("--no-cache", action="store_true",
                        help="do not read or write cached readings")
    parser.add_argument("--cache-dir", type=Path, default=None,
                        help="reading cache (default: data/processed/query_understanding)")
    parser.add_argument("--output", type=Path, help="write the full JSON report to this file")
    parser.add_argument("--json", action="store_true", help="print the JSON report, not a summary")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="preflight: check the configuration and show what a run would do, "
                           "without sending any request")
    mode.add_argument("--smoke", action="store_true",
                      help="send exactly one short test request to the configured model (no "
                           "retry, no benchmark question) and report the outcome; billed")
    args = parser.parse_args(argv)
    if args.smoke and args.output:
        parser.error("--smoke writes no report")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if args.smoke:
        return _run_smoke(args.json)
    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    try:
        llm = None
        if any(s in NEEDS_MODEL for s in strategies):
            settings = load_settings()
            if settings.llm_provider != "mock":
                llm = make_llm(settings)  # builds the client; sends nothing
        cache = None if args.no_cache else (UnderstandingCache(args.cache_dir) if args.cache_dir
                                            else UnderstandingCache())
        if args.check:
            print(json.dumps(preflight(args.benchmark, llm, cache, strategies),
                             ensure_ascii=False, indent=2))
            return 0
        report = run(args.benchmark, args.build_dir, strategies=strategies, llm=llm,
                     cache=cache)
    except (FileNotFoundError, ConfigError, EvaluationDataError, ExplorerError, ProvisionError,
            QueryUnderstandingError, LLMError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        if not args.check:
            print("no report was written", file=sys.stderr)
        return 2
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text if args.json else format_summary(report))
    failures = report["understanding"].get("failures") or []
    if failures:
        print(f"warning: {len(failures)} reading(s) failed ({', '.join(failures)}); those "
              "questions used the original query alone in B-D", file=sys.stderr)
        return 1
    return 0 if report["strategies"].get("A", {}).get("means") else 1


if __name__ == "__main__":
    sys.exit(main())
