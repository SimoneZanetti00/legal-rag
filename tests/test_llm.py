"""Tests for src/llm.py. No test here contacts an external service: the Anthropic tests use a
fake SDK client (or a real one whose request method is replaced) and real SDK error classes."""

import json
import logging
import subprocess
import sys
from types import SimpleNamespace

import pytest

from src.config import PROJECT_ROOT, load_settings
from src.llm import (
    REFUSAL_FALLBACK_BETA,
    SDK_MAX_RETRIES,
    AnthropicLLM,
    LLMAuthenticationError,
    LLMConfigError,
    LLMMalformedOutputError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMRequestError,
    LLMSchemaError,
    LLMTimeoutError,
    LLMTransportError,
    LLMTruncatedError,
    MockLLM,
    RawCompletion,
    check_schema,
    make_llm,
    parse_json_object,
    validate_json,
)

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer", "tags", "note"],
    "properties": {
        "answer": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string", "enum": ["a", "b"]}},
        "note": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    },
}
GOOD = {"answer": "ok", "tags": ["a"], "note": None}
KEY = "sk-ant-test-key-0123456789"


# --- Schema subset -----------------------------------------------------------------------------


def test_check_schema_accepts_the_supported_subset():
    check_schema(SCHEMA)


@pytest.mark.parametrize(
    ("schema", "fragment"),
    [
        ({"type": "string", "minLength": 1}, "unsupported keywords"),
        ({"type": "object", "properties": {}}, "additionalProperties to false"),
        ({"type": "object", "properties": {}, "additionalProperties": True}, "additionalProperties"),
        ({"type": "object", "additionalProperties": False, "required": ["x"]}, "undeclared"),
        ({"type": "array"}, "arrays must give items"),
        ({"type": ["string", "null"]}, "'type' must be one of"),
        ({"type": "string", "anyOf": [{"type": "string"}]}, "anyOf must stand alone"),
        ({"type": "string", "enum": [1]}, "is not a string"),
        ({"type": "string", "items": {"type": "string"}}, "items on a non-array"),
    ],
)
def test_check_schema_rejects_what_it_cannot_enforce(schema, fragment):
    with pytest.raises(LLMConfigError, match=fragment):
        check_schema(schema)


def test_validate_json_accepts_valid_values():
    validate_json(GOOD, SCHEMA)
    validate_json({**GOOD, "note": "text", "tags": []}, SCHEMA)


@pytest.mark.parametrize(
    ("value", "fragment"),
    [
        ({"answer": 1, "tags": [], "note": None}, r"\$\.answer: expected string, got integer"),
        ({"answer": "ok", "tags": []}, "missing required"),
        ({**GOOD, "extra": 1}, "unexpected properties"),
        ({**GOOD, "tags": ["c"]}, r"\$\.tags\[0\]: 'c' is not one of"),
        ({**GOOD, "note": 3}, "none of the allowed alternatives"),
    ],
)
def test_validate_json_rejects_with_a_path(value, fragment):
    with pytest.raises(LLMSchemaError, match=fragment):
        validate_json(value, SCHEMA)


def test_booleans_are_not_numbers():
    with pytest.raises(LLMSchemaError):
        validate_json(True, {"type": "integer"})
    with pytest.raises(LLMSchemaError):
        validate_json(1, {"type": "boolean"})


@pytest.mark.parametrize("text", ['```json\n{"a": 1}\n```', '{"a": NaN}', "{'a': 1}", ""])
def test_parse_json_object_is_strict(text):
    with pytest.raises(LLMMalformedOutputError):
        parse_json_object(text)


def test_parse_json_object_needs_an_object():
    with pytest.raises(LLMSchemaError, match="expected object"):
        parse_json_object("[1, 2]")


# --- MockLLM and the shared retry rule ---------------------------------------------------------


def test_mock_returns_validated_json_and_records_calls():
    llm = MockLLM({"demo": [GOOD]})
    result = llm.complete_json("demo", "system text", "user text", SCHEMA)
    assert result.data == GOOD
    assert (result.provider, result.model, result.served_by) == ("mock", "mock", "mock")
    assert (result.attempts, result.fallback_used) == (1, False)
    assert [(c.task, c.system, c.user) for c in llm.calls] == [("demo", "system text", "user text")]


