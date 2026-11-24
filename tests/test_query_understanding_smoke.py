"""`python -m src.query_understanding_eval --smoke`, with a stand-in SDK client only.

No test sends a request or needs a real key: AnthropicLLM gets tests/test_llm.py's FakeClient,
which returns scripted Messages API responses or raises the SDK's own exceptions. Settings come
from load_settings({...}), which does not read .env. Every experiment entry point is replaced by
a function that fails the test, so a smoke test that touched the benchmark, the build, the
cache or a reading would fail.
"""

import json

import pytest

import src.query_understanding_eval as qe
from src.config import load_settings
from src.llm import AnthropicLLM, MockLLM, make_llm
from tests.test_llm import (  # noqa: F401  (wire is a fixture)
    KEY,
    FakeClient,
    api_response,
    connection_error,
    error_reply,
    message_body,
    status_error,
    wire,
)
from tests.test_query_understanding_anthropic import ANTHROPIC

OK = json.dumps({"reply": qe.SMOKE_TOKEN})
EXPERIMENT = ("load_benchmark", "dev_questions", "read_questions", "understand", "run",
              "evaluate_strategies", "preflight", "resolve_judgments", "find_recorded_build",
              "UnderstandingCache")


@pytest.fixture
def sdk():
    return pytest.importorskip("anthropic")


@pytest.fixture
def smoke(sdk, monkeypatch, capsys):
    """Run `--smoke` with `state["env"]` as settings and FakeClient(*outcomes) as the SDK."""
    state = {"env": dict(ANTHROPIC), "llms": [], "clients": []}

    def fake_make_llm(settings):
        llm = make_llm(settings)
        llm._client = state["clients"][-1]
        state["llms"].append(llm)
        return llm

    def forbidden(*args, **kwargs):
        raise AssertionError("the smoke test touched the experiment")

    monkeypatch.setattr(qe, "load_settings", lambda: load_settings(state["env"]))
    monkeypatch.setattr(qe, "make_llm", fake_make_llm)
    for name in EXPERIMENT:
        monkeypatch.setattr(qe, name, forbidden)
    monkeypatch.setattr(qe.ProvisionExplorer, "open", forbidden)

    def run(*outcomes, args=()):
        state["clients"].append(client := FakeClient(*outcomes))
        code = qe.main(["--smoke", *args])
        captured = capsys.readouterr()
        assert KEY not in captured.out + captured.err
        return code, captured.out + captured.err, client

    state["run"] = run
    return state


# --- Success -----------------------------------------------------------------------------------


def test_success_is_one_request_to_the_configured_model(smoke):
    code, out, client = smoke["run"](api_response(OK))
    assert code == 0 and "result: SUCCESS" in out
    [(endpoint, request)] = client.requests
    assert endpoint == "messages"
    assert request["model"] == "test-model"
    assert request["system"] == qe.SMOKE_SYSTEM
    assert request["messages"] == [{"role": "user", "content": qe.SMOKE_USER}]
    assert request["output_config"]["format"]["schema"] == qe.SMOKE_SCHEMA
    [llm] = smoke["llms"]
    assert isinstance(llm, AnthropicLLM) and llm.max_attempts == 1
    assert "anthropic/test-model" in out and "req_ok" in out


def test_success_as_json(smoke):
    code, out, _ = smoke["run"](api_response(OK), args=["--json"])
    result = json.loads(out)
    assert code == 0
    assert (result["ok"], result["outcome"], result["attempts"]) == (True, "success", 1)
    assert (result["provider"], result["model"], result["served_by"]) == (
        "anthropic", "test-model", "test-model")
    assert result["request_ids"] == ["req_ok"]


def test_one_attempt_even_when_settings_allow_a_retry_and_a_fallback_model(smoke):
    smoke["env"] |= {"MAX_GENERATION_RETRIES": "1", "LLM_REFUSAL_FALLBACK": "true"}
    code, out, client = smoke["run"](api_response("not json"), api_response(OK))
    assert code == 1 and "FAILED (invalid_response)" in out
    assert [endpoint for endpoint, _ in client.requests] == ["messages"]  # no retry, no beta


def test_a_valid_reply_with_other_text_is_not_a_success(smoke):
    code, out, client = smoke["run"](api_response(json.dumps({"reply": "hello"})))
    assert code == 1 and "FAILED (unexpected_reply)" in out and "'hello'" in out
    assert len(client.requests) == 1


# --- Failures ----------------------------------------------------------------------------------


@pytest.mark.parametrize(("cls_name", "status", "outcome", "fragment"), [
    ("AuthenticationError", 401, "authentication_failed", "ANTHROPIC_API_KEY"),
    ("PermissionDeniedError", 403, "access_denied", "HTTP 403"),
    ("NotFoundError", 404, "model_not_accessible", "LLM_MODEL"),
    ("BadRequestError", 400, "request_rejected", "HTTP 400"),
    ("RateLimitError", 429, "rate_limited", "HTTP 429"),
    ("InternalServerError", 500, "api_error", "HTTP 500"),
    ("OverloadedError", 529, "api_error", "HTTP 529"),
])
def test_api_failures_are_classified_after_one_request(sdk, smoke, cls_name, status, outcome,
                                                       fragment):
    code, out, client = smoke["run"](status_error(sdk, getattr(sdk, cls_name), status))
    assert code == 1
    assert f"FAILED ({outcome})" in out and fragment in out
    assert f"HTTP status: {status}; request id: req_err" in out
    assert len(client.requests) == 1


