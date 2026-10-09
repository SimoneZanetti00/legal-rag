"""Reranking tests. Everything is offline: scores come from a deterministic fake
scorer, and where the cross-encoder path is exercised the `sentence_transformers`
module is replaced by a fake. No real model is loaded."""

import ast
import copy
import sys
import types

import numpy as np
import pytest

from src.config import PROJECT_ROOT, Settings
from src.hybrid_retrieval import HybridRetriever, reciprocal_rank_fusion
from src.models import LegalChunk, RetrievalMethod, RetrievedPassage, SourceLocation
from src.reranking import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_CANDIDATE_TOP_K,
    DEFAULT_MODEL,
    CrossEncoderScorer,
    Reranker,
    RerankingRetriever,
)
from src.retrieval import BM25Retriever

BM25, DENSE = RetrievalMethod.BM25, RetrievalMethod.DENSE
HYBRID, RERANKED = RetrievalMethod.HYBRID, RetrievalMethod.RERANKED


def chunk(name: str) -> LegalChunk:
    return LegalChunk(
        chunk_id=f"chunk-{name}",
        doc_id="doc",
        text=f"text of {name}",
        chunk_index=0,
        location=SourceLocation(source_path="data/raw/doc.txt", page=2, article=name),
    )


A, B, C, D, E = (chunk(n) for n in "ABCDE")


def ranked(method: RetrievalMethod, chunks, scores=None) -> list[RetrievedPassage]:
    """A first-stage result list; scores default to 10, 9, 8, ..."""
    scores = scores or [10.0 - i for i in range(len(chunks))]
    return [
        RetrievedPassage(chunk=c, method=method, rank=i, score=s)
        for i, (c, s) in enumerate(zip(chunks, scores), start=1)
    ]


class FakeScorer:
    """Returns a fixed score per chunk text and records every call."""

    def __init__(self, scores: dict[str, float], default: float = 0.0) -> None:
        self.scores = {f"text of {name}": value for name, value in scores.items()}
        self.default = default
        self.calls: list[tuple[str, list[str]]] = []

    def score(self, query: str, texts: list[str]) -> list[float]:
        self.calls.append((query, list(texts)))
        return [self.scores.get(text, self.default) for text in texts]


def reranker(scores: dict[str, float] | None = None, **kwargs) -> Reranker:
    return Reranker(scorer=FakeScorer(scores or {}), **kwargs)


def ids(results) -> list[str]:
    return [p.chunk.chunk_id for p in results]


CANDIDATES = ranked(BM25, [A, B, C, D], [7.5, 6.0, 4.5, 3.0])
SCORES = {"A": 0.2, "B": -1.5, "C": 3.0, "D": 1.1}  # raw scores may be negative


# --- Ordering -----------------------------------------------------------------------------


def test_passages_are_reordered_by_reranker_score():
    results = reranker(SCORES).rerank("query", CANDIDATES)
    assert ids(results) == ["chunk-C", "chunk-D", "chunk-A", "chunk-B"]


def test_scores_are_in_descending_order_and_taken_from_the_scorer():
    results = reranker(SCORES).rerank("query", CANDIDATES)
    assert [p.score for p in results] == [3.0, 1.1, 0.2, -1.5]
    assert all(isinstance(p.score, float) for p in results)


def test_method_rank_and_score_are_replaced():
    results = reranker(SCORES).rerank("query", CANDIDATES)
    assert all(p.method is RERANKED for p in results)
    assert [p.rank for p in results] == [1, 2, 3, 4]
    first = results[0]
    assert first.chunk is C
    assert (first.rank, first.score) == (1, 3.0)  # was BM25 rank 3 with score 4.5


def test_reranking_is_repeatable():
    engine = reranker(SCORES)
    assert engine.rerank("query", CANDIDATES) == engine.rerank("query", CANDIDATES)


def test_no_passage_is_added_or_dropped():
    results = reranker(SCORES).rerank("query", CANDIDATES)
    assert sorted(ids(results)) == sorted(ids(CANDIDATES))


def test_the_scorer_receives_the_query_and_the_chunk_texts():
    scorer = FakeScorer(SCORES)
    Reranker(scorer=scorer).rerank("obblighi del datore", CANDIDATES)
    assert scorer.calls == [
        ("obblighi del datore", ["text of A", "text of B", "text of C", "text of D"])
    ]


# --- top_k ---------------------------------------------------------------------------------


def test_top_k_none_returns_every_candidate():
    assert len(reranker(SCORES).rerank("query", CANDIDATES, top_k=None)) == 4
    assert len(reranker(SCORES).rerank("query", CANDIDATES)) == 4  # None is the default


def test_top_k_truncates_after_reranking():
    engine = reranker(SCORES)
    everything = engine.rerank("query", CANDIDATES)
    assert engine.rerank("query", CANDIDATES, top_k=2) == everything[:2]
    # The best passage was third in the input: it is found because all are scored first.
    assert ids(engine.rerank("query", CANDIDATES, top_k=1)) == ["chunk-C"]


def test_top_k_does_not_reduce_what_is_scored():
    scorer = FakeScorer(SCORES)
    Reranker(scorer=scorer).rerank("query", CANDIDATES, top_k=1)
    assert len(scorer.calls[0][1]) == 4


def test_fewer_candidates_than_top_k_are_returned_without_padding():
    results = reranker(SCORES).rerank("query", CANDIDATES[:2], top_k=10)
    assert ids(results) == ["chunk-A", "chunk-B"]
    assert [p.rank for p in results] == [1, 2]


