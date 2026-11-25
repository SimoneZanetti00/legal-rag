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
    Quote,
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
from src.claim_repair import TASK as REPAIR_TASK
from tests.test_answer_generation import (
    ART1,
    ART2,
    ART3,
    EVIDENCE,
    INFORM,
    NOTIFY,
    QUESTION,
    analysis,
    Q1,
    Q2,
    Q3,
    claim,
    item,
    reply,
)
from tests.test_text_normalization import ART6_1, ART6_1_READING, SHY

S = VerificationStatus


def verdicts(**levels):
    return {"verdicts": [{"claim_id": cid, "support": level} for cid, level in levels.items()]}


def declined(*verification_replies):
    """A repair reply that rewrites none of the claims the first support check held apart."""
    first = verification_replies[0] if verification_replies else None
    if not isinstance(first, dict):
        return None
    held = [v["claim_id"] for v in first["verdicts"]
            if v["support"] in ("partially_supported", "uncertain")]
    return {"repairs": [{"claim_id": cid, "rewrites": []} for cid in held]} if held else None


def rewrites(**claims):
    """A repair reply: claim ID -> [(text, quotation numbers), ...]."""
    return {"repairs": [{"claim_id": cid, "rewrites": [{"text": t, "quotes": list(q)}
                                                       for t, q in parts]}
                        for cid, parts in claims.items()]}


def run(*verification_replies, verify=True, generation=None, summary=False, repair=None):
    """generate_answer on scripted replies. Unless `repair` is given, the repair pass declines
    to rewrite, so the claims the support check held apart stay held apart."""
    script = {TASK: [generation or reply(NOTIFY, INFORM)]}
    if verification_replies:
        script[VERIFY_TASK] = list(verification_replies)
    repair = declined(*verification_replies) if repair is None else repair
    if repair is not None:
        script[REPAIR_TASK] = [repair] if isinstance(repair, dict) else list(repair)
    llm = MockLLM(script)
    return generate_answer(QUESTION, analysis(), EVIDENCE, llm, verify_support=verify,
                           show_summary=summary), llm


def test_schema_and_prompt():
    check_schema(SCHEMA)
    assert PROMPT_VERSION == "claim-verification-v3"
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


# --- The summary: only the sentences whose cited claims are all SUPPORTED and in the answer ----


def summarised(summary, *claims, **levels):
    generation = {**reply(*(claims or (NOTIFY, INFORM))), "summary": summary}
    return run(verdicts(**(levels or {"C1": "supported", "C2": "supported"})),
               generation=generation, summary=True)[0]


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


def test_only_the_summary_sentences_citing_supported_claims_are_shown():
    result = summarised("Il titolare notifica entro settantadue ore [1]. Lo comunica "
                        "all'interessato [2]. Il Garante vigila [1][2].",
                        C1="supported", C2="partially_supported")
    assert result.summary == "Il titolare notifica entro settantadue ore [C1]."
    assert result.summary_claim_ids == ("C1",)
    assert ("summary_sentences_left_out: sentence 2: it cites [2], which is not a supported "
            "claim of the answer; sentence 3: it cites [2], which is not a supported claim of "
            "the answer") in result.warnings


def test_a_summary_sentence_without_a_claim_reference_is_left_out():
    result = summarised("Notifica entro settantadue ore [1]. Una frase senza riferimenti. "
                        "Comunicazione all'interessato [2].")
    assert result.summary == ("Notifica entro settantadue ore [C1]. Comunicazione "
                              "all'interessato [C2].")
    assert any("sentence 2: it cites no claim" in w for w in result.warnings)


@pytest.mark.parametrize("text, sentences", [
    ("Lo prevede l'art. 33, par. 1 [1]. Il Garante vigila [2].",
     ["Lo prevede l'art. 33, par. 1 [1].", "Il Garante vigila [2]."]),
    ("Il d.lgs. n. 196 del 2003 e il Reg. (UE) 2016/679 [1]. «Entro 72 ore» [2]",
     ["Il d.lgs. n. 196 del 2003 e il Reg. (UE) 2016/679 [1].", "«Entro 72 ore» [2]"]),
    ("Notifica entro 72 ore. [1][2] Comunicazione [3].",
     ["Notifica entro 72 ore. [1][2]", "Comunicazione [3]."]),
])
def test_the_summary_is_split_into_sentences_at_sentence_ends_only(text, sentences):
    from src.answer_generation import _sentences
    assert _sentences(text) == sentences


def test_without_the_support_check_no_summary_is_shown():
    generation = {**reply(NOTIFY, INFORM), "summary": "Notifica [1]; comunicazione [2]."}
    result, _ = run(verify=False, generation=generation, summary=True)
    assert result.summary is None


