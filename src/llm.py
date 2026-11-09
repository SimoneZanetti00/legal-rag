"""LLM access behind one interface: complete_json(task, system, user, schema).

Two implementations:

- MockLLM: scripted, deterministic and offline. It is what LLM_PROVIDER=mock (the default)
  gives you, and the only client the default test suite uses. It never invents a reply: a
  task without a scripted reply is an error.
- AnthropicLLM: Claude through the official `anthropic` SDK. The SDK is imported only when
  this client is created, so nothing else needs it installed.

Both return JSON that has been parsed and checked against the caller's schema (a small,
explicitly supported subset of JSON Schema, see check_schema).

Retries are decided here and nowhere else. One call sends at most `max_attempts` =
1 + max_schema_retries requests (max_schema_retries is 0 or 1, from MAX_GENERATION_RETRIES).
The one retry is only for a reply that is not JSON, or breaks the schema or the caller's
check. A provider failure (connection, timeout, any HTTP error), a refusal, or a reply cut off
at the token limit ends the call at once with a typed error. The SDK's automatic retries are
off (SDK_MAX_RETRIES = 0), so one attempt is one HTTP request, and one call waits about
max_attempts x LLM_TIMEOUT_SECONDS at most (see AnthropicLLM for the timeout).

Failures raise typed errors (LLMError and its subclasses) so callers can fail closed. The API
key is never kept on the client object, written to the log, or put in an error message.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from src.config import MAX_ALLOWED_GENERATION_RETRIES, ConfigError, Settings, load_settings

logger = logging.getLogger(__name__)

# Thinking counts toward max_tokens on current Claude models, so leave room beyond the JSON.
DEFAULT_MAX_OUTPUT_TOKENS = 16000
# The SDK's automatic retries (by default 2, for connection errors, 408, 409, 429, 5xx and
# whenever the server sends "x-should-retry: true") are turned off: every retry is decided in
# complete_json, so one attempt is exactly one HTTP request.
SDK_MAX_RETRIES = 0
# Beta header for `fallbacks="default"` (server-side re-run of a refused request).
REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"

_TASK_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}")
_MAX_DETAIL_CHARS = 500
_KEY_LIKE = re.compile(r"sk-ant-[A-Za-z0-9_\-]+")


# --- Errors ------------------------------------------------------------------------------------


class LLMError(Exception):
    """Any failure to get usable structured output from an LLM."""


class LLMConfigError(LLMError):
    """The client cannot be used as configured: no API key or model, SDK missing, bad script."""


class LLMTransportError(LLMError):
    """The provider request failed: connection, HTTP error, unexpected response."""

    def __init__(self, message: str, *, status_code: int | None = None,
                 request_id: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id


class LLMAuthenticationError(LLMTransportError):
    """The API key was rejected (401) or is not allowed to make the request (403)."""


class LLMRateLimitError(LLMTransportError):
    """Rate or spend limit reached (429). Not retried."""


class LLMTimeoutError(LLMTransportError):
    """No response in time, client side (LLM_TIMEOUT_SECONDS) or server side (408, 504)."""


class LLMRequestError(LLMTransportError):
    """The API rejected the request itself (4xx): bad parameters, unknown model, too large."""


class LLMRefusalError(LLMError):
    """The model declined (stop_reason "refusal"). Never retried here."""

    def __init__(self, message: str, *, category: str | None = None,
                 model: str | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.model = model


class LLMOutputError(LLMError):
    """A reply arrived but cannot be used. `attempts` is how many replies were tried."""

    retryable = True

    def __init__(self, message: str, *, attempts: int = 1) -> None:
        super().__init__(message)
        self.attempts = attempts


class LLMMalformedOutputError(LLMOutputError):
    """The reply has no text, or its text is not one JSON value."""


class LLMSchemaError(LLMOutputError):
    """The reply is JSON but breaks the schema or the caller's check."""


class LLMTruncatedError(LLMOutputError):
    """The reply stopped early (token or context limit). Retrying the same request would not help."""

    retryable = False


# --- Results -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class RawCompletion:
    """One provider reply, before any parsing."""

    text: str | None
    stop_reason: str
    model: str  # the model that produced this reply
    refusal_category: str | None = None
    fallback_used: bool = False
    request_id: str | None = None


