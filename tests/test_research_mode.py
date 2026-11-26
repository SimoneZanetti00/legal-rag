"""Research demo mode and verified mode (answer_generation.Mode), with MockLLM only.

The two modes are evidence policies over one pipeline. These tests check that:
- verified mode is unchanged: the default, the same result as before, the same abstentions;
- research mode may rest an answer on provisions pending human review, and only on those and
  citable ones, while every other check still applies (exact quotations, references, support
  check, abstention) and every item keeps its tier and citable flag;
- retrieval and evidence assembly are identical in both modes;
- nothing in the review data changes.

The synthetic act (src/demo.py) gives a reviewed Art. 1 and Art. 3, an unreviewed Art. 2 and
blocked Arts. 4 and 4-bis. Tests marked "recorded build" use the real corpus with scripted
replies and skip without it. No test sends a request to a model provider.
"""

import copy
import dataclasses
import hashlib
import json

import pytest

import src.demo as demo
from src.answer_generation import (
    NO_CITABLE_EVIDENCE,
    NO_ITEM_CITABLE_IN_VERIFIED_MODE,
    RESEARCH_QUALIFICATION,
    Mode,
    Outcome,
    answer_question,
    generate_answer,
    usable,
    validate_claims,
)
from src.answer_generation import TASK as GENERATION_TASK
from src.config import PROJECT_ROOT, load_settings
from src.llm import MockLLM
from src.models import VerificationStatus
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.provisions import load_ledger
from src.query_analysis import TASK as ANALYSIS_TASK
from src.source_status import CATEGORIES, evidence_status
from src.support_verification import TASK as VERIFICATION_TASK

SETTINGS = load_settings({})  # defaults: 5 evidence items, 3,000 tokens, support check on
TEXTS = [claim["text"] for _, _, claim in demo.SCRIPTED_CLAIMS]
E2_CLAIM = TEXTS[4]  # the claim quoting the unreviewed Art. 2


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    """The fictional act's explorer, built once."""
    return demo.build_synthetic_corpus(tmp_path_factory.mktemp("valdoria"))


def script(generation=None, verification=None, analysis=None):
    return {ANALYSIS_TASK: [analysis or demo.ANALYSIS_REPLY],
            GENERATION_TASK: [generation or demo.GENERATION_REPLY],
            VERIFICATION_TASK: [verification or demo.VERIFICATION_REPLY]}


def run(explorer, mode=None, **replies):
    llm = MockLLM(script(**replies))
    kwargs = {} if mode is None else {"mode": mode}
    return answer_question(demo.SYNTHETIC_QUESTION, llm, explorer, settings=SETTINGS,
                           **kwargs), llm


# Research mode validates four claims (C1 Art. 1, C2 Art. 3, C3 Art. 2, C4 the overstated one).
RESEARCH_VERDICTS = {"verdicts": [{"claim_id": "C1", "support": "supported"},
                                  {"claim_id": "C2", "support": "supported"},
                                  {"claim_id": "C3", "support": "supported"},
                                  {"claim_id": "C4", "support": "unsupported"}]}


# --- Verified mode is unchanged ----------------------------------------------------------------


def test_verified_is_the_default_and_behaves_as_before(synthetic):
    default, llm = run(synthetic)
    explicit, _ = run(synthetic, Mode.VERIFIED)
    assert default.to_dict() == explicit.to_dict()
    assert default.mode == "verified" and RESEARCH_QUALIFICATION not in default.qualifications
    demo._check_synthetic(default, llm)  # every statement the offline demo makes still holds
    removed = {r.text: r.reasons for r in default.rejected_claims}
    assert removed[E2_CLAIM] == ("not_citable:E2",)


def test_an_unknown_mode_is_refused(synthetic):
    with pytest.raises(ValueError):
        answer_question(demo.SYNTHETIC_QUESTION, MockLLM(script()), synthetic,
                        settings=SETTINGS, mode="unsafe")


# --- Research mode -----------------------------------------------------------------------------