# --- Empty input ----------------------------------------------------------------------------


def test_empty_candidates_return_nothing_without_calling_the_scorer():
    scorer = FakeScorer(SCORES)
    engine = Reranker(scorer=scorer)
    assert engine.rerank("query", []) == []
    assert engine.rerank("query", [], top_k=5) == []
    assert scorer.calls == []


def test_empty_candidates_still_validate_the_arguments():
    with pytest.raises(ValueError, match="query"):
        reranker().rerank("  ", [])
    with pytest.raises(ValueError, match="top_k"):
        reranker().rerank("query", [], top_k=0)


# --- Validation -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "error", "message"),
    [
        ("", ValueError, "query must not be empty or whitespace."),
        ("   ", ValueError, "query must not be empty or whitespace."),
        (None, TypeError, "query must be a string (got NoneType)."),
        (7, TypeError, "query must be a string (got int)."),
    ],
)
def test_invalid_query_is_rejected_before_scoring(query, error, message):
    scorer = FakeScorer(SCORES)
    with pytest.raises(error) as caught:
        Reranker(scorer=scorer).rerank(query, CANDIDATES)
    assert str(caught.value) == message
    assert scorer.calls == []


@pytest.mark.parametrize(
    ("top_k", "error", "message"),
    [
        (0, ValueError, "top_k must be >= 1 (got 0)."),
        (-2, ValueError, "top_k must be >= 1 (got -2)."),
        (True, TypeError, "top_k must be an int (got bool)."),
        (2.0, TypeError, "top_k must be an int (got float)."),
        ("3", TypeError, "top_k must be an int (got str)."),
    ],
)
def test_invalid_top_k_is_rejected_before_scoring(top_k, error, message):
    scorer = FakeScorer(SCORES)
    with pytest.raises(error) as caught:
        Reranker(scorer=scorer).rerank("query", CANDIDATES, top_k=top_k)
    assert str(caught.value) == message
    assert scorer.calls == []


@pytest.mark.parametrize(("batch_size", "error"), [(0, ValueError), (-1, ValueError),
                                                   (True, TypeError), (1.5, TypeError)])
def test_invalid_batch_size_is_rejected(batch_size, error):
    with pytest.raises(error, match="batch_size"):
        reranker(batch_size=batch_size)


# --- Ties ------------------------------------------------------------------------------------


def test_ties_keep_the_first_stage_order():
    results = reranker({}).rerank("query", CANDIDATES)  # every passage scores 0.0
    assert len({p.score for p in results}) == 1
    assert ids(results) == ["chunk-A", "chunk-B", "chunk-C", "chunk-D"]


def test_ties_follow_the_first_stage_rank_not_the_input_position():
    shuffled = [CANDIDATES[2], CANDIDATES[0], CANDIDATES[3], CANDIDATES[1]]  # ranks 3, 1, 4, 2
    results = reranker({}).rerank("query", shuffled)
    assert ids(results) == ["chunk-A", "chunk-B", "chunk-C", "chunk-D"]


def test_partial_ties_are_broken_only_among_the_tied_passages():
    results = reranker({"A": 1.0, "B": 5.0, "C": 1.0, "D": 5.0}).rerank("query", CANDIDATES)
    assert ids(results) == ["chunk-B", "chunk-D", "chunk-A", "chunk-C"]


def test_equal_score_and_equal_first_stage_rank_fall_back_to_input_position():
    same_rank = [
        RetrievedPassage(chunk=B, method=BM25, rank=1, score=1.0),
        RetrievedPassage(chunk=A, method=DENSE, rank=1, score=0.9),
    ]
    assert ids(reranker({}).rerank("query", same_rank)) == ["chunk-B", "chunk-A"]


# --- Nothing given to the reranker is changed -----------------------------------------------


def test_original_chunk_objects_are_preserved():
    results = reranker(SCORES).rerank("query", CANDIDATES)
    by_id = {p.chunk.chunk_id: p.chunk for p in CANDIDATES}
    assert all(p.chunk is by_id[p.chunk.chunk_id] for p in results)
    assert results[0].chunk.location == SourceLocation("data/raw/doc.txt", 2, None, None, "C", None)


def test_the_input_list_is_not_mutated():
    candidates = ranked(BM25, [A, B, C, D])
    same_objects = list(candidates)
    reranker(SCORES).rerank("query", candidates, top_k=2)
    assert len(candidates) == 4
    assert all(a is b for a, b in zip(candidates, same_objects))  # same objects, same order


def test_the_input_passages_are_not_mutated():
    candidates = reciprocal_rank_fusion(
        {BM25: ranked(BM25, [A, B, C]), DENSE: ranked(DENSE, [C, A, D], [0.9, 0.8, 0.7])}
    )
    before = copy.deepcopy(candidates)
    results = reranker(SCORES).rerank("query", candidates)

    assert candidates == before
    assert all(p.method is HYBRID for p in candidates)
    for original, output in zip(candidates, sorted(results, key=lambda p: p.method_ranks[HYBRID])):
        assert HYBRID not in original.method_ranks  # the input's own dicts were not extended
        assert output.method_ranks is not original.method_ranks
        assert output.method_scores is not original.method_scores


def test_a_tuple_of_passages_is_accepted():
    assert ids(reranker(SCORES).rerank("query", tuple(CANDIDATES), top_k=1)) == ["chunk-C"]


# --- Provenance of the previous stages -------------------------------------------------------