def test_a_timeout_and_a_connection_failure_are_classified(sdk, smoke):
    code, out, client = smoke["run"](connection_error(sdk, sdk.APITimeoutError))
    assert code == 1 and "FAILED (timeout)" in out and len(client.requests) == 1
    code, out, client = smoke["run"](connection_error(sdk, sdk.APIConnectionError))
    assert code == 1 and "FAILED (api_error)" in out and "could not reach" in out
    assert len(client.requests) == 1


def test_a_refusal_and_a_cut_off_reply_are_classified(smoke):
    code, out, client = smoke["run"](api_response(text=None, stop_reason="refusal",
                                                  category="other"))
    assert code == 1 and "FAILED (refused)" in out and len(client.requests) == 1
    code, out, client = smoke["run"](api_response('{"reply": "ANTH', stop_reason="max_tokens"))
    assert code == 1 and "FAILED (invalid_response)" in out and len(client.requests) == 1


# --- No fallback, no request on a configuration error ------------------------------------------


def test_the_mock_provider_is_refused_not_used(smoke):
    smoke["env"] = {}
    code, out, client = smoke["run"]()
    assert code == 2 and "needs a real provider" in out and "no request was sent" in out
    assert smoke["llms"] == [] and client.requests == []


def test_a_mock_client_from_the_factory_is_refused(smoke, monkeypatch):
    monkeypatch.setattr(qe, "make_llm", lambda settings: MockLLM({qe.SMOKE_TASK: [{}]}))
    code, out, _ = smoke["run"]()
    assert code == 2 and "mock provider" in out and "no request was sent" in out


@pytest.mark.parametrize(("change", "fragment"), [
    ({"ANTHROPIC_API_KEY": ""}, "ANTHROPIC_API_KEY is required"),
    ({"LLM_MODEL": ""}, "LLM_MODEL must be set"),
])
def test_a_configuration_error_sends_nothing(smoke, change, fragment):
    smoke["env"] |= change
    code, out, client = smoke["run"](api_response(OK))
    assert code == 2 and fragment in out and "no request was sent" in out
    assert client.requests == []


def test_smoke_test_refuses_a_client_that_may_retry(sdk):
    client = FakeClient(api_response(OK))
    llm = AnthropicLLM(api_key=None, model="test-model", client=client, max_schema_retries=1)
    with pytest.raises(ValueError, match="one attempt"):
        qe.smoke_test(llm)
    assert client.requests == []


def test_smoke_settings_keep_the_configuration_but_one_attempt_and_no_fallback():
    settings = load_settings({**ANTHROPIC, "LLM_REFUSAL_FALLBACK": "true",
                              "LLM_TIMEOUT_SECONDS": "30"})
    smoke = qe.smoke_settings(settings)
    assert (smoke.llm_provider, smoke.llm_model, smoke.llm_timeout_seconds) == (
        "anthropic", "test-model", 30.0)
    assert (smoke.max_generation_retries, smoke.llm_refusal_fallback) == (0, False)
    assert smoke.anthropic_api_key == settings.anthropic_api_key


# --- Options -----------------------------------------------------------------------------------


@pytest.mark.parametrize("args", [["--smoke", "--check"], ["--smoke", "--output", "r.json"]])
def test_smoke_excludes_check_and_report_output(args):
    with pytest.raises(SystemExit):
        qe.main(args)


# --- The production SDK client on a fake HTTP transport (tests/test_llm.py wire) ---------------


def production_smoke_llm(**env):
    """The client --smoke builds: make_llm on smoke_settings, with the SDK's real HTTP client."""
    return make_llm(qe.smoke_settings(load_settings({**ANTHROPIC, **env})))


def test_smoke_success_on_the_production_client_is_one_plain_request(wire):
    seen, replies = wire
    replies.extend([message_body(OK), message_body(OK)])
    result = qe.smoke_test(production_smoke_llm(MAX_GENERATION_RETRIES="1",
                                                LLM_REFUSAL_FALLBACK="true"))
    assert (result["ok"], result["outcome"], result["attempts"]) == (True, "success", 1)
    [request] = seen
    assert (request.method, request.url.path) == ("POST", "/v1/messages")
    assert "anthropic-beta" not in request.headers
    body = json.loads(request.content)
    assert body["model"] == "test-model" and "fallbacks" not in body


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_smoke_redirect_on_the_production_client_is_one_request(wire, status):
    httpx = pytest.importorskip("httpx2")
    seen, replies = wire
    replies.extend([
        httpx.Response(status, headers={"location": "https://api.anthropic.com/v1/messages"}),
        message_body(OK),
    ])
    result = qe.smoke_test(production_smoke_llm())
    assert (result["ok"], result["outcome"], result["status_code"]) == (
        False, "redirect_refused", status)
    assert "not sent again" in result["message"]
    assert len(seen) == 1 and len(replies) == 1  # not followed; the success never requested
    assert KEY not in json.dumps(result) + qe.format_smoke(result)


@pytest.mark.parametrize(("status", "outcome"), [(529, "api_error"), (500, "api_error"),
                                                 (429, "rate_limited"), (408, "timeout")])
def test_smoke_errors_the_sdk_would_retry_are_one_request(wire, status, outcome):
    seen, replies = wire
    replies.extend([error_reply(status), message_body(OK)])
    result = qe.smoke_test(production_smoke_llm())
    assert (result["ok"], result["outcome"]) == (False, outcome)
    assert len(seen) == 1