def test_research_mode_may_rest_on_a_provision_pending_review(synthetic):
    result, llm = run(synthetic, Mode.RESEARCH, verification=RESEARCH_VERDICTS)
    assert result.mode == "research"
    assert result.qualifications[0] == RESEARCH_QUALIFICATION
    assert [c.text for c in result.claims] == [TEXTS[0], TEXTS[1], E2_CLAIM]
    assert all(c.verification == VerificationStatus.SUPPORTED for c in result.claims)
    by_id = {ref.evidence_id: ref for ref in result.citations}
    assert set(by_id) == {"E1", "E2", "E3"}
    # Art. 2 keeps its status: it is cited in research mode, never made citable.
    assert (by_id["E2"].tier, by_id["E2"].citable) == ("internal_only", False)
    assert "structure_not_reviewed" in by_id["E2"].reasons
    assert (by_id["E1"].citable, by_id["E3"].citable) == (True, True)
    assert result.non_authoritative == ()
    # The model was given Art. 2 in research mode, and the same three tasks ran.
    assert [c.task for c in llm.calls] == [ANALYSIS_TASK, GENERATION_TASK, VERIFICATION_TASK]
    assert "titolari delle schede entro sette giorni" in llm.calls[1].user


def test_every_check_still_applies_in_research_mode(synthetic):
    result, _ = run(synthetic, Mode.RESEARCH, verification=RESEARCH_VERDICTS)
    removed = {r.text: r.reasons for r in result.rejected_claims}
    assert removed == {
        TEXTS[2]: ("quote_not_found:E1",),  # a fabricated quotation
        TEXTS[3]: ("unsupported_reference:articolo 9",),  # a citation no evidence supports
        TEXTS[5]: ("not_supported_by_evidence",),  # removed by the support check
    }
    assert result.verification is not None  # the support check ran
    # Removed claims do not limit the answer by themselves: every issue keeps a supported claim.
    assert result.outcome == Outcome.ANSWER


def test_retrieval_and_evidence_are_identical_in_both_modes(synthetic):
    verified, _ = run(synthetic, Mode.VERIFIED)
    research, _ = run(synthetic, Mode.RESEARCH, verification=RESEARCH_VERDICTS)
    assert research.evidence.to_dict() == verified.evidence.to_dict()
    assert research.analysis == verified.analysis
    assert research.preflight == verified.preflight
    assert research.question_references == verified.question_references
    assert research.generation.prompt_version == verified.generation.prompt_version


def test_claims_link_only_to_retrieved_evidence(synthetic):
    reply = copy.deepcopy(demo.GENERATION_REPLY)
    reply["claims"].append(demo._claim("I1", "Il custode segnala ogni incidente.",
                                       ("E9", "segnala ogni incidente informativo all'Ufficio")))
    result, _ = run(synthetic, Mode.RESEARCH, generation=reply, verification=RESEARCH_VERDICTS)
    ids = {item.evidence_id for item in result.evidence.items}
    for claim in result.claims:
        assert set(claim.evidence_ids) <= ids
        assert set(claim.evidence_ids) <= {ref.evidence_id for ref in result.citations}
    assert ("unknown_evidence:E9",) in [r.reasons for r in result.rejected_claims]


def test_blocked_provisions_stay_unusable_in_research_mode(synthetic):
    verified, _ = run(synthetic, Mode.VERIFIED)
    evidence = verified.evidence
    blocked = dataclasses.replace(
        evidence, items=tuple(dataclasses.replace(i, tier="blocked", citable=False)
                              if i.evidence_id == "E2" else i for i in evidence.items))
    item = {i.evidence_id: i for i in blocked.items}["E2"]
    assert not usable(item, Mode.RESEARCH) and not usable(item, Mode.VERIFIED)
    kept, rejected = validate_claims([demo.SCRIPTED_CLAIMS[4][2]], issue_ids={"I1", "I2", "I3"},
                                     evidence=blocked, mode=Mode.RESEARCH)
    assert kept == [] and rejected[0].reasons == ("not_usable:E2",)
    # Nothing usable at all: abstain before the generation call.
    all_blocked = dataclasses.replace(evidence, items=tuple(
        dataclasses.replace(i, tier="blocked", citable=False) for i in evidence.items))
    llm = MockLLM({})
    result = generate_answer(demo.SYNTHETIC_QUESTION, verified.analysis, all_blocked, llm,
                             mode=Mode.RESEARCH)
    assert (result.outcome, result.abstention_reason) == (Outcome.ABSTAIN, NO_CITABLE_EVIDENCE)
    assert "even in research mode" in result.abstention_detail
    assert llm.calls == [] and result.mode == "research"