def test_previous_rank_and_score_are_kept_under_the_previous_method():
    results = {p.chunk.chunk_id: p for p in reranker(SCORES).rerank("query", CANDIDATES)}
    assert results["chunk-C"].method_ranks == {BM25: 3}
    assert results["chunk-C"].method_scores == {BM25: 4.5}
    assert results["chunk-A"].method_ranks == {BM25: 1}
    assert results["chunk-A"].method_scores == {BM25: 7.5}


def test_dense_input_keeps_its_own_history():
    [result] = reranker().rerank("query", ranked(DENSE, [A], [0.87]))
    assert result.method_ranks == {DENSE: 1}
    assert result.method_scores == {DENSE: 0.87}


def test_hybrid_provenance_survives_reranking():
    fused = reciprocal_rank_fusion(
        {
            BM25: ranked(BM25, [A, B, C], [7.5, 4.0, 1.5]),
            DENSE: ranked(DENSE, [C, A, D], [0.91, 0.88, 0.80]),
        }
    )
    assert ids(fused) == ["chunk-A", "chunk-C", "chunk-B", "chunk-D"]
    results = {
        p.chunk.chunk_id: p
        for p in reranker({"A": 0.1, "B": 0.4, "C": 0.3, "D": 0.2}).rerank("query", fused)
    }

    # Found by both retrievers, then fused, then reranked: all four stages are visible.
    a = results["chunk-A"]
    assert (a.method, a.rank, a.score) == (RERANKED, 4, 0.1)
    assert a.method_ranks == {BM25: 1, DENSE: 2, HYBRID: 1}
    assert a.method_scores == {BM25: 7.5, DENSE: 0.88, HYBRID: pytest.approx(1 / 61 + 1 / 62)}

    # Found by dense retrieval only: BM25 stays absent.
    d = results["chunk-D"]
    assert d.method_ranks == {DENSE: 3, HYBRID: 4}
    assert d.method_scores == {DENSE: 0.80, HYBRID: pytest.approx(1 / 63)}
    assert BM25 not in d.method_ranks

    # Found by BM25 only.
    assert results["chunk-B"].method_ranks == {BM25: 2, HYBRID: 3}
    assert results["chunk-B"].rank == 1


def test_reranking_twice_keeps_the_earlier_reranked_position():
    first = reranker(SCORES).rerank("query", CANDIDATES)
    second = reranker({"A": 9.0}).rerank("query", first)
    top = second[0]
    assert top.chunk is A
    assert top.method_ranks == {BM25: 1, RERANKED: 3}
    assert top.method_scores == {BM25: 7.5, RERANKED: 0.2}


# --- What the scorer returns ------------------------------------------------------------------


class FixedOutputScorer:
    def __init__(self, output) -> None:
        self.output = output

    def score(self, query, texts):
        return self.output(texts) if callable(self.output) else self.output


@pytest.mark.parametrize(
    ("output", "returned"),
    [([1.0, 2.0, 3.0], 3), ([1.0, 2.0, 3.0, 4.0, 5.0], 5), ([], 0)],
)
def test_wrong_number_of_scores_is_rejected(output, returned):
    engine = Reranker(scorer=FixedOutputScorer(output))
    with pytest.raises(ValueError) as caught:
        engine.rerank("query", CANDIDATES)
    assert str(caught.value) == (
        f"scorer returned {returned} score(s) for 4 passage(s); "
        "expected exactly one score per passage."
    )


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_score_is_rejected(bad):
    engine = Reranker(scorer=FixedOutputScorer([1.0, bad, 0.5, 0.2]))
    with pytest.raises(ValueError, match="non-finite score"):
        engine.rerank("query", CANDIDATES)


@pytest.mark.parametrize("bad", ["high", None, [1.0, 2.0]])
def test_non_numeric_score_is_rejected(bad):
    engine = Reranker(scorer=FixedOutputScorer([1.0, bad, 0.5, 0.2]))
    with pytest.raises(ValueError, match="non-numeric score"):
        engine.rerank("query", CANDIDATES)


def test_numpy_scores_are_accepted_and_returned_as_floats():
    engine = Reranker(scorer=FixedOutputScorer(np.array([0.5, 2.5, -1.0, 1.5], dtype=np.float32)))
    results = engine.rerank("query", CANDIDATES)
    assert ids(results) == ["chunk-B", "chunk-D", "chunk-A", "chunk-C"]
    assert all(type(p.score) is float for p in results)


@pytest.mark.parametrize("error", [RuntimeError("model crashed"), OSError("model not found")])
def test_scorer_errors_propagate_without_fallback(error):
    def fail(texts):
        raise error

    with pytest.raises(type(error), match=str(error)):
        Reranker(scorer=FixedOutputScorer(fail)).rerank("query", CANDIDATES)


# --- Batching ----------------------------------------------------------------------------------


def test_passages_are_scored_in_batches_of_the_configured_size():
    scorer = FakeScorer({"A": 1, "B": 2, "C": 3, "D": 4, "E": 5})
    results = Reranker(scorer=scorer, batch_size=2).rerank("query", ranked(BM25, [A, B, C, D, E]))
    assert [texts for _, texts in scorer.calls] == [
        ["text of A", "text of B"], ["text of C", "text of D"], ["text of E"],
    ]
    assert all(query == "query" for query, _ in scorer.calls)
    assert ids(results) == ["chunk-E", "chunk-D", "chunk-C", "chunk-B", "chunk-A"]


