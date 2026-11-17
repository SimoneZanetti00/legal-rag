"""Evidence-support verification (src/support_verification.py) inside answer generation.

MockLLM only: the verdicts are scripted stand-ins for model output, so these tests check what the
application does with each verdict, not how well a model judges support.
"""

import dataclasses

import pytest

from src.answer_generation import (
    AS_OF_QUALIFICATION,
    DIGITAL_OMNIBUS_CAVEAT,
    HELD_CLAIMS_TITLE,
    HELD_ONLY,
    NOT_COVERED,
    HELD_SOURCES_TITLE,
    NOT_VERIFIED_QUALIFICATION,
    REPORTED_UNANSWERED,
    SUPPORT_FAILED_NOTICE,
    SUPPORT_NOT_RUN_NOTICE,
    SUPPORT_QUALIFICATION,
    TASK,
    AnswerClaim,
    Outcome,
    generate_answer,
    answer_sources,
    dated,
    decide_coverage,
    in_answer,
    support_check_notice,
)
from src.answer_generation import SYSTEM_PROMPT as SYSTEM_PROMPT_GENERATION
from src.llm import MockLLM, check_schema
from src.models import VerificationStatus
from src.provision_cli import render_answer
from src.support_verification import (
    PROMPT_VERSION,
    SCHEMA,
    SYSTEM_PROMPT,
    ClaimToVerify,
    build_user_message,
)
from src.support_verification import TASK as VERIFY_TASK
from tests.test_answer_generation import (
    ART1,
    ART2,
    ART3,
    EVIDENCE,
    INFORM,
    NOTIFY,
    QUESTION,
    analysis,
    Q2,
    claim,
    item,
    reply,
)
from tests.test_text_normalization import ART6_1, ART6_1_READING, SHY

S = VerificationStatus


def verdicts(**levels):
    return {"verdicts": [{"claim_id": cid, "support": level} for cid, level in levels.items()]}


def run(*verification_replies, verify=True, generation=None):
    script = {TASK: [generation or reply(NOTIFY, INFORM)]}
    if verification_replies:
        script[VERIFY_TASK] = list(verification_replies)
    llm = MockLLM(script)
    return generate_answer(QUESTION, analysis(), EVIDENCE, llm, verify_support=verify), llm


def test_schema_and_prompt():
    check_schema(SCHEMA)
    assert PROMPT_VERSION == "claim-verification-v2"
    assert "only against its own cited items" in SYSTEM_PROMPT
    assert "not judging whether the law is correct, valid or in force" in SYSTEM_PROMPT


def test_the_verifier_reads_the_evidence_in_its_reading_form():
    evidence = item("E1", "6", ART6_1, instrument="eu-reg-2016-679")
    user = build_user_message([ClaimToVerify("C1", "Il trattamento è lecito.", ("E1",))],
                              [evidence])
    assert ART6_1_READING in user and ART6_1 not in user and SHY not in user
    assert evidence.text == ART6_1  # the stored text is unchanged


def test_directly_supported_claims_make_a_complete_answer():
    result, llm = run(verdicts(C1="supported", C2="supported"))
    assert result.outcome == Outcome.ANSWER
    assert [c.verification for c in result.claims] == [S.SUPPORTED, S.SUPPORTED]
    assert SUPPORT_QUALIFICATION in result.qualifications
    assert NOT_VERIFIED_QUALIFICATION not in result.qualifications
    assert result.verification.prompt_version == PROMPT_VERSION
    assert [call.task for call in llm.calls] == [TASK, VERIFY_TASK]


def test_a_partially_supported_claim_is_kept_but_limits_the_answer():
    result, _ = run(verdicts(C1="supported", C2="partially_supported"))
    assert result.outcome == Outcome.ANSWER_LIMITED
    assert [(c.claim_id, c.verification) for c in result.claims] == [
        ("C1", S.SUPPORTED), ("C2", S.PARTIALLY_SUPPORTED)]


def test_an_unsupported_claim_is_removed():
    result, _ = run(verdicts(C1="supported", C2="unsupported"))
    assert result.outcome == Outcome.ANSWER_LIMITED
    assert [c.claim_id for c in result.claims] == ["C1"]
    assert result.rejected_claims[0].reasons == ("not_supported_by_evidence",)
    assert [(u.issue_id, u.reason) for u in result.unanswered_issues] == [
        ("I2", "No validated claim addresses this issue.")]
    assert [c.evidence_id for c in result.citations] == ["E1"]  # E2 is no longer cited