@dataclass(frozen=True)
class JSONResult:
    data: dict[str, Any]  # parsed, schema-checked
    task: str
    provider: str
    model: str  # the configured model
    served_by: str  # the model that produced the accepted reply (differs after a fallback)
    attempts: int  # replies requested, including the accepted one
    fallback_used: bool
    request_ids: tuple[str, ...] = ()


JSONCheck = Callable[[dict[str, Any]], None]  # raises LLMSchemaError to reject a reply


@runtime_checkable
class LLMClient(Protocol):
    provider: str
    model: str

    def complete_json(self, task: str, system: str, user: str, schema: Mapping[str, Any], *,
                      check: JSONCheck | None = None) -> JSONResult:
        """One structured-JSON task. `task` names it in logs and selects MockLLM's script."""
        ...


# --- JSON Schema subset ------------------------------------------------------------------------

# What check_schema accepts and validate_json enforces. All of it is also accepted by Claude's
# structured outputs; length and number bounds are not, so they are left out on purpose.
_SCHEMA_KEYWORDS = frozenset(
    {"type", "properties", "required", "additionalProperties", "items", "enum", "anyOf",
     "description"}
)
_JSON_TYPES = ("object", "array", "string", "integer", "number", "boolean", "null")


def check_schema(schema: Mapping[str, Any], path: str = "$") -> None:
    """Fail unless `schema` uses only the subset that validate_json implements.

    Every object must set additionalProperties to false and list only declared properties as
    required; every array must give `items`; `anyOf` stands alone (with an optional description).
    """
    if not isinstance(schema, Mapping):
        raise LLMConfigError(f"schema {path}: expected an object")
    unknown = set(schema) - _SCHEMA_KEYWORDS
    if unknown:
        raise LLMConfigError(f"schema {path}: unsupported keywords {sorted(unknown)}")
    if "anyOf" in schema:
        options = schema["anyOf"]
        if set(schema) - {"anyOf", "description"}:
            raise LLMConfigError(f"schema {path}: anyOf must stand alone")
        if not isinstance(options, list) or not options:
            raise LLMConfigError(f"schema {path}: anyOf must be a non-empty list")
        for i, option in enumerate(options):
            check_schema(option, f"{path}.anyOf[{i}]")
        return

    kind = schema.get("type")
    if kind not in _JSON_TYPES:
        raise LLMConfigError(f"schema {path}: 'type' must be one of {', '.join(_JSON_TYPES)}")
    if kind == "object":
        if schema.get("additionalProperties") is not False:
            raise LLMConfigError(f"schema {path}: objects must set additionalProperties to false")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, Mapping) or not isinstance(required, list):
            raise LLMConfigError(f"schema {path}: bad properties or required")
        if not set(required) <= set(properties):
            raise LLMConfigError(f"schema {path}: required names undeclared properties")
        for name, sub in properties.items():
            check_schema(sub, f"{path}.{name}")
    elif {"properties", "required", "additionalProperties"} & set(schema):
        raise LLMConfigError(f"schema {path}: object keywords on a non-object type")
    if kind == "array":
        if "items" not in schema:
            raise LLMConfigError(f"schema {path}: arrays must give items")
        check_schema(schema["items"], f"{path}[]")
    elif "items" in schema:
        raise LLMConfigError(f"schema {path}: items on a non-array type")
    if "enum" in schema:
        values = schema["enum"]
        if not isinstance(values, list) or not values:
            raise LLMConfigError(f"schema {path}: enum must be a non-empty list")
        for value in values:
            if not _has_type(value, kind):
                raise LLMConfigError(f"schema {path}: enum value {value!r} is not a {kind}")