def test_an_out_of_scope_question_abstains_in_research_mode(synthetic):
    analysis = {**demo.ANALYSIS_REPLY, "in_scope": False, "issues": [],
                "search_queries_it": [], "scope_reason": "Riguarda un altro ramo del diritto."}
    result, llm = run(synthetic, Mode.RESEARCH, analysis=analysis)
    assert (result.outcome, result.abstention_reason) == (Outcome.ABSTAIN, "out_of_scope")
    assert [c.task for c in llm.calls] == [ANALYSIS_TASK]  # no generation call
    assert result.qualifications[0] == RESEARCH_QUALIFICATION


def test_insufficient_evidence_abstains_in_research_mode(synthetic):
    reply = {"outcome": "abstain", "claims": [], "unanswered_issues": [], "limitations": [],
             "abstention_reason": "The evidence does not answer the question.",
             "direct_answer": None}
    result, _ = run(synthetic, Mode.RESEARCH, generation=reply)
    assert (result.outcome, result.abstention_reason) == (Outcome.ABSTAIN, "model_abstained")
    assert "supplied evidence (E1, E2, E3)" in result.abstention_detail
    assert result.claims == () and result.citations == ()


def test_research_mode_reports_no_citable_item_as_information():
    from tests.test_answer_generation import ART1, QUESTION, analysis, claim, evidence_set, item
    from tests.test_answer_generation import reply as generation_reply
    pending = evidence_set(item("E1", "1", ART1, tier="internal_only"),
                           warnings=("no_citable_evidence",))
    answer = generation_reply(claim("Il titolare notifica la violazione al Garante.",
                                    ("E1", "notifica la violazione al Garante")))
    research = generate_answer(QUESTION, analysis(), pending,
                               MockLLM({GENERATION_TASK: [answer]}), mode=Mode.RESEARCH)
    assert research.outcome != Outcome.ABSTAIN
    assert NO_ITEM_CITABLE_IN_VERIFIED_MODE in research.warnings
    assert "no_citable_evidence" not in research.warnings
    assert research.evidence.warnings == ("no_citable_evidence",)  # the evidence set is unchanged
    verified = generate_answer(QUESTION, analysis(), pending, MockLLM({}))
    assert (verified.outcome, verified.abstention_reason) == (Outcome.ABSTAIN, NO_CITABLE_EVIDENCE)
    assert "no_citable_evidence" in verified.warnings
    assert NO_ITEM_CITABLE_IN_VERIFIED_MODE not in verified.warnings


def test_research_results_serialise_with_their_mode(synthetic):
    result, _ = run(synthetic, Mode.RESEARCH, verification=RESEARCH_VERDICTS)
    data = json.loads(json.dumps(result.to_dict(), ensure_ascii=False))
    assert data["mode"] == "research"
    assert {c["evidence_id"]: c["citable"] for c in data["citations"]}["E2"] is False


# --- Source status -----------------------------------------------------------------------------


