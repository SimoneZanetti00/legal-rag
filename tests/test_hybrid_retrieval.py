"""Hybrid retrieval tests. Everything is offline: fusion is tested on fixed lists,
`HybridRetriever` on stub retrievers and on the real BM25 retriever with a fake
dense encoder. The only real-model test is opt-in (RUN_REAL_MODEL_TESTS=1)."""

import hashlib
import json
import math
import os
import re
import sys
import types
from dataclasses import replace

import numpy as np
import pytest

from src.chunk_store import read_chunks
from src.config import PROJECT_ROOT, Settings
from src.dense_retrieval import DEFAULT_MODEL, DenseRetriever, SentenceTransformerEncoder
from src.hybrid_retrieval import (
    DEFAULT_BM25_TOP_K,
    DEFAULT_DENSE_TOP_K,
    DEFAULT_RRF_K,
    HybridRetriever,
    main,
    reciprocal_rank_fusion,
)
from src.models import LegalChunk, RetrievalMethod, RetrievedPassage, SourceLocation
from src.retrieval import BM25Retriever
from src.retrieval_eval import main as eval_main
from src.retrieval_eval import run_evaluation

BM25, DENSE, HYBRID = RetrievalMethod.BM25, RetrievalMethod.DENSE, RetrievalMethod.HYBRID
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "synthetic_retrieval"
FIXTURE_CHUNKS = FIXTURE / "chunks.jsonl"
FIXTURE_FILES = (FIXTURE_CHUNKS, FIXTURE / "queries.jsonl", FIXTURE / "qrels.jsonl")
E5_NAME = "fake/multilingual-e5-test"


def chunk(name: str, text: str | None = None) -> LegalChunk:
    return LegalChunk(
        chunk_id=f"chunk-{name}",
        doc_id="doc",
        text=text or f"text of {name}",
        chunk_index=0,
        location=SourceLocation(source_path="data/raw/doc.txt", article=name),
    )


A, B, C, D, X, Y = (chunk(n) for n in "ABCDXY")


def ranked(method: RetrievalMethod, chunks, scores=None) -> list[RetrievedPassage]:
    """A ranked list as a retriever would return it; scores default to 10, 9, 8, ..."""
    scores = scores or [10.0 - i for i in range(len(chunks))]
    return [
        RetrievedPassage(chunk=c, method=method, rank=i, score=s)
        for i, (c, s) in enumerate(zip(chunks, scores), start=1)
    ]


def ids(results) -> list[str]:
    return [p.chunk.chunk_id for p in results]


class StubRetriever:
    """Returns a fixed ranking (or raises) and records how it was called."""

    def __init__(self, method: RetrievalMethod, chunks=(), error: Exception | None = None):
        self.method, self.chunks, self.error = method, list(chunks), error
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, top_k: int = 5) -> list[RetrievedPassage]:
        self.calls.append((query, top_k))
        if self.error is not None:
            raise self.error
        return ranked(self.method, self.chunks)[:top_k]


def hybrid(bm25_chunks=(), dense_chunks=(), **kwargs) -> HybridRetriever:
    return HybridRetriever(
        StubRetriever(BM25, bm25_chunks), StubRetriever(DENSE, dense_chunks), **kwargs
    )


# --- Reciprocal rank fusion: the formula ------------------------------------------------


def test_rrf_hand_computed_example():
    fused = reciprocal_rank_fusion(
        {
            BM25: ranked(BM25, [A, B, C], [7.5, 4.0, 1.5]),
            DENSE: ranked(DENSE, [C, A, D], [0.91, 0.88, 0.80]),
        }
    )
    assert ids(fused) == ["chunk-A", "chunk-C", "chunk-B", "chunk-D"]
    assert [p.score for p in fused] == pytest.approx(
        [1 / 61 + 1 / 62, 1 / 63 + 1 / 61, 1 / 62, 1 / 63]
    )
    assert [p.rank for p in fused] == [1, 2, 3, 4]
    assert all(p.method is HYBRID for p in fused)


def test_rrf_default_constant_is_60():
    [only] = reciprocal_rank_fusion({BM25: ranked(BM25, [A])})
    assert only.score == 1 / 61
    assert DEFAULT_RRF_K == 60


def x_ranks_above_y(results) -> bool:
    order = ids(results)
    return order.index("chunk-X") < order.index("chunk-Y")


# X is first in one list only; Y is fourth in both lists.
X_FIRST_ONCE_Y_FOURTH_TWICE = ([X, A, B, Y], [C, D, chunk("E"), Y])


