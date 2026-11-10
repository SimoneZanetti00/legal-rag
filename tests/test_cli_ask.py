"""The ask command (src/provision_cli.py, src/cli.py) and answer_question, end to end.

Runs on the synthetic act of tests/test_provision_cli.py (Art. 1 primary, Art. 2
internal_only, Art. 3 repealed, Art. 4 and 4-bis blocked) with scripted MockLLM replies.
The replies stand in for model output (test data). One test uses the recorded build if it is
present; the live test is opt-in (RUN_LIVE_LLM_TESTS=1) and calls the configured provider.
"""

import json
import logging
import os

import pytest

import src.answer_generation as answer_generation
import src.provision_cli as cli
from src import cli as entry_point
from src.answer_generation import Outcome, _with_question_lookups, answer_question
from src.citations import Basis, Reference, Resolution, Status, resolve_references
from src.config import load_settings
from src.corpus_build import parse_spec, run_build
from src.corpus_identity import current_dependency_versions, file_sha256
from src.evidence import EvidenceRequest, ProvisionRequest, assemble
from src.llm import LLMRateLimitError, MockLLM
from src.provision_anchors import write_passage_links, write_segment_maps
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.provisions import load_ledger, load_store
from src.query_analysis import analyze
from tests.test_provision_cli import CLEAN, PAGES, make_store, prov, provisions
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


# The support check's stand-in verdict for the one claim that passes validation (C1).
SUPPORTED_C1 = {"verdicts": [{"claim_id": "C1", "support": "supported"}]}


def scripted(explored):
    ids = evidence_ids(explored)
    assert (ids["1"], ids["2"]) == ("E1", "E2")  # Art. 1 primary, Art. 2 internal_only
    return MockLLM({"query_analysis": [ANALYSIS], "answer_generation": [generation_reply(ids)],
                    "claim_verification": [SUPPORTED_C1]})


# --- The command -------------------------------------------------------------------------------