def test_batch_size_does_not_change_the_result():
    candidates = ranked(BM25, [A, B, C, D, E])
    scores = {"A": 1, "B": 5, "C": 3, "D": 5, "E": 0}
    assert reranker(scores, batch_size=1).rerank("q", candidates) == reranker(
        scores, batch_size=64
    ).rerank("q", candidates)


def test_wrong_score_count_is_detected_per_batch():
    engine = Reranker(scorer=FixedOutputScorer(lambda texts: [1.0]), batch_size=3)
    with pytest.raises(ValueError, match=r"1 score\(s\) for 3 passage\(s\)"):
        engine.rerank("query", CANDIDATES)


# --- Description and defaults -------------------------------------------------------------------


def test_defaults_match_the_configuration():
    assert DEFAULT_MODEL == Settings().reranker_model
    engine = Reranker()  # creating it loads nothing
    assert engine.model_name == DEFAULT_MODEL
    assert engine.batch_size == DEFAULT_BATCH_SIZE == 16


def test_describe_with_the_default_cross_encoder():
    assert Reranker(model_name="some/model", batch_size=8).describe() == {
        "reranker_model": "some/model",
        "reranker_scorer": {
            "type": "cross-encoder",
            "library": "sentence-transformers",
            "model": "some/model",
            "scores": "raw model output (no sigmoid)",
        },
        "reranker_batch_size": 8,
        "reranker_scores": "raw scorer output; orders passages, not a probability",
    }


def test_describe_with_an_injected_scorer_names_its_class():
    details = reranker(model_name="fake/model").describe()
    assert details["reranker_model"] == "fake/model"
    assert details["reranker_scorer"] == "FakeScorer"


# --- The cross-encoder path, with a fake sentence_transformers module --------------------------


@pytest.fixture
def fake_cross_encoder(monkeypatch):
    """Replace sentence_transformers; returns the fake CrossEncoder class."""

    class FakeCrossEncoder:
        instances: list["FakeCrossEncoder"] = []

        def __init__(self, model_name: str, local_files_only: bool = False) -> None:
            self.model_name = model_name
            self.local_files_only = local_files_only
            self.calls: list[tuple[list, dict]] = []
            FakeCrossEncoder.instances.append(self)

        def predict(self, pairs, **kwargs):
            self.calls.append((list(pairs), kwargs))
            # "Raw output": how many query words the text contains, minus 0.5.
            logits = [len(set(q.split()) & set(t.split())) - 0.5 for q, t in pairs]
            return np.array(logits, dtype=np.float32)

    module = types.ModuleType("sentence_transformers")
    module.CrossEncoder = FakeCrossEncoder
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    return FakeCrossEncoder


@pytest.fixture
def no_model_allowed(monkeypatch):
    """Make any attempt to create a cross-encoder fail loudly."""

    class Forbidden:
        def __init__(self, *args, **kwargs):
            raise AssertionError("a real model must not be loaded in this test")

    module = types.ModuleType("sentence_transformers")
    module.CrossEncoder = Forbidden
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)


def test_an_injected_scorer_means_no_model_is_loaded(no_model_allowed):
    results = reranker(SCORES).rerank("query", CANDIDATES)
    assert ids(results)[0] == "chunk-C"


def test_creating_a_reranker_or_scorer_loads_no_model(no_model_allowed):
    Reranker()
    Reranker(model_name="some/model").describe()
    CrossEncoderScorer("some/model", local_files_only=True).describe()


def test_empty_candidates_load_no_model(no_model_allowed):
    assert Reranker().rerank("query", []) == []


def test_the_model_is_loaded_on_first_use_and_only_once(fake_cross_encoder):
    scorer = CrossEncoderScorer("fake/cross-encoder", local_files_only=True)
    assert fake_cross_encoder.instances == []
    scorer.score("alpha beta", ["alpha", "gamma"])
    scorer.score("alpha beta", ["beta"])
    [model] = fake_cross_encoder.instances
    assert (model.model_name, model.local_files_only) == ("fake/cross-encoder", True)
    assert len(model.calls) == 2


def test_cross_encoder_scorer_asks_for_raw_scores_of_query_text_pairs(fake_cross_encoder):
    scores = CrossEncoderScorer("fake/cross-encoder").score("alpha beta", ["alpha beta", "gamma"])
    assert scores == [1.5, -0.5]
    assert all(type(s) is float for s in scores)

    pairs, kwargs = fake_cross_encoder.instances[0].calls[0]
    assert pairs == [("alpha beta", "alpha beta"), ("alpha beta", "gamma")]
    assert kwargs["show_progress_bar"] is False
    assert kwargs["batch_size"] == 2
    # The activation leaves the model's output untouched: no sigmoid is applied.
    marker = object()
    assert kwargs["activation_fn"](marker) is marker


def test_reranker_with_the_default_scorer_end_to_end(fake_cross_encoder):
    passages = [
        RetrievedPassage(chunk=chunk(name), method=BM25, rank=i, score=1.0)
        for i, name in enumerate(["uno", "due", "tre"], start=1)
    ]
    engine = Reranker(model_name="fake/cross-encoder", batch_size=2)
    first = engine.rerank("text of tre", passages)
    engine.rerank("text of due", passages)

    assert ids(first)[0] == "chunk-tre"
    assert first[0].score == 2.5 and first[0].method is RERANKED
    [model] = fake_cross_encoder.instances  # one model for the reranker's lifetime
    assert model.model_name == "fake/cross-encoder"
    assert [len(pairs) for pairs, _ in model.calls] == [2, 1, 2, 1]


