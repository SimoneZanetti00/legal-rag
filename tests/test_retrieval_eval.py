import hashlib
import json
import math
import re
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from src.chunk_store import read_chunks
from src.config import PROJECT_ROOT
from src.hybrid_retrieval import HybridRetriever
from src.models import LegalChunk, RetrievalMethod, RetrievedPassage
from src.reranking import Reranker, RerankingRetriever
from src.retrieval import BM25Retriever
from src.retrieval_eval import (
    RETRIEVERS,
    EvaluationDataError,
    Query,
    check_judged_chunks_exist,
    evaluate,
    load_qrels,
    load_queries,
    main,
    ndcg_at_k,
    query_metrics,
    recall_at_k,
    reciprocal_rank_at_k,
    run_evaluation,
)

FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "synthetic_retrieval"
CHUNKS, QUERIES, QRELS = FIXTURE / "chunks.jsonl", FIXTURE / "queries.jsonl", FIXTURE / "qrels.jsonl"


def log2_discount(position: int) -> float:
    return 1 / math.log2(position + 1)


# --- Metrics: hand-computed examples -------------------------------------------------

RANKED = ["a", "b", "c", "d"]
GRADES = {"b": 2, "d": 1, "e": 1, "x": 0}  # relevant: b, d, e (e is never retrieved)


def test_recall_hand_computed():
    assert recall_at_k(RANKED, GRADES, 1) == 0
    assert recall_at_k(RANKED, GRADES, 3) == pytest.approx(1 / 3)
    assert recall_at_k(RANKED, GRADES, 4) == pytest.approx(2 / 3)


def test_reciprocal_rank_hand_computed():
    assert reciprocal_rank_at_k(RANKED, GRADES, 1) == 0
    assert reciprocal_rank_at_k(RANKED, GRADES, 2) == 0.5
    assert reciprocal_rank_at_k(RANKED, GRADES, 10) == 0.5


def test_ndcg_hand_computed_with_graded_relevance():
    # DCG@3 = 2/log2(3); ideal order of grades 2, 1, 1 -> IDCG@3 = 2 + 1/log2(3) + 1/log2(4).
    expected = (2 * log2_discount(2)) / (2 + log2_discount(2) + log2_discount(3))
    assert ndcg_at_k(RANKED, GRADES, 3) == pytest.approx(expected)
    # DCG@4 adds d (grade 1) at position 4.
    expected = (2 * log2_discount(2) + log2_discount(4)) / (2 + log2_discount(2) + log2_discount(3))
    assert ndcg_at_k(RANKED, GRADES, 4) == pytest.approx(expected)


def test_perfect_ranking_scores_one():
    grades = {"a": 3, "b": 2, "c": 1}
    assert query_metrics(["a", "b", "c"], grades, [1, 3]) == {
        "recall@1": pytest.approx(1 / 3),
        "mrr@1": 1.0,
        "ndcg@1": 1.0,
        "recall@3": 1.0,
        "mrr@3": 1.0,
        "ndcg@3": 1.0,
    }


def test_order_among_equally_relevant_chunks_does_not_matter():
    grades = {"a": 1, "b": 1}
    assert ndcg_at_k(["a", "b"], grades, 2) == ndcg_at_k(["b", "a"], grades, 2) == 1.0


def test_empty_results_score_zero():
    assert query_metrics([], {"a": 1}, [1, 10]) == {
        "recall@1": 0.0, "mrr@1": 0.0, "ndcg@1": 0.0,
        "recall@10": 0.0, "mrr@10": 0.0, "ndcg@10": 0.0,
    }


def test_fewer_than_k_results_keep_the_full_denominators():
    grades = {"b": 1, "c": 1}
    assert recall_at_k(["b"], grades, 10) == 0.5
    assert ndcg_at_k(["b"], grades, 10) == pytest.approx(1 / (1 + log2_discount(2)))


def test_unjudged_retrieved_chunks_count_as_not_relevant():
    assert reciprocal_rank_at_k(["unjudged", "a"], {"a": 1}, 2) == 0.5


def test_duplicate_ids_count_once_but_keep_their_positions():
    grades = {"b": 1, "d": 1}
    assert recall_at_k(["b", "b"], grades, 2) == 0.5  # no double counting
    assert recall_at_k(["b", "b", "d"], grades, 3) == 1.0
    # The repeat of b takes position 2, so d is found at position 3.
    expected = (1 + log2_discount(3)) / (1 + log2_discount(2))
    assert ndcg_at_k(["b", "b", "d"], grades, 3) == pytest.approx(expected)
    assert recall_at_k(["b", "b", "d"], grades, 2) == 0.5  # d falls outside the top 2


