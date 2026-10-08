"""Second-stage reranking: reorder passages that a retriever already returned.

    reranker = Reranker()            # or Reranker(scorer=my_scorer)
    candidates = hybrid_retriever.search("obblighi del datore di lavoro", top_k=20)
    best = reranker.rerank("obblighi del datore di lavoro", candidates, top_k=5)

What reranking does, and does not do
------------------------------------
A scorer reads the query and one passage text together and returns a relevance
score for that pair. The reranker scores every passage it is given and returns
the same passages in a new order.

- It works only on the passages passed in. It never searches the corpus and
  never adds a passage.
- It does not change any `LegalChunk`, the input list, or the input passages.
- It does not decide how much evidence to use. Selecting evidence for an
  answer is a later, separate step.

Result
------
Each returned `RetrievedPassage` has `method=RERANKED`, the reranker's `rank`
and `score`, and the original chunk object. What the previous stage said is
kept: its rank and score are added to `method_ranks` and `method_scores` under
the previous method, next to anything already recorded there. A passage that
came from hybrid retrieval therefore still shows its BM25, dense and hybrid
ranks and scores.

Order: reranker score, highest first. Equal scores keep the order of the
previous stage (its rank, lowest first).

Scores
------
Scores are the model's raw output, with no sigmoid or other normalization
applied. They only order passages for one query. They are not probabilities,
not comparable between models, and not a relevance threshold.

Failures
--------
If the scorer fails, or returns the wrong number of scores or a score that is
not a finite number, an error is raised. The original order is never returned
in place of a reranked one.

Model
-----
`CrossEncoderScorer` uses a sentence-transformers cross-encoder. The model is
loaded the first time a score is needed, not when the object is created, and
the library is imported only then. The first use downloads the model unless
`local_files_only=True`, which `Reranker(local_files_only=True)` passes on to
the scorer it creates. Inputs longer than the model's limit are truncated by
the model, so the end of a long passage may not be read.

Retrieval and reranking as one retriever
----------------------------------------
`RerankingRetriever` puts the two steps of the example above behind the usual
`search(query, top_k)`:

    retriever = RerankingRetriever(hybrid_retriever, Reranker(), candidate_top_k=20)
    best = retriever.search("obblighi del datore di lavoro", top_k=5)

The wrapped retriever chooses the candidates; the reranker only reorders them.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, Protocol

from src.models import RetrievalMethod, RetrievedPassage
from src.retrieval_common import Retriever, require_positive_int, require_query

# Same value as the RERANKER_MODEL default in src/config.py.
DEFAULT_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
DEFAULT_BATCH_SIZE = 16
# Same value as the RERANK_TOP_K default in src/config.py.
DEFAULT_CANDIDATE_TOP_K = 20


class PairScorer(Protocol):
    def score(self, query: str, texts: list[str]) -> Sequence[float]:
        """Return one relevance score per text, in the same order; higher is more relevant."""
        ...


def _raw_scores(scores: Any) -> Any:
    """Activation passed to the cross-encoder so that it returns its output unchanged."""
    return scores


class CrossEncoderScorer:
    """Scores (query, text) pairs with a sentence-transformers cross-encoder.

    Creating the object loads nothing. The model is loaded on the first call
    to `score` and reused afterwards.
    """

    def __init__(self, model_name: str, *, local_files_only: bool = False) -> None:
        self.model_name = model_name
        self.local_files_only = local_files_only
        self._model: Any = None

    def describe(self) -> dict[str, Any]:
        return {
            "type": "cross-encoder",
            "library": "sentence-transformers",
            "model": self.model_name,
            "scores": "raw model output (no sigmoid)",
        }

    def score(self, query: str, texts: list[str]) -> Sequence[float]:
        if self._model is None:
            # Imported here: the library pulls in torch, which takes seconds to
            # import and is not needed until a real score is computed.
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name, local_files_only=self.local_files_only)
        scores = self._model.predict(
            [(query, text) for text in texts],
            batch_size=max(len(texts), 1),
            show_progress_bar=False,
            activation_fn=_raw_scores,
            convert_to_numpy=True,
        )
        return [float(score) for score in scores]


class Reranker:
    """Reorders retrieved passages by a pair scorer's relevance scores.

    Without `scorer`, a `CrossEncoderScorer` is created for `model_name`
    (`DEFAULT_MODEL` if not given), with `local_files_only` passed on to it.

    With `scorer` (tests use fakes), that object is used as it is:
    `local_files_only` is ignored and the scorer is never replaced or changed.

    `model_name` on the instance, and in `describe`, is the model actually in
    use: the scorer's own `model_name` if it has one, otherwise the
    `model_name` argument as a label, otherwise None.
    """

    def __init__(
        self,
        *,
        model_name: str | None = None,
        scorer: PairScorer | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        local_files_only: bool = False,
    ) -> None:
        require_positive_int(batch_size, "batch_size")
        self.batch_size = batch_size
        if scorer is None:
            # Cheap to create: a CrossEncoderScorer loads its model on first use.
            scorer = CrossEncoderScorer(
                model_name or DEFAULT_MODEL, local_files_only=local_files_only
            )
        self._scorer: PairScorer = scorer
        self.model_name: str | None = getattr(scorer, "model_name", None) or model_name

    def describe(self) -> dict[str, Any]:
        """Settings that identify this reranker's results.

        `reranker_model` is the model of the scorer in use (see the class
        docstring), never a default that is not being used.
        """
        scorer_describe = getattr(self._scorer, "describe", None)
        return {
            "reranker_model": self.model_name,
            "reranker_scorer": (
                scorer_describe() if callable(scorer_describe) else type(self._scorer).__name__
            ),
            "reranker_batch_size": self.batch_size,
            "reranker_scores": "raw scorer output; orders passages, not a probability",
        }

    def rerank(
        self, query: str, passages: Sequence[RetrievedPassage], top_k: int | None = None
    ) -> list[RetrievedPassage]:
        """Return the given passages ordered by reranker score, best first.

        `top_k=None` returns all of them; otherwise the best `top_k`, or fewer
        if fewer were given. An empty input returns [] without using the scorer.
        Raises TypeError/ValueError for an invalid `query` or `top_k`, and
        ValueError if the scorer returns a wrong number of scores or a score
        that is not a finite number. Errors raised by the scorer are not caught.
        """
        require_query(query)
        if top_k is not None:
            require_positive_int(top_k, "top_k")
        candidates = list(passages)
        if not candidates:
            return []

        scores = self._score(query, [passage.chunk.text for passage in candidates])
        # Ties: the previous stage's rank decides, then the position in the input.
        order = sorted(
            range(len(candidates)), key=lambda i: (-scores[i], candidates[i].rank, i)
        )
        reranked = []
        for rank, i in enumerate(order[:top_k], start=1):
            previous = candidates[i]
            reranked.append(
                RetrievedPassage(
                    chunk=previous.chunk,
                    method=RetrievalMethod.RERANKED,
                    rank=rank,
                    score=scores[i],
                    method_ranks={**previous.method_ranks, previous.method: previous.rank},
                    method_scores={**previous.method_scores, previous.method: previous.score},
                )
            )
        return reranked

    def _score(self, query: str, texts: list[str]) -> list[float]:
        """Score all texts in batches and check what the scorer returned."""
        scores: list[float] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            batch_scores = list(self._scorer.score(query, batch))
            if len(batch_scores) != len(batch):
                raise ValueError(
                    f"scorer returned {len(batch_scores)} score(s) for {len(batch)} passage(s); "
                    "expected exactly one score per passage."
                )
            for value in batch_scores:
                try:
                    score = float(value)
                except (TypeError, ValueError):
                    raise ValueError(f"scorer returned a non-numeric score: {value!r}.") from None
                if not math.isfinite(score):
                    raise ValueError(f"scorer returned a non-finite score: {score!r}.")
                scores.append(score)
        return scores


class RerankingRetriever:
    """A retriever whose results are reordered by a reranker (second-stage retrieval).

    One search has two stages:

    1. `retriever.search(query, top_k=candidate_top_k)` returns the candidates.
       This is the only search of the corpus, and it is made once.
    2. `reranker.rerank(query, candidates, top_k=top_k)` reorders those
       candidates and keeps the best `top_k`.

    The wrapped retriever alone decides which passages are candidates. The
    reranker only reorders them: every result is one of the candidates, and no
    other passage of the corpus can appear. A relevant passage that the
    retriever did not return within `candidate_top_k` cannot be recovered.

    Any object with `search(query, top_k)` can be wrapped (BM25, dense, hybrid,
    or a later retriever), and both stages are passed in: nothing is built or
    loaded here.

    Results are what `Reranker.rerank` returns. Each one keeps its original
    chunk and, in `method_ranks` and `method_scores`, the rank and score from
    the wrapped retriever and from any stage before it.

    The reranker's score estimates how well a passage matches the query. It
    says nothing about whether the passage is valid, in force or authoritative.
    """

    def __init__(
        self,
        retriever: Retriever,
        reranker: Reranker,
        *,
        candidate_top_k: int = DEFAULT_CANDIDATE_TOP_K,
    ) -> None:
        require_positive_int(candidate_top_k, "candidate_top_k")
        self._retriever = retriever
        self._reranker = reranker
        self.candidate_top_k = candidate_top_k

    @property
    def max_results(self) -> int:
        """The most results one search can return: no more than the candidates."""
        limit = getattr(self._retriever, "max_results", None)
        return self.candidate_top_k if limit is None else min(self.candidate_top_k, limit)

    def describe(self) -> dict[str, Any]:
        """Settings that identify this retriever's results: those of both stages."""
        details: dict[str, Any] = {}
        for stage in (self._retriever, self._reranker):
            stage_describe = getattr(stage, "describe", None)
            if callable(stage_describe):
                details.update(stage_describe())
        details["reranker_candidate_top_k"] = self.candidate_top_k
        return details

    def search(self, query: str, top_k: int = 5) -> list[RetrievedPassage]:
        """Return up to `top_k` of the retriever's candidates, best first by reranker score.

        Fewer are returned when the retriever returns fewer candidates, and []
        when it returns none; the reranker is not used in that case.

        Validation matches the other retrievers. In addition `top_k` must not
        exceed `candidate_top_k`: ValueError is raised, and neither value is
        adjusted. Errors raised by the retriever or the reranker are not
        caught, and the candidates are never returned in their original order
        in place of a reranked result.
        """
        require_query(query)
        require_positive_int(top_k, "top_k")
        if top_k > self.candidate_top_k:
            raise ValueError(
                f"top_k must be <= candidate_top_k (got top_k={top_k}, "
                f"candidate_top_k={self.candidate_top_k})."
            )
        candidates = self._retriever.search(query, top_k=self.candidate_top_k)
        if not candidates:
            return []
        return self._reranker.rerank(query, candidates, top_k=top_k)
