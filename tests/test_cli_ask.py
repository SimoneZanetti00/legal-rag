"""The ask command (src/provision_cli.py, src/cli.py) and answer_question, end to end.

Runs on the synthetic act of tests/test_provision_cli.py (Art. 1 primary, Art. 2
internal_only, Art. 3 repealed, Art. 4 and 4-bis blocked) with scripted MockLLM replies.
The replies stand in for model output (test data). One test uses the recorded build if it is
present; the live test is opt-in (RUN_LIVE_LLM_TESTS=1) and calls the configured provider.
"""

import json
import os

import pytest

import src.provision_cli as cli
from src import cli as entry_point
from src.answer_generation import Outcome, answer_question
from src.config import load_settings
from src.evidence import assemble
from src.llm import LLMRateLimitError, MockLLM
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.provisions import load_ledger
from src.query_analysis import analyze
from tests.test_provision_cli import built, explored  # noqa: F401  (fixtures)

QUESTION = "Quando va notificata la violazione al Garante?"
SETTINGS = load_settings({})  # defaults: mock provider, 5 evidence items, 3,000 tokens

ANALYSIS = {
    "language": "it", "in_scope": True,
    "scope_reason": "Riguarda la notifica di una violazione dei dati personali.",
    "issues": [{"question": "Entro quando il titolare notifica la violazione al Garante?"},
               {"question": "Quando il titolare comunica la violazione all'interessato?"}],
    "search_queries_it": ["notifica della violazione al Garante",
                          "comunicazione della violazione all'interessato"],
    "suggested_provisions": [], "uncertainty": None, "clarification_question": None,
}
OUT_OF_SCOPE = {**ANALYSIS, "in_scope": False, "scope_reason": "Riguarda il diritto tributario.",
                "issues": [], "search_queries_it": []}
ONLY_ART_2 = {**ANALYSIS, "issues": ANALYSIS["issues"][1:],
              "search_queries_it": ["comunica senza ritardo"]}


def evidence_ids(explored, analysis_reply=ANALYSIS):
    """Article label -> evidence ID, from the same deterministic assembly the CLI runs."""
    build_dir, store = explored
    explorer = ProvisionExplorer.open(build_dir, store=store)
    analysis = analyze(QUESTION, MockLLM({"query_analysis": [analysis_reply]}))
    evidence = assemble(analysis.to_evidence_request(), explorer, settings=SETTINGS)
    return {item.label: item.evidence_id for item in evidence.items}


def generation_reply(ids):
    notify = {"issue_ids": ["I1"], "kind": "source_statement",
              "text": "Il titolare notifica la violazione al Garante entro settantadue ore.",
              "support": [{"evidence_id": ids["1"], "quote":
                           "Il titolare notifica la violazione al Garante entro settantadue ore."}]}
    inform = {"issue_ids": ["I2"], "kind": "source_statement",
              "text": "Il titolare comunica la violazione all'interessato senza ritardo.",
              "support": [{"evidence_id": ids["2"], "quote":
                           "Il titolare comunica la violazione all'interessato senza ritardo."}]}
    return {"outcome": "answer", "claims": [notify, inform], "unanswered_issues": [],
            "limitations": [], "abstention_reason": None}


def ask(capsys, explored, llm, *extra, question=QUESTION, settings=SETTINGS):
    code = cli.main(["ask", question, "--build-dir", str(explored[0]), *extra], llm=llm,
                    settings=settings)
    out = capsys.readouterr()
    return code, out.out, out.err


def scripted(explored):
    ids = evidence_ids(explored)
    assert (ids["1"], ids["2"]) == ("E1", "E2")  # Art. 1 primary, Art. 2 internal_only
    return MockLLM({"query_analysis": [ANALYSIS], "answer_generation": [generation_reply(ids)]})


# --- The command -------------------------------------------------------------------------------


def test_ask_prints_citations_and_keeps_internal_only_evidence_apart(explored, capsys):
    code, out, err = ask(capsys, explored, scripted(explored))
    assert code == 0, err
    assert out.startswith(f"question: {QUESTION}\noutcome: ANSWER LIMITED\n")
    assert "Experimental prototype. Not legal advice." in out
    assert ("C1 [I1] (source statement) Il titolare notifica la violazione al Garante entro "
            "settantadue ore.") in out
    assert "E1: «Il titolare notifica la violazione al Garante entro settantadue ore.»" in out
    citations = out.split("citations (citable provisions):")[1].split("\n\n")[0]
    assert "[E1] x-act Art. 1" in citations and "[E2]" not in citations
    assert "removed by validation: 1 claim(s), not part of the answer:\n  - not_citable:E2" in out
    references = out.split("non-authoritative references (NOT citations")[1]
    assert "[E2] x-act Art. 2" in references and "tier internal_only: structure_not_reviewed" in (
        references)
    assert "inspect: python -m src.cli lookup x-act 2" in references
    assert "  I2  No validated claim addresses this issue." in out
    assert "models: analysis mock/mock, 1 attempt(s); generation mock/mock, 1 attempt(s)" in out


