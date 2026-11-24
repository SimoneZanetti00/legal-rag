"""Local web interface for the `ask` pipeline: `python -m src.web_demo`.

    python -m src.web_demo [--port 8000] [--build-dir DIR]

A small standard-library HTTP server bound to 127.0.0.1 only. It serves one page and two JSON
endpoints, and adds no retrieval, generation or checking of its own:

    GET  /             the page (src/web_static/: index.html, app.css, app.js)
    GET  /api/health   status: the build, how many articles may be cited (and used in research
                       mode), the modes, the provider and model (never a key), and the
                       project's own explanations of the codes the page displays
    POST /api/ask      {"question": "...", "mode": "verified" | "research"} ->
                       answer_question(...).to_dict(), unchanged, plus "source_status": the
                       status of every evidence item's source (src/source_status.py), and
                       "display_qualifications": the qualifications as shown (the fixed ones
                       in Italian for an Italian question; answer_generation)

The answer comes from answer_question() on the recorded build, with the settings and the LLM
client `python -m src.cli ask` uses; LLM_PROVIDER=mock is refused, as it is there.

Modes (answer_generation.Mode) are evidence policies, not separate pipelines. "verified", the
default when a request names none, uses citable provisions only. "research" also lets the answer
rest on provisions pending human review; each keeps its tier and is marked in source_status. Any
other value is refused (400), so a request never falls into research mode by accident.

Errors are JSON {"error": {"code", "message"}}: 400 an invalid question or body; 403 a request
whose Host or Origin is not this server; 404/405; 411/413/415 a missing, oversized or non-JSON
body; 502/503/504 a provider failure, by category only; 500 anything else. A response never
contains an exception's message (apart from the question checks' own), a traceback, a setting's
value or a key; the console logs the error type only, and never the question.

Local use by default. Requests must name this server in Host (DNS rebinding) and, when they carry
an Origin, come from it; /api/ask accepts only application/json, so another site open in the
browser cannot make this server spend API credit. Questions are answered one at a time.

Public live mode (--public, the Hugging Face Docker Space in deploy/live-space/): the server
listens on 0.0.0.0, answers in research mode only (with its notice), refuses questions longer than
Limits.max_question_chars, and applies src/live_limits.py before each question: per-visitor and
global question limits and a daily spend cap computed from the API's reported token usage. A
refused question gets 429 with a message and the URL of the replay. A visitor is the keyed hash of
the address the proxy reports last in X-Forwarded-For (else the socket's address); neither the
address nor the question is logged or kept. The page may be framed by huggingface.co (the Space
page). Counters reset when the server restarts.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import secrets
import sys
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from src.answer_generation import (
    MODEL_NOTES_LABEL,
    RESEARCH_QUALIFICATION,
    USABLE_TIERS,
    AnswerResult,
    CorpusPreflight,
    Mode,
    answer_question,
    corpus_preflight,
    display_qualifications,
)
from src.config import ConfigError, Settings, load_settings
from src.llm import (
    LLMAuthenticationError,
    LLMConfigError,
    LLMError,
    LLMRateLimitError,
    LLMRequestError,
    LLMTimeoutError,
    LLMTransportError,
    PRICES_USD_PER_MTOK,
    make_llm,
    usage_cost,
)
from src.live_limits import LIMITS, Limits, LiveGate
from src.provision_cli import MOCK_PROVIDER_MESSAGE
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.provisions import QUALIFICATIONS, REASONS, ProvisionError
from src.query_analysis import (
    CORPUS_INSTRUMENTS,
    MAX_QUESTION_CHARS,
    QueryAnalysisError,
    check_question,
)
from src.source_status import CATEGORIES, evidence_status

HOST = "127.0.0.1"
DEFAULT_PORT = 8000
PUBLIC_HOST = "0.0.0.0"  # the public live mode: inside the Space's container
PUBLIC_PORT = 7860  # the port a Hugging Face Docker Space serves (app_port)
REPLAY_URL = "https://huggingface.co/spaces/SimoneZanetti00/legal-rag-demo"
MAX_BODY_BYTES = 16 * 1024
STATIC_DIR = Path(__file__).resolve().parent / "web_static"
STATIC_FILES = {  # request path -> (file in STATIC_DIR, content type); nothing else is served
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
SECURITY_HEADERS = {
    "Content-Security-Policy": ("default-src 'self'; base-uri 'none'; form-action 'none'; "
                                "frame-ancestors 'none'"),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}
# Public mode: as above, except that huggingface.co may frame the page (the Space page shows the app
# in a frame); no other site may.
PUBLIC_SECURITY_HEADERS = {
    **SECURITY_HEADERS,
    "Content-Security-Policy": ("default-src 'self'; base-uri 'none'; form-action 'none'; "
                                "frame-ancestors 'self' https://huggingface.co"),
}
# Provider failures, by category: (error class, HTTP status, code, message). The first match wins,
# so subclasses come first. The provider's own message is never passed on.
_PROVIDER_ERRORS: tuple[tuple[type[LLMError], int, str, str], ...] = (
    (LLMAuthenticationError, 502, "provider_authentication",
     "The language-model provider rejected the credentials or did not permit the request."),
    (LLMRateLimitError, 503, "provider_rate_limited",
     "The language-model provider's rate or spend limit was reached. Try again later."),
    (LLMTimeoutError, 504, "provider_timeout",
     "The language-model provider did not answer in time. Try again."),
    (LLMRequestError, 502, "provider_rejected_request",
     "The language-model provider rejected the request."),
    (LLMTransportError, 502, "provider_unavailable",
     "The language-model provider could not be reached or returned an error."),
    (LLMConfigError, 503, "model_not_configured",
     "The language model is not configured on this server."),
    (LLMError, 502, "model_error", "The language model call failed."),
)

MODES = tuple(mode.value for mode in Mode)
DEFAULT_MODE = Mode.VERIFIED.value

Answer = Callable[[str, str], AnswerResult]  # (question, mode) -> result
Describe = Callable[[AnswerResult], dict[str, Any]]  # result -> source status by evidence ID


@dataclass(frozen=True)
class Reply:
    status: int
    payload: dict[str, Any]


@dataclass(frozen=True)
class Public:
    """The public live mode: research only, short questions, the limits of `gate`. `spent` is
    what the model client has spent so far, in US dollars (all its replies, priced)."""

    gate: LiveGate
    spent: Callable[[], float]
    replay_url: str = REPLAY_URL

    @property
    def limits(self) -> Limits:
        return self.gate.limits


def error(status: int, code: str, message: str, **extra: Any) -> Reply:
    return Reply(status, {"error": {"code": code, "message": message, **extra}})


class DemoApp:
    """The endpoints, independent of HTTP: `answer` is answer_question bound to its LLM client,
    build and settings (or a stand-in in tests); `describe` gives the source status of a
    result's evidence; `info` is what /api/health reports."""

    def __init__(self, answer: Answer, info: Mapping[str, Any],
                 describe: Describe | None = None, *, public: Public | None = None) -> None:
        self._answer = answer
        self._describe = describe or (lambda result: {})
        self.info = dict(info)
        self.public = public
        if public is not None:
            self.info.update(public_info(public))
        self._modes = ("research",) if public else MODES
        self._default_mode = "research" if public else DEFAULT_MODE
        self._lock = threading.Lock()  # one question at a time
        self._salt = secrets.token_bytes(16)  # visitor keys are not comparable across restarts

    def visitor(self, address: str) -> str:
        """The key a client address is counted under: a keyed hash, never the address itself."""
        return hmac.new(self._salt, address.encode("utf-8"), hashlib.sha256).hexdigest()[:16]

    def health(self) -> Reply:
        return Reply(200, {"status": "ok", **self.info})

    def ask(self, body: bytes, visitor: str = "local") -> Reply:
        """Answer one question. `visitor` (see visitor()) is what the public limits count."""
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return error(400, "invalid_json", "The request body is not valid JSON.")
        if not isinstance(data, dict) or not isinstance(data.get("question"), str):
            return error(400, "invalid_request",
                         'Send a JSON object with the question as text: {"question": "..."}.')
        mode = data.get("mode", self._default_mode)
        if not isinstance(mode, str) or mode not in self._modes:
            return error(400, "invalid_mode",
                         f'"mode" must be one of: {", ".join(self._modes)} '
                         f"(default {self._default_mode}).")
        if self.public and len(data["question"].strip()) > self.public.limits.max_question_chars:
            return error(400, "question_too_long",
                         f"Ask in at most {self.public.limits.max_question_chars} characters.")
        try:
            question = check_question(data["question"])
        except QueryAnalysisError as exc:  # its messages describe the question only
            return error(400, "invalid_question", _sentence(str(exc)))
        with self._lock:
            if self.public is None:
                return self._answer_one(question, mode)
            refusal = self.public.gate.admit(visitor)
            if refusal is not None:
                return error(429, refusal.code, f"{refusal.message} The saved answers remain "
                             "available in the replay.", replay_url=self.public.replay_url)
            before = self.public.spent()
            try:
                return self._answer_one(question, mode)
            finally:
                self.public.gate.spend(self.public.spent() - before)
                today = self.public.gate.today()
                _log(f"live: {today['questions']} question(s) today, ${today['spent_usd']:.4f} "
                     f"of ${self.public.limits.spend_usd_day:.2f} spent")

    def _answer_one(self, question: str, mode: str) -> Reply:
        """The answer to a checked question, or the error reply. Called holding the lock."""
        try:
            result = self._answer(question, mode)
        except QueryAnalysisError as exc:
            return error(400, "invalid_question", _sentence(str(exc)))
        except LLMError as exc:
            return _provider_error(exc)
        except Exception as exc:  # noqa: BLE001 - never let an internal error reach the page
            _log(f"internal error answering a question: {type(exc).__name__}")
            return error(500, "internal_error",
                         "The server could not answer this question. See its console.")
        try:
            status = self._describe(result)
        except Exception as exc:  # noqa: BLE001
            _log(f"internal error describing the sources: {type(exc).__name__}")
            return error(500, "internal_error",
                         "The server could not describe the sources. See its console.")
        return Reply(200, {**result.to_dict(), "source_status": status,
                           "display_qualifications": list(display_qualifications(result))})


