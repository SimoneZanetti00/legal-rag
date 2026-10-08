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
`local_files_only=True`. Inputs longer than the model's limit are truncated by
the model, so the end of a long passage may not be read.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, Protocol

from src.models import RetrievalMethod, RetrievedPassage
from src.retrieval_common import require_positive_int, require_query

# Same value as the RERANKER_MODEL default in src/config.py.
DEFAULT_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
DEFAULT_BATCH_SIZE = 16


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

    `scorer` replaces the cross-encoder (tests use fakes). `model_name` names
    the cross-encoder to load when no scorer is given, and is what `describe`
    reports as the model.
    """

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_MODEL,
        scorer: PairScorer | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        require_positive_int(batch_size, "batch_size")
        self.model_name = model_name
        self.batch_size = batch_size
        # A CrossEncoderScorer is cheap to create: it loads its model on first use.
        self._scorer: PairScorer = scorer if scorer is not None else CrossEncoderScorer(model_name)

    def describe(self) -> dict[str, Any]:
        """Settings that identify this reranker's results."""
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