def test_ask_json(explored, capsys):
    code, out, err = ask(capsys, explored, scripted(explored), "--json")
    assert code == 0, err
    result = json.loads(out)
    assert result["outcome"] == "answer_limited"
    assert [c["evidence_ids"] for c in result["claims"]] == [["E1"]]
    assert result["claims"][0]["quotes"][0]["evidence_id"] == "E1"
    assert [c["evidence_id"] for c in result["citations"]] == ["E1"]
    assert all(c["citable"] for c in result["citations"])
    assert "E2" in [r["evidence_id"] for r in result["non_authoritative"]]
    assert result["generation"]["prompt_version"] == "answer-generation-v1"
    assert result["analysis"]["provenance"]["prompt_version"] == "query-analysis-v1"
    assert result["evidence"]["build_id"]


def test_answer_question_runs_analysis_evidence_and_generation_on_one_llm(explored):
    llm = scripted(explored)
    build_dir, store = explored
    result = answer_question(QUESTION, llm, ProvisionExplorer.open(build_dir, store=store),
                             settings=SETTINGS)
    assert [call.task for call in llm.calls] == ["query_analysis", "answer_generation"]
    assert result.outcome == Outcome.ANSWER_LIMITED
    assert result.evidence.build_id == ProvisionExplorer.open(
        build_dir, store=store).identity()["build_id"]
    assert result.generation.supplied_evidence_ids == ("E1",)  # only the citable item


def test_out_of_scope_question_is_answered_with_an_abstention(explored, capsys):
    llm = MockLLM({"query_analysis": [OUT_OF_SCOPE]})
    code, out, _ = ask(capsys, explored, llm, question="Come si calcola l'IVA sulle importazioni?")
    assert code == 0
    assert ("outcome: ABSTAIN (out_of_scope)\n  The query analysis assessed the question as "
            "outside the corpus") in out
    assert "diritto tributario" not in out  # the model's own scope reason is not shown
    assert "generation: not run" in out
    assert [call.task for call in llm.calls] == ["query_analysis"]


def test_no_citable_evidence_abstains_without_generation(explored, capsys):
    ids = evidence_ids(explored, ONLY_ART_2)
    assert list(ids) == ["2"]
    llm = MockLLM({"query_analysis": [ONLY_ART_2]})  # a generation call would fail: no script
    code, out, err = ask(capsys, explored, llm)
    assert code == 0, err
    assert "outcome: ABSTAIN (no_citable_evidence)" in out
    assert "[E1] x-act Art. 2" in out.split("non-authoritative references")[1]
    assert "citations (citable provisions)" not in out
    assert [call.task for call in llm.calls] == ["query_analysis"]


def test_failed_analysis_is_an_abstention(explored, capsys):
    llm = MockLLM({"query_analysis": ["not json", "still not json"]})
    code, out, _ = ask(capsys, explored, llm)
    assert code == 0
    assert "outcome: ABSTAIN (analysis_failed)" in out


# --- Configuration and failures ----------------------------------------------------------------


def test_the_default_mock_provider_is_refused_with_instructions(capsys):
    code = cli.main(["ask", QUESTION], settings=SETTINGS)
    err = capsys.readouterr().err
    assert code == 2
    assert "LLM_PROVIDER is 'mock'" in err and "ANTHROPIC_API_KEY" in err


def test_missing_api_key_is_reported(capsys):
    settings = load_settings({"LLM_PROVIDER": "anthropic", "LLM_MODEL": "test-model"})
    code = cli.main(["ask", QUESTION], settings=settings)
    err = capsys.readouterr().err
    assert code == 2
    assert "ANTHROPIC_API_KEY is required" in err


def test_provider_failure_exits_with_3(explored, capsys):
    llm = MockLLM({"query_analysis": [LLMRateLimitError("rate limited (HTTP 429)",
                                                         status_code=429)]})
    code, _, err = ask(capsys, explored, llm)
    assert code == 3
    assert "error: the LLM provider request failed: rate limited (HTTP 429)" in err