def test_a_model_that_cannot_be_loaded_raises_without_fallback(monkeypatch):
    class Unloadable:
        def __init__(self, *args, **kwargs):
            raise OSError("We couldn't connect to 'https://huggingface.co'")

    module = types.ModuleType("sentence_transformers")
    module.CrossEncoder = Unloadable
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    with pytest.raises(OSError, match="couldn't connect"):
        Reranker().rerank("query", CANDIDATES)


# --- The model that is reported, and local_files_only ------------------------------------------

DESCRIBE_KEYS = {"reranker_model", "reranker_scorer", "reranker_batch_size", "reranker_scores"}


def test_describe_reports_the_model_of_an_injected_cross_encoder_scorer(no_model_allowed):
    engine = Reranker(scorer=CrossEncoderScorer("other-org/other-model"))
    details = engine.describe()
    assert engine.model_name == "other-org/other-model"
    assert details["reranker_model"] == "other-org/other-model"
    assert details["reranker_scorer"]["model"] == "other-org/other-model"
    assert DEFAULT_MODEL not in repr(details)  # the unused default appears nowhere


def test_the_injected_scorer_model_wins_over_a_different_model_name(no_model_allowed):
    scorer = CrossEncoderScorer("other-org/other-model")
    engine = Reranker(model_name="some/label", scorer=scorer)
    assert engine.describe()["reranker_model"] == "other-org/other-model"
    assert scorer.model_name == "other-org/other-model"  # the scorer was not renamed


def test_describe_of_the_default_reranker_reports_the_default_model(no_model_allowed):
    assert Reranker().describe() == {
        "reranker_model": DEFAULT_MODEL,
        "reranker_scorer": {
            "type": "cross-encoder",
            "library": "sentence-transformers",
            "model": DEFAULT_MODEL,
            "scores": "raw model output (no sigmoid)",
        },
        "reranker_batch_size": DEFAULT_BATCH_SIZE,
        "reranker_scores": "raw scorer output; orders passages, not a probability",
    }


def test_an_injected_scorer_without_a_model_name_reports_no_model(no_model_allowed):
    details = reranker().describe()
    assert details["reranker_model"] is None  # not a default that is not in use
    assert details["reranker_scorer"] == "FakeScorer"


@pytest.mark.parametrize(
    "engine_factory",
    [
        lambda: Reranker(),
        lambda: Reranker(local_files_only=True),
        lambda: Reranker(scorer=CrossEncoderScorer("other-org/other-model")),
        lambda: reranker(),
        lambda: reranker(model_name="fake/model", local_files_only=True),
    ],
    ids=["default", "local-files-only", "injected-cross-encoder", "fake", "fake-with-label"],
)
def test_describe_fields_are_the_same_for_every_configuration(no_model_allowed, engine_factory):
    details = engine_factory().describe()
    assert set(details) == DESCRIBE_KEYS
    assert details["reranker_batch_size"] == DEFAULT_BATCH_SIZE
    assert details["reranker_scores"] == "raw scorer output; orders passages, not a probability"


@pytest.mark.parametrize("local_files_only", [True, False])
def test_local_files_only_reaches_the_cross_encoder_the_reranker_creates(
    fake_cross_encoder, local_files_only
):
    engine = Reranker(model_name="fake/cross-encoder", local_files_only=local_files_only)
    assert fake_cross_encoder.instances == []  # nothing is loaded until a score is needed
    engine.rerank("query", CANDIDATES)
    [model] = fake_cross_encoder.instances
    assert model.model_name == "fake/cross-encoder"
    assert model.local_files_only is local_files_only


def test_local_files_only_is_off_by_default(fake_cross_encoder):
    Reranker().rerank("query", CANDIDATES)
    [model] = fake_cross_encoder.instances
    assert (model.model_name, model.local_files_only) == (DEFAULT_MODEL, False)


def test_local_files_only_does_not_change_an_injected_cross_encoder_scorer(fake_cross_encoder):
    scorer = CrossEncoderScorer("other-org/other-model", local_files_only=False)
    before = dict(vars(scorer))
    engine = Reranker(scorer=scorer, local_files_only=True)
    assert vars(scorer) == before

    engine.rerank("query", CANDIDATES)
    # The injected scorer did the scoring, with its own settings.
    [model] = fake_cross_encoder.instances
    assert (model.model_name, model.local_files_only) == ("other-org/other-model", False)
    assert scorer.local_files_only is False


def test_local_files_only_does_not_replace_or_change_an_injected_fake_scorer(no_model_allowed):
    scorer = FakeScorer(SCORES)
    before = copy.deepcopy(vars(scorer))
    engine = Reranker(scorer=scorer, local_files_only=True)
    assert vars(scorer) == before  # no attribute added, none changed

    results = engine.rerank("query", CANDIDATES)
    assert ids(results)[0] == "chunk-C"
    assert len(scorer.calls) == 1  # this object, not a replacement, was asked for the scores


# --- RerankingRetriever: a retriever followed by the reranker ----------------------------------

MANY = [chunk(f"n{i:02d}") for i in range(30)]


class StubRetriever:
    """Returns fixed passages (or raises); records its calls and the lists it returned."""

    def __init__(self, passages=(), error: Exception | None = None, log: list | None = None):
        self.passages, self.error = list(passages), error
        self.log = log if log is not None else []
        self.calls: list[tuple[str, int]] = []
        self.returned: list[list[RetrievedPassage]] = []

    def search(self, query: str, top_k: int = 5) -> list[RetrievedPassage]:
        self.calls.append((query, top_k))
        self.log.append("retriever")
        if self.error is not None:
            raise self.error
        self.returned.append(self.passages[:top_k])
        return self.returned[-1]


