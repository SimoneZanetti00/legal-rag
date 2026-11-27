"""Tests for src/web_demo.py and its page (src/web_static/). Offline: no test sends a request
to a model provider.

The pipeline is replaced by a stand-in, or by the offline synthetic demonstration
(src/demo.py: the real answer_question on a fictional act with scripted MockLLM replies), so
that a full answer with citations can be served. HTTP tests use a real server on a free port
of 127.0.0.1.
"""

import http.client
import json
import re
import threading
from dataclasses import fields

import pytest

import src.demo as demo
import src.web_demo as web
from src.answer_generation import (
    NO_CITABLE_EVIDENCE,
    CorpusPreflight,
    DirectAnswer,
    GenerationProvenance,
    RejectedClaim,
    SourceReference,
    _abstain,
    corpus_preflight,
    display_qualifications,
)
from src.citations import Resolution
from src.config import load_settings
from src.evidence import DroppedCandidate
from src.query_analysis import SuggestedProvision
from src.source_status import SourceStatus
from src.llm import (
    AnthropicLLM,
    LLMAuthenticationError,
    LLMConfigError,
    LLMError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMRequestError,
    LLMTimeoutError,
    LLMTransportError,
)
from src.provision_cli import MOCK_PROVIDER_MESSAGE
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.provisions import load_ledger
from src.query_analysis import MAX_QUESTION_CHARS, QueryAnalysisError

SECRET = "sk-ant-api03-THIS-MUST-NEVER-REACH-A-RESPONSE"
QUESTION = "Entro quando il titolare deve notificare una violazione dei dati personali?"
INFO = {"build_id": "build-test", "citable_articles": 0, "research_usable_articles": 319,
        "article_tiers": {"blocked": 2, "internal_only": 319}, "modes": ["verified", "research"],
        "default_mode": "verified", "research_qualification": "research", "provider": "anthropic",
        "model": "test-model", "semantic_verification": True,
        "max_question_chars": MAX_QUESTION_CHARS, "instruments": {}, "reasons": {},
        "qualifications": {}, "source_categories": {}, "model_notes_label": "notes"}
FAKE_ANTHROPIC = {"LLM_PROVIDER": "anthropic", "LLM_MODEL": "test-model",
                  "ANTHROPIC_API_KEY": SECRET}


@pytest.fixture(scope="module")
def synthetic_result():
    """A real AnswerResult with claims, citations and non-citable evidence (offline)."""
    return demo.synthetic(lambda line: None).result


@pytest.fixture
def abstention():
    preflight = CorpusPreflight("build-test", (("blocked", 2), ("internal_only", 319)), 0)
    return _abstain(QUESTION, NO_CITABLE_EVIDENCE,
                    "No article in build build-test may be cited; the question was not sent "
                    "to any model.", preflight=preflight)


class Pipeline:
    """A stand-in for answer_question: records questions and modes, returns or raises
    `outcome`."""

    def __init__(self, outcome):
        self.outcome = outcome
        self.questions = []
        self.modes = []

    def __call__(self, question, mode):
        self.questions.append(question)
        self.modes.append(mode)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def served_payload(result, status=None):
    """What /api/ask returns for `result`: to_dict() plus the source status and the
    qualifications as shown."""
    return {**result.to_dict(), "source_status": status or {},
            "display_qualifications": list(display_qualifications(result))}


def body(value):
    return json.dumps(value).encode("utf-8")


# --- Endpoints, without HTTP -------------------------------------------------------------------


def test_health_reports_status_and_the_page_information():
    reply = web.DemoApp(Pipeline(None), INFO).health()
    assert reply.status == 200
    assert reply.payload == {"status": "ok", **INFO}


def test_a_question_is_answered_with_to_dict_unchanged(synthetic_result):
    pipeline = Pipeline(synthetic_result)
    reply = web.DemoApp(pipeline, INFO).ask(body({"question": f"  {QUESTION}\n"}))
    assert reply.status == 200
    assert reply.payload == served_payload(synthetic_result)
    assert pipeline.questions == [QUESTION]  # stripped, as check_question does
    assert pipeline.modes == ["verified"]  # the default when no mode is named
    assert synthetic_result.outcome.value in {"answer", "answer_limited"}
    assert reply.payload["citations"] and reply.payload["claims"]
    json.loads(json.dumps(reply.payload, ensure_ascii=False))  # serialisable as sent


