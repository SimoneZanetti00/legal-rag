import json
import math
from pathlib import Path

import pytest

from src.chunk_store import read_chunks
from src.config import PROJECT_ROOT
from src.models import LegalChunk, RetrievalMethod, RetrievedPassage
from src.retrieval import BM25Retriever
from src.retrieval_eval import (
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
