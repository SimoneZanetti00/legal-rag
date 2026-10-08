"""Retrieval evaluation: Recall@k, MRR@k and nDCG@k over labelled queries.

Usage (from the project root):

    .\\.venv\\Scripts\\python.exe -m src.retrieval_eval --k 1 5 10 --output eval_bm25.json

Evaluation data (UTF-8 JSON Lines, one object per line; blank lines ignored)
------------------------------------------------------------------------------
queries.jsonl   {"query_id": "q01", "text": "obblighi del datore di lavoro"}
                Optional key: "notes" (string). query_id must be unique.
qrels.jsonl     {"query_id": "q01", "chunk_id": "doc-...-0001-...", "relevance": 2}
                relevance is an integer >= 0: 0 = judged not relevant, >= 1 =
                relevant; higher grades mean more relevant (used by nDCG).
                Each (query_id, chunk_id) pair may appear once, query_id must
                exist in queries.jsonl, and chunk_id must exist in the chunk file.

Chunk IDs change whenever a document or the chunking settings change, so
judgments are tied to one chunk file. Unknown chunk IDs are an error rather
than silently scoring zero.

Metric definitions (k = cutoff; only the first k retrieved chunk IDs count)
-----------------------------------------------------------------------------
- Relevant set R = judged chunks with relevance >= 1. Unjudged chunks count as
  not relevant. A chunk ID repeated in the ranking counts only at its first
  position; later repeats take up their positions but earn nothing.
- Recall@k = |relevant chunks in the top k| / |R|. It cannot reach 1 when |R| > k.
- MRR@k: reciprocal rank 1/r of the first relevant chunk within the top k
  (0 if none), averaged over queries.
- nDCG@k = DCG@k / IDCG@k, with DCG@k = sum(relevance_i / log2(i + 1)) over
  positions i = 1..k (linear gain) and IDCG@k the DCG of the ideal ranking of
  the judged grades.
- Fewer than k results, or none, simply score lower; the denominators do not
  shrink.
- Queries without any relevant judgment are not evaluated: they are listed as
  skipped and excluded from the averages.
- Aggregate scores are unweighted means over the evaluated queries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from src.chunk_store import read_chunks
from src.config import ConfigError, load_settings
from src.dense_retrieval import DenseRetriever
from src.ingestion import display_path
from src.models import LegalChunk, RetrievedPassage
from src.retrieval import BM25Retriever

DEFAULT_KS = (1, 5, 10)
METRIC_NAMES = ("recall", "mrr", "ndcg")


class EvaluationDataError(ValueError):
    """Evaluation data is malformed or inconsistent; the message says where."""


class Retriever(Protocol):
    """What the evaluator needs. A retriever may also define `describe() -> dict`
    to record its settings (e.g. the embedding model) in the report."""

    def search(self, query: str, top_k: int = ...) -> list[RetrievedPassage]: ...


def _dense_retriever(chunks: list[LegalChunk]) -> DenseRetriever:
    """Dense retriever using the EMBEDDING_MODEL setting and the <INDEX_DIR> embedding cache."""
    settings = load_settings()
    return DenseRetriever(
        chunks, model_name=settings.embedding_model, cache_dir=settings.index_dir / "embeddings"
    )


# Retriever name -> constructor from chunks. Add new retrievers here.
RETRIEVERS: dict[str, Callable[[list[LegalChunk]], Retriever]] = {
    "bm25": lambda chunks: BM25Retriever(chunks),
    "bm25-okapi": lambda chunks: BM25Retriever(chunks, positive_idf=False),
    "dense": _dense_retriever,
}


@dataclass(frozen=True)
class Query:
    query_id: str
    text: str
    notes: str | None = None


# query_id -> {chunk_id: relevance grade}
Qrels = dict[str, dict[str, int]]


# --- Metrics -------------------------------------------------------------------------


def _check_k(k: int) -> None:
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError(f"k must be a positive int (got {k!r}).")


def _relevant(grades: Mapping[str, int]) -> set[str]:
    relevant = {chunk_id for chunk_id, grade in grades.items() if grade >= 1}
    if not relevant:
        raise ValueError("the query has no relevant judgments; it cannot be evaluated.")
    return relevant


def _first_positions(ranked_ids: Sequence[str], k: int) -> list[tuple[int, str]]:
    """(1-based position, chunk_id) of each chunk's first occurrence within the top k."""
    seen: set[str] = set()
    positions = []
    for position, chunk_id in enumerate(ranked_ids[:k], start=1):
        if chunk_id not in seen:
            seen.add(chunk_id)
            positions.append((position, chunk_id))
    return positions


