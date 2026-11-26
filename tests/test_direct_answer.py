"""The direct answer to yes/no and premise questions (TECHNICAL_DEBT.md TD-069): the question
type from the query analysis, the direct answer from generation, its mechanical checks, the
outcome rule, the page and the benchmark.

MockLLM only: the replies are scripted stand-ins for model output, so these tests check what the
application does with each reply, not how well a model classifies or answers.
"""

import dataclasses
import json
import re

import pytest

import src.answer_benchmark as ab
import src.answer_benchmark_run as run
from src.answer_generation import (
    DIRECT_BAD_REFERENCE,
    DIRECT_MISSING,
    DIRECT_NOT_ESTABLISHED,
    DIRECT_NOT_SHOWN,
    DIRECT_NOT_SUPPORTED,
    DIRECT_SHOWN,
    SCHEMA,
    SYSTEM_PROMPT,
    TASK,
    DirectAnswer,
    Outcome,
    build_user_message,
    decide_coverage,
    generate_answer,
)
from src.claim_repair import TASK as REPAIR_TASK
from src.llm import MockLLM, check_schema
from src.provision_cli import render_answer
from src.query_analysis import QUESTION_TYPES, analyze
from src.query_analysis import SCHEMA as ANALYSIS_SCHEMA
from src.query_analysis import SYSTEM_PROMPT as ANALYSIS_PROMPT
from src.support_verification import TASK as VERIFY_TASK
from src.text_normalization import normalise
from tests.test_answer_generation import EVIDENCE, INFORM, NOTIFY, QUESTION, analysis, reply
from tests.test_query_analysis import DEMO_REPLY
from tests.test_support_verification import INFORM_REPAIRED, declined, rewrites, verdicts

YES = "Sì: il titolare notifica la violazione al Garante senza ingiustificato ritardo."


def direct(value, text, *claims):
    return {"value": value, "text": text, "claims": list(claims)}


def ask(*verification_replies, given=None, question_type="yes_no", verify=True, repair=None,
        generation=None):
    """generate_answer on scripted replies, for a question of `question_type`. Unless `repair`
    is given, the repair pass declines to rewrite."""
    script = {TASK: [generation or reply(NOTIFY, INFORM, direct=given)]}
    if verification_replies:
        script[VERIFY_TASK] = list(verification_replies)
    repair = declined(*verification_replies) if repair is None else repair
    if repair is not None:
        script[REPAIR_TASK] = [repair] if isinstance(repair, dict) else list(repair)
    llm = MockLLM(script)
    typed = dataclasses.replace(analysis(), question_type=question_type)
    return generate_answer(QUESTION, typed, EVIDENCE, llm, verify_support=verify), llm


BOTH = verdicts(C1="supported", C2="supported")


# --- The prompts --------------------------------------------------------------------------------


def test_the_analysis_classifies_the_form_of_the_question():
    check_schema(ANALYSIS_SCHEMA)
    assert QUESTION_TYPES == ("yes_no", "premise", "open")
    assert "question_type" in ANALYSIS_SCHEMA["required"]
    assert "Classify the form only; do not judge whether a premise is true." in ANALYSIS_PROMPT
    out = analyze("Il titolare deve notificare la violazione?",
                  MockLLM({"query_analysis": [{**DEMO_REPLY, "question_type": "yes_no"}]}))
    assert out.question_type == "yes_no" and out.to_dict()["question_type"] == "yes_no"


def test_generation_asks_for_a_direct_answer_only_for_yes_no_and_premise_questions():
    check_schema(SCHEMA)
    assert "direct_answer" in SCHEMA["required"]
    assert "direct_answer: null unless the request below asks for a direct answer" in SYSTEM_PROMPT
    assert "state that rule in a claim and rest" in SYSTEM_PROMPT
    requests = {}
    for kind in QUESTION_TYPES:
        message = build_user_message(QUESTION, dataclasses.replace(analysis(), question_type=kind),
                                     EVIDENCE.items[:1])
        requests[kind] = next(line for line in message.splitlines()
                              if line.startswith("Direct answer:"))
    assert requests == {
        "yes_no": "Direct answer: the question asks whether something is so. Give a "
                  "direct_answer.",
        "premise": "Direct answer: the question rests on a fact it states as given. Give a "
                   "direct_answer on whether that fact holds.",
        "open": "Direct answer: not asked for. Give direct_answer null."}