@pytest.mark.parametrize("grades", [{}, {"a": 0, "b": 0}])
def test_queries_without_relevant_judgments_cannot_be_scored(grades):
    for metric in (recall_at_k, reciprocal_rank_at_k, ndcg_at_k):
        with pytest.raises(ValueError, match="no relevant judgments"):
            metric(["a"], grades, 5)


@pytest.mark.parametrize("k", [0, -1, True, 1.5, "5"])
def test_invalid_k_is_rejected(k):
    with pytest.raises(ValueError, match="k must be a positive int"):
        recall_at_k(["a"], {"a": 1}, k)


# --- Loading and validating evaluation data ------------------------------------------


def write_lines(path: Path, *lines: str) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_fixture_loads():
    queries = load_queries(QUERIES)
    assert [q.query_id for q in queries][:2] == ["synthetic-q01", "synthetic-q02"]
    assert queries[1].notes is None
    qrels = load_qrels(QRELS, [q.query_id for q in queries])
    assert qrels["synthetic-q01"] == {"syn-a-0001": 2, "syn-a-0002": 1, "syn-a-0003": 0}
    assert "synthetic-q06" not in qrels


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        (['{"query_id": "q1", "text": "a"', ], "line 1: invalid JSON"),
        (['["q1", "a"]'], "expected a JSON object"),
        (['{"query_id": "q1"}'], "missing key"),
        (['{"query_id": "q1", "text": "a", "txet": "b"}'], "unknown key"),
        (['{"query_id": "", "text": "a"}'], "'query_id' must be a non-empty string"),
        (['{"query_id": "q1", "text": "  "}'], "'text' must be a non-empty string"),
        (['{"query_id": 7, "text": "a"}'], "'query_id' must be a non-empty string"),
        (['{"query_id": "q1", "text": "a", "notes": 3}'], "'notes' must be a string"),
        (
            ['{"query_id": "q1", "text": "a"}', "", '{"query_id": "q1", "text": "b"}'],
            r"line 3: duplicate query_id 'q1' \(first on line 1\)",
        ),
        ([""], "no queries found"),
    ],
)
def test_malformed_queries_are_rejected(tmp_path, lines, message):
    path = write_lines(tmp_path / "queries.jsonl", *lines)
    with pytest.raises(EvaluationDataError, match=message):
        load_queries(path)


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ('{"query_id": "q1", "chunk_id": "c1", "relevance": -1}', "integer >= 0"),
        ('{"query_id": "q1", "chunk_id": "c1", "relevance": 1.5}', "integer >= 0"),
        ('{"query_id": "q1", "chunk_id": "c1", "relevance": "1"}', "integer >= 0"),
        ('{"query_id": "q1", "chunk_id": "c1", "relevance": true}', "integer >= 0"),
        ('{"query_id": "q1", "chunk_id": "c1"}', "missing key"),
        ('{"query_id": "q1", "chunk_id": "c1", "relevance": 1, "grade": 1}', "unknown key"),
        ('{"query_id": "q9", "chunk_id": "c1", "relevance": 1}', "unknown query_id 'q9'"),
        ('{"query_id": "q1", "chunk_id": "", "relevance": 1}', "'chunk_id' must be a non-empty"),
    ],
)
def test_malformed_qrels_are_rejected(tmp_path, line, message):
    path = write_lines(tmp_path / "qrels.jsonl", line)
    with pytest.raises(EvaluationDataError, match=message):
        load_qrels(path, ["q1"])


def test_duplicate_judgment_is_rejected(tmp_path):
    line = '{"query_id": "q1", "chunk_id": "c1", "relevance": 1}'
    path = write_lines(tmp_path / "qrels.jsonl", line, line)
    with pytest.raises(EvaluationDataError, match="line 2: duplicate judgment"):
        load_qrels(path, ["q1"])


def test_missing_evaluation_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="evaluation file not found"):
        load_queries(tmp_path / "missing.jsonl")


def test_judgments_for_unknown_chunks_are_rejected():
    qrels = {"q1": {"c1": 1, "gone-1": 1}, "q2": {"gone-2": 0}}
    with pytest.raises(EvaluationDataError, match=r"2 judged chunk ID\(s\).*gone-1, gone-2.*re-run"):
        check_judged_chunks_exist(qrels, {"c1"})
    check_judged_chunks_exist({"q1": {"c1": 1}}, {"c1"})  # no error


# --- evaluate() with a stand-in retriever ----------------------------------------------