def test_mock_is_deterministic():
    def run():
        llm = MockLLM({"demo": ["not json", {**GOOD, "answer": "second"}]})
        return llm.complete_json("demo", "s", "u", SCHEMA), [c.user for c in llm.calls]

    assert run() == run()


def test_mock_never_invents_a_reply():
    with pytest.raises(LLMConfigError, match="no scripted reply for task 'demo'"):
        MockLLM().complete_json("demo", "s", "u", SCHEMA)


def test_mock_script_can_be_used_up():
    llm = MockLLM({"demo": [GOOD]})
    llm.complete_json("demo", "s", "u", SCHEMA)
    with pytest.raises(LLMConfigError, match="used up after 1 replies"):
        llm.complete_json("demo", "s", "u", SCHEMA)


def test_malformed_reply_is_retried_once_with_feedback():
    llm = MockLLM({"demo": ["Sure! Here it is: {", GOOD]})
    result = llm.complete_json("demo", "s", "the question", SCHEMA)
    assert result.data == GOOD
    assert result.attempts == 2
    first, second = (c.user for c in llm.calls)
    assert first == "the question"
    assert second.startswith("the question\n\n[Your previous reply was rejected:")
    assert "not valid JSON" in second


def test_retries_stop_after_one():
    llm = MockLLM({"demo": ["nope", "still nope", GOOD]})
    with pytest.raises(LLMMalformedOutputError, match=r"\[attempt 2 of 2\]") as exc_info:
        llm.complete_json("demo", "s", "u", SCHEMA)
    assert exc_info.value.attempts == 2
    assert len(llm.calls) == 2


def test_no_retry_when_retries_are_off():
    llm = MockLLM({"demo": ["nope", GOOD]}, max_schema_retries=0)
    with pytest.raises(LLMMalformedOutputError, match=r"\[attempt 1 of 1\]"):
        llm.complete_json("demo", "s", "u", SCHEMA)
    assert len(llm.calls) == 1


def test_retry_bound_is_at_most_one():
    assert (MockLLM().max_attempts, MockLLM(max_schema_retries=0).max_attempts) == (2, 1)
    with pytest.raises(LLMConfigError, match="between 0 and 1"):
        MockLLM(max_schema_retries=2)


def test_schema_violation_is_retried_then_raised():
    bad = {**GOOD, "tags": ["z"]}
    llm = MockLLM({"demo": [bad, bad]})
    with pytest.raises(LLMSchemaError, match="is not one of") as exc_info:
        llm.complete_json("demo", "s", "u", SCHEMA)
    assert exc_info.value.attempts == 2
    assert "is not one of" in llm.calls[1].user


def test_a_rejected_reply_is_logged_without_its_content(caplog):
    sentinel = "SENSITIVE-CASE-DETAIL Rossi"
    llm = MockLLM({"demo": [{**GOOD, "tags": [sentinel]}, GOOD]})  # breaks the enum, then fine
    with caplog.at_level(logging.DEBUG):
        assert llm.complete_json("demo", "s", f"question about {sentinel}", SCHEMA).attempts == 2
    assert "llm mock task=demo: reply 1 rejected (LLMSchemaError), retrying once" in caplog.text
    assert "SENSITIVE" not in caplog.text and "Rossi" not in caplog.text
    assert f"'{sentinel}' is not one of" in llm.calls[1].user  # the model still gets the reason


def test_caller_check_shares_the_retry_budget():
    def check(data):
        if data["answer"] != "fine":
            raise LLMSchemaError("answer must be 'fine'")

    llm = MockLLM({"demo": [GOOD, {**GOOD, "answer": "fine"}]})
    assert llm.complete_json("demo", "s", "u", SCHEMA, check=check).attempts == 2
    assert "answer must be 'fine'" in llm.calls[1].user