def test_the_prompt_examples_are_not_benchmark_questions():
    """The prompts must not be tuned to the questions they are measured on."""
    prompts = normalise(ANALYSIS_PROMPT + SYSTEM_PROMPT)
    for q in ab.load_benchmark().questions:
        words = re.sub(r"[?¿!.]", "", normalise(q.question)).strip()
        assert words not in prompts, q.query_id


# --- The direct answer and the outcome ----------------------------------------------------------


def test_a_direct_answer_resting_on_supported_claims_is_shown_and_completes_the_answer():
    result, _ = ask(BOTH, given=direct("yes", YES, 1))
    assert result.direct_answer == DirectAnswer("yes", YES, ("C1",), DIRECT_SHOWN)
    assert result.outcome == Outcome.ANSWER
    assert f"direct answer (an interpretation of the statements it rests on: C1): YES. {YES}" in (
        render_answer(result))
    assert result.to_dict()["direct_answer"] == {"value": "yes", "text": YES,
                                                 "claim_ids": ["C1"], "status": "shown"}


@pytest.mark.parametrize("given, status", [
    (None, DIRECT_MISSING),
    (direct("yes", "   ", 1), DIRECT_MISSING),
    (direct("yes", "x" * 401, 1), DIRECT_MISSING),
    (direct("cannot_establish", "Le disposizioni non lo stabiliscono."), DIRECT_NOT_ESTABLISHED),
    (direct("yes", YES), DIRECT_NOT_SUPPORTED),  # it rests on no claim
    (direct("no", "No: lo prevede l'articolo 2.", 1), DIRECT_BAD_REFERENCE),  # E1 is art. 1
])
def test_without_a_direct_answer_shown_the_answer_is_limited(given, status):
    result, _ = ask(BOTH, given=given)
    assert result.direct_answer.status == status and result.outcome == Outcome.ANSWER_LIMITED
    assert all(c.verification.value == "SUPPORTED" for c in result.claims)  # only the direct answer
    assert f"direct answer: none shown ({DIRECT_NOT_SHOWN[status]})" in render_answer(result)


def test_the_text_may_name_the_articles_of_its_claims():
    result, _ = ask(BOTH, given=direct("yes", "Sì: lo prevede l'articolo 1, che rinvia all'articolo 3.",
                                       1))
    assert result.direct_answer.status == DIRECT_SHOWN  # art. 1 is cited; art. 3 is named in it


def test_a_direct_answer_resting_on_a_claim_held_apart_is_not_shown():
    result, _ = ask(verdicts(C1="partially_supported", C2="supported"), given=direct("yes", YES, 1))
    assert result.direct_answer == DirectAnswer("yes", YES, ("C1",), DIRECT_NOT_SUPPORTED)
    assert result.outcome == Outcome.ANSWER_LIMITED


def test_links_to_removed_or_unknown_claims_are_dropped():
    result, _ = ask(verdicts(C1="unsupported", C2="supported"), given=direct("yes", YES, 1, 7))
    assert result.direct_answer.claim_ids == () and result.direct_answer.status == (
        DIRECT_NOT_SUPPORTED)
    assert "direct_answer_link_dropped: [1] is not a claim of the answer" in result.warnings
    assert "direct_answer_link_dropped: [7] is not a claim of the answer" in result.warnings
    partly, _ = ask(verdicts(C1="unsupported", C2="supported"), given=direct("yes", YES, 1, 2))
    assert partly.direct_answer.claim_ids == ("C2",)  # IDs are kept: C2 remains
    assert partly.direct_answer.status == DIRECT_SHOWN