class FixedRetriever:
    """Returns predetermined rankings and records the calls it receives."""

    def __init__(self, rankings: dict[str, list[str]]) -> None:
        self.rankings = rankings
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, top_k: int = 5) -> list[RetrievedPassage]:
        self.calls.append((query, top_k))
        return [
            RetrievedPassage(
                chunk=LegalChunk(chunk_id=cid, doc_id="d", text=cid, chunk_index=i),
                method=RetrievalMethod.BM25,
                rank=i + 1,
                score=1.0,
            )
            for i, cid in enumerate(self.rankings.get(query, [])[:top_k])
        ]


QUERY_SET = [Query("q1", "first"), Query("q2", "second"), Query("q3", "unjudged"), Query("q4", "zeros")]
JUDGMENTS = {"q1": {"a": 1}, "q2": {"b": 1, "c": 1}, "q4": {"a": 0}}


def test_skipped_queries_are_excluded_from_means_and_not_searched():
    retriever = FixedRetriever({"first": ["a"], "second": []})
    report = evaluate(retriever, QUERY_SET, JUDGMENTS, [1])

    assert report["queries_total"] == 4
    assert report["queries_evaluated"] == 2
    assert report["queries_skipped"] == ["q3", "q4"]
    assert [call[0] for call in retriever.calls] == ["first", "second"]
    # q1 is perfect, q2 retrieves nothing: the mean is over two queries, not four.
    assert report["metrics"] == {"recall@1": 0.5, "mrr@1": 0.5, "ndcg@1": 0.5}
    entries = {e["query_id"]: e for e in report["per_query"]}
    assert entries["q2"]["retrieved"] == []
    assert entries["q3"]["skipped"] == "no judgments for this query"
    assert entries["q4"]["skipped"] == "no judgment with relevance >= 1"
    assert "metrics" not in entries["q3"]


def test_each_query_is_searched_once_at_the_largest_k():
    retriever = FixedRetriever({"first": ["x", "y", "a"]})
    report = evaluate(retriever, QUERY_SET[:1], JUDGMENTS, [10, 1, 5, 5])
    assert retriever.calls == [("first", 10)]
    assert report["ks"] == [1, 5, 10]
    assert report["metrics"]["mrr@1"] == 0
    assert report["metrics"]["mrr@5"] == pytest.approx(1 / 3)


def test_duplicates_are_reported_per_query():
    report = evaluate(FixedRetriever({"first": ["a", "a"]}), QUERY_SET[:1], JUDGMENTS, [2])
    assert report["per_query"][0]["duplicates"] == 1
    assert report["metrics"]["recall@2"] == 1.0


def test_nothing_to_evaluate_gives_no_means():
    report = evaluate(FixedRetriever({}), QUERY_SET[2:], JUDGMENTS, [5])
    assert report["queries_evaluated"] == 0
    assert report["metrics"] is None


@pytest.mark.parametrize("ks", [[], [0], [5, -1]])
def test_evaluate_rejects_invalid_ks(ks):
    with pytest.raises(ValueError):
        evaluate(FixedRetriever({}), QUERY_SET, JUDGMENTS, ks)


# --- End to end with BM25 on the synthetic fixture ----------------------------------------


def test_bm25_end_to_end_on_synthetic_fixture():
    report = run_evaluation("bm25", CHUNKS, QUERIES, QRELS, [1, 5])

    assert report["retriever"] == "bm25"
    assert report["config"]["ks"] == [1, 5]
    assert report["config"]["chunk_count"] == 9
    assert report["config"]["chunks"]["path"] == "tests/fixtures/synthetic_retrieval/chunks.jsonl"
    assert len(report["config"]["qrels"]["sha256"]) == 64
    assert report["queries_skipped"] == ["synthetic-q05", "synthetic-q06"]

    per_query = {e["query_id"]: e for e in report["per_query"]}
    q01 = per_query["synthetic-q01"]
    assert q01["retrieved"][:3] == ["syn-a-0001", "syn-a-0003", "syn-a-0002"]
    ndcg_q01 = (2 + log2_discount(3)) / (2 + log2_discount(2))  # grade 0 chunk at position 2
    assert q01["metrics"]["ndcg@5"] == pytest.approx(ndcg_q01)
    assert q01["metrics"]["recall@1"] == 0.5
    assert per_query["synthetic-q03"]["retrieved"] == []  # lexical gap: "licenziamento"
    assert per_query["synthetic-q03"]["metrics"]["recall@5"] == 0
    ndcg_q04 = 1 / (1 + log2_discount(2))
    assert per_query["synthetic-q04"]["metrics"]["ndcg@5"] == pytest.approx(ndcg_q04)

    means = report["metrics"]
    assert means["recall@1"] == pytest.approx((0.5 + 1 + 0 + 0.5) / 4)
    assert means["recall@5"] == pytest.approx((1 + 1 + 0 + 0.5) / 4)
    assert means["mrr@5"] == pytest.approx(3 / 4)
    assert means["ndcg@5"] == pytest.approx((ndcg_q01 + 1 + 0 + ndcg_q04) / 4)