def test_rrf_k_changes_how_much_rank_position_matters():
    bm25, dense = X_FIRST_ONCE_Y_FOURTH_TWICE
    lists = {BM25: ranked(BM25, bm25), DENSE: ranked(DENSE, dense)}
    # Large constant: positions matter little, so appearing in both lists wins (2/64 > 1/61).
    assert not x_ranks_above_y(reciprocal_rank_fusion(lists, rrf_k=60))
    # Small constant: a first place outweighs two fourth places (1/2 > 2/5).
    assert x_ranks_above_y(reciprocal_rank_fusion(lists, rrf_k=1))


def test_with_default_settings_a_chunk_in_both_lists_beats_any_single_list_chunk():
    fillers = [chunk(f"f{i:02d}") for i in range(40)]
    both = chunk("both")
    bm25 = [X] + fillers[:18] + [both]  # X first; `both` last at depth 20
    dense = fillers[20:39] + [both]
    assert len(bm25) == DEFAULT_BM25_TOP_K and len(dense) == DEFAULT_DENSE_TOP_K
    fused = reciprocal_rank_fusion({BM25: ranked(BM25, bm25), DENSE: ranked(DENSE, dense)})
    assert fused[0].chunk is both  # 2/80 > 1/61
    assert fused[0].score == pytest.approx(2 / 80)


# --- Merging, per-method ranks and scores -----------------------------------------------


def test_chunk_in_both_lists_is_merged_with_both_ranks_and_scores():
    fused = reciprocal_rank_fusion(
        {BM25: ranked(BM25, [A, B], [7.5, 4.0]), DENSE: ranked(DENSE, [B, C], [0.91, 0.88])}
    )
    assert ids(fused).count("chunk-B") == 1
    merged = next(p for p in fused if p.chunk is B)
    assert merged.score == pytest.approx(1 / 62 + 1 / 61)
    assert merged.method_ranks == {BM25: 2, DENSE: 1}
    assert merged.method_scores == {BM25: 4.0, DENSE: 0.91}


def test_single_list_chunks_record_only_their_own_method():
    fused = {p.chunk.chunk_id: p for p in reciprocal_rank_fusion(
        {BM25: ranked(BM25, [A], [7.5]), DENSE: ranked(DENSE, [C], [0.9])}
    )}
    assert fused["chunk-A"].method_ranks == {BM25: 1}
    assert fused["chunk-A"].method_scores == {BM25: 7.5}
    assert fused["chunk-C"].method_ranks == {DENSE: 1}
    assert DENSE not in fused["chunk-A"].method_ranks  # visible that dense did not return it


def test_results_keep_the_original_chunk_object():
    fused = reciprocal_rank_fusion({BM25: ranked(BM25, [A]), DENSE: ranked(DENSE, [A, B])})
    assert fused[0].chunk is A
    assert fused[1].chunk is B
    assert isinstance(fused[0].score, float)


def test_inputs_are_not_modified():
    bm25, dense = ranked(BM25, [A, B]), ranked(DENSE, [B, A])
    before = (list(bm25), list(dense))
    reciprocal_rank_fusion({BM25: bm25, DENSE: dense})
    assert (bm25, dense) == before
    assert bm25[0].method is BM25 and bm25[0].method_ranks == {}


# --- Empty and missing lists ----------------------------------------------------------------


def test_empty_bm25_list_returns_the_dense_order():
    fused = reciprocal_rank_fusion({BM25: [], DENSE: ranked(DENSE, [C, A, D])})
    assert ids(fused) == ["chunk-C", "chunk-A", "chunk-D"]
    assert all(p.method_ranks.keys() == {DENSE} for p in fused)
    assert [p.score for p in fused] == [1 / 61, 1 / 62, 1 / 63]


def test_empty_dense_list_returns_the_bm25_order():
    fused = reciprocal_rank_fusion({BM25: ranked(BM25, [B, A]), DENSE: []})
    assert ids(fused) == ["chunk-B", "chunk-A"]
    assert all(p.method_ranks.keys() == {BM25} for p in fused)


@pytest.mark.parametrize("lists", [{}, {BM25: []}, {BM25: [], DENSE: []}])
def test_no_candidates_returns_nothing(lists):
    assert reciprocal_rank_fusion(lists) == []


# --- Ties and determinism -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("bm25", "dense"),
    [([A, B], [B, A]), ([B, A], [A, B])],
)
def test_symmetric_tie_is_broken_by_chunk_id(bm25, dense):
    fused = reciprocal_rank_fusion({BM25: ranked(BM25, bm25), DENSE: ranked(DENSE, dense)})
    assert fused[0].score == fused[1].score  # exactly equal, not merely close
    assert ids(fused) == ["chunk-A", "chunk-B"]