def _provider_error(exc: LLMError) -> Reply:
    for cls, status, code, message in _PROVIDER_ERRORS:
        if isinstance(exc, cls):
            _log(f"language-model error: {type(exc).__name__}")
            extra = {}
            provider_status = getattr(exc, "status_code", None)
            if isinstance(provider_status, int):
                extra["provider_status"] = provider_status
            return error(status, code, message, **extra)
    raise AssertionError("unreachable: LLMError is the last entry")  # pragma: no cover


def _sentence(text: str) -> str:
    text = text.strip()
    return (text[:1].upper() + text[1:]).rstrip(".") + "." if text else "Invalid question."


def _log(message: str) -> None:
    print(f"[web_demo] {message}", file=sys.stderr, flush=True)


# --- HTTP --------------------------------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    # HTTP/1.0 (the default): the connection closes after each response, so a request refused
    # before its body is read leaves nothing behind.
    server_version = "LegalRAGDemo"
    sys_version = ""

    @property
    def app(self) -> DemoApp:
        return self.server.app  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802 - the http.server naming
        path = urlsplit(self.path).path
        if not self._from_this_server():
            return
        if path == "/api/health":
            self._send_json(self.app.health())
        elif path in STATIC_FILES:
            name, content_type = STATIC_FILES[path]
            self._send(200, (STATIC_DIR / name).read_bytes(), content_type)
        elif path == "/api/ask":
            self._send_json(error(405, "method_not_allowed", "Use POST for /api/ask."),
                            {"Allow": "POST"})
        else:
            self._send_json(error(404, "not_found", "No such page."))

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if not self._from_this_server():
            return
        if path in STATIC_FILES or path == "/api/health":
            self._send_json(error(405, "method_not_allowed", "Use GET for this page."),
                            {"Allow": "GET"})
            return
        if path != "/api/ask":
            self._send_json(error(404, "not_found", "No such page."))
            return
        content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if content_type != "application/json":
            self._send_json(error(415, "unsupported_media_type",
                                  "Send the question as application/json."))
            return
        length = self.headers.get("Content-Length")
        if length is None or not length.isdigit():
            self._send_json(error(411, "length_required", "The request has no Content-Length."))
            return
        if int(length) > MAX_BODY_BYTES:
            self._send_json(error(413, "body_too_large",
                                  f"The request body is larger than {MAX_BODY_BYTES} bytes."))
            return
        body = self.rfile.read(int(length))
        self._send_json(self.app.ask(body, self.app.visitor(self._client_address())))

    def _client_address(self) -> str:
        """In public mode, the address the proxy in front of the server reports last in
        X-Forwarded-For (a client can prepend entries, not append them); otherwise, and when
        there is none, the socket's peer address."""
        if self.app.public is not None:
            forwarded = [a.strip() for a in self.headers.get("X-Forwarded-For", "").split(",")]
            if forwarded and forwarded[-1]:
                return forwarded[-1]
        return str(self.client_address[0])

    def _from_this_server(self) -> bool:
        if self.app.public is not None:  # any host name; a browser request must come from it
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            if not host or (origin is not None
                            and origin not in {f"https://{host}", f"http://{host}"}):
                self._send_json(error(403, "forbidden_origin",
                                      "Requests from other sites are refused."))
                return False
            return True
        port = self.server.server_address[1]
        hosts = {f"{HOST}:{port}", f"localhost:{port}"}
        if self.headers.get("Host", "") not in hosts:
            self._send_json(error(403, "forbidden_host",
                                  "This server answers local requests only."))
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin not in {f"http://{h}" for h in hosts}:
            self._send_json(error(403, "forbidden_origin",
                                  "Requests from other sites are refused."))
            return False
        return True

    def _send_json(self, reply: Reply, headers: Mapping[str, str] | None = None) -> None:
        body = json.dumps(reply.payload, ensure_ascii=False).encode("utf-8")
        self._send(reply.status, body, "application/json; charset=utf-8", headers)

    def _send(self, status: int, body: bytes, content_type: str,
              headers: Mapping[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        security = PUBLIC_SECURITY_HEADERS if self.app.public is not None else SECURITY_HEADERS
        for name, value in {**security, **(headers or {})}.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - http.server API
        # Method, path and status only: the question is in the body, never in the log.
        _log(format % args)


def create_server(app: DemoApp, port: int = DEFAULT_PORT, host: str = HOST) -> ThreadingHTTPServer:
    """A server for `app` on `host`:`port` (0 picks a free port), not yet serving. Only the
    public live mode listens on another address than 127.0.0.1."""
    if host != HOST and app.public is None:
        raise ValueError("only the public live mode listens on another address than 127.0.0.1")
    server = ThreadingHTTPServer((host, port), _Handler)
    server.daemon_threads = True
    server.app = app  # type: ignore[attr-defined]
    return server


# --- The real pipeline -------------------------------------------------------------------------


def page_info(preflight: CorpusPreflight, *, provider: str, model: str,
              semantic_verification: bool) -> dict[str, Any]:
    """What /api/health reports (besides "status"): the build, the modes, the provider and model,
    and the project's own explanations of the codes the page displays. Also the page's data in
    a static replay (src/web_replay.py)."""
    tiers = dict(preflight.article_tiers)
    return {
        "build_id": preflight.build_id,
        "citable_articles": preflight.citable_articles,
        "research_usable_articles": sum(count for tier, count in tiers.items()
                                        if tier in USABLE_TIERS[Mode.RESEARCH]),
        "article_tiers": tiers,
        "modes": list(MODES),
        "default_mode": DEFAULT_MODE,
        "research_qualification": RESEARCH_QUALIFICATION,
        "provider": provider,
        "model": model,
        "semantic_verification": semantic_verification,
        "max_question_chars": MAX_QUESTION_CHARS,
        "instruments": dict(CORPUS_INSTRUMENTS),
        "reasons": dict(REASONS),
        "qualifications": dict(QUALIFICATIONS),
        "source_categories": dict(CATEGORIES),
        "model_notes_label": MODEL_NOTES_LABEL,
    }


def public_info(public: Public) -> dict[str, Any]:
    """What /api/health adds in the public live mode: research only, the limits, the replay."""
    return {"public": True, "modes": ["research"], "default_mode": "research",
            "max_question_chars": public.limits.max_question_chars,
            "limits": public.limits.to_dict(), "replay_url": public.replay_url}


def build_app(*, build_dir: Path | None = None, settings: Settings | None = None,
              public: bool = False, limits: Limits = LIMITS) -> DemoApp:
    """answer_question() on the recorded build, with the configured LLM, as `ask` runs it.
    Building the client sends nothing; no request is made until a question needs one. With
    `public`, the public live mode, with a LiveGate on `limits` and the client's spend priced
    at PRICES_USD_PER_MTOK."""
    settings = settings or load_settings()
    if settings.llm_provider == "mock":
        raise LLMConfigError(MOCK_PROVIDER_MESSAGE)
    if public and settings.llm_model not in PRICES_USD_PER_MTOK:
        raise LLMConfigError(f"no price is recorded for LLM_MODEL {settings.llm_model!r} "
                             "(llm.PRICES_USD_PER_MTOK); the public mode's spend cap needs one")
    llm = make_llm(settings)
    explorer = ProvisionExplorer.open(build_dir or find_recorded_build())
    info = page_info(corpus_preflight(explorer), provider=getattr(llm, "provider", ""),
                     model=getattr(llm, "model", ""),
                     semantic_verification=settings.semantic_verification)

    def answer(question: str, mode: str) -> AnswerResult:
        return answer_question(question, llm, explorer, settings=settings, mode=mode)

    def describe(result: AnswerResult) -> dict[str, Any]:
        return evidence_status(result.evidence, explorer.store)

    live = None
    if public:
        live = Public(LiveGate(limits), lambda: usage_cost(llm.usage_spent, llm.model))
    return DemoApp(answer, info, describe, public=live)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.web_demo",
        description="Serve the Legal RAG `ask` pipeline as a local web page on 127.0.0.1.")
    parser.add_argument("--port", type=int,
                        help=f"port (default: {DEFAULT_PORT}, or {PUBLIC_PORT} with --public; "
                             "0 picks a free one)")
    parser.add_argument("--build-dir", type=Path,
                        help="corpus build (default: the recorded build in data/processed/builds/)")
    parser.add_argument("--public", action="store_true",
                        help=f"the public live mode (a Hugging Face Space): listen on {PUBLIC_HOST}, "
                             "research mode only, with the limits of src/live_limits.py")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    host = PUBLIC_HOST if args.public else HOST
    port = args.port if args.port is not None else PUBLIC_PORT if args.public else DEFAULT_PORT
    try:
        app = build_app(build_dir=args.build_dir, public=args.public)
        server = create_server(app, port, host)
    except (ConfigError, LLMConfigError, ExplorerError, ProvisionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: cannot listen on {host}:{port}: {exc.strerror or exc}", file=sys.stderr)
        return 2
    info = app.info
    if app.public is not None:
        limits = app.public.limits
        print(f"Legal RAG live demo (public): listening on {host}:{server.server_address[1]}",
              flush=True)
        print(f"  build {info['build_id']}; model {info['provider']}/{info['model']}; research "
              f"mode only; questions of at most {limits.max_question_chars} characters")
        print(f"  limits: {limits.per_visitor_hour} per visitor per hour, {limits.per_visitor_day} "
              f"per visitor per day, {limits.global_day} per day in total, "
              f"${limits.spend_usd_day:.2f} of API spend per day (UTC); counters reset on "
              "restart", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    print(f"Legal RAG web demo: http://{HOST}:{server.server_address[1]}/", flush=True)
    print(f"  build {info['build_id']}; model {info['provider']}/{info['model']}")
    print(f"  verified mode (default): {info['citable_articles']} citable articles"
          + ("; no human review is recorded, so verified questions abstain before any model "
             "call" if not info["citable_articles"] else ""))
    print(f"  research demo mode (select it in the page): {info['research_usable_articles']} "
          "articles usable, including those pending human review, each marked as such")
    print("  A question is sent to the configured provider only when usable evidence exists "
          "for its mode. Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
