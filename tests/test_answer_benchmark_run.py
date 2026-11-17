"""The answers-v0 runner (src/answer_benchmark_run.py): recording and replaying model calls,
saving runs, and the deterministic stage metrics. MockLLM and hand-made results only; the
saved baseline run is checked against the recorded build when both are available."""

import json

import pytest

import src.answer_benchmark as ab
import src.answer_benchmark_run as run
from src.llm import LLMConfigError, LLMRateLimitError, MockLLM
from src.provision_eval import Provenance
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["x"],
          "properties": {"x": {"type": "string"}}}
CANDIDATE = Provenance("test", "2026-11-17", "candidate", None, None)
REVIEWED = Provenance("test", "2026-11-17", "owner_reviewed", "owner", "2026-11-17")

# Three articles of a fictional act, with numbered paragraphs.
TEXTS = {"1": "Art. 1\n1. Il titolare notifica la violazione entro settantadue ore.\n"
              "2. Il responsabile informa il titolare senza ritardo.",
         "2": "Art. 2\n1. Il titolare comunica la violazione agli interessati.",
         "3": "Art. 3\n1. Il Garante è l'autorità di controllo."}


def article_text(instrument, article):
    return TEXTS[article]


def question(qid="a01", split="dev", outcome="answer", provenance=CANDIDATE):
    return ab.Question(qid, f"Domanda {qid}?", "it", "breach", outcome, None, None, None, split,
                       provenance)


def row(article, unit=None, role="core", qid="a01", provenance=CANDIDATE):
    return ab.Expectation(qid, "x-act", article, unit, role, "test", provenance)


def item(eid, article, text, whole=True):
    return {"evidence_id": eid, "instrument_id": "x-act", "label": article, "text": text,
            "whole_provision": whole, "point": None}


def claim(cid, eid, quote, verification):
    return {"claim_id": cid, "issue_ids": ["I1"], "kind": "source_statement", "text": "Testo.",
            "quotes": [{"evidence_id": eid, "text": quote}], "verification": verification}


def result(items, claims=(), dropped=(), rejected=(), outcome="answer"):
    return {"outcome": outcome, "abstention_reason": None,
            "evidence": {"items": list(items), "dropped": list(dropped)},
            "claims": list(claims), "rejected_claims": list(rejected),
            "citations": [{"instrument_id": "x-act", "label": i["label"]} for i in items]}


# --- Recording and replay ------------------------------------------------------------------------


def test_recorded_calls_are_replayed_and_unknown_calls_go_live_or_fail():
    recorder = run.RecordingLLM(MockLLM({"task_a": [{"x": "uno"}]}))
    first = recorder.complete_json("task_a", "system", "user", SCHEMA)
    [call] = recorder.calls
    assert call["data"] == {"x": "uno"} and "user" not in call and "system" not in call
    assert call["user_sha256"] == run.sha256("user") and call["replayed"] is False

    replay = run.ReplayLLM(recorder.calls, live=None, provider="mock", model="mock")
    again = replay.complete_json("task_a", "system", "user", SCHEMA)
    assert again.data == first.data and (replay.replayed, replay.called) == (1, 0)
    with pytest.raises(LLMConfigError, match="no saved reply"):
        replay.complete_json("task_a", "system", "another message", SCHEMA)

    live = MockLLM({"task_a": [{"x": "due"}]})
    mixed = run.RecordingLLM(run.ReplayLLM(recorder.calls, live=live, provider="mock",
                                           model="mock"))
    assert mixed.complete_json("task_a", "system", "user", SCHEMA).data == {"x": "uno"}
    assert mixed.complete_json("task_a", "system", "changed", SCHEMA).data == {"x": "due"}
    assert [c["replayed"] for c in mixed.calls] == [True, False]
    assert len(live.calls) == 1