def recall_at_k(ranked_ids: Sequence[str], grades: Mapping[str, int], k: int) -> float:
    _check_k(k)
    relevant = _relevant(grades)
    found = sum(1 for _, chunk_id in _first_positions(ranked_ids, k) if chunk_id in relevant)
    return found / len(relevant)


def reciprocal_rank_at_k(ranked_ids: Sequence[str], grades: Mapping[str, int], k: int) -> float:
    _check_k(k)
    relevant = _relevant(grades)
    for position, chunk_id in _first_positions(ranked_ids, k):
        if chunk_id in relevant:
            return 1 / position
    return 0.0


def ndcg_at_k(ranked_ids: Sequence[str], grades: Mapping[str, int], k: int) -> float:
    _check_k(k)
    _relevant(grades)
    dcg = sum(
        grades.get(chunk_id, 0) / math.log2(position + 1)
        for position, chunk_id in _first_positions(ranked_ids, k)
    )
    ideal = sorted((g for g in grades.values() if g >= 1), reverse=True)[:k]
    idcg = sum(grade / math.log2(position + 1) for position, grade in enumerate(ideal, start=1))
    return dcg / idcg


def query_metrics(
    ranked_ids: Sequence[str], grades: Mapping[str, int], ks: Iterable[int]
) -> dict[str, float]:
    """All metrics for one query, keyed like "recall@5"."""
    metrics = {}
    for k in ks:
        metrics[f"recall@{k}"] = recall_at_k(ranked_ids, grades, k)
        metrics[f"mrr@{k}"] = reciprocal_rank_at_k(ranked_ids, grades, k)
        metrics[f"ndcg@{k}"] = ndcg_at_k(ranked_ids, grades, k)
    return metrics


# --- Loading evaluation data ---------------------------------------------------------


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
                    f"{path}, line {line_number}: invalid JSON ({exc.msg})."
                ) from None
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
            f"{where}: unknown key(s) {unknown}; allowed: {sorted(required | optional)}."
        )


def _require_text(record: dict[str, Any], key: str, where: str) -> str:
    value = record[key]
    if not isinstance(value, str) or not value.strip():
        raise EvaluationDataError(f"{where}: {key!r} must be a non-empty string.")
    return value


def load_queries(path: Path) -> list[Query]:
    """Load queries in file order; query IDs must be unique."""
    queries: list[Query] = []
    seen: dict[str, int] = {}
    for line_number, record in _read_jsonl_objects(path):
        where = f"{path}, line {line_number}"
        _check_keys(record, {"query_id", "text"}, {"notes"}, where)
        query_id = _require_text(record, "query_id", where)
        if query_id in seen:
            raise EvaluationDataError(
                f"{where}: duplicate query_id {query_id!r} (first on line {seen[query_id]})."
            )
        notes = record.get("notes")
        if notes is not None and not isinstance(notes, str):
            raise EvaluationDataError(f"{where}: 'notes' must be a string.")
        seen[query_id] = line_number
        queries.append(Query(query_id, _require_text(record, "text", where), notes))
    if not queries:
        raise EvaluationDataError(f"{path}: no queries found.")
    return queries


