"""Hybrid retrieval: BM25 and dense results combined with Reciprocal Rank Fusion.

Usage (from the project root, after running `python -m src.ingestion`):

    .\\.venv\\Scripts\\python.exe -m src.hybrid_retrieval "obblighi del datore di lavoro" --top-k 5

Or from Python:

    retriever = HybridRetriever.from_jsonl(Path("data/processed/chunks.jsonl"))
    for passage in retriever.search("obblighi del datore di lavoro", top_k=5):
        print(passage.rank, passage.score, passage.method_ranks, passage.chunk.chunk_id)

Reciprocal Rank Fusion (RRF)
----------------------------
Each retriever returns a ranked list of candidates. A chunk's fused score is

    score(chunk) = sum of 1 / (rrf_k + rank) over the lists that contain it

where rank is the chunk's 1-based position in a list. Only ranks are used: the
BM25 score and the cosine similarity are on unrelated scales and are never
compared, normalized or weighted. A chunk found by both retrievers is one
result whose contributions are added. Results are ordered by fused score
(highest first); equal scores are ordered by chunk ID, so the order is fully
deterministic.

Fixed candidate depths
----------------------
BM25 always contributes its top `bm25_top_k` chunks and dense retrieval its
top `dense_top_k`, whatever `top_k` is requested. The fused order therefore
does not depend on `top_k`: `search(q, 5)` equals `search(q, 10)[:5]`. At most
`bm25_top_k + dense_top_k` results can be returned.

What the result records
-----------------------
Each `RetrievedPassage` has `method=HYBRID`, the fused `rank` and `score`, and
`method_ranks` / `method_scores` holding the rank and original score from each
retriever that returned the chunk. A method missing from those dicts did not
return that chunk.

Limits
------
- The fused score only orders results. It is not a probability or a
  confidence, and it ignores how large the original scores were.
- With the default settings a chunk returned by both retrievers always
  outranks one returned by a single retriever (true whenever the candidate
  depth is below rrf_k + 2). Dense retrieval returns candidates for every
  query, so on a corpus no larger than `dense_top_k` every BM25 match is
  "returned by both".
- `rrf_k` and the candidate depths are untuned defaults.
- If either retriever fails, the error is raised. There is no silent
  fallback to the other retriever.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from src.chunk_store import read_chunks
from src.config import ConfigError, load_settings
from src.dense_retrieval import DenseRetriever
from src.models import LegalChunk, RetrievalMethod, RetrievedPassage
from src.retrieval import BM25Retriever, _format_passage

# Same values as the BM25_TOP_K, DENSE_TOP_K and RRF_K defaults in src/config.py.
DEFAULT_BM25_TOP_K = 20
DEFAULT_DENSE_TOP_K = 20
DEFAULT_RRF_K = 60


class _Searchable(Protocol):
    def search(self, query: str, top_k: int = ...) -> list[RetrievedPassage]: ...


def _require_positive_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int (got {type(value).__name__}).")
    if value < 1:
        raise ValueError(f"{name} must be >= 1 (got {value}).")


def _require_query(query: object) -> None:
    if not isinstance(query, str):
        raise TypeError(f"query must be a string (got {type(query).__name__}).")
    if not query.strip():
        raise ValueError("query must not be empty or whitespace.")


def reciprocal_rank_fusion(
    ranked_lists: Mapping[RetrievalMethod, Sequence[RetrievedPassage]],
    *,
    rrf_k: int = DEFAULT_RRF_K,
    top_k: int | None = None,
) -> list[RetrievedPassage]:
    """Fuse ranked lists, one per retrieval method, into a single ranking.

    - A chunk's rank in a list is its 1-based position there. If a chunk ID
      occurs more than once in one list, only its first position counts.
    - Chunks are merged by `chunk_id`. The same ID with different chunk content
      in two lists means the lists come from different corpora: ValueError.
    - `top_k=None` returns every fused result.
    """
    _require_positive_int(rrf_k, "rrf_k")
    if top_k is not None:
        _require_positive_int(top_k, "top_k")

    chunks: dict[str, LegalChunk] = {}
    method_ranks: dict[str, dict[RetrievalMethod, int]] = {}
    method_scores: dict[str, dict[RetrievalMethod, float]] = {}
    for method, passages in ranked_lists.items():
        seen_in_list: set[str] = set()
        for position, passage in enumerate(passages, start=1):
            chunk_id = passage.chunk.chunk_id
            if chunk_id in seen_in_list:
                continue
            seen_in_list.add(chunk_id)
            if chunks.setdefault(chunk_id, passage.chunk) != passage.chunk:
                raise ValueError(
                    f"chunk {chunk_id!r} has different content in two result lists; "
                    "the retrievers must be built from the same chunks."
                )
            method_ranks.setdefault(chunk_id, {})[method] = position
            method_scores.setdefault(chunk_id, {})[method] = passage.score

    # Contributions are added in ascending rank order, so two chunks with the
    # same set of ranks get exactly the same float and tie reliably.
    fused = {
        chunk_id: sum(1 / (rrf_k + rank) for rank in sorted(ranks.values()))
        for chunk_id, ranks in method_ranks.items()
    }
    ordered = sorted(fused, key=lambda chunk_id: (-fused[chunk_id], chunk_id))
    return [
        RetrievedPassage(
            chunk=chunks[chunk_id],
            method=RetrievalMethod.HYBRID,
            rank=rank,
            score=fused[chunk_id],
            method_ranks=method_ranks[chunk_id],
            method_scores=method_scores[chunk_id],
        )
        for rank, chunk_id in enumerate(ordered[:top_k], start=1)
    ]


class HybridRetriever:
    """Combines a BM25 retriever and a dense retriever with RRF.

    The two retrievers are used through their `search(query, top_k)` method
    only, and are meant to be built from the same chunks. That is not
    verified. The one check made is on a chunk ID returned by both retrievers
    for a query: if its content differs between them, ValueError is raised.
    Retrievers built from different corpora that share no chunk ID are fused
    without any error.
    """

    def __init__(
        self,
        bm25: _Searchable,
        dense: _Searchable,
        *,
        bm25_top_k: int = DEFAULT_BM25_TOP_K,
        dense_top_k: int = DEFAULT_DENSE_TOP_K,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> None:
        _require_positive_int(bm25_top_k, "bm25_top_k")
        _require_positive_int(dense_top_k, "dense_top_k")
        _require_positive_int(rrf_k, "rrf_k")
        self._bm25 = bm25
        self._dense = dense
        self.bm25_top_k = bm25_top_k
        self.dense_top_k = dense_top_k
        self.rrf_k = rrf_k

    @classmethod
    def from_jsonl(
        cls,
        path: Path,
        *,
        bm25_top_k: int = DEFAULT_BM25_TOP_K,
        dense_top_k: int = DEFAULT_DENSE_TOP_K,
        rrf_k: int = DEFAULT_RRF_K,
        **dense_kwargs: Any,
    ) -> HybridRetriever:
        """Build both retrievers from a chunk file; `dense_kwargs` go to DenseRetriever."""
        if not path.is_file():
            raise FileNotFoundError(
                f"chunk file not found: {path}. Run `python -m src.ingestion` first."
            )
        chunks = list(read_chunks(path))
        return cls(
            BM25Retriever(chunks),
            DenseRetriever(chunks, **dense_kwargs),
            bm25_top_k=bm25_top_k,
            dense_top_k=dense_top_k,
            rrf_k=rrf_k,
        )

    def __len__(self) -> int:
        return len(self._bm25)  # type: ignore[arg-type]

    @property
    def max_results(self) -> int:
        """The most results one search can return: both candidate depths combined."""
        return self.bm25_top_k + self.dense_top_k

    def describe(self) -> dict[str, Any]:
        """Settings that identify this retriever's results (used in evaluation reports)."""
        dense_describe = getattr(self._dense, "describe", None)
        details: dict[str, Any] = dict(dense_describe()) if callable(dense_describe) else {}
        details.update(
            fusion="rrf",
            rrf_k=self.rrf_k,
            bm25_top_k=self.bm25_top_k,
            dense_top_k=self.dense_top_k,
        )
        return details

    def search(self, query: str, top_k: int = 5) -> list[RetrievedPassage]:
        """Return up to `top_k` fused results, best first.

        Validation matches BM25Retriever.search and DenseRetriever.search.
        Returns [] when neither retriever returns a candidate. Errors raised by
        either retriever are not caught.
        """
        _require_query(query)
        _require_positive_int(top_k, "top_k")
        return reciprocal_rank_fusion(self._candidates(query), rrf_k=self.rrf_k, top_k=top_k)

    def _candidates(self, query: str) -> dict[RetrievalMethod, list[RetrievedPassage]]:
        """Each retriever's candidates, at its fixed depth (independent of the output size)."""
        _require_query(query)
        return {
            RetrievalMethod.BM25: self._bm25.search(query, top_k=self.bm25_top_k),
            RetrievalMethod.DENSE: self._dense.search(query, top_k=self.dense_top_k),
        }