def test_ask_prints_citations_and_keeps_internal_only_evidence_apart(explored, capsys):
    code, out, err = ask(capsys, explored, scripted(explored))
    assert code == 0, err
    assert out.startswith(f"question: {QUESTION}\noutcome: ANSWER LIMITED\n")
    assert "Experimental prototype. Not legal advice." in out
    assert ("C1 [I1] (source statement; support: supported) Il titolare notifica la violazione "
            "al Garante entro "
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
    assert ("models: analysis mock/mock, 1 attempt(s); generation mock/mock, 1 attempt(s); "
            "support check mock/mock, 1 attempt(s)") in out
    assert "support was assessed by a model, which is not legal validation" in out


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
    assert result["generation"]["prompt_version"] == "answer-generation-v2"
    assert result["analysis"]["provenance"]["prompt_version"] == "query-analysis-v2"
    assert result["preflight"]["citable_articles"] == 1  # Art. 1
    assert result["evidence"]["build_id"]
    assert result["claims"][0]["verification"] == "SUPPORTED"
    assert result["verification"]["prompt_version"] == "claim-verification-v1"
    assert result["verification"]["supplied_evidence_ids"] == ["E1"]  # only what C1 cites
    assert result["question_references"] == []  # the question names no article


def test_answer_question_runs_analysis_evidence_and_generation_on_one_llm(explored):
    llm = scripted(explored)
    build_dir, store = explored
    result = answer_question(QUESTION, llm, ProvisionExplorer.open(build_dir, store=store),
                             settings=SETTINGS)
    assert [call.task for call in llm.calls] == ["query_analysis", "answer_generation",
                                                 "claim_verification"]
    assert result.outcome == Outcome.ANSWER_LIMITED
    assert (result.preflight.passed, result.preflight.citable_articles) == (True, 1)
    hash(result)  # hashable with a preflight, an analysis, evidence and generation
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


# --- Corpus preflight: no citable article, no model call ---------------------------------------


@pytest.fixture
def unreviewed(tmp_path, write_pdf, monkeypatch):
    """The same synthetic act with Art. 1 not reviewed: no article may be cited (3 internal_only,
    2 blocked)."""
    pdf = write_pdf(tmp_path / "src" / "act.pdf", PAGES)
    spec = parse_spec({
        "schema_version": 1, "name": "x", "description": "x", "chunk_size": 1200,
        "chunk_overlap": 150, "assembly_format": "concatenated-jsonl/1",
        "sources": [{"version_id": "x-act@v1", "path": "src/act.pdf",
                     "sha256": file_sha256(pdf), "end_before": None}],
    }, "x.json")
    result = run_build(spec, detect_code=lambda: CLEAN, output_root=tmp_path / "builds",
                       recorded_root=tmp_path / "builds", base_dir=tmp_path,
                       dependencies=current_dependency_versions())
    store = make_store(file_sha256(pdf),
                       [prov("1", 1, title="(Notifica della violazione)"), *provisions()[1:]])
    write_segment_maps(result.directory, store=store, registry=store.registry,
                       detect_code=lambda: CLEAN)
    write_passage_links(result.directory, store=store, registry=store.registry)
    monkeypatch.setattr(cli, "load_store", lambda: store)
    return result.directory, store


def test_without_a_citable_article_no_model_is_called(unreviewed, capsys):
    llm = MockLLM()  # unscripted: any call would fail
    code, out, err = ask(capsys, unreviewed, llm)
    assert code == 0, err
    assert "outcome: ABSTAIN (no_citable_evidence)" in out
    assert "The question was not sent to any model." in out
    assert "articles: 2 blocked, 3 internal_only; 0 citable" in out
    assert out.rstrip().endswith("models: none called (no citable article in the corpus)")
    assert "issues found by the query analysis" not in out
    assert llm.calls == []


def test_preflight_abstention_json(unreviewed, capsys):
    code, out, err = ask(capsys, unreviewed, MockLLM(), "--json")
    assert code == 0, err
    result = json.loads(out)
    assert (result["outcome"], result["abstention_reason"]) == ("abstain", "no_citable_evidence")
    assert result["preflight"] == {"build_id": unreviewed[0].name,
                                   "article_tiers": {"blocked": 2, "internal_only": 3},
                                   "citable_articles": 0}
    assert (result["analysis"], result["evidence"], result["generation"]) == (None, None, None)
    assert result["citations"] == [] and result["non_authoritative"] == []


def test_answer_question_runs_the_preflight_first(unreviewed):
    build_dir, store = unreviewed
    llm = MockLLM()
    result = answer_question(QUESTION, llm, ProvisionExplorer.open(build_dir, store=store),
                             settings=SETTINGS)
    assert (result.outcome, result.abstention_reason) == (Outcome.ABSTAIN, "no_citable_evidence")
    assert (result.preflight.passed, result.preflight.citable_articles) == (False, 0)
    assert result.preflight.article_tiers == (("blocked", 2), ("internal_only", 3))
    hash(result)  # a result carrying a preflight stays hashable
    assert llm.calls == []


def test_a_real_provider_client_sends_no_request_when_nothing_is_citable(unreviewed, capsys,
                                                                        monkeypatch):
    sdk = pytest.importorskip("anthropic")
    httpx = pytest.importorskip("httpx2")
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(500)

    real_client = sdk.Anthropic
    monkeypatch.setattr(sdk, "Anthropic", lambda **kwargs: real_client(
        **kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handle))))
    settings = load_settings({"LLM_PROVIDER": "anthropic", "LLM_MODEL": "test-model",
                              "ANTHROPIC_API_KEY": "sk-ant-test-key"})
    code = cli.main(["ask", QUESTION, "--build-dir", str(unreviewed[0])], settings=settings)
    out = capsys.readouterr().out
    assert code == 0
    assert "outcome: ABSTAIN (no_citable_evidence)" in out
    assert requests == []  # not one HTTP request to the provider


@pytest.mark.parametrize("question", ["   ", "x" * 2001])
def test_question_validation_still_comes_first(unreviewed, capsys, question):
    code, _, err = ask(capsys, unreviewed, MockLLM(), question=question)
    assert code == 2
    assert err.startswith("error: the question is")


# --- Privacy: question text and case details stay out of the logs ------------------------------

CASE_DETAILS = "Rossi Mario della Clinica San Luca"


def test_question_and_case_details_never_reach_the_log(explored, capsys, caplog):
    ids = evidence_ids(explored)
    english = {**ANALYSIS, "search_queries_it": [f"notification of the breach of {CASE_DETAILS}"]}
    llm = MockLLM({"query_analysis": [english, ANALYSIS],
                   "answer_generation": [generation_reply(ids)],
                   "claim_verification": [SUPPORTED_C1]})
    question = f"Il mio cliente {CASE_DETAILS} ha subito una violazione: va notificata?"
    with caplog.at_level(logging.DEBUG):
        code, out, err = ask(capsys, explored, llm, question=question)
    assert code == 0, err
    assert "task=query_analysis: reply 1 rejected (LLMSchemaError), retrying once" in caplog.text
    for detail in ("Rossi", "San Luca"):
        assert detail not in caplog.text
        assert detail not in err
    # The rejection reason, which quotes the query, still goes to the model as feedback.
    assert f"'notification of the breach of {CASE_DETAILS}': is English" in llm.calls[1].user