@pytest.mark.parametrize(("bm25", "dense"), [([Y], [X]), ([X], [Y])])
def test_single_list_tie_is_broken_by_chunk_id(bm25, dense):
    fused = reciprocal_rank_fusion({BM25: ranked(BM25, bm25), DENSE: ranked(DENSE, dense)})
    assert fused[0].score == fused[1].score == 1 / 61
    assert ids(fused) == ["chunk-X", "chunk-Y"]


def test_result_does_not_depend_on_the_order_of_the_lists():
    bm25, dense = ranked(BM25, [A, B, C, X]), ranked(DENSE, [C, Y, A, D])
    assert reciprocal_rank_fusion({BM25: bm25, DENSE: dense}) == reciprocal_rank_fusion(
        {DENSE: dense, BM25: bm25}
    )


def test_fusion_is_repeatable():
    lists = {BM25: ranked(BM25, [A, B, C]), DENSE: ranked(DENSE, [C, A, D])}
    assert reciprocal_rank_fusion(lists) == reciprocal_rank_fusion(lists)


# --- Duplicates and mismatched corpora ------------------------------------------------------


def test_repeated_chunk_id_in_one_list_counts_once_at_its_first_position():
    fused = {p.chunk.chunk_id: p for p in reciprocal_rank_fusion({BM25: ranked(BM25, [A, A, B])})}
    assert len(fused) == 2
    assert fused["chunk-A"].method_ranks == {BM25: 1}
    assert fused["chunk-A"].score == 1 / 61  # not doubled
    assert fused["chunk-B"].method_ranks == {BM25: 3}  # the repeat still took position 2


def test_same_chunk_id_with_different_content_is_rejected():
    altered = replace(A, text="different text under the same ID")
    with pytest.raises(ValueError, match="chunk 'chunk-A' has different content"):
        reciprocal_rank_fusion({BM25: ranked(BM25, [A]), DENSE: ranked(DENSE, [altered])})


def test_equal_chunks_from_separately_loaded_corpora_are_accepted():
    first, second = list(read_chunks(FIXTURE_CHUNKS)), list(read_chunks(FIXTURE_CHUNKS))
    assert first[0] is not second[0]
    fused = reciprocal_rank_fusion(
        {BM25: ranked(BM25, first[:2]), DENSE: ranked(DENSE, second[:2])}
    )
    assert len(fused) == 2


# --- top_k and argument validation of the function -----------------------------------------


def test_top_k_truncates_after_fusion():
    lists = {BM25: ranked(BM25, [A, B, C]), DENSE: ranked(DENSE, [C, A, D])}
    everything = reciprocal_rank_fusion(lists)
    assert reciprocal_rank_fusion(lists, top_k=2) == everything[:2]
    assert reciprocal_rank_fusion(lists, top_k=100) == everything  # fewer than top_k: no padding


@pytest.mark.parametrize(("name", "value", "error"), [
    ("rrf_k", 0, ValueError), ("rrf_k", -1, ValueError), ("rrf_k", True, TypeError),
    ("rrf_k", 60.0, TypeError), ("rrf_k", "60", TypeError),
    ("top_k", 0, ValueError), ("top_k", False, TypeError), ("top_k", 2.0, TypeError),
])
def test_rrf_rejects_invalid_parameters(name, value, error):
    with pytest.raises(error, match=name):
        reciprocal_rank_fusion({BM25: ranked(BM25, [A])}, **{name: value})


# --- HybridRetriever on stub retrievers -------------------------------------------------------


def test_search_fuses_both_retrievers():
    results = hybrid([A, B, C], [C, A, D]).search("any query", top_k=10)
    assert ids(results) == ["chunk-A", "chunk-C", "chunk-B", "chunk-D"]
    assert results[0].method is HYBRID
    assert results[0].method_ranks == {BM25: 1, DENSE: 2}
    assert results[0].chunk is A


def test_defaults_match_the_configuration_defaults():
    settings = Settings()
    retriever = hybrid()
    assert (retriever.bm25_top_k, retriever.dense_top_k, retriever.rrf_k) == (
        settings.bm25_top_k, settings.dense_top_k, settings.rrf_k,
    ) == (DEFAULT_BM25_TOP_K, DEFAULT_DENSE_TOP_K, DEFAULT_RRF_K)


@pytest.mark.parametrize("top_k", [1, 5, 500])
def test_candidate_depths_do_not_depend_on_top_k(top_k):
    bm25, dense = StubRetriever(BM25, [A, B]), StubRetriever(DENSE, [B, C])
    HybridRetriever(bm25, dense, bm25_top_k=7, dense_top_k=9).search("query text", top_k=top_k)
    assert bm25.calls == [("query text", 7)]
    assert dense.calls == [("query text", 9)]


