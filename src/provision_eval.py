"""Provision-level retrieval evaluation (M4, phase P1): the BM25 search that `ask` uses, measured
at the level legal relevance is judged at, the article.

Usage (from the project root):

    .\\.venv\\Scripts\\python.exe -m src.provision_eval --benchmark data/evaluation/legal-v2
        [--scenario technical|natural] [--build-dir DIR] [--chunk-depth N] [--output FILE]
        [--json]

A benchmark is a directory of three files. docs/evaluation/guidelines.md defines them and the
rules for judging:
- benchmark.json: schema_version (1 or 2), benchmark_id, version, kind ("real" or
  "synthetic"), description;
- questions.jsonl: one question per line, with its fixed, hand-written Italian search queries,
  category, expected outcome, dev/test split and provenance. Schema 2 gives each question a
  second list of queries, search_queries_it_natural;
- judgments.jsonl: one judgment per line, keyed by instrument ID and article label (and an
  optional point), never by chunk or provision ID, with a grade of 0, 1 or 2, a rationale and
  provenance.

Judgments are resolved against the provision store at evaluation time. An unknown instrument,
article or point is an error, and every such problem is listed at once.

Query scenarios: a run uses one list of search queries per question, and the report names it.
- "technical" (the default) uses search_queries_it;
- "natural" uses search_queries_it_natural, which only a schema-2 benchmark has.

The questions and judgments are the same in both scenarios.

What is measured: each search query goes through ProvisionExplorer.search, the BM25 provision
search of `ask`, unchanged. Its results are grouped by article there. A chunk without article
text (recitals, front matter, headings, running headers) adds nothing, and an article found in
several chunks counts once, at its best chunk rank. When a question has several queries, their
rankings are interleaved by chunk rank, query by query, as evidence assembly takes search hits.
The metrics are those of src/retrieval_eval.py, applied to article provision IDs:
- Recall@1, Recall@5, Recall@10 and MRR@10 count grade >= 1 as relevant;
- nDCG@10 uses the grades as gains;
- an article with no judgment counts as not relevant;
- a question without any grade >= 1 judgment is reported but not scored.

This measures ranking against the benchmark's judgments, not legal correctness. Results on a
synthetic benchmark test the evaluator only.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

from src.citations import part_markers
from src.config import PROJECT_ROOT
from src.corpus_identity import (
    CodeVersion,
    CodeVersionError,
    current_dependency_versions,
    detect_code_version,
)
from src.evidence import EvidenceRequest
from src.ingestion import display_path
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.provisions import ProvisionError, ProvisionStore, load_store
from src.query_analysis import query_problem
from src.retrieval_eval import EvaluationDataError, ndcg_at_k, recall_at_k, reciprocal_rank_at_k

SCHEMA_VERSIONS = (1, 2)  # 2 adds the natural-query scenario (search_queries_it_natural)
REPORT = "provision-retrieval-evaluation/2"
BENCHMARK_FILES = ("benchmark.json", "questions.jsonl", "judgments.jsonl")
DEFAULT_BENCHMARK = PROJECT_ROOT / "data" / "evaluation" / "legal-v2"  # frozen at Gate 3
DEFAULT_CHUNK_DEPTH = 20  # chunks requested per search query; `ask` requests fewer (see report)

# Query scenarios: which list of search queries a run uses. The question key of each scenario.
QUERY_SCENARIOS = ("technical", "natural")
DEFAULT_SCENARIO = "technical"
SCENARIO_FIELDS = {"technical": "search_queries_it", "natural": "search_queries_it_natural"}

KINDS = ("real", "synthetic")
CATEGORIES = ("definition", "obligation", "procedure", "authority", "rights",
              "cross_instrument", "explicit_citation", "other")
EXPECTED_OUTCOMES = ("answerable", "needs_clarification", "out_of_scope", "not_in_corpus")
SPLITS = ("dev", "test")
REVIEW_STATUSES = ("synthetic", "candidate", "owner_reviewed", "expert_reviewed")
GRADES = (0, 1, 2)
RELEVANT_GRADE = 1  # the convention of src/retrieval_eval.py: grade >= 1 is relevant
METRICS: tuple[tuple[str, Callable[..., float], int], ...] = (
    ("recall@1", recall_at_k, 1),
    ("recall@5", recall_at_k, 5),
    ("recall@10", recall_at_k, 10),
    ("mrr@10", reciprocal_rank_at_k, 10),
    ("ndcg@10", ndcg_at_k, 10),
)
SHOWN = 10  # ranked articles listed per question in the report

SYNTHETIC_LABEL = ("SYNTHETIC BENCHMARK: invented act, questions and judgments. It tests the "
                   "evaluator only and says nothing about legal retrieval quality.")
REAL_LABEL = ("Ranking quality against this benchmark's judgments, for the BM25 search of "
              "`ask`. It is not a measure of legal correctness.")

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_POINT = re.compile(r"\d{1,3}")


# --- Benchmark data ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Provenance:
    drafted_by: str
    drafted_on: str  # YYYY-MM-DD
    review_status: str  # one of REVIEW_STATUSES
    reviewed_by: str | None
    reviewed_on: str | None


@dataclass(frozen=True)
class Question:
    query_id: str
    question: str
    search_queries_it: tuple[str, ...]  # the technical scenario
    category: str
    expected_outcome: str
    split: str
    provenance: Provenance
    notes: str | None
    search_queries_it_natural: tuple[str, ...] = ()  # the natural scenario (schema 2 only)

    def queries(self, scenario: str) -> tuple[str, ...]:
        """The search queries of `scenario` for this question."""
        if scenario not in SCENARIO_FIELDS:
            raise ValueError(f"unknown query scenario {scenario!r}; "
                             f"use one of {list(QUERY_SCENARIOS)}.")
        queries = getattr(self, SCENARIO_FIELDS[scenario])
        if not queries:
            raise EvaluationDataError(f"question {self.query_id!r} has no {scenario} queries.")
        return queries


@dataclass(frozen=True)
class Judgment:
    query_id: str
    instrument: str  # instrument ID, as in data/reference/instruments.json
    article: str  # article label exactly as printed
    point: str | None  # a numbered point "N)" of the article, as digits
    grade: int
    rationale: str
    provenance: Provenance
    where: str  # file and line, for error messages


@dataclass(frozen=True)
class Benchmark:
    benchmark_id: str
    version: str
    kind: str
    description: str
    questions: tuple[Question, ...]
    judgments: tuple[Judgment, ...]
    files: dict[str, dict[str, str]]  # file name -> {"path", "sha256"}
    schema_version: int = 1

    @property
    def query_scenarios(self) -> tuple[str, ...]:
        """The scenarios whose queries every question of this benchmark carries."""
        return QUERY_SCENARIOS if self.schema_version >= 2 else (DEFAULT_SCENARIO,)


def load_benchmark(directory: Path) -> Benchmark:
    """Read and validate a benchmark directory (structure only; see resolve_judgments)."""
    manifest_path = directory / "benchmark.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"no benchmark at {display_path(directory)}: {display_path(manifest_path)} not found "
            "(docs/evaluation/guidelines.md describes the files)")
    manifest = _load_manifest(manifest_path)
    kind, schema_version = manifest["kind"], manifest["schema_version"]
    questions = _load_questions(directory / "questions.jsonl", kind, schema_version)
    judgments = _load_judgments(directory / "judgments.jsonl",
                                {q.query_id for q in questions}, kind)
    files = {name: _file_info(directory / name) for name in BENCHMARK_FILES}
    return Benchmark(manifest["benchmark_id"], manifest["version"], kind,
                     manifest["description"], questions, judgments, files, schema_version)


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvaluationDataError(f"{path}: invalid JSON ({exc.msg}).") from None
    where = str(path)
    if not isinstance(manifest, dict):
        raise EvaluationDataError(f"{where}: expected a JSON object.")
    _check_keys(manifest, {"schema_version", "benchmark_id", "version", "kind", "description"},
                set(), where)
    schema_version = manifest["schema_version"]
    if type(schema_version) is not int or schema_version not in SCHEMA_VERSIONS:  # not True
        raise EvaluationDataError(
            f"{where}: schema_version must be one of {list(SCHEMA_VERSIONS)}.")
    _require_id(manifest, "benchmark_id", where)
    _require_text(manifest, "version", where)
    _require_text(manifest, "description", where)
    _require_choice(manifest, "kind", KINDS, where)
    return manifest


def _load_questions(path: Path, kind: str, schema_version: int) -> tuple[Question, ...]:
    natural = SCENARIO_FIELDS["natural"]
    required = {"query_id", "question", "search_queries_it", "category", "expected_outcome",
                "split", "provenance"}
    if schema_version >= 2:  # schema 1 rejects the natural key as unknown
        required.add(natural)
    questions: list[Question] = []
    seen: set[str] = set()
    for line_number, record in _read_jsonl_objects(path):
        where = f"{path}, line {line_number}"
        _check_keys(record, required, {"notes"}, where)
        query_id = _require_id(record, "query_id", where)
        if query_id in seen:
            raise EvaluationDataError(f"{where}: duplicate query_id {query_id!r}.")
        seen.add(query_id)
        technical_queries = _search_queries(record, "search_queries_it", where)
        natural_queries = _search_queries(record, natural, where) if natural in required else ()
        notes = record.get("notes")
        if notes is not None:
            _require_text(record, "notes", where)
        questions.append(Question(
            query_id=query_id,
            question=_require_text(record, "question", where),
            search_queries_it=technical_queries,
            category=_require_choice(record, "category", CATEGORIES, where),
            expected_outcome=_require_choice(record, "expected_outcome", EXPECTED_OUTCOMES, where),
            split=_require_choice(record, "split", SPLITS, where),
            provenance=_provenance(record["provenance"], where, kind),
            notes=notes,
            search_queries_it_natural=natural_queries,
        ))
    if not questions:
        raise EvaluationDataError(f"{path}: no questions.")
    return tuple(questions)


def _search_queries(record: dict[str, Any], key: str, where: str) -> tuple[str, ...]:
    """A non-empty list of queries, each passing the check `ask` applies to model queries."""
    queries = record[key]
    if not isinstance(queries, list) or not queries:
        raise EvaluationDataError(f"{where}: {key!r} must be a non-empty list of Italian queries.")
    for query in queries:
        problem = query_problem(query) if isinstance(query, str) else "is not a string"
        if problem:
            raise EvaluationDataError(f"{where}: search query {query!r} in {key!r} {problem}.")
    return tuple(queries)


def _load_judgments(path: Path, query_ids: set[str], kind: str) -> tuple[Judgment, ...]:
    judgments: list[Judgment] = []
    seen: set[tuple[str, str, str, str | None]] = set()
    for line_number, record in _read_jsonl_objects(path):
        where = f"{path}, line {line_number}"
        _check_keys(record, {"query_id", "instrument", "article", "grade", "rationale",
                             "provenance"}, {"point"}, where)
        query_id = _require_text(record, "query_id", where)
        if query_id not in query_ids:
            raise EvaluationDataError(f"{where}: unknown query_id {query_id!r}.")
        point = record.get("point")
        if point is not None and not (isinstance(point, str) and _POINT.fullmatch(point)):
            raise EvaluationDataError(
                f"{where}: 'point' must be null or the point's digits as a string, e.g. \"12\".")
        grade = record["grade"]
        if not isinstance(grade, int) or isinstance(grade, bool) or grade not in GRADES:
            raise EvaluationDataError(f"{where}: 'grade' must be one of {list(GRADES)}.")
        instrument = _require_text(record, "instrument", where)
        article = _require_text(record, "article", where)
        key = (query_id, instrument, article, point)
        if key in seen:
            raise EvaluationDataError(f"{where}: duplicate judgment for {key}.")
        seen.add(key)
        judgments.append(Judgment(query_id, instrument, article, point, grade,
                                  _require_text(record, "rationale", where),
                                  _provenance(record["provenance"], where, kind), where))
    return tuple(judgments)


def _provenance(raw: Any, where: str, kind: str) -> Provenance:
    where = f"{where}, provenance"
    if not isinstance(raw, dict):
        raise EvaluationDataError(f"{where}: expected a JSON object.")
    _check_keys(raw, {"drafted_by", "drafted_on", "review_status"},
                {"reviewed_by", "reviewed_on"}, where)
    status = _require_choice(raw, "review_status", REVIEW_STATUSES, where)
    if (status == "synthetic") != (kind == "synthetic"):
        raise EvaluationDataError(
            f"{where}: review_status 'synthetic' is required in a synthetic benchmark and "
            "allowed only there.")
    reviewed = status in ("owner_reviewed", "expert_reviewed")
    for key in ("reviewed_by", "reviewed_on"):
        if reviewed and raw.get(key) is None:
            raise EvaluationDataError(f"{where}: {status!r} requires {key!r}.")
        if not reviewed and raw.get(key) is not None:
            raise EvaluationDataError(f"{where}: {key!r} must be null for {status!r}.")
    return Provenance(
        drafted_by=_require_text(raw, "drafted_by", where),
        drafted_on=_require_date(raw, "drafted_on", where),
        review_status=status,
        reviewed_by=_require_text(raw, "reviewed_by", where) if reviewed else None,
        reviewed_on=_require_date(raw, "reviewed_on", where) if reviewed else None,
    )


# The JSON Lines conventions of src/retrieval_eval.py: UTF-8, one object per line, blank lines
# ignored, unknown or missing keys rejected, every error naming the file and line.


def _read_jsonl_objects(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    if not path.is_file():
        raise FileNotFoundError(f"evaluation file not found: {path}")
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EvaluationDataError(
                    f"{path}, line {line_number}: invalid JSON ({exc.msg}).") from None
            if not isinstance(record, dict):
                raise EvaluationDataError(f"{path}, line {line_number}: expected a JSON object.")
            yield line_number, record


def _check_keys(record: dict[str, Any], required: set[str], optional: set[str], where: str) -> None:
    missing = sorted(required - record.keys())
    unknown = sorted(record.keys() - required - optional)
    if missing:
        raise EvaluationDataError(f"{where}: missing key(s) {missing}.")
    if unknown:
        raise EvaluationDataError(
            f"{where}: unknown key(s) {unknown}; allowed: {sorted(required | optional)}.")


def _require_text(record: dict[str, Any], key: str, where: str) -> str:
    value = record[key]
    if not isinstance(value, str) or not value.strip():
        raise EvaluationDataError(f"{where}: {key!r} must be a non-empty string.")
    return value


def _file_info(path: Path) -> dict[str, str]:
    with path.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    return {"path": display_path(path), "sha256": digest}


def _require_id(record: dict[str, Any], key: str, where: str) -> str:
    value = _require_text(record, key, where)
    if not _ID.fullmatch(value):
        raise EvaluationDataError(
            f"{where}: {key!r} may contain only letters, digits, '_', '.' and '-'.")
    return value


def _require_choice(record: dict[str, Any], key: str, choices: Sequence[str], where: str) -> str:
    value = record[key]
    if value not in choices:
        raise EvaluationDataError(f"{where}: {key!r} must be one of {list(choices)}.")
    return value


def _require_date(record: dict[str, Any], key: str, where: str) -> str:
    value = _require_text(record, key, where)
    try:
        if not _DATE.fullmatch(value):
            raise ValueError
        datetime.date.fromisoformat(value)
    except ValueError:
        raise EvaluationDataError(f"{where}: {key!r} must be a date, YYYY-MM-DD.") from None
    return value


# --- Resolution against the provision store ----------------------------------------------------


def resolve_judgments(judgments: Sequence[Judgment],
                      explorer: ProvisionExplorer) -> dict[str, dict[str, int]]:
    """query_id -> {article provision ID: grade}. Point judgments count for their article, at
    the highest grade given to it. Every unknown instrument, article or point is reported."""
    store = explorer.store
    grades: dict[str, dict[str, int]] = {}
    problems: list[str] = []
    for j in judgments:
        provision = _resolve(j, store, explorer, problems)
        if provision is not None:
            per_query = grades.setdefault(j.query_id, {})
            per_query[provision] = max(per_query.get(provision, 0), j.grade)
    if problems:
        raise EvaluationDataError("the judgments do not match the provision store:\n  "
                                  + "\n  ".join(problems))
    return grades


def _resolve(j: Judgment, store: ProvisionStore, explorer: ProvisionExplorer,
             problems: list[str]) -> str | None:
    try:
        store.registry.instrument(j.instrument)
    except ProvisionError:
        try:
            known = store.resolve_instrument(j.instrument).instrument_id
            hint = f"; use its instrument ID {known!r}"
        except ProvisionError:
            hint = ""
        problems.append(f"{j.where}: unknown instrument {j.instrument!r}{hint}")
        return None
    try:
        provision = store.lookup(j.instrument, j.article)
    except ProvisionError:
        problems.append(f"{j.where}: {j.instrument} has no article {j.article!r}")
        return None
    if provision.label_as_printed != j.article:
        problems.append(f"{j.where}: write the article label as printed, "
                        f"{provision.label_as_printed!r}, not {j.article!r}")
        return None
    if j.point is not None:
        text = "".join(piece["text"] for piece in explorer.provision_view(provision)["text"])
        if ("point", j.point) not in part_markers(text):
            problems.append(f"{j.where}: {j.instrument} art. {j.article} has no point {j.point})")
            return None
    return provision.provision_id


# --- Ranking and metrics -----------------------------------------------------------------------


@dataclass(frozen=True)
class RankedArticle:
    provision_id: str
    instrument_id: str
    label: str
    query: int  # 1-based index of the search query that found it first
    chunk_rank: int  # its best chunk rank in that query's results


def rank_articles(explorer: ProvisionExplorer, queries: Sequence[str],
                  chunk_depth: int) -> tuple[list[RankedArticle], list[dict[str, Any]]]:
    """The article ranking of `queries`, from ProvisionExplorer.search, and one summary per query.

    Each query's articles come from the search result's "provisions" (already grouped by
    article, at their best chunk rank). Several queries are interleaved by chunk rank, query by
    query; an article already ranked keeps its first position.
    """
    per_query: list[list[dict[str, Any]]] = []
    searches: list[dict[str, Any]] = []
    for query in queries:
        result = explorer.search(query, top_k=chunk_depth)
        per_query.append(result["provisions"])
        searches.append({
            "query": query,
            "chunks": len(result["results"]),
            "context_only_chunks": sum(r["role"] == "context_only" for r in result["results"]),
            "articles": len(result["provisions"]),
        })
    ranking: list[RankedArticle] = []
    seen: set[str] = set()
    for rank in range(1, chunk_depth + 1):
        for number, provisions in enumerate(per_query, 1):
            for p in provisions:
                if p["best_rank"] == rank and p["provision_id"] not in seen:
                    seen.add(p["provision_id"])
                    instrument = explorer.store.get(p["provision_id"]).instrument_id
                    ranking.append(RankedArticle(p["provision_id"], instrument, p["label"],
                                                 number, rank))
    return ranking, searches


def evaluate(benchmark: Benchmark, explorer: ProvisionExplorer, *,
             chunk_depth: int = DEFAULT_CHUNK_DEPTH,
             scenario: str = DEFAULT_SCENARIO) -> dict[str, Any]:
    """Per-question rankings and metrics, and their means (all scored questions, and by split),
    for the search queries of one scenario."""
    if type(chunk_depth) is not int or chunk_depth < 1:
        raise ValueError("chunk_depth must be a positive integer.")
    _check_scenario(benchmark, scenario)
    grades = resolve_judgments(benchmark.judgments, explorer)
    per_query: list[dict[str, Any]] = []
    for q in benchmark.questions:
        ranking, searches = rank_articles(explorer, q.queries(scenario), chunk_depth)
        judged = grades.get(q.query_id, {})
        relevant = sum(1 for g in judged.values() if g >= RELEVANT_GRADE)
        ranked_ids = [r.provision_id for r in ranking]
        entry: dict[str, Any] = {
            "query_id": q.query_id,
            "split": q.split,
            "category": q.category,
            "expected_outcome": q.expected_outcome,
            "judged_articles": len(judged),
            "relevant_articles": relevant,
            "searches": searches,
            "ranking_length": len(ranking),
            "ranking": [{"position": n, "provision_id": r.provision_id,
                         "instrument_id": r.instrument_id, "label": r.label, "query": r.query,
                         "chunk_rank": r.chunk_rank, "grade": judged.get(r.provision_id)}
                        for n, r in enumerate(ranking[:SHOWN], 1)],
            "unjudged_in_top10": sum(1 for pid in ranked_ids[:10] if pid not in judged),
        }
        if relevant == 0:
            entry["skipped"] = ("no judgment with grade >= 1" if judged
                                else "no judgments for this question")
        else:
            entry["metrics"] = {name: metric(ranked_ids, judged, k) for name, metric, k in METRICS}
        per_query.append(entry)

    scored = [e for e in per_query if "metrics" in e]
    by_split = {split: _means([e for e in scored if e["split"] == split]) for split in SPLITS}
    return {
        "questions_total": len(per_query),
        "questions_scored": len(scored),
        "questions_skipped": [e["query_id"] for e in per_query if "skipped" in e],
        "means": _means(scored),
        "means_by_split": {s: m for s, m in by_split.items() if m is not None},
        "warnings": _warnings(benchmark, scored, chunk_depth),
        "per_query": per_query,
    }


def _check_scenario(benchmark: Benchmark, scenario: str) -> None:
    if scenario not in QUERY_SCENARIOS:
        raise ValueError(f"unknown query scenario {scenario!r}; "
                         f"use one of {list(QUERY_SCENARIOS)}.")
    if scenario not in benchmark.query_scenarios:
        raise EvaluationDataError(
            f"benchmark {benchmark.benchmark_id} v{benchmark.version} (schema "
            f"{benchmark.schema_version}) has no {scenario!r} queries; its scenarios: "
            f"{list(benchmark.query_scenarios)}.")


def _means(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    if not entries:
        return None
    means = {name: sum(e["metrics"][name] for e in entries) / len(entries)
             for name, _, _ in METRICS}
    return {"questions": len(entries), **means}


def _warnings(benchmark: Benchmark, scored: Sequence[Mapping[str, Any]],
              chunk_depth: int) -> list[str]:
    warnings = []
    short = [e["query_id"] for e in scored if e["ranking_length"] < 10]
    if short:
        warnings.append(
            f"{len(short)} of {len(scored)} scored questions rank fewer than 10 articles at chunk "
            f"depth {chunk_depth} ({', '.join(short)}): the @10 metrics count the missing "
            "positions as misses.")
    unjudged = sum(e["unjudged_in_top10"] for e in scored)
    if unjudged:
        warnings.append(
            f"{unjudged} retrieved articles in the top 10 of scored questions have no judgment "
            "and count as not relevant; judge them to complete the pool.")
    candidates = [x for x in (*benchmark.questions, *benchmark.judgments)
                  if x.provenance.review_status == "candidate"]
    if candidates:
        warnings.append(f"{len(candidates)} questions or judgments are candidates that no person "
                        "has reviewed yet.")
    return warnings


# --- Report ------------------------------------------------------------------------------------


def run(benchmark_dir: Path, build_dir: Path | None = None, *,
        chunk_depth: int = DEFAULT_CHUNK_DEPTH, store: ProvisionStore | None = None,
        detect_code: Callable[[], CodeVersion] | None = None,
        scenario: str = DEFAULT_SCENARIO) -> dict[str, Any]:
    """Load the benchmark and the build, evaluate one query scenario, and describe everything
    the result rests on."""
    benchmark = load_benchmark(benchmark_dir)
    _check_scenario(benchmark, scenario)  # before the build is opened
    explorer = ProvisionExplorer.open(build_dir or find_recorded_build(),
                                      store=store if store is not None else load_store())
    results = evaluate(benchmark, explorer, chunk_depth=chunk_depth, scenario=scenario)
    identity = explorer.identity()
    statuses = {
        "questions": dict(sorted(Counter(q.provenance.review_status
                                         for q in benchmark.questions).items())),
        "judgments": dict(sorted(Counter(j.provenance.review_status
                                         for j in benchmark.judgments).items())),
    }
    return {
        "report": REPORT,
        "label": SYNTHETIC_LABEL if benchmark.kind == "synthetic" else REAL_LABEL,
        "benchmark": {
            "benchmark_id": benchmark.benchmark_id,
            "version": benchmark.version,
            "kind": benchmark.kind,
            "schema_version": benchmark.schema_version,
            "query_scenarios": list(benchmark.query_scenarios),
            "description": benchmark.description,
            "files": benchmark.files,
            "review_status": statuses,
        },
        "corpus": {
            "build_id": identity["build_id"],
            "build_kind": identity["build_kind"],
            "corpus_sha256": identity["corpus_sha256"],
            "build_code": identity["code"],
            "registry_sha256": explorer.store.registry.sha256,
            "sources": [{"version_id": s["version_id"], "source_sha256": s["source_sha256"]}
                        for s in identity["sources"]],
        },
        "code": _code_record(detect_code or (lambda: detect_code_version(PROJECT_ROOT))),
        "retrieval": {
            "function": "src.provision_explorer.ProvisionExplorer.search",
            "method": "bm25",
            "query_scenario": scenario,
            "query_field": SCENARIO_FIELDS[scenario],
            "chunk_depth": chunk_depth,
            "ask_chunk_depth": EvidenceRequest().top_k,
            "ranking": "articles only; a chunk without article text adds nothing; an article "
                       "in several chunks counts once, at its best chunk rank",
            "query_merge": "interleaved by chunk rank, query by query, as evidence assembly "
                           "takes search hits",
            "dependencies": _dependencies(),
        },
        "metrics": {
            "names": [name for name, _, _ in METRICS],
            "relevant": f"grade >= {RELEVANT_GRADE} (Recall, MRR)",
            "gain": "the grade (nDCG); the ideal ranking orders the judged grades",
            "unjudged": "not relevant",
            "unscored": "questions without a grade >= 1 judgment are listed, not averaged",
        },
        **results,
    }


def _code_record(detect: Callable[[], CodeVersion]) -> dict[str, Any]:
    try:
        return {"available": True, **detect().to_record()}
    except CodeVersionError as exc:
        return {"available": False, "reason": str(exc)}


def _dependencies() -> dict[str, str]:
    try:
        bm25 = importlib_metadata.version("rank-bm25")
    except importlib_metadata.PackageNotFoundError:
        bm25 = "not installed"
    return {"rank-bm25": bm25, "python": current_dependency_versions()["python"]}


def format_summary(report: Mapping[str, Any]) -> str:
    benchmark, corpus, code = report["benchmark"], report["corpus"], report["code"]
    retrieval = report["retrieval"]
    lines = ["PROVISION-LEVEL RETRIEVAL EVALUATION: the BM25 search of `ask`", report["label"]]
    lines.append(f"benchmark: {benchmark['benchmark_id']} v{benchmark['version']} "
                 f"({benchmark['kind']}); {report['questions_total']} questions; review status "
                 f"{benchmark['review_status']}")
    lines.append(f"query scenario: {retrieval['query_scenario']} ({retrieval['query_field']})")
    lines.append(f"build: {corpus['build_id']}; corpus sha256 {corpus['corpus_sha256']}")
    lines.append("code: " + (f"{code['commit']} ({code['state']})" if code["available"]
                             else f"not available ({code['reason']})"))
    lines.append(f"chunk depth: {retrieval['chunk_depth']} per search query (`ask` requests "
                 f"{retrieval['ask_chunk_depth']})")
    lines.append(f"scored: {report['questions_scored']} of {report['questions_total']}"
                 + (f"; not scored: {', '.join(report['questions_skipped'])}"
                    if report["questions_skipped"] else ""))
    names = report["metrics"]["names"]
    lines.append("")
    lines.append(f"{'':<16}" + "".join(f"{name:>11}" for name in names))
    rows = [("all", report["means"]), *report["means_by_split"].items()]
    for label, means in rows:
        if means:
            lines.append(f"{label + ' (' + str(means['questions']) + ')':<16}"
                         + "".join(f"{means[name]:>11.3f}" for name in names))
    lines.append("")
    for entry in report["per_query"]:
        head = f"{entry['query_id']:<10} {entry['split']:<5}"
        if "metrics" in entry:
            lines.append(head + "".join(f"{entry['metrics'][name]:>11.3f}" for name in names))
        else:
            lines.append(f"{head} not scored: {entry['skipped']}")
    if report["warnings"]:
        lines += ["", "warnings:"] + [f"  - {w}" for w in report["warnings"]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.provision_eval",
        description="Evaluate the BM25 provision search of `ask` against a benchmark of "
                    "article-level judgments (docs/evaluation/guidelines.md).")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK,
                        help="benchmark directory (default: data/evaluation/legal-v2)")
    parser.add_argument("--scenario", choices=QUERY_SCENARIOS, default=DEFAULT_SCENARIO,
                        help="which search queries to use: technical (search_queries_it, the "
                             "default) or natural (search_queries_it_natural, schema 2 only)")
    parser.add_argument("--build-dir", type=Path,
                        help="corpus build (default: the recorded build in data/processed/builds/)")
    parser.add_argument("--chunk-depth", type=int, default=DEFAULT_CHUNK_DEPTH,
                        help=f"chunks per search query (default: {DEFAULT_CHUNK_DEPTH})")
    parser.add_argument("--output", type=Path, help="write the full JSON report to this file")
    parser.add_argument("--json", action="store_true", help="print the JSON report, not a summary")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # article text may not fit the console encoding
        sys.stdout.reconfigure(errors="replace")
    try:
        report = run(args.benchmark, args.build_dir, chunk_depth=args.chunk_depth,
                     scenario=args.scenario)
    except (FileNotFoundError, EvaluationDataError, ExplorerError, ProvisionError,
            ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text if args.json else format_summary(report))
    return 0 if report["questions_scored"] else 1


if __name__ == "__main__":
    sys.exit(main())