def test_evaluation_is_deterministic():
    first = run_evaluation("bm25", CHUNKS, QUERIES, QRELS, [1, 5, 10])
    second = run_evaluation("bm25", CHUNKS, QUERIES, QRELS, [1, 5, 10])
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_existing_bm25_retriever_satisfies_the_interface():
    chunks = list(read_chunks(CHUNKS))
    queries = load_queries(QUERIES)
    qrels = load_qrels(QRELS, [q.query_id for q in queries])
    direct = evaluate(BM25Retriever(chunks), queries, qrels, [5])
    assert direct["metrics"] == run_evaluation("bm25", CHUNKS, QUERIES, QRELS, [5])["metrics"]


def test_okapi_variant_is_available():
    report = run_evaluation("bm25-okapi", CHUNKS, QUERIES, QRELS, [5])
    assert report["retriever"] == "bm25-okapi"
    assert report["queries_evaluated"] == 4


def test_unknown_retriever_is_rejected():
    with pytest.raises(ValueError, match="unknown retriever 'no-such-retriever'"):
        run_evaluation("no-such-retriever", CHUNKS, QUERIES, QRELS, [5])


def test_stale_judgments_are_detected(tmp_path):
    qrels = write_lines(
        tmp_path / "qrels.jsonl",
        '{"query_id": "synthetic-q01", "chunk_id": "syn-a-0099", "relevance": 1}',
    )
    with pytest.raises(EvaluationDataError, match="not in the chunk file"):
        run_evaluation("bm25", CHUNKS, QUERIES, qrels, [5])


# --- CLI ------------------------------------------------------------------------------


def cli_args(*extra: str) -> list[str]:
    return ["--chunks", str(CHUNKS), "--queries", str(QUERIES), "--qrels", str(QRELS), *extra]


def test_cli_writes_json_and_prints_summary(tmp_path, capsys):
    output = tmp_path / "report.json"
    assert main(cli_args("--k", "1", "5", "--output", str(output))) == 0
    out = capsys.readouterr().out
    assert "Retriever: bm25" in out
    assert "6 total, 4 evaluated, 2 skipped" in out
    assert "synthetic-q05, synthetic-q06" in out
    assert "Scores describe only this query set and corpus." in out

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report == json.loads(json.dumps(run_evaluation("bm25", CHUNKS, QUERIES, QRELS, [1, 5])))


def test_cli_exit_1_when_nothing_can_be_evaluated(tmp_path, capsys):
    qrels = write_lines(tmp_path / "qrels.jsonl", "")
    assert main(["--chunks", str(CHUNKS), "--queries", str(QUERIES), "--qrels", str(qrels)]) == 1
    assert "nothing was evaluated" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (["--k", "0"], "k must be a positive int"),
        (["--output", "report.txt"], ".json extension"),
    ],
)
def test_cli_invalid_arguments_exit_2(capsys, extra, message):
    assert main(cli_args(*extra)) == 2
    assert message in capsys.readouterr().err


def test_cli_missing_chunk_file_exit_2(tmp_path, capsys):
    args = ["--chunks", str(tmp_path / "none.jsonl"), "--queries", str(QUERIES), "--qrels", str(QRELS)]
    assert main(args) == 2
    assert "chunk file not found" in capsys.readouterr().err


# --- hybrid-rerank: the hybrid retriever followed by the reranker ---------------------------
# Both models are fakes. These tests show that the pipeline can be evaluated, not that
# reranking improves anything: the fake scores are arbitrary.

E5_NAME = "intfloat/multilingual-e5-small"
RERANKER_NAME = "fake-org/fake-reranker"
EVALUATED = ["synthetic-q01", "synthetic-q02", "synthetic-q03", "synthetic-q04"]


def fake_embedding(text: str, dim: int = 512) -> np.ndarray:
    """Deterministic stand-in for an embedding: hashed word counts, prefixes ignored."""
    vector = np.zeros(dim, dtype=np.float32)
    for word in re.findall(r"\w+", text.lower()):
        if word not in {"query", "passage"}:
            vector[int(hashlib.sha256(word.encode()).hexdigest(), 16) % dim] += 1
    return vector


def fake_relevance(query: str, text: str) -> float:
    """Deterministic stand-in for a cross-encoder score, unrelated to the hybrid order."""
    return int(hashlib.sha256(f"{query}|{text}".encode()).hexdigest(), 16) % 1000 / 100 - 5