def test_a_replayed_reply_still_passes_the_callers_check():
    recorder = run.RecordingLLM(MockLLM({"task_a": [{"x": "uno"}]}))
    recorder.complete_json("task_a", "s", "u", SCHEMA)
    replay = run.ReplayLLM(recorder.calls, live=None, provider="mock", model="mock")

    def refuse(data):
        raise ab.BenchmarkError("rejected")

    with pytest.raises(ab.BenchmarkError):
        replay.complete_json("task_a", "s", "u", SCHEMA, check=refuse)


# --- Stage metrics -------------------------------------------------------------------------------


def test_stage_metrics_follow_each_core_provision_through_the_stages():
    rows = [row("1", ab.Unit(paragraph="1")), row("2"), row("3")]
    res = result(
        [item("E1", "1", TEXTS["1"])],
        claims=[claim("C1", "E1", "notifica la violazione entro settantadue ore", "SUPPORTED")],
        dropped=[{"provision_id": "x-act@v1/body/article:2", "label": "2", "origins": ["query:1"],
                  "reason": "token_budget", "tokens": 40}],
        rejected=[{"reasons": ["quote_not_found:E1"]}, {"reasons": ["not_supported_by_evidence"]},
                  {"reasons": ["quote_not_found:E2", "unknown_issue:I9"]}])
    m = run.stage_metrics(question(), rows, res, article_text)
    assert (m["core_candidate_recall"], m["core_evidence_recall"]) == (2 / 3, 1 / 3)
    assert m["core_citation_recall"] == 1 / 3
    assert m["missing_from_evidence"] == [
        {"provision": "x-act art. 2", "reason": "dropped_token_budget"},
        {"provision": "x-act art. 3", "reason": "not_a_candidate"}]
    assert m["claims_removed"] == {"not_supported_by_evidence": 1, "quote_not_found": 2,
                                   "unknown_issue": 1}
    assert m["outcome_match"] is True and (m["claims_in_answer"], m["claims_held_apart"]) == (1, 0)


def test_only_claims_in_the_main_answer_count_as_citations():
    rows = [row("1", ab.Unit(paragraph="1"))]
    quote = "notifica la violazione entro settantadue ore"
    for verification, cited in (("SUPPORTED", 1.0), ("NOT_VERIFIED", 1.0),
                                ("PARTIALLY_SUPPORTED", 0.0), ("UNCERTAIN", 0.0)):
        res = result([item("E1", "1", TEXTS["1"])], claims=[claim("C1", "E1", quote, verification)])
        m = run.stage_metrics(question(), rows, res, article_text)
        assert m["core_citation_recall"] == cited, verification
        assert m["claims_held_apart"] == (0 if cited else 1)


def test_a_unit_outside_an_excerpt_and_an_unlocated_unit_are_told_apart():
    rows = [row("1", ab.Unit(paragraph="2")), row("2", ab.Unit(paragraph="7"))]
    res = result([item("E1", "1", "1. Il titolare notifica la violazione.", whole=False),
                  item("E2", "2", TEXTS["2"])])
    m = run.stage_metrics(question(), rows, res, article_text)
    assert [x["reason"] for x in m["missing_from_evidence"]] == [
        "unit_outside_excerpt", "unit_not_located"]


# --- Running and reporting -----------------------------------------------------------------------


def benchmark(questions, rows):
    return ab.Benchmark("answers", "test", "end_to_end", "build-" + "0" * 32, "test", 1,
                        tuple(questions), tuple(rows), {})