@pytest.mark.parametrize("mode", ["verified", "research"])
def test_the_mode_is_passed_to_the_pipeline(synthetic_result, mode):
    pipeline = Pipeline(synthetic_result)
    reply = web.DemoApp(pipeline, INFO).ask(body({"question": QUESTION, "mode": mode}))
    assert reply.status == 200 and pipeline.modes == [mode]


@pytest.mark.parametrize("mode", ["Research", "RESEARCH", "unsafe", "", " research", None, 1,
                                  True, ["research"], {"mode": "research"}])
def test_an_invalid_mode_is_refused_before_the_pipeline(mode):
    pipeline = Pipeline(None)
    reply = web.DemoApp(pipeline, INFO).ask(body({"question": QUESTION, "mode": mode}))
    assert reply.status == 400 and reply.payload["error"]["code"] == "invalid_mode"
    assert pipeline.questions == []


def test_the_source_status_is_added_to_the_result(synthetic_result):
    status = {"E1": {"category": "unofficial_transcription", "human_review": "pending"}}
    app = web.DemoApp(Pipeline(synthetic_result), INFO, describe=lambda result: status)
    reply = app.ask(body({"question": QUESTION, "mode": "research"}))
    assert reply.payload == served_payload(synthetic_result, status)


def test_a_failure_describing_the_sources_is_a_500_without_details(synthetic_result, capsys):
    def describe(result):
        raise KeyError(SECRET)

    app = web.DemoApp(Pipeline(synthetic_result), INFO, describe=describe)
    reply = app.ask(body({"question": QUESTION}))
    assert reply.status == 500 and SECRET not in json.dumps(reply.payload)
    assert SECRET not in capsys.readouterr().err


def test_an_abstention_is_a_result_not_an_error(abstention):
    reply = web.DemoApp(Pipeline(abstention), INFO).ask(body({"question": QUESTION}))
    assert reply.status == 200
    payload = reply.payload
    assert (payload["outcome"], payload["abstention_reason"]) == ("abstain", "no_citable_evidence")
    assert "was not sent to any model" in payload["abstention_detail"]
    assert payload["claims"] == [] and payload["citations"] == []
    assert payload["preflight"]["article_tiers"] == {"blocked": 2, "internal_only": 319}


@pytest.mark.parametrize("question", ["", "   ", "\n\t"])
def test_an_empty_question_is_refused_before_the_pipeline(question):
    pipeline = Pipeline(None)
    reply = web.DemoApp(pipeline, INFO).ask(body({"question": question}))
    assert reply.status == 400
    assert reply.payload["error"] == {"code": "invalid_question",
                                      "message": "The question is empty."}
    assert pipeline.questions == []


def test_a_question_that_is_too_long_is_refused():
    pipeline = Pipeline(None)
    reply = web.DemoApp(pipeline, INFO).ask(body({"question": "x" * (MAX_QUESTION_CHARS + 1)}))
    assert reply.status == 400 and "longer than" in reply.payload["error"]["message"]
    assert pipeline.questions == []


@pytest.mark.parametrize("raw", [b"", b"{", b"not json", b"\xff\xfe\x00", b'{"question": "a"'])
def test_malformed_json_is_refused(raw):
    reply = web.DemoApp(Pipeline(None), INFO).ask(raw)
    assert reply.status == 400 and reply.payload["error"]["code"] == "invalid_json"


@pytest.mark.parametrize("value", [[], "text", {"q": QUESTION}, {"question": 3},
                                   {"question": None}, {"question": [QUESTION]}])
def test_a_body_without_a_text_question_is_refused(value):
    reply = web.DemoApp(Pipeline(None), INFO).ask(body(value))
    assert reply.status == 400 and reply.payload["error"]["code"] == "invalid_request"


def test_a_question_error_from_the_pipeline_is_a_400():
    reply = web.DemoApp(Pipeline(QueryAnalysisError("the question is empty")), INFO).ask(
        body({"question": QUESTION}))
    assert (reply.status, reply.payload["error"]["code"]) == (400, "invalid_question")


def test_an_internal_error_is_a_500_without_its_details(capsys):
    failure = RuntimeError(f"boom {SECRET} C:/Users/someone/.env line 3")
    reply = web.DemoApp(Pipeline(failure), INFO).ask(body({"question": QUESTION}))
    assert reply.status == 500
    assert reply.payload["error"]["code"] == "internal_error"
    text = json.dumps(reply.payload)
    assert SECRET not in text and ".env" not in text and "Traceback" not in text
    err = capsys.readouterr().err
    assert "RuntimeError" in err and SECRET not in err and QUESTION not in err