def test_the_summary_is_not_shown_by_default():
    generation = {**reply(NOTIFY, INFORM), "summary": "Notifica [1]; comunicazione [2]."}
    result, _ = run(verdicts(C1="supported", C2="supported"), generation=generation)
    assert result.summary is None and result.summary_claim_ids == ()
    assert not any(w.startswith("summary") for w in result.warnings)
    from src.config import load_settings
    assert load_settings({}).show_summary is False
    assert load_settings({"SHOW_SUMMARY": "true"}).show_summary is True


def test_the_summary_is_asked_for_in_the_language_of_the_question():
    _, llm = run(verdicts(C1="supported", C2="supported"))
    assert "Write the summary in Italian too." in llm.calls[0].user
    assert "summary: two or three sentences" in SYSTEM_PROMPT_GENERATION


# --- The repair pass: one rewrite of the claims held apart, checked again ----------------------

INFORM_REPAIRED = "Il titolare comunica la violazione all'interessato senza ingiustificato ritardo."


def test_a_claim_confirmed_after_repair_enters_the_answer_marked_repaired():
    result, llm = run(verdicts(C1="supported", C2="partially_supported"), verdicts(C2="supported"),
                      repair=rewrites(C2=[(INFORM_REPAIRED, [1])]))
    assert [call.task for call in llm.calls] == [TASK, VERIFY_TASK, REPAIR_TASK, VERIFY_TASK]
    repaired = result.claims[1]
    assert (repaired.claim_id, repaired.text, repaired.verification) == (
        "C2", INFORM_REPAIRED, S.SUPPORTED)
    assert repaired.repaired_from == INFORM["text"] and repaired.quotes == (Quote("E2", Q3),)
    assert result.outcome == Outcome.ANSWER  # the unchanged outcome rule, on the repaired claims
    assert result.repair.prompt_version == "claim-repair-v1"
    assert result.repair_verification.prompt_version == PROMPT_VERSION
    repair_call, second_check = llm.calls[2], llm.calls[3]
    assert '<claim id="C2" rating="partially_supported">' in repair_call.user
    assert f'<quote n="1" evidence="E2">{Q3}</quote>' in repair_call.user
    assert '<claim id="C1"' not in repair_call.user  # only the claims held apart
    assert "Write every rewrite in Italian." in repair_call.user  # the answer's language
    assert '<claim id="C1"' not in second_check.user  # only the rewrites are checked again
    assert "rewritten from: " + INFORM["text"] in render_answer(result)


def test_a_rewrite_not_confirmed_leaves_the_claim_held_apart():
    result, _ = run(verdicts(C1="supported", C2="partially_supported"), verdicts(C2="uncertain"),
                    repair=rewrites(C2=[(INFORM_REPAIRED, [1])]))
    assert [(c.claim_id, c.verification, c.repaired_from) for c in result.claims] == [
        ("C1", S.SUPPORTED, None), ("C2", S.PARTIALLY_SUPPORTED, None)]
    assert "repair_not_confirmed: C2 (uncertain)" in result.warnings
    assert result.outcome == Outcome.ANSWER_LIMITED


def test_a_split_claim_keeps_its_confirmed_parts_and_its_original_held_apart():
    result, _ = run(
        verdicts(C1="partially_supported", C2="supported"),
        verdicts(**{"C1.1": "supported", "C1.2": "partially_supported"}),
        repair=rewrites(C1=[("Il titolare notifica la violazione al Garante senza ingiustificato "
                             "ritardo.", [1]),
                            ("Ove possibile, la notifica avviene entro settantadue ore.", [2])]))
    assert [(c.claim_id, c.verification) for c in result.claims] == [
        ("C1.1", S.SUPPORTED), ("C1", S.PARTIALLY_SUPPORTED), ("C2", S.SUPPORTED)]
    assert result.claims[0].repaired_from == NOTIFY["text"]
    assert result.claims[0].quotes == (Quote("E1", Q1),)
    assert "repair_not_confirmed: C1.2 (partially_supported)" in result.warnings
    assert result.outcome == Outcome.ANSWER


def test_a_rewrite_failing_the_deterministic_checks_is_dropped():
    result, llm = run(verdicts(C1="supported", C2="partially_supported"),
                      repair=rewrites(C2=[("Lo prevede l'articolo 99.", [1])]))
    assert [call.task for call in llm.calls] == [TASK, VERIFY_TASK, REPAIR_TASK]
    assert result.claims[1].verification == S.PARTIALLY_SUPPORTED
    assert any(w.startswith("repair_rejected: C2 (") for w in result.warnings)
    assert result.repair is not None and result.repair_verification is None