# --- References in the question (M2) -----------------------------------------------------------

BASE_REQUEST = EvidenceRequest(queries=("notifica della violazione",),
                               provisions=(ProvisionRequest("eu-reg-2016-679", "4", "12"),))


@pytest.fixture(scope="module")
def real_store():
    return load_store()


def lookups_for(question, store):
    return _with_question_lookups(BASE_REQUEST, resolve_references(question, store)).provisions


def test_a_resolved_gdpr_reference_becomes_an_exact_lookup_first(real_store):
    assert lookups_for("Cosa prevede l'articolo 33 GDPR?", real_store) == (
        ProvisionRequest("eu-reg-2016-679", "33", None), *BASE_REQUEST.provisions)


def test_a_resolved_code_reference_becomes_an_exact_lookup(real_store):
    assert lookups_for("Cosa dice l'articolo 2-bis del Codice Privacy?", real_store)[0] == (
        ProvisionRequest("it-dlgs-2003-196", "2-bis", None))
    both = lookups_for("Qual è il rapporto tra l'articolo 2-bis del Codice Privacy e "
                       "l'articolo 51 del GDPR?", real_store)
    assert [(p.instrument, p.label) for p in both[:2]] == [("it-dlgs-2003-196", "2-bis"),
                                                          ("eu-reg-2016-679", "51")]


@pytest.mark.parametrize("question", [
    "Cosa prevede l'articolo 33?",  # ambiguous: no act
    "Quali sono gli obblighi previsti dall'articolo 34, paragrafo 2?",  # ambiguous
    "Cosa prevede l'articolo 2 del D.Lgs. 101/2018?",  # outside the corpus
    "Cosa prevede l'articolo 100 GDPR?",  # no such article
    "Cosa prevede l'Article 34(2) GDPR?",  # partially resolved: no article text given here
    "Quando si notifica una violazione al Garante?",  # no reference at all
])
def test_only_resolved_references_are_looked_up(real_store, question):
    assert lookups_for(question, real_store) == BASE_REQUEST.provisions


def test_a_lookup_already_requested_is_not_duplicated(real_store):
    request = EvidenceRequest(provisions=(ProvisionRequest("eu-reg-2016-679", "33"),))
    merged = _with_question_lookups(request, resolve_references("art. 33 GDPR", real_store))
    assert merged.provisions == (ProvisionRequest("eu-reg-2016-679", "33", None),)


ART_4_QUESTION = ("Cosa si intende per violazione dei dati personali ai sensi dell'articolo 4 "
                  "del GDPR?")


def test_a_whole_article_question_lookup_gives_way_to_a_requested_point(real_store):
    # BASE_REQUEST already looks up point 12 of GDPR Art. 4: that lookup takes the question's place.
    assert lookups_for(ART_4_QUESTION, real_store) == BASE_REQUEST.provisions
    assert lookups_for("Cosa prevedono gli articoli 33 e 4 del GDPR?", real_store) == (
        ProvisionRequest("eu-reg-2016-679", "33", None), *BASE_REQUEST.provisions)


def test_a_requested_point_is_not_displaced_by_the_whole_article(recorded_build):
    """GDPR Art. 4 in full exceeds the 3,000-token budget; its point 12 fits."""
    explorer = ProvisionExplorer.open(recorded_build)
    request = _with_question_lookups(BASE_REQUEST,
                                     resolve_references(ART_4_QUESTION, explorer.store))
    evidence = assemble(request, explorer, settings=SETTINGS)
    first = evidence.items[0]
    assert (first.instrument_id, first.label) == ("eu-reg-2016-679", "4")
    assert first.text.startswith("12)") and first.tokens < 200  # the point, not the article
    assert first.provision_id not in {d.provision_id for d in evidence.dropped}
    # The whole article, had it been requested, would not have fitted at all.
    whole = assemble(EvidenceRequest(provisions=(ProvisionRequest("eu-reg-2016-679", "4"),)),
                     explorer, settings=SETTINGS)
    assert whole.items == () and [d.reason for d in whole.dropped] == ["token_budget"]