def test_refusal_is_not_retried():
    refusal = RawCompletion(None, "refusal", "mock", refusal_category="cyber")
    llm = MockLLM({"demo": [refusal, GOOD]})
    with pytest.raises(LLMRefusalError, match="declined") as exc_info:
        llm.complete_json("demo", "s", "u", SCHEMA)
    assert exc_info.value.category == "cyber"
    assert len(llm.calls) == 1


def test_truncated_reply_is_not_retried():
    llm = MockLLM({"demo": [RawCompletion('{"answer": "o', "max_tokens", "mock"), GOOD]})
    with pytest.raises(LLMTruncatedError, match="cut off"):
        llm.complete_json("demo", "s", "u", SCHEMA)
    assert len(llm.calls) == 1


@pytest.mark.parametrize(
    ("reply", "fragment"),
    [
        (RawCompletion(None, "end_turn", "mock"), "contains no text"),
        (RawCompletion("  ", "end_turn", "mock"), "contains no text"),
        (RawCompletion("{}", "tool_use", "mock"), "unexpected stop_reason"),
    ],
)
def test_unusable_replies(reply, fragment):
    with pytest.raises(LLMMalformedOutputError, match=fragment):
        MockLLM({"demo": [reply, reply]}).complete_json("demo", "s", "u", SCHEMA)


def test_provider_failure_propagates_without_retry():
    llm = MockLLM({"demo": [LLMRateLimitError("slow down", status_code=429), GOOD]})
    with pytest.raises(LLMRateLimitError, match="slow down"):
        llm.complete_json("demo", "s", "u", SCHEMA)
    assert len(llm.calls) == 1


def test_bad_task_name_and_bad_schema_fail_before_any_call():
    llm = MockLLM({"demo": [GOOD]})
    with pytest.raises(LLMConfigError, match="task must be"):
        llm.complete_json("Demo Task", "s", "u", SCHEMA)
    with pytest.raises(LLMConfigError, match="unsupported keywords"):
        llm.complete_json("demo", "s", "u", {**SCHEMA, "minProperties": 1})
    assert llm.calls == []


def test_mock_works_without_the_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)  # any `import anthropic` now fails
    assert MockLLM({"demo": [GOOD]}).complete_json("demo", "s", "u", SCHEMA).data == GOOD


def test_importing_the_llm_modules_does_not_import_the_sdk():
    code = "import sys, src.llm, src.query_analysis; print('anthropic' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT, capture_output=True,
                         text=True, check=True)
    assert out.stdout.strip() == "False"


# --- AnthropicLLM ------------------------------------------------------------------------------


@pytest.fixture
def sdk():
    return pytest.importorskip("anthropic")


class FakeClient:
    """Stands in for anthropic.Anthropic: records each request and returns scripted outcomes."""

    def __init__(self, *outcomes):
        self.requests = []  # (endpoint, kwargs)
        self._outcomes = list(outcomes)
        self.messages = SimpleNamespace(create=lambda **kw: self._next("messages", kw))
        self.beta = SimpleNamespace(
            messages=SimpleNamespace(create=lambda **kw: self._next("beta", kw))
        )

    def _next(self, endpoint, kwargs):
        self.requests.append((endpoint, kwargs))
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def api_response(text='{"answer": "ok", "tags": ["a"], "note": null}', *, stop_reason="end_turn",
                 model="test-model", category=None, iterations=None, request_id="req_ok"):
    """A Messages API response shaped like the SDK's: a thinking block, then the text block."""
    content = [SimpleNamespace(type="thinking", thinking="", signature="sig")]
    if text is not None:
        content.append(SimpleNamespace(type="text", text=text))
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category=category) if category else None,
        model=model,
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, iterations=iterations),
        _request_id=request_id,
    )


def status_error(sdk, cls, status, message="boom"):
    httpx = pytest.importorskip("httpx2")
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status, request=request, headers={"request-id": "req_err"})
    body = {"type": "error", "error": {"type": "some_error", "message": message}}
    return cls(message, response=response, body=body)


def connection_error(sdk, cls):
    httpx = pytest.importorskip("httpx2")
    return cls(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))