def test_empty_question_exits_with_2(explored, capsys):
    llm = MockLLM({"query_analysis": [ANALYSIS]})
    code, _, err = ask(capsys, explored, llm, question="   ")
    assert code == 2 and "the question is empty" in err
    assert llm.calls == []


def test_missing_build_exits_with_2(tmp_path, capsys):
    code = cli.main(["ask", QUESTION, "--build-dir", str(tmp_path / "absent")],
                    llm=MockLLM(), settings=SETTINGS)
    assert code == 2 and capsys.readouterr().err.startswith("error:")


def test_src_cli_is_the_same_command_line(capsys):
    with pytest.raises(SystemExit) as exc_info:
        entry_point.main(["--help"])
    out = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert out.startswith("usage: python -m src.cli")
    for command in ("build", "lookup", "search", "ask"):
        assert command in out


# --- Recorded build ----------------------------------------------------------------------------

DEMO_QUESTION = "Quando è obbligatorio notificare un data breach al Garante?"
# A stand-in for a model's analysis of DEMO_QUESTION (test data, not real model output).
DEMO_ANALYSIS = {
    "language": "it", "in_scope": True,
    "scope_reason": "Riguarda la notifica di una violazione dei dati personali.",
    "issues": [
        {"question": "Il titolare deve notificare la violazione dei dati personali all'autorità "
                     "di controllo, e quale autorità è competente in Italia?"},
        {"question": "Quando la notifica non è necessaria in base al rischio?"},
        {"question": "Entro quale termine va effettuata la notifica?"},
        {"question": "Quando la violazione va comunicata anche all'interessato?"},
    ],
    "search_queries_it": [
        "notifica di una violazione dei dati personali all'autorità di controllo",
        "comunicazione di una violazione dei dati personali all'interessato",
        "autorità di controllo competente",
        "Garante per la protezione dei dati personali autorità di controllo",
    ],
    "suggested_provisions": [
        {"instrument": "eu-reg-2016-679", "article": "4", "point": "12", "reason": "definizione"},
        {"instrument": "eu-reg-2016-679", "article": "33", "point": None, "reason": "notifica"},
    ],
    "uncertainty": None, "clarification_question": None,
}


@pytest.fixture(scope="module")
def recorded_build():
    try:
        return find_recorded_build()
    except ExplorerError as exc:
        pytest.skip(f"recorded build unavailable: {exc}")


def test_demo_question_on_the_recorded_build(recorded_build, capsys):
    llm = MockLLM({"query_analysis": [DEMO_ANALYSIS]})  # no generation script on purpose
    code = cli.main(["ask", DEMO_QUESTION, "--json"], llm=llm, settings=SETTINGS)
    out, err = capsys.readouterr()
    assert code == 0, err
    result = json.loads(out)
    found = {r["label"] for r in result["non_authoritative"]} | {
        c["label"] for c in result["citations"]}
    assert {"4", "33", "34", "55", "2-bis"} <= found
    assert all(c["citable"] for c in result["citations"])
    assert not any(r["citable"] for r in result["non_authoritative"])
    if not load_ledger():  # nothing reviewed yet: nothing may be cited, so no answer
        assert (result["outcome"], result["abstention_reason"]) == ("abstain",
                                                                  "no_citable_evidence")
        assert result["generation"] is None
        assert [call.task for call in llm.calls] == ["query_analysis"]


# --- Opt-in live call --------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_LLM_TESTS") != "1",
    reason="set RUN_LIVE_LLM_TESTS=1 to run; calls the configured provider and is billed",
)
def test_live_ask_on_the_recorded_build(recorded_build, capsys):
    settings = load_settings()
    if settings.llm_provider != "anthropic":
        pytest.skip("needs LLM_PROVIDER=anthropic, LLM_MODEL and ANTHROPIC_API_KEY")
    code = cli.main(["ask", DEMO_QUESTION, "--json"], settings=settings)
    out, err = capsys.readouterr()
    assert code == 0, err
    result = json.loads(out)
    print(json.dumps({k: result[k] for k in ("outcome", "abstention_reason", "claims",
                                               "citations", "unanswered_issues")},
                     ensure_ascii=False, indent=2))
    assert result["outcome"] in {o.value for o in Outcome}
    assert all(c["citable"] for c in result["citations"])
    if not load_ledger():
        assert result["abstention_reason"] == "no_citable_evidence"