def load_qrels(path: Path, query_ids: Iterable[str]) -> Qrels:
    """Load relevance judgments; every query_id must be one of `query_ids`."""
    known = set(query_ids)
    qrels: Qrels = {}
    for line_number, record in _read_jsonl_objects(path):
        where = f"{path}, line {line_number}"
        _check_keys(record, {"query_id", "chunk_id", "relevance"}, set(), where)
        query_id = _require_text(record, "query_id", where)
        chunk_id = _require_text(record, "chunk_id", where)
        grade = record["relevance"]
        if isinstance(grade, bool) or not isinstance(grade, int) or grade < 0:
            raise EvaluationDataError(
                f"{where}: 'relevance' must be an integer >= 0 (got {grade!r})."
            )
        if query_id not in known:
            raise EvaluationDataError(
                f"{where}: unknown query_id {query_id!r} (not in the queries file)."
            )
        judged = qrels.setdefault(query_id, {})
        if chunk_id in judged:
            raise EvaluationDataError(
                f"{where}: duplicate judgment for query {query_id!r} and chunk {chunk_id!r}."
            )
        judged[chunk_id] = grade
    return qrels


def check_judged_chunks_exist(qrels: Qrels, chunk_ids: set[str]) -> None:
    """Fail if judgments refer to chunks that are not in the evaluated corpus."""
    unknown = sorted({c for judged in qrels.values() for c in judged} - chunk_ids)
    if unknown:
        shown = ", ".join(unknown[:5]) + (" ..." if len(unknown) > 5 else "")
        raise EvaluationDataError(
            f"{len(unknown)} judged chunk ID(s) are not in the chunk file: {shown}. "
            "Chunk IDs change when documents or chunking settings change; re-run "
            "ingestion with the settings used for labelling, or update the judgments."
        )


# --- Running an evaluation -----------------------------------------------------------


def evaluate(
    retriever: Retriever, queries: Sequence[Query], qrels: Qrels, ks: Sequence[int]
) -> dict[str, Any]:
    """Search each query once (top max(ks)) and compute per-query and mean metrics."""
    if not ks:
        raise ValueError("at least one k is required.")
    for k in ks:
        _check_k(k)
    ks = sorted(set(ks))
    depth = ks[-1]

    per_query: list[dict[str, Any]] = []
    evaluated: list[dict[str, float]] = []
    skipped: list[str] = []
    for query in queries:
        grades = qrels.get(query.query_id, {})
        relevant_count = sum(1 for g in grades.values() if g >= 1)
        entry: dict[str, Any] = {
            "query_id": query.query_id,
            "text": query.text,
            "judged": len(grades),
            "relevant": relevant_count,
        }
        if relevant_count == 0:
            entry["skipped"] = (
                "no judgment with relevance >= 1" if grades else "no judgments for this query"
            )
            skipped.append(query.query_id)
        else:
            ranked_ids = [p.chunk.chunk_id for p in retriever.search(query.text, top_k=depth)]
            entry["retrieved"] = ranked_ids
            entry["duplicates"] = len(ranked_ids) - len(set(ranked_ids))
            entry["metrics"] = query_metrics(ranked_ids, grades, ks)
            evaluated.append(entry["metrics"])
        per_query.append(entry)

    means = None
    if evaluated:
        means = {name: sum(m[name] for m in evaluated) / len(evaluated) for name in evaluated[0]}
    return {
        "ks": ks,
        "queries_total": len(queries),
        "queries_evaluated": len(evaluated),
        "queries_skipped": skipped,
        "metrics": means,
        "per_query": per_query,
    }


def _file_info(path: Path) -> dict[str, str]:
    with path.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    return {"path": display_path(path), "sha256": digest}


def run_evaluation(
    retriever_name: str,
    chunks_path: Path,
    queries_path: Path,
    qrels_path: Path,
    ks: Sequence[int],
) -> dict[str, Any]:
    """Load everything, validate it, and evaluate the named retriever."""
    if retriever_name not in RETRIEVERS:
        raise ValueError(f"unknown retriever {retriever_name!r}; choose from {sorted(RETRIEVERS)}.")
    if not chunks_path.is_file():
        raise FileNotFoundError(
            f"chunk file not found: {chunks_path}. Run `python -m src.ingestion` first."
        )
    queries = load_queries(queries_path)
    qrels = load_qrels(qrels_path, (q.query_id for q in queries))
    chunks = list(read_chunks(chunks_path))
    check_judged_chunks_exist(qrels, {c.chunk_id for c in chunks})

    retriever = RETRIEVERS[retriever_name](chunks)
    results = evaluate(retriever, queries, qrels, ks)
    describe = getattr(retriever, "describe", None)
    return {
        "retriever": retriever_name,
        "retriever_details": describe() if callable(describe) else {},
        "config": {
            "ks": results.pop("ks"),
            "chunk_count": len(chunks),
            "chunks": _file_info(chunks_path),
            "queries": _file_info(queries_path),
            "qrels": _file_info(qrels_path),
        },
        **results,
    }