def test_with_every_claim_unsupported_the_system_abstains():
    result, _ = run(verdicts(C1="unsupported", C2="unsupported"))
    assert (result.outcome, result.abstention_reason) == (Outcome.ABSTAIN, "no_supported_claims")
    assert "not_supported_by_evidence" in result.abstention_detail
    assert result.claims == () and result.verification is not None


def test_uncertain_support_is_kept_unverified():
    result, _ = run(verdicts(C1="uncertain", C2="supported"))
    assert result.outcome == Outcome.ANSWER_LIMITED
    assert result.claims[0].verification == S.UNCERTAIN


def test_unsupported_or_uncertain_claims_are_never_shown_as_verified():
    result, _ = run(verdicts(C1="uncertain", C2="partially_supported"))
    text = render_answer(result)
    assert "C1 [I1] (source statement; support: uncertain)" in text
    assert "C2 [I2] (source statement; support: partially supported)" in text
    assert "support: supported" not in text
    assert "support was assessed by a model, which is not legal validation" in text
    assert "a claim marked partially supported or uncertain is not verified" in text


def test_disabling_the_verifier_keeps_the_deterministic_checks():
    result, llm = run(verify=False)  # no verification script: a call would fail
    assert result.outcome == Outcome.ANSWER
    assert all(c.verification == S.NOT_VERIFIED for c in result.claims)
    assert NOT_VERIFIED_QUALIFICATION in result.qualifications and result.verification is None
    assert [call.task for call in llm.calls] == [TASK]


@pytest.mark.parametrize("bad", [
    "not json",
    verdicts(C1="supported"),  # C2 missing
    verdicts(C1="supported", C2="supported", C9="supported"),  # unknown claim
    {"verdicts": [{"claim_id": "C1", "support": "probably"}]},  # not a level
])
def test_a_verifier_that_fails_leaves_claims_unverified(bad):
    result, llm = run(bad, bad)
    assert result.outcome == Outcome.ANSWER_LIMITED  # nothing assessed, so not complete
    assert all(c.verification == S.NOT_VERIFIED for c in result.claims)
    assert "support_verification_unavailable: " in "; ".join(result.warnings)
    assert result.verification is None and NOT_VERIFIED_QUALIFICATION in result.qualifications
    assert [call.task for call in llm.calls] == [TASK, VERIFY_TASK, VERIFY_TASK]


def test_the_verifier_sees_only_the_claims_and_their_cited_evidence():
    _, llm = run(verdicts(C1="supported", C2="supported"))
    user = llm.calls[1].user
    assert '<claim id="C1" cites="E1">' in user and '<claim id="C2" cites="E2">' in user
    assert ART1.split("\n")[0] in user and ART2 in user
    assert ART3 not in user  # E3 is in the evidence set but cited by no claim
    assert QUESTION not in user  # the question itself is not sent to the verifier


# --- Claims not rated SUPPORTED are shown apart from the answer --------------------------------


def sections(text):
    """(main answer, its citations, held section) of a rendered result; held may be empty."""
    answer = text[text.index("answer (each claim"):text.index("citations (citable")]
    start = text.index("citations (citable")
    citations = text[start:text.index("\n\n", start)]
    if HELD_CLAIMS_TITLE not in text:
        return answer, citations, ""
    start = text.index(HELD_CLAIMS_TITLE)
    return answer, citations, text[start:text.index("\n\n", start)]


def test_only_supported_or_unrated_claims_are_in_the_answer():
    def rated(status):
        return AnswerClaim("C1", ("I1",), "source_statement", "Testo.", (), status)

    assert [in_answer(rated(s)) for s in (
        S.SUPPORTED, S.NOT_VERIFIED, S.PARTIALLY_SUPPORTED, S.UNCERTAIN)] == [
        True, True, False, False]


def test_a_partially_supported_claim_is_shown_below_the_answer_with_its_quotations():
    result, _ = run(verdicts(C1="supported", C2="partially_supported"))
    assert result.outcome == Outcome.ANSWER_LIMITED  # the outcome rules are unchanged
    assert [c.claim_id for c in result.claims] == ["C1", "C2"]  # and so is the result
    answer, citations, held = sections(render_answer(result))
    assert "C1 [I1] (source statement; support: supported)" in answer and "C2 [" not in answer
    assert held.startswith(f"{HELD_CLAIMS_TITLE}:")
    assert "C2 [I2] (source statement; support: partially supported)" in held
    assert all(f"{q.evidence_id}: «" in held for q in result.claims[1].quotes)