@pytest.mark.parametrize(("failure", "status", "code", "provider_status"), [
    (LLMAuthenticationError(f"key {SECRET} rejected", status_code=401),
     502, "provider_authentication", 401),
    (LLMRateLimitError(f"limit {SECRET}", status_code=429), 503, "provider_rate_limited", 429),
    (LLMTimeoutError(f"slow {SECRET}"), 504, "provider_timeout", None),
    (LLMRequestError(f"credit balance too low {SECRET}", status_code=400),
     502, "provider_rejected_request", 400),
    (LLMTransportError(f"overloaded {SECRET}", status_code=529), 502, "provider_unavailable", 529),
    (LLMConfigError(f"ANTHROPIC_API_KEY={SECRET}"), 503, "model_not_configured", None),
    (LLMRefusalError(f"declined {SECRET}"), 502, "model_error", None),
    (LLMError(f"other {SECRET}"), 502, "model_error", None),
])
def test_provider_errors_are_reported_by_category_only(failure, status, code, provider_status,
                                                       capsys):
    reply = web.DemoApp(Pipeline(failure), INFO).ask(body({"question": QUESTION}))
    assert reply.status == status
    assert reply.payload["error"]["code"] == code
    assert reply.payload["error"].get("provider_status") == provider_status
    assert SECRET not in json.dumps(reply.payload)
    assert SECRET not in capsys.readouterr().err


# --- HTTP --------------------------------------------------------------------------------------


