"""Tests for src/query_fusion.py, src/query_understanding_eval.py and
src/query_understanding_demo.py. MockLLM only; no network.

Most tests use a stand-in explorer whose searches are a table (query -> articles at chunk
ranks); the numbers test the fusion and the experiment's bookkeeping, not retrieval quality.
Tests marked "recorded build" open the real build and skip without it.
"""

import ast
import copy
import dataclasses
from fractions import Fraction
from types import SimpleNamespace

import pytest

import src.provision_eval as pe
import src.query_understanding_demo as demo
import src.query_understanding_eval as qe
from src.config import PROJECT_ROOT
from src.hybrid_retrieval import DEFAULT_RRF_K
from src.llm import LLMTimeoutError, MockLLM
from src.provision_eval import Provenance, Question
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.query_fusion import (
    QueryVariant,
    fuse_rankings,
    query_variants,
    search_variants,
)
from src.query_understanding import TASK, understand

PROV = Provenance("test", "2026-11-12", "synthetic", None, None)


class FakeStore:
    def get(self, pid):
        return SimpleNamespace(instrument_id=pid.split(":")[0])


class FakeExplorer:
    """search(query) returns the table's articles for that query, as ProvisionExplorer.search
    shapes them (provisions in best-rank order, one evidence chunk per rank)."""

    def __init__(self, table):
        self.table = table
        self.store = FakeStore()
        self.calls = []

    def identity(self):
        return {"build_id": "build-fake"}

    def search(self, question, top_k=5):
        self.calls.append((question, top_k))
        rows = sorted((r for r in self.table.get(question, []) if r[1] <= top_k),
                      key=lambda r: r[1])
        provisions = [{"provision_id": pid, "label": pid.split(":")[1], "best_rank": rank,
                       "heading": f"Art. {pid.split(':')[1]}", "title": None,
                       "eligibility": {"tier": "internal_only"},
                       "legal_validity": "not_established",
                       "structural_status": "auto_unreviewed"} for pid, rank in rows]
        results = []
        for rank in sorted({rank for _, rank in rows}):
            results.append({
                "rank": rank, "chunk_id": f"chunk-{question[:5]}-{rank}",
                "role": "article_evidence",
                "source_path": "fake.pdf", "version_id": "fake@v1",
                "evidence": [{"provision_id": pid, "pieces": [
                    {"text": f"testo di {pid}", "page": 1, "char_start": 0, "char_end": 9}]}
                    for pid, r in rows if r == rank]})
        return {"results": results, "provisions": provisions}


def ranking(*rows):
    return [{"provision_id": pid, "label": pid.split(":")[1], "best_rank": rank}
            for pid, rank in rows]


# --- Variants ----------------------------------------------------------------------------------


def reading_of(question, legal="dati personali del dipendente", semantic="dati di chi lavora"):
    reply = {"legal_query": legal, "semantic_query": semantic, "legal_concepts": [],
             "entities": [], "relationships": [], "conditions": [], "ambiguities": [],
             "clarification_needed": False}
    return understand(question, MockLLM({TASK: [reply]}))


def test_without_a_reading_the_original_is_searched_alone():
    assert query_variants(" domanda ") == (QueryVariant("original", "domanda"),)


def test_reformulation_can_be_switched_on_and_off():
    reading = reading_of("domanda")
    kinds = lambda **kw: [v.kind for v in query_variants("domanda", reading, **kw)]  # noqa: E731
    assert kinds() == ["original", "legal", "semantic"]
    assert kinds(semantic=False) == ["original", "legal"]
    assert kinds(legal=False) == ["original", "semantic"]
    assert kinds(legal=False, semantic=False) == ["original"]


def test_a_reading_of_another_question_is_refused():
    with pytest.raises(ValueError, match="another question"):
        query_variants("altra domanda", reading_of("domanda"))


# --- RRF ---------------------------------------------------------------------------------------


def test_rrf_sums_one_over_k_plus_the_best_chunk_rank():
    fused = fuse_rankings([ranking(("g:5", 1), ("g:6", 3)), ranking(("g:6", 1), ("g:17", 2))],
                          ["original", "legal"], {"g:5": "g", "g:6": "g", "g:17": "g"})
    k = DEFAULT_RRF_K
    assert [a.provision_id for a in fused] == ["g:6", "g:5", "g:17"]
    assert fused[0].score == float(Fraction(1, k + 3) + Fraction(1, k + 1))
    assert [(c.kind, c.chunk_rank) for c in fused[0].contributions] == [("original", 3),
                                                                       ("legal", 1)]
    assert fused[1].score == 1 / (k + 1) and fused[2].score == 1 / (k + 2)