def make(sdk, client, **kwargs):
    return AnthropicLLM(api_key=None, model="test-model", client=client, **kwargs)


def test_default_request_has_no_fallback(sdk):
    client = FakeClient(api_response())
    llm = make(sdk, client)
    assert llm.refusal_fallback is False
    llm.complete_json("demo", "sys", "usr", SCHEMA)
    [(endpoint, kwargs)] = client.requests
    assert endpoint == "messages"
    assert kwargs == {
        "model": "test-model",
        "max_tokens": 16000,
        "system": "sys",
        "messages": [{"role": "user", "content": "usr"}],
        "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}},
    }


def test_refusal_by_default_is_an_error_and_no_other_model_is_tried(sdk):
    client = FakeClient(api_response(text=None, stop_reason="refusal", category="cyber"),
                        api_response())
    with pytest.raises(LLMRefusalError) as exc_info:
        make(sdk, client).complete_json("demo", "s", "u", SCHEMA)
    assert (exc_info.value.category, exc_info.value.model) == ("cyber", "test-model")
    assert [(endpoint, kwargs["model"]) for endpoint, kwargs in client.requests] == [
        ("messages", "test-model")]


def test_request_shape_with_refusal_fallback_enabled(sdk):
    client = FakeClient(api_response())
    result = make(sdk, client, refusal_fallback=True).complete_json("demo", "sys", "usr", SCHEMA)
    assert result.data == GOOD
    assert (result.provider, result.model, result.served_by) == ("anthropic", "test-model",
                                                                 "test-model")
    assert result.request_ids == ("req_ok",)
    [(endpoint, kwargs)] = client.requests
    assert endpoint == "beta"
    assert kwargs == {
        "betas": [REFUSAL_FALLBACK_BETA],
        "fallbacks": "default",
        "model": "test-model",
        "max_tokens": 16000,
        "system": "sys",
        "messages": [{"role": "user", "content": "usr"}],
        "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}},
    }


def test_enabled_fallback_reports_the_serving_model(sdk, caplog):
    iterations = [SimpleNamespace(type="message"), SimpleNamespace(type="fallback_message")]
    client = FakeClient(api_response(model="fallback-model", iterations=iterations))
    with caplog.at_level(logging.WARNING, logger="src.llm"):
        result = make(sdk, client, refusal_fallback=True).complete_json("demo", "s", "u", SCHEMA)
    assert (result.model, result.served_by, result.fallback_used) == (
        "test-model", "fallback-model", True)
    assert "served by fallback model fallback-model (configured: test-model)" in caplog.text


def test_enabled_fallback_that_also_refuses_is_still_an_error(sdk):
    iterations = [SimpleNamespace(type="message"), SimpleNamespace(type="fallback_message")]
    client = FakeClient(api_response(text=None, stop_reason="refusal", model="fallback-model",
                                     iterations=iterations))
    with pytest.raises(LLMRefusalError, match="fallback-model"):
        make(sdk, client, refusal_fallback=True).complete_json("demo", "s", "u", SCHEMA)
    assert len(client.requests) == 1


def test_refusal_and_truncation_from_the_api(sdk):
    refused = FakeClient(api_response(text=None, stop_reason="refusal", category="bio"))
    with pytest.raises(LLMRefusalError) as exc_info:
        make(sdk, refused).complete_json("demo", "s", "u", SCHEMA)
    assert exc_info.value.category == "bio"
    assert len(refused.requests) == 1

    cut = FakeClient(api_response(text='{"answer": "o', stop_reason="max_tokens"))
    with pytest.raises(LLMTruncatedError):
        make(sdk, cut).complete_json("demo", "s", "u", SCHEMA)
    assert len(cut.requests) == 1


def test_invalid_api_output_is_retried_once_on_the_same_model(sdk):
    client = FakeClient(api_response(text="oops"), api_response())
    assert make(sdk, client).complete_json("demo", "s", "u", SCHEMA).attempts == 2
    assert [(endpoint, kwargs["model"]) for endpoint, kwargs in client.requests] == [
        ("messages", "test-model"), ("messages", "test-model")]