def test_source_status_states_each_distinction(synthetic):
    result, _ = run(synthetic, Mode.RESEARCH, verification=RESEARCH_VERDICTS)
    status = evidence_status(result.evidence, synthetic.store)
    assert set(status) == {"E1", "E2", "E3"}
    e1, e2 = status["E1"], status["E2"]
    assert e1["category"] == "official_extraction_not_checked"  # no official check recorded
    assert (e1["source"], e1["extraction"]) == ("official_publication", "not_compared")
    assert (e1["human_review"], e1["citable_in_verified_mode"]) == ("reviewed", True)
    assert (e2["human_review"], e2["citable_in_verified_mode"]) == ("pending", False)
    for entry in status.values():
        assert entry["legal_currency"] == "not_established"
        assert entry["category"] in CATEGORIES
        assert any("legal currency not established" in s.lower() for s in entry["statements"])
    assert any("Human review pending" in s for s in e2["statements"])
    assert any("authenticity of this copy is not established" in s for s in e1["statements"])
    assert evidence_status(None, synthetic.store) == {}


# --- The recorded build ------------------------------------------------------------------------

REVIEW_DATA = sorted((PROJECT_ROOT / "data" / "reference").glob("*.json"))
QUESTION = ("When is a personal data breach required to be notified to the Italian Data "
            "Protection Authority?")
GDPR, CODE = "eu-reg-2016-679", "it-dlgs-2003-196"
ANALYSIS = {
    "language": "en", "in_scope": True,
    "scope_reason": "It concerns the notification of a personal data breach under the GDPR.",
    "question_type": "open",
    "issues": [{"question": "When must the controller notify a personal data breach to the "
                            "supervisory authority?"},
               {"question": "Which authority is the supervisory authority in Italy?"}],
    "search_queries_it": ["notifica di una violazione dei dati personali all'autorità di "
                          "controllo", "Garante per la protezione dei dati personali"],
    "suggested_provisions": [
        {"instrument": GDPR, "article": "33", "point": None, "reason": "notification"},
        {"instrument": GDPR, "article": "4", "point": "12", "reason": "definition"},
        {"instrument": CODE, "article": "2-bis", "point": None, "reason": "the authority"},
    ],
    "uncertainty": None, "clarification_question": None,
}
# Lookups come first, in request order: E1 = GDPR Art. 33, E2 = Art. 4(12), E3 = Code 2-bis.
GENERATION = {"outcome": "answer", "claims": [
    {"issue_ids": ["I1"], "kind": "source_statement",
     "text": "The controller must notify a personal data breach to the competent supervisory "
             "authority without undue delay and, where feasible, within 72 hours of becoming "
             "aware of it.",
     "support": [{"evidence_id": "E1", "quote": "il titolare del trattamento notifica la "
                  "violazione all'autorità di controllo competente a norma dell'articolo 55 "
                  "senza ingiustificato ritardo e, ove possibile, entro 72 ore dal momento in "
                  "cui ne è venuto a conoscenza"}]},
    {"issue_ids": ["I2"], "kind": "source_statement",
     "text": "In Italy the supervisory authority is the Garante per la protezione dei dati "
             "personali.",
     "support": [{"evidence_id": "E3", "quote": "è individuata nel Garante per la protezione "
                  "dei dati personali"}]},
], "unanswered_issues": [], "limitations": [], "abstention_reason": None,
    "direct_answer": None}
VERDICTS = {"verdicts": [{"claim_id": "C1", "support": "supported"},
                         {"claim_id": "C2", "support": "supported"}]}


@pytest.fixture(scope="module")
def recorded():
    try:
        return ProvisionExplorer.open(find_recorded_build())
    except ExplorerError as exc:
        pytest.skip(f"recorded build unavailable: {exc}")


def digests():
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in REVIEW_DATA}


def test_recorded_build_verified_mode_still_abstains_before_any_model_call(recorded):
    if load_ledger():
        pytest.skip("the review ledger has records")
    llm = MockLLM({})
    result = answer_question(QUESTION, llm, recorded, settings=SETTINGS)
    assert (result.outcome, result.abstention_reason) == (Outcome.ABSTAIN, NO_CITABLE_EVIDENCE)
    assert llm.calls == [] and result.mode == "verified"