def test_candidate_depth_limits_what_each_retriever_contributes():
    retriever = hybrid([A, B, C], [D, X, Y], bm25_top_k=1, dense_top_k=2)
    assert set(ids(retriever.search("q", top_k=10))) == {"chunk-A", "chunk-D", "chunk-X"}


def test_rrf_k_is_passed_to_the_fusion():
    assert not x_ranks_above_y(hybrid(*X_FIRST_ONCE_Y_FOURTH_TWICE, rrf_k=60).search("q", top_k=10))
    assert x_ranks_above_y(hybrid(*X_FIRST_ONCE_Y_FOURTH_TWICE, rrf_k=1).search("q", top_k=10))


def test_top_k_truncation_and_prefix_consistency():
    retriever = hybrid([A, B, C, X], [C, Y, A, D])
    ten = retriever.search("q", top_k=10)
    assert len(ten) == 6
    assert [p.rank for p in ten] == [1, 2, 3, 4, 5, 6]
    assert retriever.search("q", top_k=3) == ten[:3]
    assert retriever.search("q", top_k=1) == ten[:1]


def test_fewer_than_top_k_results_are_not_padded():
    assert len(hybrid([A], [A, B]).search("q", top_k=10)) == 2


def test_only_dense_returns_results():
    results = hybrid([], [C, A]).search("q")
    assert ids(results) == ["chunk-C", "chunk-A"]
    assert all(BM25 not in p.method_ranks for p in results)  # BM25 visibly contributed nothing


def test_only_bm25_returns_results():
    results = hybrid([B, A], []).search("q")
    assert ids(results) == ["chunk-B", "chunk-A"]
    assert all(DENSE not in p.method_ranks for p in results)


def test_both_retrievers_empty_returns_nothing():
    assert hybrid([], []).search("q") == []


def test_search_is_repeatable():
    retriever = hybrid([A, B, C], [C, A, D])
    assert retriever.search("q") == retriever.search("q")


@pytest.mark.parametrize("failing", ["bm25", "dense"])
def test_retriever_errors_propagate_without_fallback(failing):
    error = OSError("embedding model could not be loaded")
    bm25 = StubRetriever(BM25, [A, B], error=error if failing == "bm25" else None)
    dense = StubRetriever(DENSE, [B, C], error=error if failing == "dense" else None)
    with pytest.raises(OSError, match="could not be loaded"):
        HybridRetriever(bm25, dense).search("q")


def test_mismatched_corpora_are_detected_in_search():
    altered = replace(A, text="another corpus")
    with pytest.raises(ValueError, match="different content"):
        hybrid([A], [altered]).search("q")


def test_disjoint_corpora_are_not_detected():
    # Documented limit: only a chunk ID returned by both retrievers is compared.
    # Corpora that share no chunk ID are fused as if they were one corpus.
    results = hybrid([A, B], [X, Y]).search("q", top_k=10)
    assert set(ids(results)) == {"chunk-A", "chunk-B", "chunk-X", "chunk-Y"}
    assert all(len(p.method_ranks) == 1 for p in results)


def test_max_results_is_the_sum_of_the_candidate_depths():
    assert hybrid().max_results == DEFAULT_BM25_TOP_K + DEFAULT_DENSE_TOP_K == 40
    retriever = hybrid([A, B, C], [D, X, Y], bm25_top_k=2, dense_top_k=1)
    assert retriever.max_results == 3
    assert len(retriever.search("q", top_k=100)) == 3


@pytest.mark.parametrize("parameter", ["bm25_top_k", "dense_top_k", "rrf_k"])
@pytest.mark.parametrize(("value", "error"), [
    (0, ValueError), (-3, ValueError), (True, TypeError), (1.5, TypeError), ("20", TypeError),
    (None, TypeError),
])
def test_constructor_rejects_invalid_parameters(parameter, value, error):
    with pytest.raises(error, match=parameter):
        hybrid(**{parameter: value})


def test_describe_combines_fusion_settings_with_the_dense_details():
    assert hybrid(rrf_k=10, bm25_top_k=3, dense_top_k=4).describe() == {
        "fusion": "rrf", "rrf_k": 10, "bm25_top_k": 3, "dense_top_k": 4,
    }


# --- Real BM25 retriever with a fake dense encoder ------------------------------------------