def test_one_ranking_alone_keeps_its_order_and_ties():
    rows = ranking(("g:4", 1), ("c:2-bis", 1), ("g:9", 3))
    fused = fuse_rankings([rows], ["original"], {"g:4": "g", "c:2-bis": "c", "g:9": "g"})
    assert [a.provision_id for a in fused] == ["g:4", "c:2-bis", "g:9"]


def test_equal_scores_keep_the_interleaved_order():
    fused = fuse_rankings([ranking(("g:1", 2)), ranking(("g:2", 1), ("g:3", 2))],
                          ["original", "legal"], {"g:1": "g", "g:2": "g", "g:3": "g"})
    assert [a.provision_id for a in fused] == ["g:2", "g:1", "g:3"]  # g:1 and g:3 tie at 1/62


def test_a_ranking_may_not_list_an_article_twice():
    with pytest.raises(ValueError, match="twice"):
        fuse_rankings([ranking(("g:1", 1), ("g:1", 2))], ["original"], {"g:1": "g"})


@pytest.mark.parametrize("bad", [0, -1, True, 1.5])
def test_rrf_k_must_be_a_positive_int(bad):
    with pytest.raises((TypeError, ValueError)):
        fuse_rankings([], [], {}, rrf_k=bad)


def test_search_variants_drops_a_repeat_and_records_it():
    explorer = FakeExplorer({"Domanda": [("g:5", 1)], "dati": [("g:6", 1)]})
    fused = search_variants(explorer, [QueryVariant("original", "Domanda"),
                                       QueryVariant("legal", " domanda "),
                                       QueryVariant("semantic", "dati")])
    assert [v.kind for v in fused.variants] == ["original", "semantic"]
    assert [v.kind for v in fused.dropped] == ["legal"]
    assert explorer.calls == [("Domanda", pe.DEFAULT_CHUNK_DEPTH), ("dati", pe.DEFAULT_CHUNK_DEPTH)]
    assert fused.summary()["dropped_variants"][0]["reason"] == "repeats an earlier variant"


@pytest.mark.parametrize("queries", [
    ["q1"], ["q1", "q2"], ["q2", "q1", "q3"],
])
def test_one_query_through_fusion_equals_rank_articles(queries):
    table = {"q1": [("g:1", 1), ("c:2", 1), ("g:3", 4)], "q2": [("g:3", 1), ("g:7", 2)],
             "q3": [("c:9", 3)]}
    explorer = FakeExplorer(table)
    for q in queries:
        fused = search_variants(explorer, [QueryVariant("original", q)])
        expected, _ = pe.rank_articles(explorer, [q], pe.DEFAULT_CHUNK_DEPTH)
        assert fused.ranked_ids() == [r.provision_id for r in expected]


# --- Experiment --------------------------------------------------------------------------------


def question(qid, text, split="dev"):
    return Question(qid, text, (f"{text} tecnico",), "obligation", "answerable", split, PROV,
                    None, (f"{text} naturale",))


QUESTIONS = (question("d1", "uno"), question("d2", "due"))
GRADES = {"d1": {"g:1": 2, "g:2": 0}, "d2": {"g:4": 1}}
TABLE = {
    "uno": [("g:2", 1), ("g:1", 3)], "uno tecnico": [("g:1", 1)], "uno naturale": [("g:9", 1)],
    "due": [("g:5", 1)], "due tecnico": [("g:4", 2)], "due naturale": [("g:4", 1)],
    "legale uno": [("g:1", 1)], "semplice uno": [("g:2", 1)],
    "legale due": [("g:6", 1)], "semplice due": [("g:4", 4)],
}


def readings_for(*pairs):
    out = {}
    for q, (legal, semantic) in zip(QUESTIONS, pairs):
        out[q.query_id] = {"status": "ok", "reading": reading_of(q.question, legal, semantic)}
    return out