def _format_sources(passage: RetrievedPassage) -> str:
    """One line saying which retrievers returned the chunk, with their ranks and scores."""
    parts = [
        f"{method.value} #{rank} (score {passage.method_scores[method]:.4f})"
        for method, rank in passage.method_ranks.items()
    ]
    return "    from: " + " | ".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.hybrid_retrieval",
        description="Search ingested chunks with BM25 and dense retrieval, fused with RRF. "
        "Candidate depths and the RRF constant come from BM25_TOP_K, DENSE_TOP_K and RRF_K.",
    )
    parser.add_argument("query", help="search text")
    parser.add_argument("--top-k", type=int, default=5, help="maximum results (default: 5)")
    parser.add_argument(
        "--chunks", type=Path, help="JSONL chunk file (default: <DATA_DIR>/processed/chunks.jsonl)"
    )
    parser.add_argument("--model", help="embedding model (default: the EMBEDDING_MODEL setting)")
    parser.add_argument(
        "--no-cache", action="store_true", help="do not read or write <INDEX_DIR>/embeddings"
    )
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2
    chunks_path = args.chunks or settings.processed_dir / "chunks.jsonl"
    model_name = args.model or settings.embedding_model

    try:
        _require_query(args.query)  # checked first, before any model is loaded
        _require_positive_int(args.top_k, "top_k")
        retriever = HybridRetriever.from_jsonl(
            chunks_path,
            bm25_top_k=settings.bm25_top_k,
            dense_top_k=settings.dense_top_k,
            rrf_k=settings.rrf_k,
            model_name=model_name,
            cache_dir=None if args.no_cache else settings.index_dir / "embeddings",
        )
        candidates = retriever._candidates(args.query)
        results = reciprocal_rank_fusion(candidates, rrf_k=retriever.rrf_k, top_k=args.top_k)
    except (FileNotFoundError, TypeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:  # the model could not be downloaded or loaded
        print(f"Error: could not load embedding model {model_name!r}: {exc}", file=sys.stderr)
        return 2

    dense_cache = getattr(retriever._dense, "cache_status", "n/a")
    print(
        f"Indexed {len(retriever)} chunk(s) from {chunks_path} with {model_name} "
        f"(embedding cache: {dense_cache})"
    )
    bm25_count = len(candidates[RetrievalMethod.BM25])
    dense_count = len(candidates[RetrievalMethod.DENSE])
    print(
        f"Candidates: BM25 {bm25_count} (depth {retriever.bm25_top_k}), "
        f"dense {dense_count} (depth {retriever.dense_top_k}); fusion: RRF, rrf_k={retriever.rrf_k}"
    )
    if len(retriever) == 0:
        print("The corpus is empty: the chunk file contains no chunks.")
    else:
        if bm25_count == 0:
            print("BM25 returned no candidates: no chunk shares a word with the query.")
        if dense_count == 0:
            print("Dense retrieval returned no candidates.")
    if not results:
        print("No results.")
    for passage in results:
        print(_format_passage(passage))
        print(_format_sources(passage))
    return 0


if __name__ == "__main__":
    sys.exit(main())