def bag_of_words(text: str, dim: int = 512) -> np.ndarray:
    """Deterministic stand-in for an embedding: hashed word counts, prefixes ignored."""
    vector = np.zeros(dim, dtype=np.float32)
    for word in re.findall(r"\w+", text.lower()):
        if word not in {"query", "passage"}:
            vector[int(hashlib.sha256(word.encode()).hexdigest(), 16) % dim] += 1
    return vector


class FakeEncoder:
    def encode(self, texts: list[str]) -> np.ndarray:
        return np.stack([bag_of_words(t) for t in texts])


@pytest.fixture
def fixture_retriever() -> HybridRetriever:
    return HybridRetriever.from_jsonl(FIXTURE_CHUNKS, encoder=FakeEncoder(), model_name=E5_NAME)


def test_from_jsonl_builds_both_retrievers(fixture_retriever, tmp_path):
    assert len(fixture_retriever) == 9
    assert fixture_retriever.describe()["model"] == E5_NAME
    assert fixture_retriever.describe()["fusion"] == "rrf"
    with pytest.raises(FileNotFoundError, match="src.ingestion"):
        HybridRetriever.from_jsonl(tmp_path / "missing.jsonl", encoder=FakeEncoder())


def test_real_bm25_and_fake_dense_results_are_consistent_with_their_sources(fixture_retriever):
    chunks = list(read_chunks(FIXTURE_CHUNKS))
    bm25 = BM25Retriever(chunks).search("obblighi del datore di lavoro", top_k=20)
    dense = DenseRetriever(chunks, encoder=FakeEncoder(), model_name=E5_NAME).search(
        "obblighi del datore di lavoro", top_k=20
    )
    bm25_rank = {p.chunk.chunk_id: p for p in bm25}
    dense_rank = {p.chunk.chunk_id: p for p in dense}

    results = fixture_retriever.search("obblighi del datore di lavoro", top_k=20)
    assert set(ids(results)) == set(bm25_rank) | set(dense_rank)
    assert len(ids(results)) == len(set(ids(results)))
    sources = ((BM25, bm25_rank), (DENSE, dense_rank))
    for p in results:
        cid = p.chunk.chunk_id
        expected_ranks = {m: r[cid].rank for m, r in sources if cid in r}
        assert p.method_ranks == expected_ranks
        assert p.method_scores == {m: r[cid].score for m, r in sources if cid in r}
        assert p.score == pytest.approx(sum(1 / (60 + r) for r in expected_ranks.values()))
        assert p.chunk == (bm25_rank.get(cid) or dense_rank[cid]).chunk  # provenance preserved
    scores = [p.score for p in results]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.parametrize("query", [
    "obblighi del datore di lavoro", "data breach notification 72 hours", "sanzione amministrativa",
])
def test_prefix_consistency_on_the_fixture(fixture_retriever, query):
    ten = fixture_retriever.search(query, top_k=10)
    assert fixture_retriever.search(query, top_k=3) == ten[:3]
    assert fixture_retriever.search(query, top_k=5) == ten[:5]


def test_query_without_lexical_match_still_returns_dense_results(fixture_retriever):
    results = fixture_retriever.search("licenziamento", top_k=3)  # no chunk contains this word
    assert len(results) == 3
    assert all(p.method_ranks.keys() == {DENSE} for p in results)


def test_empty_corpus_returns_nothing():
    retriever = HybridRetriever(BM25Retriever([]), DenseRetriever([], encoder=FakeEncoder()))
    assert len(retriever) == 0
    assert retriever.search("lavoro") == []


@pytest.mark.parametrize(
    ("query", "top_k"),
    [("", 5), ("   ", 5), (None, 5), (7, 5), ("lavoro", 0), ("lavoro", -2),
     ("lavoro", True), ("lavoro", 2.0), ("lavoro", "3")],
)
def test_invalid_arguments_are_rejected_like_the_other_retrievers(fixture_retriever, query, top_k):
    chunks = list(read_chunks(FIXTURE_CHUNKS))
    errors = []
    for retriever in (
        BM25Retriever(chunks),
        DenseRetriever(chunks, encoder=FakeEncoder(), model_name=E5_NAME),
        fixture_retriever,
    ):
        with pytest.raises((TypeError, ValueError)) as caught:
            retriever.search(query, top_k=top_k)
        errors.append((type(caught.value), str(caught.value)))
    assert errors[0] == errors[1] == errors[2]


def test_invalid_query_is_rejected_before_any_retriever_is_called():
    bm25, dense = StubRetriever(BM25, [A]), StubRetriever(DENSE, [A])
    with pytest.raises(ValueError, match="query"):
        HybridRetriever(bm25, dense).search("   ")
    with pytest.raises(TypeError, match="top_k"):
        HybridRetriever(bm25, dense).search("ok", top_k=True)
    assert bm25.calls == [] and dense.calls == []