def test_strategies_a_to_d_are_scored_with_provenance():
    explorer = FakeExplorer(TABLE)
    readings = readings_for(("legale uno", "semplice uno"), ("legale due", "semplice due"))
    out = qe.evaluate_strategies(QUESTIONS, GRADES, explorer, strategies=list(qe.STRATEGIES),
                                 readings=readings)
    a, b = out["strategies"]["A"], out["strategies"]["B"]
    assert a["per_query"][0]["ranking"][0]["provision_id"] == "g:2"
    assert b["per_query"][0]["ranking"][0]["provision_id"] == "g:1"
    assert b["means"]["recall@1"] == 0.5  # d1 found at 1; d2's legal query finds nothing judged
    d = out["strategies"]["D"]["per_query"][1]
    assert [v["kind"] for v in d["variants"]] == ["original", "legal", "semantic"]
    assert d["ranking"][-1]["found_by"] == [{"kind": "semantic", "variant": 3, "chunk_rank": 4}]
    assert out["checks"] == {"A_equals_rank_articles": True}
    assert set(out["not_run"]) == {"E"}
    assert out["comparison_with_A"]["B"]["ndcg@10_per_question"]["better"] == 1


def test_the_references_reproduce_the_frozen_evaluator_ranking():
    explorer = FakeExplorer(TABLE)
    out = qe.evaluate_strategies(QUESTIONS, GRADES, explorer, strategies=["A"])
    entry = out["controls"]["ref-technical"]["per_query"][1]
    expected, _ = pe.rank_articles(explorer, QUESTIONS[1].queries("technical"), 20)
    assert [r["provision_id"] for r in entry["ranking"]] == [r.provision_id for r in expected]
    assert entry["metrics"]["recall@5"] == 1.0


def test_without_a_model_b_to_d_are_listed_as_not_run():
    out = qe.evaluate_strategies(QUESTIONS, GRADES, FakeExplorer(TABLE),
                                 strategies=list(qe.STRATEGIES))
    assert list(out["strategies"]) == ["A"]
    assert set(out["not_run"]) == {"B", "C", "D", "E"}


def test_a_failed_reading_falls_back_to_the_original_and_is_reported():
    client = MockLLM({TASK: [LLMTimeoutError("no response within 1s")] * 2})
    readings = qe.read_questions(QUESTIONS, client)
    assert {r["status"] for r in readings.values()} == {"failed"}
    assert readings["d1"]["error"]["type"] == "LLMTimeoutError"
    out = qe.evaluate_strategies(QUESTIONS, GRADES, FakeExplorer(TABLE), strategies=["A", "B", "D"],
                                 readings=readings, controls=[])
    for name in ("B", "D"):
        block = out["strategies"][name]
        assert block["fallbacks"] == ["d1", "d2"]
        assert block["means"] == out["strategies"]["A"]["means"]
    assert "the original query alone" in out["strategies"]["B"]["per_query"][0]["fallback"]


def test_test_questions_are_never_read_searched_or_scored():
    held_out = question("t1", "segreta", split="test")
    client = MockLLM({TASK: []})
    with pytest.raises(ValueError, match="only dev"):
        qe.read_questions([held_out], client)
    explorer = FakeExplorer(TABLE)
    with pytest.raises(ValueError, match="only dev"):
        qe.evaluate_strategies([*QUESTIONS, held_out], GRADES, explorer, strategies=["A"])
    assert client.calls == [] and explorer.calls == []
    bench = SimpleNamespace(questions=(*QUESTIONS, held_out))
    assert qe.dev_questions(bench) == QUESTIONS


def test_unknown_strategies_and_controls_are_refused():
    with pytest.raises(ValueError, match="unknown strategies"):
        qe.evaluate_strategies(QUESTIONS, GRADES, FakeExplorer(TABLE), strategies=["E"])
    with pytest.raises(ValueError, match="unknown controls"):
        qe.evaluate_strategies(QUESTIONS, GRADES, FakeExplorer(TABLE), strategies=["A"],
                               controls=["x"])


# --- Demo --------------------------------------------------------------------------------------


DEMO_TABLE = {
    demo.DEFAULT_QUESTION: [("c:37", 1)],
    demo.SCRIPTED_REPLY["legal_query"]: [("g:5", 1), ("g:17", 2)],
    demo.SCRIPTED_REPLY["semantic_query"]: [("g:5", 2), ("c:37", 3)],
}