def test_recorded_build_research_mode_answers_from_provisions_pending_review(recorded):
    before = digests()
    statuses = {pid: recorded.store.get(pid).review for pid in (
        f"{GDPR}@oj-l119-2016-it/body/article:33", f"{GDPR}@oj-l119-2016-it/body/article:4")}
    llm = MockLLM({ANALYSIS_TASK: [ANALYSIS], GENERATION_TASK: [GENERATION],
                   VERIFICATION_TASK: [VERDICTS]})
    result = answer_question(QUESTION, llm, recorded, settings=SETTINGS, mode=Mode.RESEARCH)

    assert result.outcome == Outcome.ANSWER and result.mode == "research"
    assert [c.task for c in llm.calls] == [ANALYSIS_TASK, GENERATION_TASK, VERIFICATION_TASK]
    labels = {item.evidence_id: (item.instrument_id, item.label) for item in result.evidence.items}
    assert (labels["E1"], labels["E2"], labels["E3"]) == (
        (GDPR, "33"), (GDPR, "4"), (CODE, "2-bis"))
    cited = {ref.evidence_id: ref for ref in result.citations}
    assert set(cited) == {"E1", "E3"}
    for ref in cited.values():  # cited for research, still not citable
        assert (ref.tier, ref.citable) == ("internal_only", False)
    status = evidence_status(result.evidence, recorded.store)
    assert status["E1"]["category"] == "official_extraction_not_checked"
    assert status["E3"]["category"] == "unofficial_transcription"  # the Code transcription
    assert status["E3"]["source"] == "unofficial_transcription"
    assert all(entry["human_review"] == "pending" for entry in status.values())
    # Nothing in the review data changed.
    assert digests() == before  # inventories, registry and review ledger, byte for byte
    for pid, review in statuses.items():
        assert recorded.store.get(pid).review == review


# --- The page marks unreviewed sources ---------------------------------------------------------

STATIC = PROJECT_ROOT / "src" / "web_static"


def test_the_page_marks_unreviewed_sources_and_starts_in_verified_mode():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    for text in ("Human review pending", "unreviewed", "Not citable in verified mode",
                 "Legal currency not established",
                 "This answer rests on sources pending human review"):
        assert text in js
    assert 'input[name="mode"][value="verified"]\').checked = true' in js  # never remembered
    assert "localStorage" not in js and "sessionStorage" not in js
    assert 'value="verified" checked' in page and 'id="ack"' in page
    assert "Research demo mode: experimental." in page


def test_answer_question_dates_every_result(synthetic):
    import datetime
    from src.answer_generation import AS_OF_QUALIFICATION
    day = datetime.date(2026, 11, 17)
    result = answer_question(demo.SYNTHETIC_QUESTION, MockLLM(script()), synthetic,
                             settings=SETTINGS, today=day)
    assert result.as_of == "2026-11-17"
    assert AS_OF_QUALIFICATION.format(as_of="2026-11-17") in result.qualifications
    out_of_scope = {**demo.ANALYSIS_REPLY, "in_scope": False, "issues": [],
                    "search_queries_it": [], "suggested_provisions": [],
                    "scope_reason": "Fuori dal corpus."}
    abstention = answer_question(demo.SYNTHETIC_QUESTION,
                                 MockLLM({ANALYSIS_TASK: [out_of_scope]}), synthetic,
                                 settings=SETTINGS, today=day)
    assert abstention.outcome == Outcome.ABSTAIN and abstention.as_of == "2026-11-17"


def test_a_research_answer_on_an_unreviewed_corpus_names_the_models_it_called(synthetic):
    import dataclasses
    from src.answer_generation import CorpusPreflight
    from src.provision_cli import render_answer
    result, _ = run(synthetic, Mode.RESEARCH, verification=RESEARCH_VERDICTS)
    unreviewed = dataclasses.replace(  # as on the real corpus: nothing citable in verified mode
        result, preflight=CorpusPreflight("build-test", (("internal_only", 3),), 0))
    text = render_answer(unreviewed)
    assert "models: none called" not in text and "models: analysis mock/" in text
    assert "citations (sources of the answer; in research mode they may be pending" in text