def validate_json(value: Any, schema: Mapping[str, Any], path: str = "$") -> None:
    """Raise LLMSchemaError if `value` does not satisfy `schema` (already check_schema'd)."""
    if "anyOf" in schema:
        for option in schema["anyOf"]:
            try:
                validate_json(value, option, path)
                return
            except LLMSchemaError:
                continue
        raise LLMSchemaError(f"{path}: matches none of the allowed alternatives")

    kind = schema["type"]
    if not _has_type(value, kind):
        raise LLMSchemaError(f"{path}: expected {kind}, got {_type_name(value)}")
    if "enum" in schema and not any(_same(value, allowed) for allowed in schema["enum"]):
        raise LLMSchemaError(f"{path}: {value!r} is not one of {schema['enum']}")
    if kind == "object":
        properties = schema.get("properties", {})
        missing = [name for name in schema.get("required", []) if name not in value]
        if missing:
            raise LLMSchemaError(f"{path}: missing required {missing}")
        extra = sorted(set(value) - set(properties))
        if extra:
            raise LLMSchemaError(f"{path}: unexpected properties {extra}")
        for name, item in value.items():
            validate_json(item, properties[name], f"{path}.{name}")
    elif kind == "array":
        for i, item in enumerate(value):
            validate_json(item, schema["items"], f"{path}[{i}]")


def _has_type(value: Any, kind: str) -> bool:
    if kind == "object":
        return isinstance(value, dict)
    if kind == "array":
        return isinstance(value, list)
    if kind == "string":
        return isinstance(value, str)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "null":
        return value is None
    if isinstance(value, bool):  # bool is an int subclass, never a JSON number
        return False
    if kind == "integer":
        return isinstance(value, int)
    return isinstance(value, (int, float)) and math.isfinite(value)


def _same(a: Any, b: Any) -> bool:
    return type(a) is type(b) and a == b


def _type_name(value: Any) -> str:
    for kind in _JSON_TYPES:
        if _has_type(value, kind):
            return kind
    return type(value).__name__


def parse_json_object(text: str) -> dict[str, Any]:
    """The JSON object in `text`. Strict: no NaN or Infinity, no surrounding prose or fences."""
    try:
        value = json.loads(text, parse_constant=_reject_constant)
    except ValueError as exc:  # json.JSONDecodeError is a ValueError
        raise LLMMalformedOutputError(f"the reply is not valid JSON ({exc})") from None
    if not isinstance(value, dict):
        raise LLMSchemaError(f"$: expected object, got {_type_name(value)}")
    return value


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not valid JSON")


# --- Shared request loop -----------------------------------------------------------------------


class _JSONClient:
    """complete_json on top of `_complete`, with the bounded schema retry. Subclasses send."""

    provider = ""

    def __init__(self, *, model: str, max_schema_retries: int) -> None:
        if not 0 <= max_schema_retries <= MAX_ALLOWED_GENERATION_RETRIES:
            raise LLMConfigError(
                f"max_schema_retries must be between 0 and {MAX_ALLOWED_GENERATION_RETRIES} "
                f"(got {max_schema_retries})"
            )
        self.model = model
        self.max_schema_retries = max_schema_retries

    @property
    def max_attempts(self) -> int:
        """The most requests one complete_json call sends."""
        return 1 + self.max_schema_retries

    def _complete(self, task: str, system: str, user: str,
                  schema: Mapping[str, Any]) -> RawCompletion:
        raise NotImplementedError

    def complete_json(self, task: str, system: str, user: str, schema: Mapping[str, Any], *,
                      check: JSONCheck | None = None) -> JSONResult:
        if not isinstance(task, str) or not _TASK_NAME.fullmatch(task):
            raise LLMConfigError(f"task must be a lower-case identifier (got {task!r})")
        check_schema(schema)
        allowed = self.max_attempts
        prompt = user
        request_ids: list[str] = []
        for attempt in range(1, allowed + 1):
            raw = self._complete(task, system, prompt, schema)
            if raw.request_id:
                request_ids.append(raw.request_id)
            logger.debug("llm %s task=%s attempt=%d/%d model=%s stop_reason=%s request_id=%s",
                         self.provider, task, attempt, allowed, raw.model, raw.stop_reason,
                         raw.request_id)
            if raw.fallback_used:
                logger.warning("llm %s task=%s: served by fallback model %s (configured: %s)",
                               self.provider, task, raw.model, self.model)
            try:
                data = _accept(raw, schema, check)
            except LLMOutputError as exc:
                if not exc.retryable or attempt == allowed:
                    raise type(exc)(f"{exc} [attempt {attempt} of {allowed}]",
                                    attempts=attempt) from None
                logger.warning("llm %s task=%s: reply %d rejected, retrying once: %s",
                               self.provider, task, attempt, exc)
                prompt = _with_feedback(user, exc)
                continue
            return JSONResult(data=data, task=task, provider=self.provider, model=self.model,
                              served_by=raw.model or self.model, attempts=attempt,
                              fallback_used=raw.fallback_used, request_ids=tuple(request_ids))
        raise AssertionError("unreachable")  # the loop always returns or raises