def test_question_references_do_not_bypass_the_preflight(recorded_build, capsys):
    if load_ledger():
        pytest.skip("the ledger has reviews: the preflight passes")
    llm = MockLLM()  # any call would fail
    code = cli.main(["ask", "Cosa prevede l'articolo 33 GDPR? E l'articolo 34?"], llm=llm,
                    settings=SETTINGS)
    out = capsys.readouterr().out
    assert code == 0 and llm.calls == []
    assert "outcome: ABSTAIN (no_citable_evidence)" in out
    assert "«articolo 33» resolved: eu-reg-2016-679 art. 33 (act named: GDPR)" in out
    assert "«articolo 34» ambiguous: the act of articolo 34 is not stated" in out
    assert "Candidates, not looked up: eu-reg-2016-679 art. 34, it-dlgs-2003-196 art. 34" in out


def test_a_question_lookup_keeps_its_eligibility(explored, capsys, monkeypatch):
    """A lookup from the question goes through evidence assembly like any other: an
    internal_only article stays non-citable, so nothing is generated from it."""
    reference = Reference("articolo 2", 0, 10, "2", (), None, "x-act", Basis.EXPLICIT, "prova")
    resolved = Resolution(reference, Status.RESOLVED, "found", "x-act@v1/body/article:2",
                          "x-act@v1/body/article:2")
    monkeypatch.setattr(answer_generation, "resolve_references", lambda *a, **k: (resolved,))
    llm = MockLLM({"query_analysis": [ONLY_ART_2]})  # a generation call would fail
    code, out, err = ask(capsys, explored, llm, "--json")
    assert code == 0, err
    result = json.loads(out)
    assert result["abstention_reason"] == "no_citable_evidence"
    [item] = result["evidence"]["items"]
    assert (item["label"], item["citable"], item["origins"][0]) == ("2", False, "lookup")
    assert result["question_references"][0]["status"] == "resolved"
    assert [call.task for call in llm.calls] == ["query_analysis"]


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
# A stand-in generation reply: a deterministic abstention, so the demo test runs to the end
# whether or not the corpus has citable evidence.
GENERATION_ABSTAIN = {"outcome": "abstain", "claims": [], "unanswered_issues": [],
                      "limitations": [], "abstention_reason": "Test stand-in: no answer."}


def demo_llm(analysis_reply=DEMO_ANALYSIS):
    """The scripted LLM of the demo test: an analysis, then an abstaining generation reply."""
    return MockLLM({"query_analysis": [analysis_reply], "answer_generation": [GENERATION_ABSTAIN]})


def test_the_demo_script_completes_a_run_that_reaches_generation(explored, capsys):
    """What the demo test's script does once something is citable: the run reaches the
    generation step and ends in the scripted abstention, not in a configuration error."""
    llm = demo_llm(ANALYSIS)
    code, out, err = ask(capsys, explored, llm, "--json")
    assert code == 0, err
    result = json.loads(out)
    assert (result["outcome"], result["abstention_reason"]) == ("abstain", "model_abstained")
    assert [call.task for call in llm.calls] == ["query_analysis", "answer_generation"]
    assert result["preflight"]["citable_articles"] == 1
    assert "1" in {item["label"] for item in result["evidence"]["items"]}


@pytest.fixture(scope="module")
def recorded_build():
    try:
        return find_recorded_build()
    except ExplorerError as exc:
        pytest.skip(f"recorded build unavailable: {exc}")


def test_demo_question_on_the_recorded_build(recorded_build, capsys):
    llm = demo_llm()
    code = cli.main(["ask", DEMO_QUESTION, "--json"], llm=llm, settings=SETTINGS)
    out, err = capsys.readouterr()
    assert code == 0, err
    result = json.loads(out)
    assert all(c["citable"] for c in result["citations"])
    assert not any(r["citable"] for r in result["non_authoritative"])
    if not load_ledger():  # nothing reviewed yet: the preflight stops before any model call
        assert (result["outcome"], result["abstention_reason"]) == ("abstain",
                                                                  "no_citable_evidence")
        assert llm.calls == []
        assert (result["analysis"], result["evidence"], result["generation"]) == (
            None, None, None)
        preflight = result["preflight"]
        assert preflight["citable_articles"] == 0
        assert set(preflight["article_tiers"]) <= {"internal_only", "blocked", "context_only"}
        assert preflight["build_id"] == recorded_build.name
    else:  # once something is citable: analysis, evidence and (if a retrieved item is
        # citable) the scripted abstaining generation; never a configuration error
        assert llm.calls[0].task == "query_analysis"
        assert result["outcome"] == "abstain"
        assert result["abstention_reason"] in {"model_abstained", "no_citable_evidence"}
        found = {item["label"] for item in result["evidence"]["items"]}
        assert {"4", "33", "34", "55", "2-bis"} <= found


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