# --- Evaluation integration and configuration -----------------------------------------------


@pytest.fixture
def fake_sentence_transformers(monkeypatch):
    """Replace the sentence_transformers module with a deterministic fake."""

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, local_files_only: bool = False) -> None:
            self.model_name = model_name

        def encode(self, texts, **kwargs):
            vectors = np.stack([bag_of_words(t) for t in texts])
            return vectors / np.linalg.norm(vectors, axis=1, keepdims=True).clip(min=1e-12)

    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)


@pytest.fixture
def hybrid_settings(monkeypatch, tmp_path, fake_sentence_transformers):
    """Fake model, a temporary index directory, and explicit hybrid settings.

    The three hybrid settings are set, not removed: an unset variable would be
    filled in from a developer's local .env file by `load_settings`.
    """
    monkeypatch.setenv("EMBEDDING_MODEL", E5_NAME)
    monkeypatch.setenv("INDEX_DIR", str(tmp_path / "indexes"))
    monkeypatch.setenv("BM25_TOP_K", "20")
    monkeypatch.setenv("DENSE_TOP_K", "20")
    monkeypatch.setenv("RRF_K", "60")
    return tmp_path / "indexes" / "embeddings"


def test_hybrid_settings_ignore_a_local_env_file(hybrid_settings, monkeypatch, tmp_path):
    # Stand-in for a developer's .env in the project root.
    (tmp_path / ".env").write_text("BM25_TOP_K=3\nDENSE_TOP_K=4\nRRF_K=7\n", encoding="utf-8")
    monkeypatch.setattr("src.config.PROJECT_ROOT", tmp_path)

    details = run_evaluation("hybrid", *FIXTURE_FILES, [5])["retriever_details"]
    assert (details["bm25_top_k"], details["dense_top_k"], details["rrf_k"]) == (20, 20, 60)


def test_hybrid_is_available_in_the_evaluator(hybrid_settings):
    report = run_evaluation("hybrid", *FIXTURE_FILES, [1, 5])
    assert report["retriever"] == "hybrid"
    assert report["retriever_details"] == {
        "model": E5_NAME, "query_prefix": "query: ", "passage_prefix": "passage: ",
        "similarity": "cosine", "fusion": "rrf", "rrf_k": 60, "bm25_top_k": 20, "dense_top_k": 20,
    }
    assert report["queries_evaluated"] == 4
    assert report["queries_skipped"] == ["synthetic-q05", "synthetic-q06"]
    assert set(report["metrics"]) == {f"{m}@{k}" for m in ("recall", "mrr", "ndcg") for k in (1, 5)}
    assert all(0.0 <= value <= 1.0 for value in report["metrics"].values())


def test_hybrid_evaluation_is_deterministic_across_cache_miss_and_hit(hybrid_settings):
    first = run_evaluation("hybrid", *FIXTURE_FILES, [1, 5, 10])
    second = run_evaluation("hybrid", *FIXTURE_FILES, [1, 5, 10])  # embeddings from the cache
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert len(list(hybrid_settings.glob("*.npy"))) == 1


def test_the_three_retrievers_share_dataset_and_metrics(hybrid_settings):
    names = ("bm25", "dense", "hybrid")
    reports = {name: run_evaluation(name, *FIXTURE_FILES, [5]) for name in names}
    assert len({json.dumps(r["config"], sort_keys=True) for r in reports.values()}) == 1
    assert len({tuple(sorted(r["metrics"])) for r in reports.values()}) == 1
    assert len({tuple(r["queries_skipped"]) for r in reports.values()}) == 1
    assert reports["bm25"]["metrics"]["recall@5"] == pytest.approx(0.625)  # BM25 is unchanged
    assert reports["bm25"]["retriever_details"] == {}


def test_configuration_reaches_the_evaluated_hybrid_retriever(hybrid_settings, monkeypatch):
    monkeypatch.setenv("BM25_TOP_K", "2")
    monkeypatch.setenv("DENSE_TOP_K", "3")
    monkeypatch.setenv("RRF_K", "7")
    report = run_evaluation("hybrid", *FIXTURE_FILES, [10])
    details = report["retriever_details"]
    assert (details["bm25_top_k"], details["dense_top_k"], details["rrf_k"]) == (2, 3, 7)
    for entry in report["per_query"]:
        assert len(entry.get("retrieved", [])) <= 2 + 3  # candidate depths bound the output