class StubReranker:
    """Stands in for Reranker: records its calls and returns the passages reversed."""

    def __init__(self, error: Exception | None = None, log: list | None = None):
        self.error = error
        self.log = log if log is not None else []
        self.calls: list[tuple[str, list[RetrievedPassage], int | None]] = []
        self.result: list[RetrievedPassage] | None = None

    def rerank(self, query, passages, top_k=None):
        self.calls.append((query, list(passages), top_k))
        self.log.append("reranker")
        if self.error is not None:
            raise self.error
        self.result = list(reversed(passages))[:top_k]
        return self.result


def test_search_calls_the_retriever_then_the_reranker_and_returns_its_result():
    log: list[str] = []
    first, second = StubRetriever(CANDIDATES, log=log), StubReranker(log=log)
    results = RerankingRetriever(first, second).search("query", top_k=2)
    assert log == ["retriever", "reranker"]  # one call each, in this order
    assert results is second.result
    assert ids(results) == ["chunk-D", "chunk-C"]


def test_the_exact_query_reaches_both_stages():
    query = "  Obblighi del DATORE di lavoro?  "  # passed on as given, not cleaned
    first, second = StubRetriever(CANDIDATES), StubReranker()
    RerankingRetriever(first, second).search(query, top_k=2)
    assert first.calls[0][0] == query
    assert second.calls[0][0] == query


@pytest.mark.parametrize("top_k", [1, 3, 7])
def test_the_retriever_is_asked_for_candidate_top_k_whatever_top_k_is(top_k):
    first = StubRetriever(ranked(BM25, MANY))
    RerankingRetriever(first, StubReranker(), candidate_top_k=7).search("query", top_k=top_k)
    assert first.calls == [("query", 7)]


def test_candidate_top_k_defaults_to_the_configured_rerank_top_k():
    assert DEFAULT_CANDIDATE_TOP_K == Settings().rerank_top_k == 20
    first = StubRetriever(ranked(BM25, MANY))
    engine = RerankingRetriever(first, StubReranker())
    engine.search("query")
    assert engine.candidate_top_k == 20
    assert first.calls == [("query", 20)]


def test_top_k_reaches_the_reranker_together_with_every_candidate():
    first, second = StubRetriever(ranked(BM25, MANY)), StubReranker()
    results = RerankingRetriever(first, second, candidate_top_k=7).search("query", top_k=3)
    [(_, passages, top_k)] = second.calls
    assert top_k == 3
    assert len(passages) == 7  # all the candidates are reranked, not only the first three
    assert all(given is returned for given, returned in zip(passages, first.returned[0]))
    assert len(results) == 3


def test_top_k_defaults_to_five_like_the_other_retrievers():
    second = StubReranker()
    RerankingRetriever(StubRetriever(ranked(BM25, MANY)), second).search("query")
    assert second.calls[0][2] == 5


def test_reranked_results_have_the_reranker_order_rank_and_score():
    results = RerankingRetriever(StubRetriever(CANDIDATES), reranker(SCORES)).search("query")
    assert ids(results) == ["chunk-C", "chunk-D", "chunk-A", "chunk-B"]
    assert [p.rank for p in results] == [1, 2, 3, 4]
    assert [p.score for p in results] == [3.0, 1.1, 0.2, -1.5]
    assert all(p.method is RERANKED for p in results)


def test_fewer_candidates_than_top_k_are_returned_without_a_second_search():
    first = StubRetriever(ranked(BM25, [A, B]))
    results = RerankingRetriever(first, reranker(SCORES), candidate_top_k=10).search("query", 5)
    assert sorted(ids(results)) == ["chunk-A", "chunk-B"]
    assert first.calls == [("query", 10)]  # the corpus is searched once, never again for more


def test_a_passage_outside_the_candidates_is_never_scored_or_returned():
    # D and E would get the best scores, but the retriever's top three are A, B and C.
    scorer = FakeScorer({"A": 0.3, "B": 0.2, "C": 0.1, "D": 50.0, "E": 99.0})
    first = StubRetriever(ranked(BM25, [A, B, C, D, E]))
    engine = RerankingRetriever(first, Reranker(scorer=scorer), candidate_top_k=3)
    results = engine.search("query", top_k=3)
    assert ids(results) == ["chunk-A", "chunk-B", "chunk-C"]
    assert scorer.calls == [("query", ["text of A", "text of B", "text of C"])]
    assert all(any(p.chunk is c.chunk for c in first.returned[0]) for p in results)


def test_search_order_does_not_depend_on_top_k():
    engine = RerankingRetriever(StubRetriever(CANDIDATES), reranker(SCORES))
    assert engine.search("query", top_k=2) == engine.search("query", top_k=4)[:2]
    assert engine.search("query", top_k=4) == engine.search("query", top_k=4)


def test_no_candidates_return_nothing_without_using_the_reranker():
    first, second = StubRetriever([]), StubReranker()
    assert RerankingRetriever(first, second).search("query") == []
    assert first.calls == [("query", 20)]
    assert second.calls == []


def test_no_candidates_and_construction_load_no_model(no_model_allowed):
    engine = RerankingRetriever(StubRetriever([]), Reranker())
    engine.describe()
    assert engine.search("query") == []