@pytest.fixture
def served(synthetic_result):
    """(port, pipeline) of a running server on 127.0.0.1 with the synthetic answer."""
    pipeline = Pipeline(synthetic_result)
    server = web.create_server(web.DemoApp(pipeline, INFO), port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1], pipeline
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def request(port, method, path, payload=None, headers=None):
    connection = http.client.HTTPConnection(web.HOST, port, timeout=10)
    try:
        connection.request(method, path, body=payload, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def post_json(port, value, **headers):
    return request(port, "POST", "/api/ask", body(value),
                   {"Content-Type": "application/json", **headers})


def test_the_server_binds_to_localhost_only(synthetic_result):
    server = web.create_server(web.DemoApp(Pipeline(synthetic_result), INFO), port=0)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()


def test_the_page_and_its_assets_are_served_with_a_strict_policy(served):
    port, _ = served
    status, headers, page = request(port, "GET", "/")
    assert status == 200 and headers["Content-Type"] == "text/html; charset=utf-8"
    text = page.decode("utf-8")
    for expected in ("Legal RAG", "Evidence-grounded legal research for Italian and EU law.",
                     "not legal advice", "no substitute for advice from a qualified lawyer",
                     'id="ask"', 'id="reset"', 'id="result"'):
        assert expected in text
    assert headers["Content-Security-Policy"].startswith("default-src 'self'")
    assert headers["X-Content-Type-Options"] == "nosniff"
    for path, content_type in (("/app.js", "text/javascript"), ("/app.css", "text/css")):
        status, headers, _ = request(port, "GET", path)
        assert status == 200 and headers["Content-Type"].startswith(content_type)


def test_health_over_http(served):
    status, headers, raw = request(served[0], "GET", "/api/health")
    assert status == 200 and headers["Content-Type"].startswith("application/json")
    assert json.loads(raw) == {"status": "ok", **INFO}


def test_ask_over_http_returns_the_result(served, synthetic_result, capsys):
    port, pipeline = served
    status, headers, raw = post_json(port, {"question": QUESTION})
    assert status == 200 and headers["Content-Type"] == "application/json; charset=utf-8"
    assert json.loads(raw.decode("utf-8")) == served_payload(synthetic_result)
    assert pipeline.questions == [QUESTION] and pipeline.modes == ["verified"]
    status, _, raw = post_json(port, {"question": QUESTION, "mode": "research"})
    assert status == 200 and pipeline.modes == ["verified", "research"]
    status, _, raw = post_json(port, {"question": QUESTION, "mode": "unsafe"})
    assert status == 400 and json.loads(raw)["error"]["code"] == "invalid_mode"
    assert QUESTION not in capsys.readouterr().err  # the log has method, path and status only


def test_a_question_from_the_same_origin_is_accepted(served):
    port = served[0]
    status, _, _ = post_json(port, {"question": QUESTION}, Origin=f"http://127.0.0.1:{port}")
    assert status == 200


@pytest.mark.parametrize("headers", [{"Host": "evil.example"},
                                     {"Origin": "https://evil.example"},
                                     {"Origin": "null"}])
def test_requests_from_other_hosts_or_sites_are_refused(served, headers):
    port, pipeline = served
    status, _, raw = post_json(port, {"question": QUESTION}, **headers)
    assert status == 403 and json.loads(raw)["error"]["code"].startswith("forbidden_")
    assert pipeline.questions == []


@pytest.mark.parametrize("content_type", ["text/plain", "application/x-www-form-urlencoded",
                                          "multipart/form-data; boundary=x"])
def test_only_json_bodies_are_accepted(served, content_type):
    port, pipeline = served
    status, _, raw = request(port, "POST", "/api/ask", body({"question": QUESTION}),
                             {"Content-Type": content_type})
    assert status == 415 and json.loads(raw)["error"]["code"] == "unsupported_media_type"
    assert pipeline.questions == []


def test_a_body_without_length_or_too_large_is_refused(served):
    port, pipeline = served
    connection = http.client.HTTPConnection(web.HOST, port, timeout=10)
    connection.putrequest("POST", "/api/ask")
    connection.putheader("Content-Type", "application/json")
    connection.endheaders()
    assert connection.getresponse().status == 411
    connection.close()
    big = body({"question": "x" * web.MAX_BODY_BYTES})
    status, _, _ = request(port, "POST", "/api/ask", big, {"Content-Type": "application/json"})
    assert status == 413 and pipeline.questions == []


def test_malformed_json_and_empty_questions_over_http(served):
    port, pipeline = served
    status, _, raw = request(port, "POST", "/api/ask", b"{not json",
                             {"Content-Type": "application/json"})
    assert status == 400 and json.loads(raw)["error"]["code"] == "invalid_json"
    status, _, raw = post_json(port, {"question": "   "})
    assert status == 400 and json.loads(raw)["error"]["code"] == "invalid_question"
    assert pipeline.questions == []


@pytest.mark.parametrize(("method", "path", "status"), [
    ("GET", "/api/ask", 405), ("POST", "/api/health", 405), ("POST", "/", 405),
    ("GET", "/nothing", 404), ("GET", "/../src/web_demo.py", 404), ("GET", "/index.html", 404),
    ("GET", "/web_static/app.js", 404),
])
def test_other_paths_and_methods(served, method, path, status):
    assert request(served[0], method, path,
                   b"" if method == "POST" else None,
                   {"Content-Type": "application/json"} if method == "POST" else None)[0] == status


def test_cross_origin_preflight_is_not_answered(served):
    status, headers, _ = request(served[0], "OPTIONS", "/api/ask",
                                 headers={"Origin": "https://evil.example",
                                          "Access-Control-Request-Method": "POST"})
    assert status == 501
    assert "Access-Control-Allow-Origin" not in headers


# --- The real pipeline wiring ------------------------------------------------------------------


def test_the_mock_provider_is_refused_as_ask_refuses_it(monkeypatch):
    monkeypatch.setattr(ProvisionExplorer, "open", lambda *a, **k: pytest.fail("build opened"))
    with pytest.raises(LLMConfigError) as exc_info:
        web.build_app(settings=load_settings({}))
    assert str(exc_info.value) == MOCK_PROVIDER_MESSAGE


def test_main_reports_a_configuration_error_and_does_not_serve(monkeypatch, capsys):
    monkeypatch.setattr(web, "load_settings", lambda: load_settings({}))
    monkeypatch.setattr(web, "create_server", lambda *a, **k: pytest.fail("server created"))
    assert web.main(["--port", "0"]) == 2
    assert "LLM_PROVIDER is 'mock'" in capsys.readouterr().err


def test_build_app_on_the_recorded_build_sends_nothing_and_shows_no_key(monkeypatch):
    try:
        build = find_recorded_build()
    except ExplorerError as exc:
        pytest.skip(f"recorded build unavailable: {exc}")

    def no_request(*args, **kwargs):  # a model request fails here, as an unreachable provider
        raise LLMTransportError("model request blocked in this test")

    monkeypatch.setattr(AnthropicLLM, "_complete", no_request)
    app = web.build_app(build_dir=build, settings=load_settings(FAKE_ANTHROPIC))
    info = app.health().payload
    explorer = ProvisionExplorer.open(build)
    assert (info["provider"], info["model"], info["build_id"]) == (
        "anthropic", "test-model", build.name)
    preflight = corpus_preflight(explorer)
    assert info["citable_articles"] == preflight.citable_articles
    assert info["research_usable_articles"] == sum(
        count for tier, count in preflight.article_tiers if tier in ("primary", "internal_only"))
    assert (info["modes"], info["default_mode"]) == (["verified", "research"], "verified")
    assert SECRET not in json.dumps(info)
    if not load_ledger():  # nothing citable: the preflight abstains before any model call
        reply = app.ask(body({"question": QUESTION}))
        assert reply.status == 200
        assert reply.payload["abstention_reason"] == "no_citable_evidence"
        assert reply.payload["mode"] == "verified" and reply.payload["source_status"] == {}
        assert SECRET not in json.dumps(reply.payload)
        # Research mode passes the preflight and reaches the model: blocked here.
        reply = app.ask(body({"question": QUESTION, "mode": "research"}))
        assert reply.status == 502 and reply.payload["error"]["code"] == "provider_unavailable"
        assert SECRET not in json.dumps(reply.payload)
    assert set(info) == set(INFO) | {"status"}  # the stand-in INFO mirrors the real keys


# --- The page renders only what the server provides --------------------------------------------

APP_JS = (web.STATIC_DIR / "app.js").read_text(encoding="utf-8")


def used(name):
    """Property names read from the JavaScript variable `name` (e.g. result.citations); not a
    property of the same name (evidence.dropped.length is not a field of `dropped`)."""
    return set(re.findall(rf"(?<![\w.]){name}\.([a-z_]+)\b", APP_JS))


def names(cls):
    return {f.name for f in fields(cls)}


def test_the_page_writes_no_server_value_as_html():
    for api in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert api not in APP_JS


def test_the_page_reads_only_fields_the_server_provides(synthetic_result):
    data = synthetic_result.to_dict()
    claim, item = data["claims"][0], data["evidence"]["items"][0]
    contract = {
        "result": set(data) | {"source_status", "display_qualifications"},
        "status": names(SourceStatus),
        "dropped": names(DroppedCandidate),
        "suggestion": names(SuggestedProvision),
        "claim": set(claim),
        "quote": set(claim["quotes"][0]),
        "ref": names(SourceReference),
        "item": set(item),
        "anchor": set(item["anchors"][0]),
        "gap": {"issue_id", "reason"},
        "rejected": names(RejectedClaim),
        "direct": names(DirectAnswer),
        "pre": set(data["preflight"]),
        "prov": names(GenerationProvenance),
        "analysis": set(data["analysis"]),
        "issue": set(data["analysis"]["issues"][0]),
        "evidence": set(data["evidence"]),
        "resolution": names(Resolution),
        "info": set(INFO) | {"public", "limits", "replay_url"},  # + web_demo.public_info()
    }
    for variable, provided in contract.items():
        assert used(variable), f"{variable} is not used in app.js"
        assert used(variable) <= provided, f"{variable}: {sorted(used(variable) - provided)}"


def test_the_footer_says_where_questions_and_evidence_are_sent():
    page = (web.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert ("Local server. Questions and evidence are sent to Anthropic's API for analysis, "
            "generation and verification.") in page
    assert "Runs locally" not in page


def test_the_page_shows_claims_not_rated_supported_apart_from_the_answer():
    from src.answer_generation import HELD_CLAIMS_TITLE
    assert f'const HELD_CLAIMS_TITLE = "{HELD_CLAIMS_TITLE}"' in APP_JS
    assert ('const inAnswer = (claim) => claim.verification === "SUPPORTED" || '
            'claim.verification === "NOT_VERIFIED";') in APP_JS
    # Held apart: collapsed under "Statements not confirmed"; the answer's own statements are
    # listed with their checks under "How this answer was produced".
    assert "fold(`Statements not confirmed (${held.length})`," in APP_JS
    assert "`${HELD_CLAIMS_TITLE}. The support check did not confirm" in APP_JS
    assert "held.map((claim) => renderClaim(" in APP_JS
    assert "shown.map((claim) => renderClaim(claim, statusById, itemById))" in APP_JS


def test_the_page_lists_only_the_answer_sources_and_notes_an_unrated_answer():
    from src.answer_generation import (HELD_SOURCES_TITLE, SUPPORT_FAILED_NOTICE,
                                       SUPPORT_NOT_RUN_NOTICE)
    assert f'const HELD_SOURCES_TITLE = "{HELD_SOURCES_TITLE}"' in APP_JS
    assert f'const SUPPORT_NOT_RUN_NOTICE = "{SUPPORT_NOT_RUN_NOTICE}"' in APP_JS
    assert f'const SUPPORT_FAILED_NOTICE = "{SUPPORT_FAILED_NOTICE}"' in APP_JS
    assert 'w.startsWith("support_verification_unavailable")' in APP_JS
    assert "mainSources.map(source)" in APP_JS
    assert "result.citations.map((ref) => renderSource(" not in APP_JS
    assert "heldSources.length ? [el(\"p\", { class: \"subhead\" }, HELD_SOURCES_TITLE)" in APP_JS
    assert ('card("What the provisions say", renderDirect(direct),\n'
            '      result.summary ? el("p", { class: "summary" }, inAnswerLang(result.summary)) : null,'
            '\n      supportNotice(result),') in APP_JS


def test_the_page_shows_the_kept_summary_and_the_as_of_date():
    assert 'result.summary ? el("p", { class: "summary" }, inAnswerLang(result.summary)) : null' in APP_JS
    assert ("`As of ${result.as_of}: the answer reflects the texts in the corpus on that date, "
            "not the law in force then or later.`") in APP_JS


def test_the_simple_view():
    page = (web.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    # On top: the question and a plain-language outcome, with the abstention reason in words.
    assert 'el("p", { class: "question" }, inAnswerLang(result.question))' in APP_JS
    for title in ('title: "Answer"', 'title: "Partial answer"', 'title: "No answer"'):
        assert title in APP_JS
    assert "reason ? `${outcome.title}: ${reason}` : outcome.title" in APP_JS
    assert 'out_of_scope: "the question is outside the GDPR and the Italian Privacy Code"' in APP_JS
    # The statements, each with a chip per provision that opens its exact quotation and page.
    assert 'const SHORT_NAMES = { "eu-reg-2016-679": "GDPR", "it-dlgs-2003-196": "Codice privacy" };' in APP_JS
    assert "`${name} art. ${ref.label}" in APP_JS
    assert '"aria-expanded": "false", "aria-controls": panelId' in APP_JS
    assert 'el("span", { class: "pending-mark" }, "pending review")' in APP_JS
    assert "· unreviewed" not in APP_JS  # the old evidence-ID links are gone
    # One line each, always visible: research mode, not legal advice, as-of date, Omnibus.
    assert 'el("ul", { class: "notices" }, lines)' in APP_JS
    assert '"Not legal advice: a research prototype.' in APP_JS
    assert ("(result.display_qualifications || result.qualifications).find((text) => "
            "text.includes(OMNIBUS_MARK))") in APP_JS
    # Collapsed by default: everything else.
    for title in ("`Sources and their status (${mainSources.length})`",
                  'fold("How this answer was produced", blocks)',
                  "`Model notes (${result.model_notes.length})`",
                  'fold("All caveats and limitations",'):
        assert title in APP_JS
    assert 'el("details", {}, el("summary", {}, title)' in APP_JS  # never open by default
    # Repaired statements are marked in the detailed view.
    assert 'claim.repaired_from ? badge("ok", "Repaired") : null' in APP_JS
    # Quotations the repair pass widened are marked, in both views.
    assert APP_JS.count('quote.widened_from ? el("span", { class: "widened-note" }') == 2
    # The reading guide, three lines, on both pages.
    guide = page[page.index('<aside class="howto"'):page.index("</aside>", page.index('<aside class="howto"'))]
    assert "How to read an answer" in guide and guide.count("<li>") == 3


# --- Accessibility ------------------------------------------------------------------------------


def test_the_page_marks_italian_text_and_announces_each_result():
    page = (web.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert '<html lang="en">' in page
    # The Italian example questions, the quotations (always Italian) and Italian answers.
    assert page.count('class="chip example" lang="it"') == 3
    assert APP_JS.count('italian(`«${quote.text}»`)') == 2
    assert 'answerLang = result.analysis && result.analysis.language === "it" ? "it" : null;' in APP_JS
    for marked in ("inAnswerLang(claim.text)", "inAnswerLang(direct.text)", "inAnswerLang(result.question)"):
        assert marked in APP_JS
    # A polite live region, visually hidden, gets the outcome of each result shown.
    assert '<p id="announce" class="sr-only" aria-live="polite"></p>' in page
    assert 'announce.textContent = `Result: ${' in APP_JS
    assert '<section id="state" aria-live="polite"></section>' in page


def test_the_focus_ring_is_solid():
    css = (web.STATIC_DIR / "app.css").read_text(encoding="utf-8")
    assert "outline: 3px solid var(--accent);" in css
    assert "color-mix(in srgb, var(--accent) 45%, transparent)" not in css