def test_links_follow_a_claim_through_the_repair_pass():
    repaired, _ = ask(verdicts(C1="supported", C2="partially_supported"), verdicts(C2="supported"),
                      given=direct("yes", YES, 1, 2),
                      repair=rewrites(C2=[(INFORM_REPAIRED, [1])]))
    assert repaired.direct_answer == DirectAnswer("yes", YES, ("C1", "C2"), DIRECT_SHOWN)
    assert repaired.claims[1].repaired_from is not None and repaired.outcome == Outcome.ANSWER
    split, _ = ask(
        verdicts(C1="partially_supported", C2="supported"),
        verdicts(**{"C1.1": "supported", "C1.2": "partially_supported"}),
        given=direct("yes", YES, 1),
        repair=rewrites(C1=[("Il titolare notifica la violazione al Garante senza ingiustificato "
                             "ritardo.", [1]),
                            ("Ove possibile, la notifica avviene entro settantadue ore.", [2])]))
    # Only part of C1 was confirmed, and C1 stays held apart: the direct answer rests on both.
    assert split.direct_answer.claim_ids == ("C1.1", "C1")
    assert split.direct_answer.status == DIRECT_NOT_SUPPORTED


def test_an_open_question_gets_no_direct_answer_and_its_outcome_is_unchanged():
    result, _ = ask(BOTH, given=direct("yes", YES, 1), question_type="open")
    assert result.direct_answer is None and result.outcome == Outcome.ANSWER
    assert "direct_answer_ignored: the question type asks for none" in result.warnings
    plain, _ = ask(BOTH, question_type="open")
    assert plain.direct_answer is None and plain.outcome == Outcome.ANSWER


def test_a_premise_question_needs_a_direct_answer_too():
    result, _ = ask(BOTH, given=direct("no", "No: il termine è di settantadue ore.", 1),
                    question_type="premise")
    assert result.direct_answer.status == DIRECT_SHOWN and result.outcome == Outcome.ANSWER


def test_without_the_support_check_the_claims_of_the_main_answer_count():
    off, _ = ask(given=direct("yes", YES, 1), verify=False)
    assert off.direct_answer.status == DIRECT_SHOWN
    failed, _ = ask("not json", "not json", given=direct("yes", YES, 1))
    assert failed.direct_answer.status == DIRECT_NOT_SUPPORTED  # nothing was rated


def test_the_outcome_rule_with_a_direct_answer():
    supported = (["I1"], "SUPPORTED")
    assert decide_coverage(["I1"], [supported], [], "ran") == (True, [])
    assert decide_coverage(["I1"], [supported], [], "ran", direct=DIRECT_SHOWN) == (True, [])
    for status in (DIRECT_MISSING, DIRECT_NOT_ESTABLISHED, DIRECT_NOT_SUPPORTED,
                   DIRECT_BAD_REFERENCE):
        assert decide_coverage(["I1"], [supported], [], "ran", direct=status) == (False, [])


def test_rescoring_uses_the_saved_status_and_leaves_older_results_unchanged():
    base = {"analysis": {"issues": [{"id": "I1"}]}, "verification": {"task": "v"},
            "warnings": [], "claims": [{"issue_ids": ["I1"], "verification": "SUPPORTED"}],
            "unanswered_issues": [], "outcome": "answer"}
    assert run.rescore_result(base)["outcome"] == "answer"  # no direct_answer key
    assert run.rescore_result({**base, "direct_answer": None})["outcome"] == "answer"
    missing = {**base, "direct_answer": {"value": None, "text": None, "claim_ids": [],
                                         "status": DIRECT_MISSING}}
    assert run.rescore_result(missing)["outcome"] == "answer_limited"


@pytest.mark.parametrize("run_id", sorted(
    p.name for p in run.RUNS_DIR.glob("*")
    if p.name.startswith("2026-11-17-final") or p.name >= "2026-11-24"))
def test_saved_results_rescore_to_their_recorded_outcomes(run_id):
    """The runs made under the current outcome rule: the direct answer changes none of them."""
    _, saved = run.load_run(run.RUNS_DIR / run_id)
    for qid, item in saved.items():
        if "result" in item:
            assert run.rescore_result(item["result"])["outcome"] == item["result"]["outcome"], qid


# --- The page -----------------------------------------------------------------------------------

APP_JS = (run.PROJECT_ROOT / "src" / "web_static" / "app.js").read_text(encoding="utf-8")