def test_hybrid_then_reranking_keeps_every_stage_of_provenance():
    hybrid = HybridRetriever(
        StubRetriever(ranked(BM25, [A, B, C], [7.5, 4.0, 1.5])),
        StubRetriever(ranked(DENSE, [C, A, D], [0.91, 0.88, 0.80])),
    )
    assert ids(hybrid.search("query", top_k=4)) == ["chunk-A", "chunk-C", "chunk-B", "chunk-D"]
    engine = RerankingRetriever(hybrid, reranker({"A": 0.1, "B": 0.4, "C": 0.3, "D": 0.2}))
    results = {p.chunk.chunk_id: p for p in engine.search("query", top_k=4)}

    a = results["chunk-A"]
    assert a.chunk is A  # which chunk, and through it which source
    assert a.chunk.location.source_path == "data/raw/doc.txt"
    assert (a.method, a.rank, a.score) == (RERANKED, 4, 0.1)  # the reranker's rank and score
    assert (a.method_ranks[HYBRID], a.method_scores[HYBRID]) == (1, pytest.approx(1 / 61 + 1 / 62))
    assert a.method_ranks == {BM25: 1, DENSE: 2, HYBRID: 1}  # which methods returned it
    assert a.method_scores == {BM25: 7.5, DENSE: 0.88, HYBRID: pytest.approx(1 / 61 + 1 / 62)}

    d = results["chunk-D"]  # found by dense retrieval only: BM25 stays absent
    assert d.method_ranks == {DENSE: 3, HYBRID: 4}
    assert d.method_scores == {DENSE: 0.80, HYBRID: pytest.approx(1 / 63)}
    assert (results["chunk-B"].rank, results["chunk-B"].method_ranks) == (1, {BM25: 2, HYBRID: 3})


@pytest.mark.parametrize("method", [BM25, DENSE, HYBRID])
def test_any_first_stage_method_is_recorded_as_the_previous_stage(method):
    candidates = ranked(method, [A, B, C, D], [7.5, 6.0, 4.5, 3.0])
    results = RerankingRetriever(StubRetriever(candidates), reranker(SCORES)).search("query")
    top = results[0]
    assert top.chunk is C
    assert top.method_ranks == {method: 3}
    assert top.method_scores == {method: 4.5}


def test_a_real_bm25_retriever_can_be_wrapped():
    bm25 = BM25Retriever([A, B, C, D, E])
    first_stage = bm25.search("text of C", top_k=3)
    assert len(first_stage) == 3
    engine = RerankingRetriever(bm25, reranker({"A": 1.0, "B": 2.0, "C": 3.0}), candidate_top_k=3)
    results = engine.search("text of C", top_k=3)
    assert sorted(ids(results)) == sorted(ids(first_stage))
    assert all(p.method is RERANKED for p in results)
    for passage in first_stage:
        [result] = [r for r in results if r.chunk is passage.chunk]
        assert result.method_ranks == {BM25: passage.rank}
        assert result.method_scores == {BM25: passage.score}


def test_the_reranking_module_does_not_depend_on_any_particular_retriever():
    tree = ast.parse((PROJECT_ROOT / "src" / "reranking.py").read_text(encoding="utf-8"))
    imported = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    }
    assert {m for m in imported if m.startswith("src")} == {"src.models", "src.retrieval_common"}


@pytest.mark.parametrize(
    "error", [RuntimeError("index unavailable"), OSError("model not found"), ValueError("bad")]
)
def test_retriever_errors_propagate_and_the_reranker_is_not_used(error):
    second = StubReranker()
    with pytest.raises(type(error)) as raised:
        RerankingRetriever(StubRetriever(error=error), second).search("query")
    assert raised.value is error
    assert second.calls == []


@pytest.mark.parametrize("error", [RuntimeError("model crashed"), OSError("model not found")])
def test_reranker_errors_propagate_without_fallback(error):
    engine = RerankingRetriever(StubRetriever(CANDIDATES), StubReranker(error=error))
    with pytest.raises(type(error)) as raised:
        engine.search("query")
    assert raised.value is error  # not an empty list, not the candidates in their first order


def test_an_invalid_scorer_output_is_an_error_not_the_first_stage_order():
    engine = RerankingRetriever(StubRetriever(CANDIDATES), Reranker(scorer=FixedOutputScorer([1.0])))
    with pytest.raises(ValueError, match="scorer returned 1 score"):
        engine.search("query")


def test_a_model_that_cannot_be_loaded_fails_the_search(monkeypatch):
    class Unloadable:
        def __init__(self, *args, **kwargs):
            raise OSError("We couldn't connect to 'https://huggingface.co'")

    module = types.ModuleType("sentence_transformers")
    module.CrossEncoder = Unloadable
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    with pytest.raises(OSError, match="couldn't connect"):
        RerankingRetriever(StubRetriever(CANDIDATES), Reranker()).search("query")


@pytest.mark.parametrize(
    ("top_k", "error", "message"),
    [
        (0, ValueError, "top_k must be >= 1 (got 0)."),
        (-1, ValueError, "top_k must be >= 1 (got -1)."),
        (True, TypeError, "top_k must be an int (got bool)."),
        (2.0, TypeError, "top_k must be an int (got float)."),
        ("3", TypeError, "top_k must be an int (got str)."),
        (None, TypeError, "top_k must be an int (got NoneType)."),
    ],
)
def test_invalid_top_k_is_rejected_before_either_stage_runs(top_k, error, message):
    first, second = StubRetriever(CANDIDATES), StubReranker()
    with pytest.raises(error) as raised:
        RerankingRetriever(first, second).search("query", top_k=top_k)
    assert str(raised.value) == message
    assert first.calls == [] and second.calls == []


