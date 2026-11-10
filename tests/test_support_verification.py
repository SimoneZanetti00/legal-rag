"""Evidence-support verification (src/support_verification.py) inside answer generation.

MockLLM only: the verdicts are scripted stand-ins for model output, so these tests check what the
application does with each verdict, not how well a model judges support.
"""

import pytest

from src.answer_generation import (
    NOT_VERIFIED_QUALIFICATION,
    SUPPORT_QUALIFICATION,
    TASK,
    Outcome,
    generate_answer,
)
from src.llm import MockLLM, check_schema
from src.models import VerificationStatus
from src.provision_cli import render_answer
from src.support_verification import PROMPT_VERSION, SCHEMA, SYSTEM_PROMPT
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
    reply,
)

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
    assert PROMPT_VERSION == "claim-verification-v1"
    assert "only against its own cited items" in SYSTEM_PROMPT
    assert "not judging whether the law is correct, valid or in force" in SYSTEM_PROMPT


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