def test_the_page_shows_the_direct_answer_as_an_interpretation_with_its_basis():
    for status, text in DIRECT_NOT_SHOWN.items():
        assert f'  {status}: "{text}"' in APP_JS  # the same words as the CLI
    assert 'if (direct.status !== "shown") {' in APP_JS
    assert "Direct answer: an interpretation of the statements marked «basis» below" in APP_JS
    assert 'isBasis ? el("span", { class: "kind-tag basis-tag" }, "Basis") : null' in APP_JS
    assert "renderStatement(claim, refById, statusById, basis.has(claim.claim_id))" in APP_JS
    assert "if (!direct) return null;" in APP_JS  # results made before it existed


# --- The benchmark ------------------------------------------------------------------------------


def benchmark_rows(**changes):
    row = {"query_id": "a01", "question": "Domanda?", "language": "it", "category": "breach",
           "expected_outcome": "answer", "expected_reason": None, "notes": None,
           "time_sensitive": None, "split": "dev",
           "provenance": {"drafted_by": "t", "drafted_on": "2026-11-26",
                          "review_status": "candidate", "reviewed_by": None,
                          "reviewed_on": None}}
    return {**row, **changes}


@pytest.mark.parametrize("changes, error", [
    ({"expected_direct_answer": "maybe"}, "expected_direct_answer must be one of"),
    ({"expected_direct_answer": "no", "expected_outcome": "abstain",
      "expected_reason": "out_of_scope"}, "an expected abstention has no direct answer"),
])
def test_the_expected_direct_answer_is_checked(changes, error):
    with pytest.raises(ab.BenchmarkError, match=error):
        ab._question(benchmark_rows(**changes), "row 1")


def test_the_expected_direct_answer_is_optional():
    assert ab._question(benchmark_rows(), "row 1").expected_direct_answer is None
    assert ab._question(benchmark_rows(expected_direct_answer="no"),
                        "row 1").expected_direct_answer == "no"


def test_the_report_scores_the_direct_answer_only_for_classified_questions():
    from tests.test_answer_benchmark_run import TEXTS, article_text, claim, item, question
    from tests.test_answer_benchmark_run import result as made, row
    expecting = dataclasses.replace(question("a01"), expected_direct_answer="no")
    base = made([item("E1", "1", TEXTS["1"])],
                [claim("C1", "E1", "Il titolare notifica la violazione", "SUPPORTED")])
    older = run.stage_metrics(expecting, [row("1")], base, article_text)
    assert "question_type" not in older and "direct_answers" not in run.aggregate([older])
    shown = {**base, "analysis": {"question_type": "yes_no"},
             "direct_answer": {"value": "no", "text": "No.", "claim_ids": ["C1"],
                               "status": "shown"}}
    entry = run.stage_metrics(expecting, [row("1")], shown, article_text)
    assert (entry["question_type"], entry["direct_answer"], entry["direct_answer_status"],
            entry["expected_direct_answer"], entry["direct_answer_match"]) == (
        "yes_no", "no", "shown", "no", True)
    open_ = run.stage_metrics(question("a02"), [row("1", qid="a02")],
                              {**base, "analysis": {"question_type": "yes_no"},
                               "direct_answer": {"value": "yes", "text": "Sì.",
                                                 "claim_ids": ["C1"], "status": "missing"}},
                              article_text)
    assert open_["direct_answer"] is None and open_["direct_answer_match"] is None
    assert run.aggregate([entry, open_])["direct_answers"] == {
        "expected": 1, "matched": 1, "shown": 1, "asked_without_expectation": 1,
        "expected_but_not_asked": 0}
    data = {"run": {"run_id": "t", "mode": "research", "model": "m", "build_id": "b",
                    "prompt_versions": {"query_analysis": "qa", "answer_generation": "ag",
                                        "claim_verification": "cv"},
                    "settings": {"final_evidence_count": 12, "context_token_budget": 12000}},
            "errors": {}, "scopes": {run.SCOPE_ALL: {"per_question": [entry, open_],
                                                     "aggregate": run.aggregate([entry, open_])}}}
    text = run.format_report(data)
    assert "[yes_no; direct no, expected no]" in text and "[yes_no; direct missing, expected -]" in text
    assert ("direct answers: shown 1; matching the expected one 1/1; asked for with none expected "
            "1; expected but not asked for 0") in text
    assert json.loads(json.dumps(data))  # plain data