@pytest.mark.parametrize(
    ("query", "error", "message"),
    [
        ("", ValueError, "query must not be empty or whitespace."),
        ("   ", ValueError, "query must not be empty or whitespace."),
        (None, TypeError, "query must be a string (got NoneType)."),
        (7, TypeError, "query must be a string (got int)."),
    ],
)
def test_invalid_query_is_rejected_before_either_stage_runs(query, error, message):
    first, second = StubRetriever(CANDIDATES), StubReranker()
    with pytest.raises(error) as raised:
        RerankingRetriever(first, second).search(query)
    assert str(raised.value) == message
    assert first.calls == [] and second.calls == []


@pytest.mark.parametrize(
    ("candidate_top_k", "error", "message"),
    [
        (0, ValueError, "candidate_top_k must be >= 1 (got 0)."),
        (-5, ValueError, "candidate_top_k must be >= 1 (got -5)."),
        (True, TypeError, "candidate_top_k must be an int (got bool)."),
        (20.0, TypeError, "candidate_top_k must be an int (got float)."),
        (None, TypeError, "candidate_top_k must be an int (got NoneType)."),
    ],
)
def test_invalid_candidate_top_k_is_rejected(candidate_top_k, error, message):
    with pytest.raises(error) as raised:
        RerankingRetriever(StubRetriever(), StubReranker(), candidate_top_k=candidate_top_k)
    assert str(raised.value) == message


@pytest.mark.parametrize(("candidate_top_k", "top_k"), [(3, 4), (3, 5), (20, 21), (1, 100)])
def test_top_k_above_candidate_top_k_is_rejected_and_nothing_is_adjusted(candidate_top_k, top_k):
    first, second = StubRetriever(ranked(BM25, MANY)), StubReranker()
    engine = RerankingRetriever(first, second, candidate_top_k=candidate_top_k)
    with pytest.raises(ValueError) as raised:
        engine.search("query", top_k=top_k)
    assert str(raised.value) == (
        f"top_k must be <= candidate_top_k (got top_k={top_k}, candidate_top_k={candidate_top_k})."
    )
    assert first.calls == [] and second.calls == []
    assert engine.candidate_top_k == candidate_top_k


def test_top_k_equal_to_candidate_top_k_is_accepted():
    first, second = StubRetriever(ranked(BM25, MANY)), StubReranker()
    results = RerankingRetriever(first, second, candidate_top_k=4).search("query", top_k=4)
    assert len(results) == 4
    assert (first.calls, second.calls[0][2]) == ([("query", 4)], 4)


def test_the_default_top_k_is_also_checked_against_candidate_top_k():
    engine = RerankingRetriever(StubRetriever(CANDIDATES), StubReranker(), candidate_top_k=3)
    with pytest.raises(ValueError, match=r"got top_k=5, candidate_top_k=3"):
        engine.search("query")


def test_the_candidates_from_the_retriever_are_not_mutated():
    first = StubRetriever(
        reciprocal_rank_fusion(
            {
                BM25: ranked(BM25, [A, B, C], [7.5, 4.0, 1.5]),
                DENSE: ranked(DENSE, [C, A, D], [0.91, 0.88, 0.80]),
            }
        )
    )
    engine = RerankingRetriever(first, reranker({"A": 0.1, "B": 0.4, "C": 0.3, "D": 0.2}))
    snapshot = copy.deepcopy(first.passages)
    results = engine.search("query", top_k=2)

    [returned] = first.returned
    assert returned == snapshot  # same passages, same order, same content
    assert all(now is before for now, before in zip(returned, first.passages))
    assert ids(results) == ["chunk-B", "chunk-C"]
    assert all(result is not candidate for result in results for candidate in returned)


def test_max_results_is_the_candidate_count_capped_by_the_retriever():
    plain = StubRetriever(CANDIDATES)  # no max_results of its own
    assert RerankingRetriever(plain, StubReranker()).max_results == 20
    assert RerankingRetriever(plain, StubReranker(), candidate_top_k=7).max_results == 7

    hybrid = HybridRetriever(StubRetriever(), StubRetriever(), bm25_top_k=4, dense_top_k=5)
    assert RerankingRetriever(hybrid, StubReranker()).max_results == 9
    assert RerankingRetriever(hybrid, StubReranker(), candidate_top_k=6).max_results == 6


def test_describe_combines_both_stages_and_the_candidate_depth():
    hybrid = HybridRetriever(StubRetriever(), StubRetriever(), bm25_top_k=4, dense_top_k=5)
    engine = RerankingRetriever(hybrid, reranker(model_name="fake/model", batch_size=8))
    assert engine.describe() == {
        "fusion": "rrf",
        "rrf_k": 60,
        "bm25_top_k": 4,
        "dense_top_k": 5,
        "reranker_model": "fake/model",
        "reranker_scorer": "FakeScorer",
        "reranker_batch_size": 8,
        "reranker_scores": "raw scorer output; orders passages, not a probability",
        "reranker_candidate_top_k": 20,
    }


def test_describe_works_when_neither_stage_describes_itself():
    engine = RerankingRetriever(StubRetriever(), StubReranker(), candidate_top_k=7)
    assert engine.describe() == {"reranker_candidate_top_k": 7}