def small_depths(monkeypatch) -> None:
    """Hybrid can return at most 2 + 3 = 5 results."""
    monkeypatch.setenv("BM25_TOP_K", "2")
    monkeypatch.setenv("DENSE_TOP_K", "3")


def test_cutoff_above_the_hybrid_candidate_depth_is_flagged(hybrid_settings, monkeypatch):
    small_depths(monkeypatch)
    report = run_evaluation("hybrid", *FIXTURE_FILES, [1, 5, 8, 10])

    [warning] = report["warnings"]
    assert "hybrid retriever returns at most 5 results" in warning
    assert "@8, @10" in warning and "@5" not in warning  # 5 is still within reach
    assert "cannot be compared directly" in warning
    # The evaluation still completes, for every cutoff.
    assert report["queries_evaluated"] == 4
    assert {"recall@8", "recall@10", "mrr@10", "ndcg@10"} <= set(report["metrics"])
    assert all(len(e.get("retrieved", [])) <= 5 for e in report["per_query"])


def test_the_warning_does_not_change_any_result(hybrid_settings, monkeypatch):
    small_depths(monkeypatch)
    flagged = run_evaluation("hybrid", *FIXTURE_FILES, [1, 5, 10])
    unflagged = run_evaluation("hybrid", *FIXTURE_FILES, [1, 5])
    assert flagged["warnings"] and not unflagged["warnings"]
    for name, value in unflagged["metrics"].items():
        assert flagged["metrics"][name] == value
    # Beyond the 5 results available, a larger cutoff adds nothing.
    assert flagged["metrics"]["recall@10"] == flagged["metrics"]["recall@5"]
    retrieved = [e.get("retrieved") for e in flagged["per_query"]]
    assert retrieved == [e.get("retrieved") for e in unflagged["per_query"]]


def test_no_cutoff_warning_within_reach_or_for_other_retrievers(hybrid_settings):
    assert run_evaluation("hybrid", *FIXTURE_FILES, [1, 5, 10, 40])["warnings"] == []
    assert run_evaluation("hybrid", *FIXTURE_FILES, [41])["warnings"] != []
    assert run_evaluation("bm25", *FIXTURE_FILES, [1000])["warnings"] == []
    assert run_evaluation("dense", *FIXTURE_FILES, [1000])["warnings"] == []


def test_evaluator_cli_prints_the_cutoff_warning_and_still_succeeds(
    hybrid_settings, monkeypatch, capsys, tmp_path
):
    small_depths(monkeypatch)
    output = tmp_path / "report.json"
    args = ["--retriever", "hybrid", "--k", "5", "10", "--chunks", str(FIXTURE_FILES[0]),
            "--queries", str(FIXTURE_FILES[1]), "--qrels", str(FIXTURE_FILES[2]),
            "--output", str(output)]
    assert eval_main(args) == 0
    out = capsys.readouterr().out
    assert "WARNING: The hybrid retriever returns at most 5 results per query" in out
    assert "recall" in out and "Per query (@10)" in out  # the tables are still printed
    assert json.loads(output.read_text(encoding="utf-8"))["warnings"] != []


def test_invalid_configuration_is_rejected_by_the_evaluator(hybrid_settings, monkeypatch, capsys):
    monkeypatch.setenv("RRF_K", "0")
    args = ["--retriever", "hybrid", "--chunks", str(FIXTURE_FILES[0]),
            "--queries", str(FIXTURE_FILES[1]), "--qrels", str(FIXTURE_FILES[2])]
    assert eval_main(args) == 2
    assert "RRF_K must be a positive integer" in capsys.readouterr().err


def test_evaluator_cli_with_hybrid(hybrid_settings, capsys, tmp_path):
    output = tmp_path / "report.json"
    args = ["--retriever", "hybrid", "--chunks", str(FIXTURE_FILES[0]),
            "--queries", str(FIXTURE_FILES[1]), "--qrels", str(FIXTURE_FILES[2]),
            "--output", str(output)]
    assert eval_main(args) == 0
    out = capsys.readouterr().out
    assert "Retriever: hybrid" in out
    assert f"Model:     {E5_NAME}" in out
    assert json.loads(output.read_text(encoding="utf-8"))["retriever_details"]["fusion"] == "rrf"


# --- CLI --------------------------------------------------------------------------------------


def test_cli_prints_fused_results_with_their_sources(hybrid_settings, capsys):
    args = ["obblighi del datore di lavoro", "--chunks", str(FIXTURE_CHUNKS), "--top-k", "2"]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert f"Indexed 9 chunk(s) from {FIXTURE_CHUNKS} with {E5_NAME} (embedding cache: miss)" in out
    assert "(depth 20), dense 9 (depth 20); fusion: RRF, rrf_k=60" in out
    assert "#1  score=" in out and "#2  score=" in out and "#3  score=" not in out
    assert "from: bm25 #" in out and "| dense #" in out
    assert "synthetic/legge_sintetica.txt" in out