def test_a_run_saves_each_question_once_and_reports_both_scopes(tmp_path):
    bench = benchmark([question("a01"), question("a02", split="test"),
                       question("a03", provenance=REVIEWED)],
                      [row("1", ab.Unit(paragraph="1")), row("2", qid="a02"),
                       row("3", qid="a03", provenance=CANDIDATE)])
    answered = []

    def answer(text, llm):
        answered.append(text)
        llm.complete_json("query_analysis", "s", text, SCHEMA)
        if text == "Domanda a03?":
            raise LLMRateLimitError("rate limit")
        return result([item("E1", "1", TEXTS["1"])])

    record = {"run_id": "t", "mode": "research", "model": "mock", "build_id": "build-x",
              "replay_of": None, "settings": {"final_evidence_count": 5,
                                              "context_token_budget": 3000},
              "prompt_versions": {"query_analysis": "qa", "answer_generation": "ag",
                                  "claim_verification": "cv"}, "code": {"state": "clean"}}
    script = {"query_analysis": [{"x": "a"}, {"x": "b"}]}
    llm = MockLLM(script)
    done = run.run_questions(bench, tmp_path, ["dev"], answer, lambda qid: llm, record,
                             log=lambda line: None)
    assert done == ["a01", "a03"] and answered == ["Domanda a01?", "Domanda a03?"]
    saved = json.loads((tmp_path / "a03.json").read_text(encoding="utf-8"))
    assert saved["error"].startswith("LLMRateLimitError") and "result" not in saved
    assert json.loads((tmp_path / "a01.json").read_text(encoding="utf-8"))["llm_calls"][0][
        "data"] == {"x": "a"}
    # A saved question is never answered again.
    assert run.run_questions(bench, tmp_path, ["dev"], answer, lambda qid: llm, record,
                             log=lambda line: None) == []
    data = run.report(bench, tmp_path, article_text)
    assert data["errors"] == {"a03": saved["error"]}
    everything = data["scopes"][run.SCOPE_ALL]
    assert [e["query_id"] for e in everything["per_question"]] == ["a01"]
    assert "empty" in data["scopes"][run.SCOPE_REVIEWED]  # a03's row is a candidate
    text = run.format_report(data)
    assert "== all rows: candidate expectations, not owner-reviewed" in text
    assert "== owner-reviewed rows only\n   empty: no question" in text
    assert run.report(bench, tmp_path, article_text) == data  # deterministic
    record_file = json.loads((tmp_path / run.RUN_RECORD).read_text(encoding="utf-8"))
    assert [i["splits"] for i in record_file["invocations"]] == [["dev"], ["dev"]]


def test_run_ids_and_splits_are_checked(tmp_path):
    for bad in ("", "Run 1", "../x", "a" * 65):
        with pytest.raises(run.RunError):
            run.check_run_id(bad)
    with pytest.raises(run.RunError, match="unknown split"):
        run.run_questions(benchmark([], []), tmp_path, ["train"], None, None, {})


# --- The saved baseline run ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def explorer():
    try:
        return ProvisionExplorer.open(find_recorded_build())
    except ExplorerError as exc:
        pytest.skip(f"recorded build unavailable: {exc}")


@pytest.mark.parametrize("run_id", sorted(p.name for p in run.RUNS_DIR.glob("*")
                                          if (p / run.REPORT_FILE).is_file()))
def test_a_saved_report_is_reproduced_offline_from_its_saved_run(explorer, run_id):
    run_dir = run.RUNS_DIR / run_id
    saved = json.loads((run_dir / run.REPORT_FILE).read_text(encoding="utf-8"))
    again = run.report(ab.load_benchmark(), run_dir, run.explorer_article_text(explorer))
    assert json.loads(json.dumps(again)) == saved


def test_a_run_can_be_limited_to_named_questions_and_saves_the_rendered_answer(tmp_path):
    bench = benchmark([question("a01"), question("a02")], [row("1"), row("2", qid="a02")])

    def answer(text, llm):
        return result([item("E1", "1", TEXTS["1"])])

    done = run.run_questions(bench, tmp_path, ["dev"], answer, lambda qid: MockLLM({}), {
        "code": {"state": "clean"}}, log=lambda line: None, only=["a02"],
        render=lambda res: f"rendered {res['outcome']}")
    assert done == ["a02"]
    assert json.loads((tmp_path / "a02.json").read_text(encoding="utf-8"))["rendered"] == (
        "rendered answer")
    with pytest.raises(run.RunError, match="unknown question"):
        run.run_questions(bench, tmp_path, ["dev"], answer, None, {}, only=["a99"])