def test_when_no_claim_is_rated_supported_the_answer_says_so():
    result, _ = run(verdicts(C1="uncertain", C2="partially_supported"))
    answer, citations, held = sections(render_answer(result))
    assert "(no claim was rated supported by the support check)" in answer
    assert "support: uncertain" in held and "support: partially supported" in held


def test_without_the_support_check_unrated_claims_stay_in_the_answer():
    result, _ = run(verify=False)
    answer, citations, held = sections(render_answer(result))
    assert held == "" and "C1 [I1]" in answer and "C2 [I2]" in answer


def test_an_answer_the_support_check_did_not_rate_says_so_at_the_top():
    answer, _, _ = sections(render_answer(run(verify=False)[0]))
    assert answer.split("\n")[1] == f"  NOTE: {SUPPORT_NOT_RUN_NOTICE}"
    bad = {"verdicts": [{"claim_id": "C1", "support": "probably"}]}
    failed, _ = run(bad, bad)
    assert support_check_notice(failed) == SUPPORT_FAILED_NOTICE
    assert f"  NOTE: {SUPPORT_FAILED_NOTICE}" in render_answer(failed)
    rated, _ = run(verdicts(C1="supported", C2="supported"))
    assert support_check_notice(rated) is None and "NOTE: " not in render_answer(rated)


def test_sources_of_held_apart_claims_are_listed_with_those_claims_only():
    result, _ = run(verdicts(C1="supported", C2="partially_supported"))  # C1 cites E1, C2 E2
    main, held = answer_sources(result)
    assert [r.evidence_id for r in main] == ["E1"] and [r.evidence_id for r in held] == ["E2"]
    _, citations, held_text = sections(render_answer(result))
    assert "[E1]" in citations and "[E2]" not in citations
    assert f"  {HELD_SOURCES_TITLE}:" in held_text and "[E2]" in held_text
    assert "[E1]" not in held_text.split(HELD_SOURCES_TITLE)[1]
    assert [r.evidence_id for r in result.citations] == ["E1", "E2"]  # the result is unchanged


# --- The outcome rule: every issue covered by a SUPPORTED claim of the main answer --------------


def test_an_issue_covered_only_by_held_apart_claims_limits_the_answer():
    result, _ = run(verdicts(C1="supported", C2="partially_supported"))
    assert result.outcome == Outcome.ANSWER_LIMITED
    assert [(u.issue_id, u.reason) for u in result.unanswered_issues] == [("I2", HELD_ONLY)]


def test_a_held_apart_claim_does_not_limit_an_answer_whose_issues_are_covered():
    extra = claim("Ove possibile, entro settantadue ore.", ("E1", Q2))  # a third claim, on I1
    result, _ = run(verdicts(C1="supported", C2="supported", C3="partially_supported"),
                    generation=reply(NOTIFY, INFORM, extra))
    assert result.outcome == Outcome.ANSWER
    assert [c.verification for c in result.claims] == [S.SUPPORTED, S.SUPPORTED,
                                                       S.PARTIALLY_SUPPORTED]
    assert result.unanswered_issues == ()


def test_the_models_partly_answered_report_limits_the_answer():
    generation = reply(NOTIFY, INFORM, outcome="answer_limited",
                       unanswered=[("I2", "Le prove non bastano.")])
    result, _ = run(verdicts(C1="supported", C2="supported"), generation=generation)
    assert result.outcome == Outcome.ANSWER_LIMITED  # I2 has a supported claim, but see below
    assert [(u.issue_id, u.reason) for u in result.unanswered_issues] == [
        ("I2", REPORTED_UNANSWERED)]
    # The model's outcome label alone, with no issue reported, does not decide the outcome.
    label_only = reply(NOTIFY, INFORM, outcome="answer_limited")
    result, _ = run(verdicts(C1="supported", C2="supported"), generation=label_only)
    assert result.outcome == Outcome.ANSWER and result.unanswered_issues == ()