def test_the_scripted_reply_passes_the_checks_and_is_labelled():
    data = demo.run_demo(demo.DEFAULT_QUESTION, FakeExplorer(DEMO_TABLE), demo.scripted_llm(),
                         scripted=True)
    assert data["question"] == demo.DEFAULT_QUESTION
    assert data["understanding"]["original_query"] == demo.DEFAULT_QUESTION
    assert data["reading_source"]["label"] == demo.SCRIPTED_LABEL
    assert [a["provision_id"] for a in data["articles"]] == ["g:5", "c:37", "g:17"]
    assert data["articles"][0]["evidence"]["text"] == "testo di g:5"
    assert data["articles"][0]["found_by"] == [{"query": "legal", "chunk_rank": 1},
                                               {"query": "semantic", "chunk_rank": 2}]
    text = demo.format_demo(data)
    assert "SCRIPTED MOCK REPLY" in text and "no answer" in text
    assert "Nothing here answers the question" in text


def test_the_demo_without_reformulation_makes_no_call():
    explorer = FakeExplorer(DEMO_TABLE)
    data = demo.run_demo(demo.DEFAULT_QUESTION, explorer, None)
    assert data["understanding"] is None
    assert [v["kind"] for v in data["search"]["variants"]] == ["original"]
    assert explorer.calls == [(demo.DEFAULT_QUESTION, pe.DEFAULT_CHUNK_DEPTH)]


def test_the_demo_survives_a_model_failure_and_says_so():
    client = MockLLM({TASK: [LLMTimeoutError("no response within 1s")] * 2})
    data = demo.run_demo(demo.DEFAULT_QUESTION, FakeExplorer(DEMO_TABLE), client)
    assert data["understanding"] is None
    assert data["reading_source"]["failure"]["type"] == "LLMTimeoutError"
    assert "Reading failed (LLMTimeoutError" in demo.format_demo(data)


def test_the_demo_without_a_model_stops_and_says_what_to_set(monkeypatch, capsys):
    monkeypatch.setattr(demo, "load_settings", lambda: SimpleNamespace(llm_provider="mock"))
    assert demo.main([]) == 2
    assert "LLM_PROVIDER=mock" in capsys.readouterr().err


def test_scripted_mode_refuses_another_question():
    with pytest.raises(SystemExit):
        demo.main(["--scripted", "--question", "Altro?"])


def test_the_scripted_reply_is_not_changed_by_the_demo():
    before = copy.deepcopy(demo.SCRIPTED_REPLY)
    demo.run_demo(demo.DEFAULT_QUESTION, FakeExplorer(DEMO_TABLE), demo.scripted_llm(),
                  scripted=True)
    assert demo.SCRIPTED_REPLY == before


# --- Defaults are unchanged --------------------------------------------------------------------

NEW_MODULES = {"query_understanding", "query_fusion", "query_understanding_eval",
               "query_understanding_demo"}


def test_no_existing_module_uses_the_new_layer():
    """`ask`, the evaluator and every other module run exactly as before: only the new
    modules import the layer."""
    users = set()
    for path in (PROJECT_ROOT / "src").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in {
                    f"src.{m}" for m in NEW_MODULES}:
                users.add(path.stem)
    assert users <= NEW_MODULES


# --- Recorded build ----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def recorded():
    try:
        explorer = ProvisionExplorer.open(find_recorded_build())
    except ExplorerError as exc:
        pytest.skip(f"recorded build unavailable: {exc}")
    benchmark = pe.load_benchmark(pe.DEFAULT_BENCHMARK)
    return explorer, benchmark, pe.resolve_judgments(benchmark.judgments, explorer)


def test_recorded_build_references_equal_the_frozen_evaluator_on_dev(recorded):
    explorer, benchmark, grades = recorded
    out = qe.evaluate_strategies(qe.dev_questions(benchmark), grades, explorer,
                                 strategies=["A"], controls=["ref-technical", "ref-natural"])
    assert out["checks"]["A_equals_rank_articles"] is True
    dev_only = dataclasses.replace(benchmark, questions=qe.dev_questions(benchmark))
    for scenario in ("technical", "natural"):  # test questions are not even searched
        frozen = pe.evaluate(dev_only, explorer, scenario=scenario)["means"]
        mine = out["controls"][f"ref-{scenario}"]["means"]
        assert mine == pytest.approx(frozen)


def test_recorded_build_scripted_demo_runs_offline(recorded):
    explorer = recorded[0]
    data = demo.run_demo(demo.DEFAULT_QUESTION, explorer, demo.scripted_llm(), scripted=True)
    assert data["understanding"]["provenance"]["provider"] == "mock"
    assert [v["kind"] for v in data["search"]["variants"]] == ["original", "legal", "semantic"]
    assert all(a["tier"] != "primary" for a in data["articles"])  # nothing citable yet
    assert all(a["evidence"] is not None for a in data["articles"])