class FakeScorer:
    """A pair scorer to inject into Reranker; records the pairs it scored."""

    def __init__(self) -> None:
        self.pairs: list[tuple[str, str]] = []

    def score(self, query: str, texts: list[str]) -> list[float]:
        self.pairs += [(query, text) for text in texts]
        return [fake_relevance(query, text) for text in texts]


@pytest.fixture
def fake_models(monkeypatch):
    """Replace sentence_transformers with a fake embedder and a fake cross-encoder."""

    class FakeSentenceTransformer:
        instances: list["FakeSentenceTransformer"] = []

        def __init__(self, model_name: str, local_files_only: bool = False) -> None:
            self.model_name = model_name
            FakeSentenceTransformer.instances.append(self)

        def encode(self, texts, **kwargs):
            vectors = np.stack([fake_embedding(t) for t in texts])
            return vectors / np.linalg.norm(vectors, axis=1, keepdims=True).clip(min=1e-12)

    class FakeCrossEncoder:
        instances: list["FakeCrossEncoder"] = []

        def __init__(self, model_name: str, local_files_only: bool = False) -> None:
            self.model_name = model_name
            self.pairs: list[tuple[str, str]] = []
            FakeCrossEncoder.instances.append(self)

        def predict(self, pairs, **kwargs):
            self.pairs += list(pairs)
            return np.array([fake_relevance(q, t) for q, t in pairs], dtype=np.float64)

    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeSentenceTransformer
    module.CrossEncoder = FakeCrossEncoder
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    return module


@pytest.fixture
def rerank_settings(monkeypatch, tmp_path, fake_models):
    """Fake models, a temporary index directory, and every setting the pipeline reads.

    The settings are set, not removed: an unset variable would be filled in
    from a developer's local .env file by `load_settings`.
    """
    settings = {
        "EMBEDDING_MODEL": E5_NAME,
        "INDEX_DIR": str(tmp_path / "indexes"),
        "BM25_TOP_K": "20",
        "DENSE_TOP_K": "20",
        "RRF_K": "60",
        "RERANKER_ENABLED": "false",
        "RERANKER_MODEL": RERANKER_NAME,
        "RERANK_TOP_K": "20",
    }
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    return fake_models


@pytest.fixture
def hybrid_calls(monkeypatch):
    """Record every HybridRetriever.search call as (query, top_k)."""
    calls: list[tuple[str, int]] = []
    original = HybridRetriever.search

    def recording_search(self, query, top_k=5):
        calls.append((query, top_k))
        return original(self, query, top_k=top_k)

    monkeypatch.setattr(HybridRetriever, "search", recording_search)
    return calls


def rerank_report(ks=(1, 5, 10)) -> dict:
    return run_evaluation("hybrid-rerank", CHUNKS, QUERIES, QRELS, list(ks))


def evaluated_queries() -> list[Query]:
    return [q for q in load_queries(QUERIES) if q.query_id in EVALUATED]


def test_hybrid_rerank_is_selectable(rerank_settings, capsys):
    assert sorted(RETRIEVERS) == ["bm25", "bm25-okapi", "dense", "hybrid", "hybrid-rerank"]
    report = rerank_report([1, 5])
    assert report["retriever"] == "hybrid-rerank"
    assert report["config"]["ks"] == [1, 5]
    assert report["queries_evaluated"] == 4
    assert report["queries_skipped"] == ["synthetic-q05", "synthetic-q06"]
    assert main(cli_args("--retriever", "hybrid-rerank")) == 0
    assert "Retriever: hybrid-rerank" in capsys.readouterr().out


def test_hybrid_rerank_is_hybrid_followed_by_the_configured_reranker(rerank_settings):
    retriever = RETRIEVERS["hybrid-rerank"](list(read_chunks(CHUNKS)))
    assert isinstance(retriever, RerankingRetriever)
    assert retriever.candidate_top_k == 20
    assert retriever.max_results == 20
    assert retriever.describe() == {
        "model": E5_NAME,
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
        "similarity": "cosine",
        "fusion": "rrf",
        "rrf_k": 60,
        "bm25_top_k": 20,
        "dense_top_k": 20,
        "reranker_model": RERANKER_NAME,
        "reranker_scorer": {
            "type": "cross-encoder",
            "library": "sentence-transformers",
            "model": RERANKER_NAME,
            "scores": "raw model output (no sigmoid)",
        },
        "reranker_batch_size": 16,
        "reranker_scores": "raw scorer output; orders passages, not a probability",
        "reranker_candidate_top_k": 20,
    }
    assert rerank_settings.CrossEncoder.instances == []  # built, but no reranker model loaded yet