@pytest.mark.parametrize(
    ("cls_name", "status", "expected", "fragment"),
    [
        ("AuthenticationError", 401, LLMAuthenticationError, "ANTHROPIC_API_KEY"),
        ("PermissionDeniedError", 403, LLMAuthenticationError, "HTTP 403"),
        ("RateLimitError", 429, LLMRateLimitError, "HTTP 429"),
        ("EnforcedSpendLimitReachedError", 429, LLMRateLimitError, "spend limit"),
        ("BadRequestError", 400, LLMRequestError, "HTTP 400"),
        ("NotFoundError", 404, LLMRequestError, "LLM_MODEL"),
        ("RequestTimeoutError", 408, LLMTimeoutError, "HTTP 408"),
        ("InternalServerError", 500, LLMTransportError, "HTTP 500"),
        ("OverloadedError", 529, LLMTransportError, "HTTP 529"),
    ],
)
def test_sdk_status_errors_are_translated(sdk, cls_name, status, expected, fragment):
    error = status_error(sdk, getattr(sdk, cls_name), status)
    client = FakeClient(error)
    with pytest.raises(expected, match=fragment) as exc_info:
        make(sdk, client).complete_json("demo", "s", "u", SCHEMA)
    assert type(exc_info.value) is expected
    assert (exc_info.value.status_code, exc_info.value.request_id) == (status, "req_err")
    assert len(client.requests) == 1  # nothing retried on top of the SDK's own retries


def test_timeout_and_connection_errors_are_translated(sdk):
    client = FakeClient(connection_error(sdk, sdk.APITimeoutError))
    with pytest.raises(LLMTimeoutError, match=r"within 7\.5s \(LLM_TIMEOUT_SECONDS\)"):
        make(sdk, client, timeout_seconds=7.5).complete_json("demo", "s", "u", SCHEMA)

    client = FakeClient(connection_error(sdk, sdk.APIConnectionError))
    with pytest.raises(LLMTransportError, match="could not reach") as exc_info:
        make(sdk, client).complete_json("demo", "s", "u", SCHEMA)
    assert type(exc_info.value) is LLMTransportError


def test_response_the_sdk_cannot_parse(sdk):
    httpx = pytest.importorskip("httpx2")
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    error = sdk.APIResponseValidationError(response=httpx.Response(200, request=request),
                                           body=None)
    with pytest.raises(LLMTransportError, match="unexpected response") as exc_info:
        make(sdk, FakeClient(error)).complete_json("demo", "s", "u", SCHEMA)
    assert type(exc_info.value) is LLMTransportError


def test_rejected_fallback_parameter_gets_a_hint(sdk):
    error = status_error(sdk, sdk.BadRequestError, 400, "fallbacks: not supported for this model")
    with pytest.raises(LLMRequestError, match="set it to false"):
        make(sdk, FakeClient(error), refusal_fallback=True).complete_json("demo", "s", "u", SCHEMA)


def test_other_exceptions_are_not_masked(sdk):
    with pytest.raises(TypeError, match="a bug"):
        make(sdk, FakeClient(TypeError("a bug"))).complete_json("demo", "s", "u", SCHEMA)


@pytest.mark.parametrize("api_key", [None, ""])
def test_missing_api_key_fails_before_the_sdk_is_needed(monkeypatch, api_key):
    monkeypatch.setitem(sys.modules, "anthropic", None)
    with pytest.raises(LLMConfigError, match="ANTHROPIC_API_KEY is required") as exc_info:
        AnthropicLLM(api_key=api_key, model="test-model")
    assert "subscription does not by itself provide API access" in str(exc_info.value)


def test_missing_model_and_bad_limits():
    with pytest.raises(LLMConfigError, match="LLM_MODEL must be set"):
        AnthropicLLM(api_key=KEY, model=" ")
    with pytest.raises(LLMConfigError, match="timeout_seconds"):
        AnthropicLLM(api_key=KEY, model="m", timeout_seconds=0)


