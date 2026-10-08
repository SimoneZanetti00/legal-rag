"""Dense (semantic) retrieval over ingested chunks with sentence-transformers.

Usage (from the project root, after running `python -m src.ingestion`):

    .\\.venv\\Scripts\\python.exe -m src.dense_retrieval "obblighi del datore di lavoro" --top-k 5

Or from Python:

    retriever = DenseRetriever.from_jsonl(Path("data/processed/chunks.jsonl"))
    for passage in retriever.search("notifica di una violazione dei dati", top_k=5):
        print(passage.rank, passage.score, passage.chunk.chunk_id)

How it works
------------
Every chunk and every query is turned into an embedding vector by the same
model. Vectors are L2-normalized, so the dot product of a query and a chunk is
their cosine similarity (from -1 to 1). Chunks are ranked by that similarity;
ties keep corpus order.

- Model: `intfloat/multilingual-e5-small` by default (the EMBEDDING_MODEL
  setting). It is a general multilingual model, not tuned for legal text. It
  is downloaded from Hugging Face on first use (about 470 MB) and then cached
  by the library. The model is loaded once per retriever, and only when an
  embedding has to be computed.
- Input prefixes: E5 models expect "query: " before queries and "passage: "
  before documents, including non-English text (model card). They are added
  automatically when the model name contains an "e5" component and can be
  overridden; other models get no prefix.
- Long inputs are truncated by the model (512 tokens for E5); the truncated
  part of a chunk does not influence its embedding.
- Unlike BM25, every chunk has a similarity, so a search returns `top_k`
  chunks whenever the corpus has that many, even if none is truly relevant.
  Similarity is not a relevance probability.

Embedding cache
---------------
With `cache_dir` set (the CLI uses <INDEX_DIR>/embeddings, which is
git-ignored), chunk embeddings are saved as one .npy file per corpus. The file
name is a SHA-256 of the model name, the passage prefix, and every chunk's ID
and text, so any change to the chunks or the model identifier uses a new file.
A cached file is used only if it loads without pickle and has the expected
shape, dtype, finite values and unit-length rows; otherwise it is recomputed
and replaced. The key does not cover model weights: after the model files
change under the same name, delete the cache directory. Deleting it is always
safe; old files are never cleaned up automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from src.chunk_store import read_chunks
from src.config import ConfigError, load_settings
from src.models import LegalChunk, RetrievalMethod, RetrievedPassage
from src.retrieval_common import format_passage, require_positive_int, require_query

DEFAULT_MODEL = "intfloat/multilingual-e5-small"
DEFAULT_BATCH_SIZE = 32
_CACHE_FORMAT = "legal-rag-embeddings-v1"


class Encoder(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray:
        """Return one embedding row per text, shape (len(texts), dimension)."""
        ...


class SentenceTransformerEncoder:
    """Loads a sentence-transformers model once and encodes batches of text."""

    def __init__(self, model_name: str, *, local_files_only: bool = False) -> None:
        # Imported here: importing torch takes seconds and is not needed for
        # BM25, for tests with fake encoders, or when embeddings are cached.
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._model = SentenceTransformer(model_name, local_files_only=local_files_only)

    def encode(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(
            texts,
            batch_size=len(texts),
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )


def input_prefixes(model_name: str) -> tuple[str, str]:
    """(query prefix, passage prefix) expected by the model: E5 needs "query: "/"passage: "."""
    name_parts = model_name.lower().rsplit("/", 1)[-1].split("-")
    return ("query: ", "passage: ") if "e5" in name_parts else ("", "")


def _normalize_rows(matrix: np.ndarray) -> None:
    """Scale each row to unit length in place; all-zero rows stay zero."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    np.divide(matrix, norms, out=matrix, where=norms > 0)