def test_the_report_identifies_both_stages_and_the_cutoffs(rerank_settings):
    report = rerank_report([1, 5, 10])
    details = report["retriever_details"]
    assert details == RETRIEVERS["hybrid-rerank"](list(read_chunks(CHUNKS))).describe()
    assert details["fusion"] == "rrf"  # the first stage
    assert (details["bm25_top_k"], details["dense_top_k"], details["rrf_k"]) == (20, 20, 60)
    assert details["reranker_model"] == RERANKER_NAME
    assert details["reranker_candidate_top_k"] == 20
    assert details["reranker_batch_size"] == 16
    assert report["config"]["ks"] == [1, 5, 10]
    assert report["warnings"] == []


def test_the_hybrid_retriever_is_searched_once_per_query_for_rerank_top_k_candidates(
    rerank_settings, hybrid_calls
):
    rerank_report([1, 5, 10])
    assert hybrid_calls == [(q.text, 20) for q in evaluated_queries()]


@pytest.mark.parametrize("rerank_top_k", [7, 12])
def test_rerank_top_k_reaches_the_reranking_retriever(
    rerank_settings, hybrid_calls, monkeypatch, rerank_top_k
):
    monkeypatch.setenv("RERANK_TOP_K", str(rerank_top_k))
    assert RETRIEVERS["hybrid-rerank"](list(read_chunks(CHUNKS))).candidate_top_k == rerank_top_k
    report = rerank_report([1, 5])
    assert report["retriever_details"]["reranker_candidate_top_k"] == rerank_top_k
    assert hybrid_calls == [(q.text, rerank_top_k) for q in evaluated_queries()]
    assert all(len(e.get("retrieved", [])) <= rerank_top_k for e in report["per_query"])


def test_the_reranker_reorders_exactly_the_hybrid_candidates(rerank_settings):
    report = rerank_report([1, 5, 10])
    per_query = {e["query_id"]: e for e in report["per_query"]}
    hybrid = RETRIEVERS["hybrid"](list(read_chunks(CHUNKS)))

    expected_pairs, changed = [], 0
    for query in evaluated_queries():
        candidates = hybrid.search(query.text, top_k=20)
        expected_pairs += [(query.text, p.chunk.text) for p in candidates]
        by_reranker = sorted(
            candidates, key=lambda p: (-fake_relevance(query.text, p.chunk.text), p.rank)
        )
        retrieved = per_query[query.query_id]["retrieved"]
        assert retrieved == [p.chunk.chunk_id for p in by_reranker][:10]
        assert set(retrieved) <= {p.chunk.chunk_id for p in candidates}  # nothing was added
        changed += retrieved != [p.chunk.chunk_id for p in candidates][:10]
    assert changed > 0  # the fake scores do reorder something: the check above is not vacuous

    [reranker_model] = rerank_settings.CrossEncoder.instances  # one fake model, loaded once
    assert reranker_model.model_name == RERANKER_NAME
    assert reranker_model.pairs == expected_pairs  # every hybrid candidate, and nothing else


def test_skipped_queries_are_not_searched_or_reranked(rerank_settings, hybrid_calls):
    report = rerank_report([5])
    skipped = {q.text for q in load_queries(QUERIES) if q.query_id in report["queries_skipped"]}
    assert skipped and not skipped & {query for query, _ in hybrid_calls}
    [reranker_model] = rerank_settings.CrossEncoder.instances
    assert not skipped & {query for query, _ in reranker_model.pairs}


def test_default_cutoffs_work_with_rerank_top_k_20(rerank_settings, capsys):
    assert main(cli_args("--retriever", "hybrid-rerank")) == 0  # no --k: 1, 5 and 10
    out = capsys.readouterr().out
    assert "Mean             @1       @5      @10" in out
    assert "WARNING" not in out


@pytest.mark.parametrize("ks", [[20], [1, 5, 10, 20]])
def test_a_cutoff_equal_to_rerank_top_k_is_accepted(rerank_settings, ks):
    report = rerank_report(ks)
    assert report["config"]["ks"] == ks
    assert report["queries_evaluated"] == 4
    assert {f"recall@{k}" for k in ks} <= set(report["metrics"])
    assert report["warnings"] == []