def test_missing_sdk_is_a_config_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)
    with pytest.raises(LLMConfigError, match="pip install -r requirements.txt"):
        AnthropicLLM(api_key=KEY, model="test-model")


def test_real_sdk_client_uses_only_the_explicit_key(sdk, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-the-environment")
    llm = AnthropicLLM(api_key=KEY, model="test-model", timeout_seconds=7.5)
    assert llm._client.api_key == KEY
    assert llm._client.timeout == 7.5
    assert SDK_MAX_RETRIES == 0
    assert llm._client.max_retries == 0


# --- The real SDK on a fake HTTP transport: no hidden retries ----------------------------------


@pytest.fixture
def wire(sdk, monkeypatch):
    """Every AnthropicLLM built in the test gets a real SDK client whose HTTP requests go to a
    fake transport. Returns (requests seen, replies): each reply is an httpx2.Response, an
    exception to raise, or a JSON-able dict sent with status 200."""
    httpx = pytest.importorskip("httpx2")
    seen, replies = [], []

    def handle(request):
        seen.append(request)
        reply = replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply if isinstance(reply, httpx.Response) else httpx.Response(200, json=reply)

    real_client = sdk.Anthropic

    def build(**kwargs):
        return real_client(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handle)))

    monkeypatch.setattr(sdk, "Anthropic", build)
    return seen, replies