def test_cli_says_when_bm25_returns_nothing(hybrid_settings, capsys):
    assert main(["licenziamento", "--chunks", str(FIXTURE_CHUNKS), "--no-cache"]) == 0
    out = capsys.readouterr().out
    assert "Candidates: BM25 0 (depth 20), dense 9 (depth 20)" in out
    assert "BM25 returned no candidates" in out
    assert "from: dense #1" in out and "bm25 #" not in out
    assert "(embedding cache: disabled)" in out
    assert not hybrid_settings.exists()


def test_cli_on_an_empty_corpus_says_the_corpus_is_empty(hybrid_settings, capsys, tmp_path):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert main(["datore di lavoro", "--chunks", str(empty), "--no-cache"]) == 0
    out = capsys.readouterr().out
    assert "Indexed 0 chunk(s)" in out
    assert "The corpus is empty: the chunk file contains no chunks." in out
    assert "No results." in out
    # Neither retriever is blamed for finding nothing in an empty corpus.
    assert "no chunk shares a word" not in out
    assert "Dense retrieval returned no candidates" not in out


def test_cli_uses_the_configured_depths_and_constant(hybrid_settings, monkeypatch, capsys):
    monkeypatch.setenv("BM25_TOP_K", "1")
    monkeypatch.setenv("DENSE_TOP_K", "2")
    monkeypatch.setenv("RRF_K", "7")
    assert main(["datore di lavoro", "--chunks", str(FIXTURE_CHUNKS), "--top-k", "10"]) == 0
    out = capsys.readouterr().out
    assert "Candidates: BM25 1 (depth 1), dense 2 (depth 2); fusion: RRF, rrf_k=7" in out
    assert out.count("  score=") <= 3


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["x", "--chunks", "MISSING"], "chunk file not found"),
        (["x", "--top-k", "0"], "top_k must be >= 1"),
        (["  "], "query must not be empty"),
    ],
)
def test_cli_errors_exit_2(hybrid_settings, capsys, tmp_path, args, message):
    args = [str(tmp_path / "missing.jsonl") if a == "MISSING" else a for a in args]
    if "--chunks" not in args:
        args += ["--chunks", str(FIXTURE_CHUNKS)]
    assert main(args) == 2
    assert message in capsys.readouterr().err


def test_cli_model_load_failure_exit_2_without_fallback(monkeypatch, tmp_path, capsys):
    class Unloadable:
        def __init__(self, *args, **kwargs):
            raise OSError("model not found")

    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = Unloadable
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    monkeypatch.setenv("INDEX_DIR", str(tmp_path))
    assert main(["datore di lavoro", "--chunks", str(FIXTURE_CHUNKS), "--no-cache"]) == 2
    captured = capsys.readouterr()
    assert "could not load embedding model" in captured.err
    assert "score=" not in captured.out  # no BM25-only results were printed


# --- Optional: the real model, only if explicitly requested and already downloaded -------


@pytest.mark.skipif(
    os.environ.get("RUN_REAL_MODEL_TESTS") != "1",
    reason="set RUN_REAL_MODEL_TESTS=1 to run; needs the model already in the Hugging Face cache",
)
def test_real_model_smoke():
    """Checks that hybrid retrieval works with the real model. No ranking is expected."""
    encoder = SentenceTransformerEncoder(DEFAULT_MODEL, local_files_only=True)  # never downloads
    chunks = list(read_chunks(FIXTURE_CHUNKS))
    retriever = HybridRetriever(
        BM25Retriever(chunks), DenseRetriever(chunks, model_name=DEFAULT_MODEL, encoder=encoder)
    )
    for query in ("obblighi del datore di lavoro", "data breach notification", "licenziamento"):
        results = retriever.search(query, top_k=5)
        assert [p.rank for p in results] == [1, 2, 3, 4, 5]
        assert len(set(ids(results))) == 5
        assert all(p.method is HYBRID for p in results)
        scores = [p.score for p in results]
        assert all(math.isfinite(s) and 0 < s <= 2 / 61 for s in scores)
        assert scores == sorted(scores, reverse=True)
        for p in results:
            assert p.method_ranks and p.method_ranks.keys() <= {BM25, DENSE}
            assert p.method_scores.keys() == p.method_ranks.keys()
        assert retriever.search(query, top_k=5) == results
        assert retriever.search(query, top_k=2) == results[:2]