def _accept(raw: RawCompletion, schema: Mapping[str, Any],
            check: JSONCheck | None) -> dict[str, Any]:
    if raw.stop_reason == "refusal":
        category = f", category {raw.refusal_category!r}" if raw.refusal_category else ""
        raise LLMRefusalError(f"the model ({raw.model}) declined the request{category}",
                              category=raw.refusal_category, model=raw.model)
    if raw.stop_reason in ("max_tokens", "model_context_window_exceeded"):
        raise LLMTruncatedError(f"the reply was cut off (stop_reason {raw.stop_reason!r})")
    if raw.stop_reason not in ("end_turn", "stop_sequence"):
        raise LLMMalformedOutputError(f"unexpected stop_reason {raw.stop_reason!r}")
    if raw.text is None or not raw.text.strip():
        raise LLMMalformedOutputError("the reply contains no text")
    data = parse_json_object(raw.text)
    validate_json(data, schema)
    if check is not None:
        check(data)
    return data


def _with_feedback(user: str, error: LLMOutputError) -> str:
    detail = _short(str(error))
    return (f"{user}\n\n[Your previous reply was rejected: {detail}. Reply again with one JSON "
            "object that satisfies the schema and the instructions.]")


def _short(text: str) -> str:
    text = _KEY_LIKE.sub("sk-ant-***", " ".join(str(text).split()))
    return text if len(text) <= _MAX_DETAIL_CHARS else text[: _MAX_DETAIL_CHARS - 1] + "…"


# --- Mock --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class MockCall:
    task: str
    system: str
    user: str
    schema: Mapping[str, Any]


class MockLLM(_JSONClient):
    """Deterministic, offline client. Replies come from a script, in order, per task.

    A scripted reply is one of:
    - a dict: sent back as JSON text, stop_reason "end_turn";
    - a str: sent back as raw text, not parsed (to exercise malformed output);
    - a RawCompletion: sent back as is (to exercise refusals and cut-off replies);
    - an exception instance: raised (to exercise provider failures).

    A task with no script, or with its script used up, raises LLMConfigError. `calls` records
    every request, including retries.
    """

    provider = "mock"

    def __init__(self, script: Mapping[str, Sequence[Any]] | None = None, *, model: str = "mock",
                 max_schema_retries: int = MAX_ALLOWED_GENERATION_RETRIES) -> None:
        super().__init__(model=model, max_schema_retries=max_schema_retries)
        self._script = {task: list(replies) for task, replies in (script or {}).items()}
        self._next = dict.fromkeys(self._script, 0)
        self.calls: list[MockCall] = []

    def __repr__(self) -> str:
        return f"MockLLM(model={self.model!r}, tasks={sorted(self._script)})"

    def _complete(self, task: str, system: str, user: str,
                  schema: Mapping[str, Any]) -> RawCompletion:
        self.calls.append(MockCall(task, system, user, schema))
        if task not in self._script:
            raise LLMConfigError(f"MockLLM has no scripted reply for task {task!r}")
        index = self._next[task]
        if index >= len(self._script[task]):
            raise LLMConfigError(
                f"MockLLM script for task {task!r} is used up after {index} replies"
            )
        self._next[task] = index + 1
        reply = self._script[task][index]
        if isinstance(reply, BaseException):
            raise reply
        if isinstance(reply, RawCompletion):
            return reply
        if isinstance(reply, dict):
            return RawCompletion(json.dumps(reply, ensure_ascii=False), "end_turn", self.model)
        if isinstance(reply, str):
            return RawCompletion(reply, "end_turn", self.model)
        raise LLMConfigError(f"MockLLM: unsupported scripted reply {type(reply).__name__}")