@pytest.mark.parametrize(
    ("rerank_top_k", "ks", "message"),
    [
        (
            20,
            [25],
            "evaluation cutoff @25 exceeds RERANK_TOP_K=20. "
            "Increase RERANK_TOP_K or use evaluation cutoffs <= 20.",
        ),
        (
            20,
            [1, 5, 10, 50, 25],
            "evaluation cutoffs @25, @50 exceed RERANK_TOP_K=20. "
            "Increase RERANK_TOP_K or use evaluation cutoffs <= 20.",
        ),
        (
            5,
            [1, 5, 10],  # the default cutoffs
            "evaluation cutoff @10 exceeds RERANK_TOP_K=5. "
            "Increase RERANK_TOP_K or use evaluation cutoffs <= 5.",
        ),
    ],
)
def test_a_cutoff_above_rerank_top_k_is_rejected_before_anything_is_evaluated(
    rerank_settings, hybrid_calls, monkeypatch, tmp_path, rerank_top_k, ks, message
):
    monkeypatch.setenv("RERANK_TOP_K", str(rerank_top_k))
    with pytest.raises(ValueError) as raised:
        rerank_report(ks)
    assert str(raised.value) == message
    # Nothing was built, loaded or searched.
    assert hybrid_calls == []
    assert rerank_settings.SentenceTransformer.instances == []
    assert rerank_settings.CrossEncoder.instances == []
    assert not (tmp_path / "indexes").exists()


def test_cli_rejects_a_cutoff_above_rerank_top_k(rerank_settings, capsys, tmp_path):
    output = tmp_path / "report.json"
    args = cli_args("--retriever", "hybrid-rerank", "--k", "1", "25", "--output", str(output))
    assert main(args) == 2
    captured = capsys.readouterr()
    assert captured.err.strip() == (
        "Error: evaluation cutoff @25 exceeds RERANK_TOP_K=20. "
        "Increase RERANK_TOP_K or use evaluation cutoffs <= 20."
    )
    assert captured.out == ""
    assert not output.exists()


def test_rerank_top_k_does_not_limit_the_other_retrievers(rerank_settings, monkeypatch):
    def reports() -> str:
        return json.dumps(
            [
                run_evaluation(name, CHUNKS, QUERIES, QRELS, [1, 5, 10, 41, 1000])
                for name in ("bm25", "bm25-okapi", "dense", "hybrid")
            ],
            sort_keys=True,
        )

    with_default = reports()
    monkeypatch.setenv("RERANK_TOP_K", "3")
    monkeypatch.setenv("RERANKER_MODEL", "")
    assert reports() == with_default  # the reranker settings are not read by these retrievers

    assert run_evaluation("bm25", CHUNKS, QUERIES, QRELS, [1000])["warnings"] == []
    assert run_evaluation("dense", CHUNKS, QUERIES, QRELS, [1000])["warnings"] == []
    [warning] = run_evaluation("hybrid", CHUNKS, QUERIES, QRELS, [41])["warnings"]  # still a warning
    assert "hybrid retriever returns at most 40 results" in warning
    assert rerank_settings.CrossEncoder.instances == []


def test_the_existing_retrievers_keep_their_results_and_summaries(rerank_settings, capsys):
    bm25 = run_evaluation("bm25", CHUNKS, QUERIES, QRELS, [1, 5])
    assert bm25["retriever_details"] == {}
    assert bm25["metrics"]["recall@5"] == pytest.approx(0.625)
    assert bm25["metrics"]["mrr@5"] == pytest.approx(0.75)
    assert run_evaluation("dense", CHUNKS, QUERIES, QRELS, [5])["retriever_details"] == {
        "model": E5_NAME, "query_prefix": "query: ", "passage_prefix": "passage: ",
        "similarity": "cosine",
    }
    assert run_evaluation("hybrid", CHUNKS, QUERIES, QRELS, [5])["retriever_details"] == {
        "model": E5_NAME, "query_prefix": "query: ", "passage_prefix": "passage: ",
        "similarity": "cosine", "fusion": "rrf", "rrf_k": 60, "bm25_top_k": 20, "dense_top_k": 20,
    }
    for name in ("bm25", "dense", "hybrid"):
        assert main(cli_args("--retriever", name)) == 0
        out = capsys.readouterr().out
        assert f"Retriever: {name}\n" in out
        assert "Rerank" not in out


def test_a_hybrid_depth_below_the_cutoff_is_still_flagged_not_rejected(rerank_settings, monkeypatch):
    monkeypatch.setenv("BM25_TOP_K", "2")
    monkeypatch.setenv("DENSE_TOP_K", "3")  # hybrid returns at most 5; RERANK_TOP_K is 20
    report = rerank_report([1, 5, 10])
    [warning] = report["warnings"]
    assert "hybrid-rerank retriever returns at most 5 results" in warning
    assert "@10" in warning and "@5" not in warning
    assert report["queries_evaluated"] == 4
    assert all(len(e.get("retrieved", [])) <= 5 for e in report["per_query"])