def test_a_repair_that_cannot_be_obtained_changes_nothing():
    result, _ = run(verdicts(C1="supported", C2="partially_supported"),
                    repair=["not json", "still not json"])
    assert result.claims[1].verification == S.PARTIALLY_SUPPORTED and result.repair is None
    assert "claim_repair_unavailable: LLMMalformedOutputError" in result.warnings


def test_the_repair_prompt_and_the_check_of_its_reply():
    from src.claim_repair import SCHEMA as REPAIR_SCHEMA
    from src.claim_repair import SYSTEM_PROMPT as REPAIR_PROMPT
    from src.claim_repair import ClaimToRepair, repair_claims
    check_schema(REPAIR_SCHEMA)
    assert "states only what its own quotations state" in REPAIR_PROMPT
    assert "keep the same quotations" in REPAIR_PROMPT and "You cannot add a quotation" in REPAIR_PROMPT
    assert 'do not add words such as "only", "always", "never"' in REPAIR_PROMPT
    llm = MockLLM({REPAIR_TASK: [rewrites(C2=[("Testo.", [2])]),  # C2 has one quotation
                                 rewrites(C2=[("Testo.", [1, 1])])]})
    out = repair_claims([ClaimToRepair("C2", "Testo", "uncertain", (("E2", Q3),))], llm)
    assert out.rewrites["C2"][0].quotes == (1,) and out.result.attempts == 2
    assert "must name its quotations by number" in llm.calls[1].user


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
        "limit notification to high-risk breaches and extend the deadline to 96 hours; this "
        "answer reflects the text in force in the corpus (72 hours).")


def test_an_italian_question_shows_the_fixed_qualifications_in_italian():
    from src.answer_generation import (
        RESEARCH_QUALIFICATION,
        VALIDITY_QUALIFICATION,
        display_qualifications,
    )
    result, _ = run(verdicts(C1="supported", C2="supported"))
    other = "Some other qualification."
    english = (VALIDITY_QUALIFICATION, RESEARCH_QUALIFICATION,
               AS_OF_QUALIFICATION.format(as_of="2026-11-17"), DIGITAL_OMNIBUS_CAVEAT, other)
    italian_question = dataclasses.replace(result, qualifications=english)
    shown = display_qualifications(italian_question)
    assert shown[:4] == (
        "Questo sistema non stabilisce se una disposizione sia giuridicamente valida, in vigore o "
        "applicabile a una qualsiasi data.",
        "MODALITÀ DIMOSTRATIVA DI RICERCA: questo risultato può basarsi su disposizioni "
        "il cui testo non ha superato la revisione umana. Ogni fonte qui sotto indica il proprio "
        "stato di revisione; una fonte in attesa di revisione non è citabile in modalità "
        "verificata e non va considerata verificata.",
        "Data di riferimento 2026-11-17: questa risposta riflette i testi presenti nel corpus a "
        "tale data. Non stabilisce il diritto vigente a quella data o successivamente.",
        "Una proposta in corso (Digital Omnibus, COM(2025) 837, non adottata al 2026-11-08) "
        "limiterebbe la notifica alle violazioni ad alto rischio ed estenderebbe il termine a 96 "
        "ore; questa risposta riflette il testo in vigore presente nel corpus (72 ore).")
    assert shown[4] == other  # anything else is shown as it is
    assert italian_question.qualifications == english  # the result keeps the English text
    assert "Data di riferimento 2026-11-17" in render_answer(italian_question)
    english_question = dataclasses.replace(
        italian_question, analysis=dataclasses.replace(result.analysis, language="en"))
    assert display_qualifications(english_question) == english
    assert display_qualifications(dataclasses.replace(italian_question, analysis=None)) == english


# --- The support check rates a claim against its own quotations --------------------------------


def test_the_verifier_sees_each_claims_quotations_and_is_told_to_rate_by_them():
    from src.support_verification import SYSTEM_PROMPT as VERIFY_PROMPT
    _, llm = run(verdicts(C1="supported", C2="supported"))
    user = llm.calls[1].user
    assert f'<quote evidence="E1">{Q1}</quote>' in user and f'<quote evidence="E2">{Q3}</quote>' in user
    assert "every element of the claim is covered by them" in VERIFY_PROMPT
    assert "stated only by item text that the claim does not quote" in VERIFY_PROMPT


def test_the_generator_is_told_to_quote_each_listed_element():
    assert "When a claim lists several elements" in SYSTEM_PROMPT_GENERATION
    assert "quote each element" in SYSTEM_PROMPT_GENERATION