class DenseRetriever:
    """Ranks chunks by cosine similarity between query and chunk embeddings.

    `encoder` replaces the sentence-transformers model (tests use fakes);
    `model_name` still identifies the embeddings for prefixes and the cache.
    """

    def __init__(
        self,
        chunks: Iterable[LegalChunk],
        *,
        model_name: str = DEFAULT_MODEL,
        encoder: Encoder | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        cache_dir: Path | None = None,
        query_prefix: str | None = None,
        passage_prefix: str | None = None,
    ) -> None:
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError(f"batch_size must be a positive int (got {batch_size!r}).")
        self._chunks = tuple(chunks)
        seen: set[str] = set()
        for chunk in self._chunks:
            if chunk.chunk_id in seen:
                raise ValueError(f"duplicate chunk_id in corpus: {chunk.chunk_id}")
            seen.add(chunk.chunk_id)

        self.model_name = model_name
        default_query_prefix, default_passage_prefix = input_prefixes(model_name)
        self.query_prefix = default_query_prefix if query_prefix is None else query_prefix
        self.passage_prefix = default_passage_prefix if passage_prefix is None else passage_prefix
        self.batch_size = batch_size
        self._encoder = encoder
        # "disabled", "empty corpus", "hit", "miss" (computed and saved) or "invalid" (replaced).
        self.cache_status = "disabled"
        self._embeddings = self._load_or_compute_embeddings(cache_dir)

    @classmethod
    def from_jsonl(cls, path: Path, **kwargs: Any) -> DenseRetriever:
        """Build a retriever from a chunk file written by `python -m src.ingestion`."""
        if not path.is_file():
            raise FileNotFoundError(
                f"chunk file not found: {path}. Run `python -m src.ingestion` first."
            )
        return cls(read_chunks(path), **kwargs)

    def __len__(self) -> int:
        return len(self._chunks)

    def describe(self) -> dict[str, Any]:
        """Settings that identify this retriever's results (used in evaluation reports).

        The cache status is left out on purpose: a cache hit must not change a report.
        """
        return {
            "model": self.model_name,
            "query_prefix": self.query_prefix,
            "passage_prefix": self.passage_prefix,
            "similarity": "cosine",
        }

    def search(self, query: str, top_k: int = 5) -> list[RetrievedPassage]:
        """Return the `top_k` most similar chunks, best first.

        Validation matches BM25Retriever.search: TypeError/ValueError for a
        non-string or blank query and for a `top_k` that is not a positive int
        (booleans are rejected). Returns [] for an empty corpus.
        """
        require_query(query)
        require_positive_int(top_k, "top_k")
        if self._embeddings is None:
            return []

        query_vector = self._encode([self.query_prefix + query])[0]
        if not np.any(query_vector):
            return []  # nothing to compare against; not a similarity of 0 to everything
        query_vector /= np.linalg.norm(query_vector)

        scores = self._embeddings @ query_vector
        order = np.argsort(-scores, kind="stable")[:top_k]
        return [
            RetrievedPassage(
                chunk=self._chunks[i],
                method=RetrievalMethod.DENSE,
                rank=rank,
                score=float(scores[i]),
            )
            for rank, i in enumerate(order, start=1)
        ]

    # --- Embeddings --------------------------------------------------------------

    def _get_encoder(self) -> Encoder:
        if self._encoder is None:
            self._encoder = SentenceTransformerEncoder(self.model_name)
        return self._encoder

    def _encode(self, texts: list[str]) -> np.ndarray:
        vectors = np.asarray(self._get_encoder().encode(texts), dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[0] != len(texts) or vectors.shape[1] == 0:
            raise ValueError(
                f"encoder returned shape {vectors.shape} for {len(texts)} text(s); "
                "expected (number of texts, dimension)."
            )
        if not np.isfinite(vectors).all():
            raise ValueError("encoder returned non-finite values.")
        return vectors

    def _compute_embeddings(self) -> np.ndarray:
        matrix: np.ndarray | None = None
        total = len(self._chunks)
        for start in range(0, total, self.batch_size):
            batch = self._chunks[start : start + self.batch_size]
            vectors = self._encode([self.passage_prefix + chunk.text for chunk in batch])
            if matrix is None:
                matrix = np.empty((total, vectors.shape[1]), dtype=np.float32)
            elif vectors.shape[1] != matrix.shape[1]:
                raise ValueError("encoder returned embeddings of different dimensions.")
            matrix[start : start + len(batch)] = vectors
        assert matrix is not None  # the corpus is not empty here
        _normalize_rows(matrix)
        return matrix

    def _load_or_compute_embeddings(self, cache_dir: Path | None) -> np.ndarray | None:
        if not self._chunks:
            self.cache_status = "empty corpus"
            return None
        if cache_dir is None:
            return self._compute_embeddings()

        path = cache_dir / f"{self._cache_key()}.npy"
        if path.is_file():
            cached = self._load_valid_cache(path)
            if cached is not None:
                self.cache_status = "hit"
                return cached
            self.cache_status = "invalid"
        else:
            self.cache_status = "miss"

        embeddings = self._compute_embeddings()
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(path.name + ".tmp")
        try:
            with tmp_path.open("wb") as file:
                np.save(file, embeddings, allow_pickle=False)
            os.replace(tmp_path, path)
        finally:
            tmp_path.unlink(missing_ok=True)
        return embeddings

    def _cache_key(self) -> str:
        digest = hashlib.sha256()
        digest.update(f"{_CACHE_FORMAT}\n{self.model_name}\n{self.passage_prefix}\n".encode())
        for chunk in self._chunks:
            digest.update(chunk.chunk_id.encode("utf-8") + b"\x00")
            digest.update(chunk.text.encode("utf-8") + b"\x00")
        return digest.hexdigest()

    def _load_valid_cache(self, path: Path) -> np.ndarray | None:
        try:
            matrix = np.load(path, allow_pickle=False)
        except (OSError, ValueError, EOFError):
            return None
        if (
            not isinstance(matrix, np.ndarray)
            or matrix.dtype != np.float32
            or matrix.ndim != 2
            or matrix.shape[0] != len(self._chunks)
            or matrix.shape[1] == 0
            or not np.isfinite(matrix).all()
        ):
            return None
        norms = np.linalg.norm(matrix, axis=1)
        if not np.all((np.abs(norms - 1) < 1e-3) | (norms == 0)):
            return None
        return matrix


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.dense_retrieval",
        description="Search ingested chunks by embedding similarity (dense retrieval).",
    )
    parser.add_argument("query", help="search text")
    parser.add_argument("--top-k", type=int, default=5, help="maximum results (default: 5)")
    parser.add_argument(
        "--chunks", type=Path, help="JSONL chunk file (default: <DATA_DIR>/processed/chunks.jsonl)"
    )
    parser.add_argument("--model", help="embedding model (default: the EMBEDDING_MODEL setting)")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
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
        retriever = DenseRetriever.from_jsonl(
            chunks_path,
            model_name=model_name,
            batch_size=args.batch_size,
            cache_dir=None if args.no_cache else settings.index_dir / "embeddings",
        )
        results = retriever.search(args.query, top_k=args.top_k)
    except (FileNotFoundError, TypeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:  # the model could not be downloaded or loaded
        print(f"Error: could not load embedding model {model_name!r}: {exc}", file=sys.stderr)
        return 2

    print(
        f"Indexed {len(retriever)} chunk(s) from {chunks_path} with {model_name} "
        f"(embedding cache: {retriever.cache_status})"
    )
    if not results:
        print("No results.")
    for passage in results:
        print(format_passage(passage))
    return 0


if __name__ == "__main__":
    sys.exit(main())