# --- Anthropic ---------------------------------------------------------------------------------


_MISSING_KEY = (
    "ANTHROPIC_API_KEY is required for LLM_PROVIDER='anthropic'. It is an API key from the "
    "Claude Console (https://platform.claude.com/settings/keys); a Claude subscription does not "
    "by itself provide API access. Set it in your environment or in a local .env file."
)


class AnthropicLLM(_JSONClient):
    """Claude through the official SDK, with structured JSON output.

    Each attempt is one non-streaming Messages API request (one HTTP request: the SDK does not
    retry) with `output_config.format` set to the caller's JSON schema and `max_tokens` =
    max_output_tokens. No `thinking` parameter is sent: current Claude models think adaptively
    by default (on Claude Opus 5.5 it cannot be turned off), and the reply is read by block
    type, so thinking blocks are skipped.

    timeout_seconds (LLM_TIMEOUT_SECONDS) is the SDK's request timeout. The HTTP client applies
    it to connecting, to sending the request and to waiting for the response; a non-streaming
    reply arrives in one piece, so an attempt lasts about timeout_seconds at most, and a call
    about max_attempts x timeout_seconds.

    refusal_fallback is off by default: a refusal raises LLMRefusalError and no other model is
    tried. When it is turned on, the request goes to the beta Messages endpoint with
    `fallbacks="default"`, so if the model's safety classifiers decline, the API itself re-runs
    the request on Anthropic's recommended fallback model. The model that served the reply is
    then reported in JSONResult.served_by (with fallback_used), and logged as a warning.
    """

    provider = "anthropic"

    def __init__(self, *, api_key: str | None, model: str, timeout_seconds: float = 120.0,
                 max_schema_retries: int = MAX_ALLOWED_GENERATION_RETRIES,
                 refusal_fallback: bool = False,
                 max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS, client: Any = None) -> None:
        """`client` replaces the SDK client (tests); otherwise one is built with `api_key`."""
        if not isinstance(model, str) or not model.strip():
            raise LLMConfigError("LLM_MODEL must be set for LLM_PROVIDER='anthropic'.")
        if not (math.isfinite(timeout_seconds) and timeout_seconds > 0):
            raise LLMConfigError(f"timeout_seconds must be positive (got {timeout_seconds})")
        if max_output_tokens <= 0:
            raise LLMConfigError(f"max_output_tokens must be positive (got {max_output_tokens})")
        if client is None and not api_key:
            raise LLMConfigError(_MISSING_KEY)
        super().__init__(model=model.strip(), max_schema_retries=max_schema_retries)
        self.timeout_seconds = timeout_seconds
        self.refusal_fallback = refusal_fallback
        self.max_output_tokens = max_output_tokens
        self._sdk = _import_sdk()  # its exception classes are needed even with an injected client
        if client is None:
            # An explicit api_key stops the SDK from reading any other credential source.
            client = self._sdk.Anthropic(api_key=api_key, timeout=timeout_seconds,
                                         max_retries=SDK_MAX_RETRIES)
        self._client = client

    def __repr__(self) -> str:
        return (f"AnthropicLLM(model={self.model!r}, timeout_seconds={self.timeout_seconds}, "
                f"refusal_fallback={self.refusal_fallback})")

    def _complete(self, task: str, system: str, user: str,
                  schema: Mapping[str, Any]) -> RawCompletion:
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_config": {"format": {"type": "json_schema", "schema": dict(schema)}},
        }
        try:
            if self.refusal_fallback:
                response = self._client.beta.messages.create(
                    betas=[REFUSAL_FALLBACK_BETA], fallbacks="default", **params
                )
            else:
                response = self._client.messages.create(**params)
        except self._sdk.APIError as exc:
            raise self._translate(exc) from exc
        return _read_response(response)

    def _translate(self, exc: Exception) -> LLMTransportError:
        sdk = self._sdk
        status = getattr(exc, "status_code", None)
        request_id = getattr(exc, "request_id", None)
        detail = _short(getattr(exc, "api_message", None) or getattr(exc, "message", None)
                        or str(exc))
        where = {"status_code": status, "request_id": request_id}
        retried = "not retried"
        if isinstance(exc, sdk.AuthenticationError):
            return LLMAuthenticationError(
                "the Anthropic API rejected the API key (HTTP 401). Check ANTHROPIC_API_KEY: it "
                "must be a Claude Console API key; a Claude subscription does not by itself "
                "provide API access.", **where)
        if isinstance(exc, sdk.PermissionDeniedError):
            return LLMAuthenticationError(
                f"the API key may not make this request (HTTP 403): {detail}", **where)
        if isinstance(exc, sdk.RateLimitError):
            return LLMRateLimitError(
                f"rate or spend limit reached (HTTP 429), {retried}: {detail}", **where)
        if isinstance(exc, sdk.APITimeoutError):
            return LLMTimeoutError(
                f"no response within {self.timeout_seconds}s (LLM_TIMEOUT_SECONDS), {retried}",
                **where)
        if isinstance(exc, sdk.APIConnectionError):
            return LLMTransportError(f"could not reach the Anthropic API, {retried}: {detail}",
                                     **where)
        if isinstance(exc, sdk.APIResponseValidationError):
            return LLMTransportError(f"unexpected response from the Anthropic API: {detail}",
                                     **where)
        if status in (408, 504):
            return LLMTimeoutError(f"the API timed out (HTTP {status}), {retried}: {detail}",
                                   **where)
        if isinstance(exc, sdk.NotFoundError):
            return LLMRequestError(
                f"not found (HTTP 404); check LLM_MODEL ({self.model!r}): {detail}", **where)
        if isinstance(status, int) and 400 <= status < 500:
            hint = ""
            if self.refusal_fallback and "fallback" in detail.lower():
                hint = (" (LLM_REFUSAL_FALLBACK=true: if this model does not support "
                        "server-side fallbacks, set it to false)")
            return LLMRequestError(f"the API rejected the request (HTTP {status}): {detail}{hint}",
                                   **where)
        if isinstance(status, int):
            return LLMTransportError(f"Anthropic API error (HTTP {status}), {retried}: {detail}",
                                     **where)
        return LLMTransportError(f"unexpected response from the Anthropic API: {detail}", **where)