@pytest.mark.parametrize("claims, reported, check, expected", [
    ([(("I1",), "SUPPORTED"), (("I2",), "SUPPORTED")], [], "ran", (True, [])),
    ([(("I1",), "SUPPORTED"), (("I2",), "UNCERTAIN")], [], "ran", (False, [("I2", HELD_ONLY)])),
    ([(("I1",), "SUPPORTED")], [], "ran", (False, [("I2", NOT_COVERED)])),
    ([(("I1",), "SUPPORTED"), (("I2",), "SUPPORTED")], ["I2"], "ran", (False, [])),
    ([(("I1", "I2"), "NOT_VERIFIED")], [], "off", (True, [])),
    ([(("I1", "I2"), "NOT_VERIFIED")], [], "failed", (False, [])),
])
def test_decide_coverage(claims, reported, check, expected):
    assert decide_coverage(["I1", "I2"], claims, reported, check) == expected


# --- The summary: shown only when every claim it cites is SUPPORTED and in the answer -----------


def summarised(summary, *claims, **levels):
    generation = {**reply(*(claims or (NOTIFY, INFORM))), "summary": summary}
    return run(verdicts(**(levels or {"C1": "supported", "C2": "supported"})),
               generation=generation)[0]


def test_a_summary_citing_supported_claims_is_shown_with_claim_ids():
    result = summarised("Il titolare notifica la violazione entro settantadue ore [1]. Se il "
                        "rischio è elevato la comunica all'interessato [2].")
    assert result.summary == ("Il titolare notifica la violazione entro settantadue ore [C1]. Se "
                              "il rischio è elevato la comunica all'interessato [C2].")
    assert result.summary_claim_ids == ("C1", "C2")
    assert render_answer(result).split("answer (each claim")[1].split("\n")[1] == (
        f"  summary: {result.summary}")


def test_the_summary_follows_the_claims_through_removals():
    fabricated = claim("Il titolare paga una sanzione.", ("E1", "il titolare paga una sanzione "
                                                                "amministrativa"), issues=("I2",))
    result = summarised("Notifica [2]; comunicazione [3].", fabricated, NOTIFY, INFORM)
    assert [c.claim_id for c in result.claims] == ["C1", "C2"]  # the fabricated claim is gone
    assert result.summary == "Notifica [C1]; comunicazione [C2]."


@pytest.mark.parametrize("summary, levels, reason", [
    ("Notifica [1]; comunicazione [2].", {"C1": "supported", "C2": "partially_supported"},
     "it cites [2], which is not a supported claim"),
    ("Una sintesi senza riferimenti.", {}, "it cites no claim"),
    ("Notifica [1], come prevede l'articolo 99 [2].", {}, "unsupported reference articolo 99"),
    ("Notifica [7].", {}, "it cites [7]"),
])
def test_a_summary_failing_a_check_is_not_shown(summary, levels, reason):
    result = summarised(summary, **levels)
    assert result.summary is None and result.summary_claim_ids == ()
    assert any(w.startswith("summary_not_shown: ") and reason in w for w in result.warnings)


def test_without_the_support_check_no_summary_is_shown():
    generation = {**reply(NOTIFY, INFORM), "summary": "Notifica [1]; comunicazione [2]."}
    result, _ = run(verify=False, generation=generation)
    assert result.summary is None


def test_the_summary_is_asked_for_in_the_language_of_the_question():
    _, llm = run(verdicts(C1="supported", C2="supported"))
    assert "Write the summary in Italian too." in llm.calls[0].user
    assert "summary: two or three sentences" in SYSTEM_PROMPT_GENERATION


# --- The as-of date and the Digital Omnibus caveat (application, not the model) ----------------


def test_every_answer_gets_its_as_of_date_and_art_33_answers_the_omnibus_caveat():
    result, _ = run(verdicts(C1="supported", C2="supported"))
    plain = dated(result, "2026-11-17")
    assert plain.as_of == "2026-11-17"
    assert AS_OF_QUALIFICATION.format(as_of="2026-11-17") in plain.qualifications
    assert DIGITAL_OMNIBUS_CAVEAT not in plain.qualifications  # x-act Art. 1, not GDPR Art. 33
    gdpr33 = dataclasses.replace(result, citations=tuple(
        dataclasses.replace(ref, instrument_id="eu-reg-2016-679", label="33")
        for ref in result.citations[:1]))
    assert DIGITAL_OMNIBUS_CAVEAT in dated(gdpr33, "2026-11-17").qualifications
    assert "as of: 2026-11-17" in render_answer(plain)
    assert DIGITAL_OMNIBUS_CAVEAT == (
        "A pending proposal (Digital Omnibus, COM(2025) 837, not adopted as of 2026-11-08) would "
        "change the Art. 33 threshold and deadline; this answer reflects the text in the corpus.")