def message_body(text='{"answer": "ok", "tags": ["a"], "note": null}', model="test-model"):
    return {"id": "msg_test", "type": "message", "role": "assistant", "model": model,
            "content": [{"type": "text", "text": text}], "stop_reason": "end_turn",
            "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}}


def error_reply(status, kind="api_error"):
    httpx = pytest.importorskip("httpx2")
    # "x-should-retry: true" makes the SDK retry whenever it has retries left.
    return httpx.Response(status, headers={"x-should-retry": "true", "retry-after": "0"},
                          json={"type": "error", "error": {"type": kind, "message": "boom"}})


def test_wire_success_is_one_request_with_the_configured_timeout(wire):
    seen, replies = wire
    replies.append(message_body())
    llm = AnthropicLLM(api_key=KEY, model="test-model", timeout_seconds=7.5)
    assert llm.complete_json("demo", "s", "u", SCHEMA).data == GOOD
    [request] = seen
    assert request.url.path == "/v1/messages" and "anthropic-beta" not in request.headers
    assert request.extensions["timeout"] == dict.fromkeys(("connect", "read", "write", "pool"),
                                                          7.5)
    body = json.loads(request.content)
    assert "fallbacks" not in body and "thinking" not in body


@pytest.mark.parametrize(
    ("status", "expected"),
    [(529, LLMTransportError), (500, LLMTransportError), (503, LLMTransportError),
     (429, LLMRateLimitError), (408, LLMTimeoutError), (409, LLMRequestError)],
)
def test_wire_errors_the_sdk_would_retry_are_sent_once(wire, status, expected):
    seen, replies = wire
    replies.extend([error_reply(status), message_body()])
    with pytest.raises(expected):
        AnthropicLLM(api_key=KEY, model="test-model").complete_json("demo", "s", "u", SCHEMA)
    assert len(seen) == 1


def test_wire_connection_errors_and_timeouts_are_sent_once(wire):
    httpx = pytest.importorskip("httpx2")
    seen, replies = wire
    llm = AnthropicLLM(api_key=KEY, model="test-model", timeout_seconds=5)
    replies.extend([httpx.ConnectError("refused"), message_body()])
    with pytest.raises(LLMTransportError, match="could not reach"):
        llm.complete_json("demo", "s", "u", SCHEMA)
    assert len(seen) == 1

    replies.clear()
    replies.extend([httpx.ReadTimeout("slow"), message_body()])
    with pytest.raises(LLMTimeoutError, match="within 5s"):
        llm.complete_json("demo", "s", "u", SCHEMA)
    assert len(seen) == 2  # one more request, not three


def test_wire_schema_retry_is_the_only_retry(wire):
    seen, replies = wire
    llm = AnthropicLLM(api_key=KEY, model="test-model")
    replies.extend([message_body("not json"), message_body()])
    assert llm.complete_json("demo", "s", "u", SCHEMA).attempts == 2
    assert len(seen) == 2

    # A provider failure on the retry ends the call: 2 requests in all, nothing multiplied.
    replies.clear()
    replies.extend([message_body("not json"), error_reply(529, "overloaded_error"),
                    message_body()])
    with pytest.raises(LLMTransportError, match="HTTP 529"):
        llm.complete_json("demo", "s", "u", SCHEMA)
    assert len(seen) == 4


def test_wire_enabled_fallback_sends_the_beta_parameter(wire):
    seen, replies = wire
    replies.append(message_body(model="served-model"))
    llm = AnthropicLLM(api_key=KEY, model="test-model", refusal_fallback=True)
    assert llm.complete_json("demo", "s", "u", SCHEMA).served_by == "served-model"
    [request] = seen
    assert REFUSAL_FALLBACK_BETA in request.headers["anthropic-beta"]
    assert json.loads(request.content)["fallbacks"] == "default"


def test_api_key_never_reaches_repr_logs_or_errors(sdk, monkeypatch, caplog):
    llm = AnthropicLLM(api_key=KEY, model="test-model")
    outcomes = [
        api_response(text="not json"),
        api_response(),
        status_error(sdk, sdk.AuthenticationError, 401, "invalid x-api-key"),
        status_error(sdk, sdk.BadRequestError, 400, f"something about {KEY}"),
    ]

    def fake_create(**kwargs):
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(llm._client.messages, "create", fake_create)
    errors = []
    with caplog.at_level(logging.DEBUG):
        llm.complete_json("demo", "s", "u", SCHEMA)
        for _ in range(2):
            with pytest.raises(LLMTransportError) as exc_info:
                llm.complete_json("demo", "s", "u", SCHEMA)
            errors.append(str(exc_info.value))
    assert caplog.records  # the calls were logged
    for text in [repr(llm), caplog.text, *errors]:
        assert KEY not in text


# --- Factory -----------------------------------------------------------------------------------


def test_make_llm_defaults_to_the_mock():
    llm = make_llm(load_settings({}))
    assert isinstance(llm, MockLLM)
    assert llm.max_schema_retries == 1


def test_make_llm_anthropic_requires_its_key():
    settings = load_settings({"LLM_PROVIDER": "anthropic", "LLM_MODEL": "test-model",
                              "LLM_API_KEY": "not-this-one"})
    with pytest.raises(LLMConfigError, match="ANTHROPIC_API_KEY is required"):
        make_llm(settings)


def test_make_llm_anthropic_defaults(sdk):
    settings = load_settings({"LLM_PROVIDER": "anthropic", "LLM_MODEL": "test-model",
                              "ANTHROPIC_API_KEY": KEY})
    llm = make_llm(settings)
    assert (llm.refusal_fallback, llm.timeout_seconds, llm.max_attempts) == (False, 120.0, 2)
    assert llm._client.max_retries == 0


def test_make_llm_anthropic_uses_the_settings(sdk):
    settings = load_settings({
        "LLM_PROVIDER": "anthropic", "LLM_MODEL": "test-model", "ANTHROPIC_API_KEY": KEY,
        "LLM_TIMEOUT_SECONDS": "45", "LLM_REFUSAL_FALLBACK": "true",
        "MAX_GENERATION_RETRIES": "0",
    })
    llm = make_llm(settings)
    assert isinstance(llm, AnthropicLLM)
    assert (llm.model, llm.timeout_seconds, llm.refusal_fallback, llm.max_attempts) == (
        "test-model", 45.0, True, 1)
    assert llm._client.api_key == KEY


def test_make_llm_rejects_unimplemented_providers():
    settings = load_settings({"LLM_PROVIDER": "openai", "LLM_MODEL": "m", "LLM_API_KEY": "k"})
    with pytest.raises(LLMConfigError, match="not implemented"):
        make_llm(settings)