def _import_sdk() -> Any:
    try:
        import anthropic
    except ImportError as exc:
        raise LLMConfigError(
            "LLM_PROVIDER='anthropic' needs the 'anthropic' package: "
            "pip install -r requirements.txt"
        ) from exc
    return anthropic


def _read_response(response: Any) -> RawCompletion:
    """Text blocks only (thinking and fallback marker blocks are skipped), plus served-by data."""
    blocks = list(getattr(response, "content", None) or [])
    texts = [block.text for block in blocks if getattr(block, "type", None) == "text"]
    usage = getattr(response, "usage", None)
    iterations = getattr(usage, "iterations", None) or []
    fallback_used = (any(getattr(it, "type", None) == "fallback_message" for it in iterations)
                     or any(getattr(block, "type", None) == "fallback" for block in blocks))
    return RawCompletion(
        text="".join(texts) if texts else None,
        stop_reason=str(getattr(response, "stop_reason", None)),
        model=str(getattr(response, "model", None) or ""),
        refusal_category=getattr(getattr(response, "stop_details", None), "category", None),
        fallback_used=fallback_used,
        request_id=getattr(response, "_request_id", None),
    )


# --- Factory -----------------------------------------------------------------------------------


def make_llm(settings: Settings | None = None) -> LLMClient:
    """The client for LLM_PROVIDER. "mock" (the default) sends nothing anywhere and has no
    script, so it answers no task until a test or developer scripts one."""
    settings = load_settings() if settings is None else settings
    provider = settings.llm_provider
    if provider == "mock":
        return MockLLM(max_schema_retries=settings.max_generation_retries)
    if provider == "anthropic":
        try:
            api_key = settings.require_llm_api_key()
        except ConfigError as exc:
            raise LLMConfigError(str(exc)) from None
        return AnthropicLLM(
            api_key=api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_schema_retries=settings.max_generation_retries,
            refusal_fallback=settings.llm_refusal_fallback,
        )
    raise LLMConfigError(f"LLM_PROVIDER={provider!r} is not implemented")