def test_reranked_metrics_come_from_the_same_metric_functions(rerank_settings):
    ks = [1, 5, 10]
    report = rerank_report(ks)
    qrels = load_qrels(QRELS, [q.query_id for q in load_queries(QUERIES)])

    scored = [e for e in report["per_query"] if "metrics" in e]
    assert [e["query_id"] for e in scored] == EVALUATED
    for entry in scored:
        assert entry["metrics"] == query_metrics(entry["retrieved"], qrels[entry["query_id"]], ks)
    for name, mean in report["metrics"].items():
        assert mean == pytest.approx(sum(e["metrics"][name] for e in scored) / len(scored))

    hybrid = run_evaluation("hybrid", CHUNKS, QUERIES, QRELS, ks)
    assert sorted(report["metrics"]) == sorted(hybrid["metrics"])  # same metrics, same cutoffs
    assert report["config"] == hybrid["config"]  # same chunks, queries and judgments
    assert set(report) == set(hybrid)  # same report structure


def test_evaluate_accepts_a_reranking_retriever_with_an_injected_scorer(monkeypatch):
    monkeypatch.delitem(sys.modules, "sentence_transformers", raising=False)
    chunks = list(read_chunks(CHUNKS))
    queries = load_queries(QUERIES)
    qrels = load_qrels(QRELS, [q.query_id for q in queries])
    scorer = FakeScorer()
    retriever = RerankingRetriever(BM25Retriever(chunks), Reranker(scorer=scorer), candidate_top_k=6)

    results = evaluate(retriever, queries, qrels, [1, 5])
    assert results["queries_evaluated"] == 4
    assert scorer.pairs  # the injected scorer produced the order
    bm25 = BM25Retriever(chunks)
    for entry in results["per_query"]:
        if "retrieved" in entry:
            candidates = bm25.search(entry["text"], top_k=6)
            expected = sorted(
                candidates, key=lambda p: (-fake_relevance(entry["text"], p.chunk.text), p.rank)
            )
            assert entry["retrieved"] == [p.chunk.chunk_id for p in expected][:5]
    assert "sentence_transformers" not in sys.modules  # the model library was never imported


def test_reranked_report_is_json_serializable_and_deterministic(rerank_settings, capsys, tmp_path):
    first, second = rerank_report(), rerank_report()
    text = json.dumps(first, sort_keys=True)
    assert text == json.dumps(second, sort_keys=True)
    assert json.loads(text)["retriever_details"]["reranker_scorer"]["model"] == RERANKER_NAME

    output = tmp_path / "report.json"
    assert main(cli_args("--retriever", "hybrid-rerank", "--output", str(output))) == 0
    capsys.readouterr()
    assert json.loads(output.read_text(encoding="utf-8")) == json.loads(json.dumps(first))


def test_the_summary_says_that_reranking_is_used(rerank_settings, capsys):
    assert main(cli_args("--retriever", "hybrid-rerank", "--k", "1", "5")) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[:4] == [
        "Retriever: hybrid-rerank",
        f"Model:     {E5_NAME}",
        f"Reranker:  {RERANKER_NAME}",
        "Reranking: the first 20 results of the first stage (fusion: rrf), batch size 16",
    ]
    assert "Mean             @1       @5" in lines


@pytest.mark.parametrize("enabled", ["true", "false"])
def test_selecting_hybrid_rerank_does_not_depend_on_reranker_enabled(
    rerank_settings, monkeypatch, enabled
):
    expected = json.dumps(rerank_report(), sort_keys=True)  # RERANKER_ENABLED=false
    monkeypatch.setenv("RERANKER_ENABLED", enabled)
    assert json.dumps(rerank_report(), sort_keys=True) == expected


def test_an_empty_reranker_model_is_rejected_instead_of_replaced_by_a_default(
    rerank_settings, monkeypatch
):
    monkeypatch.setenv("RERANKER_MODEL", "  ")
    with pytest.raises(ValueError) as raised:
        rerank_report()
    assert str(raised.value) == "RERANKER_MODEL must be set to evaluate hybrid-rerank."
    assert rerank_settings.CrossEncoder.instances == []


def test_a_reranker_model_that_cannot_be_loaded_fails_the_evaluation(
    rerank_settings, monkeypatch, capsys
):
    class Unloadable:
        def __init__(self, *args, **kwargs):
            raise OSError("We couldn't connect to 'https://huggingface.co'")

    monkeypatch.setattr(rerank_settings, "CrossEncoder", Unloadable)
    with pytest.raises(OSError, match="couldn't connect"):
        rerank_report()

    assert main(cli_args("--retriever", "hybrid-rerank")) == 2
    captured = capsys.readouterr()
    assert "Error: could not load the retriever: We couldn't connect" in captured.err
    assert captured.out == ""  # no hybrid-only metrics are printed in place of reranked ones
