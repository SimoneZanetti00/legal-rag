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

Local use only. Requests must name this server in Host (DNS rebinding) and, when they carry an
Origin, come from it; /api/ask accepts only application/json, so another site open in the
browser cannot make this server spend API credit. Questions are answered one at a time.
"""

from __future__ import annotations

import argparse
import json
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
    make_llm,
)
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


def error(status: int, code: str, message: str, **extra: Any) -> Reply:
    return Reply(status, {"error": {"code": code, "message": message, **extra}})


class DemoApp:
    """The endpoints, independent of HTTP: `answer` is answer_question bound to its LLM client,
    build and settings (or a stand-in in tests); `describe` gives the source status of a
    result's evidence; `info` is what /api/health reports."""

    def __init__(self, answer: Answer, info: Mapping[str, Any],
                 describe: Describe | None = None) -> None:
        self._answer = answer
        self._describe = describe or (lambda result: {})
        self.info = dict(info)
        self._lock = threading.Lock()  # one question at a time

    def health(self) -> Reply:
        return Reply(200, {"status": "ok", **self.info})

    def ask(self, body: bytes) -> Reply:
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return error(400, "invalid_json", "The request body is not valid JSON.")
        if not isinstance(data, dict) or not isinstance(data.get("question"), str):
            return error(400, "invalid_request",
                         'Send a JSON object with the question as text: {"question": "..."}.')
        mode = data.get("mode", DEFAULT_MODE)
        if not isinstance(mode, str) or mode not in MODES:
            return error(400, "invalid_mode",
                         f'"mode" must be one of: {", ".join(MODES)} (default {DEFAULT_MODE}).')
        try:
            question = check_question(data["question"])
        except QueryAnalysisError as exc:  # its messages describe the question only
            return error(400, "invalid_question", _sentence(str(exc)))
        with self._lock:
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
        self._send_json(self.app.ask(self.rfile.read(int(length))))

    def _from_this_server(self) -> bool:
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
        for name, value in {**SECURITY_HEADERS, **(headers or {})}.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - http.server API
        # Method, path and status only: the question is in the body, never in the log.
        _log(format % args)


def create_server(app: DemoApp, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """A server for `app` on 127.0.0.1:`port` (0 picks a free port), not yet serving."""
    server = ThreadingHTTPServer((HOST, port), _Handler)
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


def build_app(*, build_dir: Path | None = None, settings: Settings | None = None) -> DemoApp:
    """answer_question() on the recorded build, with the configured LLM, as `ask` runs it.
    Building the client sends nothing; no request is made until a question needs one."""
    settings = settings or load_settings()
    if settings.llm_provider == "mock":
        raise LLMConfigError(MOCK_PROVIDER_MESSAGE)
    llm = make_llm(settings)
    explorer = ProvisionExplorer.open(build_dir or find_recorded_build())
    info = page_info(corpus_preflight(explorer), provider=getattr(llm, "provider", ""),
                     model=getattr(llm, "model", ""),
                     semantic_verification=settings.semantic_verification)

    def answer(question: str, mode: str) -> AnswerResult:
        return answer_question(question, llm, explorer, settings=settings, mode=mode)

    def describe(result: AnswerResult) -> dict[str, Any]:
        return evidence_status(result.evidence, explorer.store)

    return DemoApp(answer, info, describe)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.web_demo",
        description="Serve the Legal RAG `ask` pipeline as a local web page on 127.0.0.1.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"port on 127.0.0.1 (default: {DEFAULT_PORT}; 0 picks a free one)")
    parser.add_argument("--build-dir", type=Path,
                        help="corpus build (default: the recorded build in data/processed/builds/)")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        app = build_app(build_dir=args.build_dir)
        server = create_server(app, args.port)
    except (ConfigError, LLMConfigError, ExplorerError, ProvisionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: cannot listen on {HOST}:{args.port}: {exc.strerror or exc}",
              file=sys.stderr)
        return 2
    info = app.info
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