def format_summary(report: dict[str, Any]) -> str:
    config = report["config"]
    ks = config["ks"]
    lines = [f"Retriever: {report['retriever']}"]
    details = report.get("retriever_details", {})
    if "model" in details:
        lines.append(f"Model:     {details['model']}")
    lines += [
        f"Chunks:    {config['chunks']['path']} ({config['chunk_count']} chunks)",
        f"Queries:   {config['queries']['path']} ({report['queries_total']} total, "
        f"{report['queries_evaluated']} evaluated, {len(report['queries_skipped'])} skipped)",
    ]
    if report["queries_skipped"]:
        lines.append(f"Skipped (no relevant judgments): {', '.join(report['queries_skipped'])}")
    if report["metrics"] is None:
        lines.append("No query has a relevant judgment; nothing was evaluated.")
        return "\n".join(lines)

    lines.append("")
    lines.append("Mean      " + "".join(f"{'@' + str(k):>9}" for k in ks))
    for name in METRIC_NAMES:
        values = "".join(f"{report['metrics'][f'{name}@{k}']:>9.3f}" for k in ks)
        lines.append(f"{name:<10}{values}")

    top = ks[-1]
    lines.append("")
    lines.append(f"Per query (@{top})" + " " * 6 + f"{'recall':>8}{'rr':>8}{'ndcg':>8}")
    for entry in report["per_query"]:
        if "metrics" in entry:
            m = entry["metrics"]
            lines.append(
                f"  {entry['query_id']:<22}{m[f'recall@{top}']:>8.3f}"
                f"{m[f'mrr@{top}']:>8.3f}{m[f'ndcg@{top}']:>8.3f}"
            )
    lines.append("")
    lines.append("Scores describe only this query set and corpus.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.retrieval_eval",
        description="Evaluate a retriever with Recall@k, MRR@k and nDCG@k.",
    )
    parser.add_argument("--retriever", default="bm25", choices=sorted(RETRIEVERS))
    parser.add_argument(
        "--k", type=int, nargs="+", default=list(DEFAULT_KS), help="cutoffs (default: 1 5 10)"
    )
    parser.add_argument("--chunks", type=Path, help="default: <DATA_DIR>/processed/chunks.jsonl")
    parser.add_argument("--queries", type=Path, help="default: <DATA_DIR>/evaluation/queries.jsonl")
    parser.add_argument("--qrels", type=Path, help="default: <DATA_DIR>/evaluation/qrels.jsonl")
    parser.add_argument("--output", type=Path, help="write the full JSON report to this file")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2
    if args.output is not None and args.output.suffix.lower() != ".json":
        print(f"Error: output file must have a .json extension: {args.output}", file=sys.stderr)
        return 2

    try:
        report = run_evaluation(
            args.retriever,
            args.chunks or settings.processed_dir / "chunks.jsonl",
            args.queries or settings.evaluation_dir / "queries.jsonl",
            args.qrels or settings.evaluation_dir / "qrels.jsonl",
            args.k,
        )
    except (FileNotFoundError, ValueError) as exc:  # EvaluationDataError is a ValueError
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:  # e.g. an embedding model that cannot be downloaded or loaded
        print(f"Error: could not load the retriever: {exc}", file=sys.stderr)
        return 2

    print(format_summary(report))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"Full report written to {display_path(args.output)}")
    return 0 if report["metrics"] is not None else 1


if __name__ == "__main__":
    sys.exit(main())
