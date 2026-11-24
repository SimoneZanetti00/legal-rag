"""The public live demo: its limits and spend cap (src/live_limits.py) and the public mode of the
web server (src/web_demo.py --public). Offline: the pipeline and the spend are stand-ins; no model
is called. The Space folder (deploy/live-space/) is tested in tests/test_live_space.py."""

import datetime
import http.client
import json
import threading

import pytest

import src.demo as demo
import src.web_demo as web
from src.live_limits import Limits, LiveGate
from src.llm import LLMConfigError, LLMRateLimitError
from src.config import load_settings
from tests.test_web_demo import INFO, SECRET, Pipeline, body

DAY = datetime.datetime(2026, 11, 24, 9, 0, tzinfo=datetime.UTC).timestamp()
QUESTION = "Entro quando il titolare deve notificare una violazione dei dati personali?"


class Clock:
    def __init__(self, at=DAY):
        self.now = at

    def __call__(self):
        return self.now


@pytest.fixture(scope="module")
def synthetic_result():
    return demo.synthetic(lambda line: None).result


# --- The limits --------------------------------------------------------------------------------


def test_the_default_limits():
    assert Limits() == Limits(per_visitor_hour=3, per_visitor_day=10, global_day=40,
                              spend_usd_day=1.50, question_reserve_usd=0.10,
                              max_question_chars=300)


def test_a_visitor_may_ask_three_questions_per_rolling_hour():
    clock = Clock()
    gate = LiveGate(clock=clock)
    assert [gate.admit("v1") for _ in range(3)] == [None, None, None]
    refusal = gate.admit("v1")
    assert refusal.code == "visitor_hourly_limit" and "3 questions in the last hour" in refusal.message
    assert gate.admit("v2") is None  # another visitor is not affected
    clock.now += 3600  # an hour after the first three
    assert gate.admit("v1") is None


def test_a_visitor_may_ask_ten_questions_per_day():
    clock = Clock()
    gate = LiveGate(clock=clock)
    for _ in range(10):
        assert gate.admit("v1") is None
        clock.now += 1300  # under three per hour
    assert gate.admit("v1").code == "visitor_daily_limit"


def test_all_visitors_together_may_ask_forty_questions_per_day():
    gate = LiveGate(clock=Clock())
    assert all(gate.admit(f"v{n}") is None for n in range(40))
    refusal = gate.admit("someone new")
    assert refusal.code == "global_daily_limit" and "40 questions" in refusal.message


def test_the_spend_cap_counts_reported_spend_and_keeps_a_reserve():
    gate = LiveGate(clock=Clock())
    for _ in range(27):  # 27 questions at $0.05: $1.35 spent
        gate.spend(0.05)
    assert gate.admit("v1") is None  # 1.35 + the $0.10 minimum reserve <= 1.50
    gate.spend(0.10)  # 1.45 + 0.10 > 1.50
    refusal = gate.admit("v2")
    assert refusal.code == "daily_spend_cap" and "$1.50" in refusal.message
    assert gate.today()["spent_usd"] == 1.45


def test_the_most_expensive_question_today_is_the_reserve():
    gate = LiveGate(clock=Clock())
    gate.spend(0.30)
    gate.spend(0.90)  # 1.20 spent; the next question could cost 0.90
    assert gate.admit("v1").code == "daily_spend_cap"


def test_a_new_utc_day_starts_every_counter_again():
    clock = Clock()
    gate = LiveGate(clock=clock)
    for n in range(40):
        gate.admit(f"v{n}")
    gate.spend(2.0)
    assert gate.admit("v1").code == "daily_spend_cap"
    clock.now += 24 * 3600
    assert gate.admit("v1") is None
    assert gate.today() == {"day": "2026-11-25", "questions": 1, "spent_usd": 0.0}


# --- The web server in public mode -------------------------------------------------------------


def public_app(outcome, *, limits=Limits(), spent=None, client_ip_header="X-Forwarded-For"):
    gate = LiveGate(limits, clock=Clock())
    meter = spent or (lambda: 0.0)
    public = web.Public(gate, meter, client_ip_header=client_ip_header)
    return web.DemoApp(Pipeline(outcome), INFO, public=public), gate


def ask(app, question=QUESTION, visitor="v1", **fields):
    return app.ask(body({"question": question, **fields}), visitor)


def test_public_mode_answers_in_research_mode_only(synthetic_result):
    app, _ = public_app(synthetic_result)
    assert ask(app).status == 200 and app._answer.modes == ["research"]  # the default
    reply = ask(app, mode="verified")
    assert (reply.status, reply.payload["error"]["code"]) == (400, "invalid_mode")
    health = app.health().payload
    assert (health["public"], health["modes"], health["default_mode"]) == (
        True, ["research"], "research")
    assert health["max_question_chars"] == 300 and health["limits"]["global_day"] == 40
    assert health["replay_url"] == web.REPLAY_URL


def test_public_mode_refuses_a_question_longer_than_300_characters(synthetic_result):
    app, gate = public_app(synthetic_result)
    reply = ask(app, "x" * 301)
    assert (reply.status, reply.payload["error"]["code"]) == (400, "question_too_long")
    assert "at most 300 characters" in reply.payload["error"]["message"]
    assert app._answer.questions == [] and gate.today()["questions"] == 0  # not counted
    assert ask(app, "Notifica " + "x" * 291).status == 200  # exactly 300


def test_a_question_over_a_limit_gets_429_with_the_replay(synthetic_result):
    app, _ = public_app(synthetic_result, limits=Limits(per_visitor_hour=1))
    assert ask(app).status == 200
    reply = ask(app)
    error = reply.payload["error"]
    assert (reply.status, error["code"]) == (429, "visitor_hourly_limit")
    assert error["replay_url"] == web.REPLAY_URL and "replay" in error["message"]
    assert len(app._answer.questions) == 1  # the refused question reached no model


def test_the_spend_of_each_question_is_counted_even_when_it_fails(synthetic_result):
    spent = [0.0]

    def answer_and_spend(question, mode):  # the client's spend grows while it answers
        spent[0] += 0.4
        raise LLMRateLimitError("rate limit")

    gate = LiveGate(Limits(), clock=Clock())
    app = web.DemoApp(answer_and_spend, INFO, public=web.Public(gate, lambda: spent[0]))
    assert ask(app).status == 503
    assert gate.today()["spent_usd"] == 0.4
    assert ask(app, visitor="v2").status == 503
    assert ask(app, visitor="v3").status == 503  # 1.2 spent; 1.2 + 0.4 > 1.5 next
    assert ask(app, visitor="v4").payload["error"]["code"] == "daily_spend_cap"


def test_neither_the_question_nor_the_visitor_is_logged(synthetic_result, capsys):
    app, _ = public_app(synthetic_result)
    ask(app, visitor=app.visitor("203.0.113.7"))
    err = capsys.readouterr().err
    assert "live: 1 question(s) today, $0.0000 of $1.50 spent" in err
    assert QUESTION not in err and "203.0.113.7" not in err


def test_a_visitor_is_a_keyed_hash_of_the_address():
    app, _ = public_app(None)
    key = app.visitor("203.0.113.7")
    assert key == app.visitor("203.0.113.7") and key != app.visitor("203.0.113.8")
    assert "203" not in key and len(key) == 16
    other, _ = public_app(None)  # another server process: another key
    assert other.visitor("203.0.113.7") != key


def test_the_public_mode_needs_a_priced_model():
    settings = load_settings({"LLM_PROVIDER": "anthropic", "LLM_MODEL": "some-other-model",
                              "ANTHROPIC_API_KEY": SECRET})
    with pytest.raises(LLMConfigError, match="no price is recorded"):
        web.build_app(settings=settings, public=True)


def test_only_the_public_mode_listens_beyond_127_0_0_1(synthetic_result):
    with pytest.raises(ValueError, match="only the public live mode"):
        web.create_server(web.DemoApp(Pipeline(synthetic_result), INFO), 0, "0.0.0.0")


def serve(app):
    server = web.create_server(app, port=0)  # 127.0.0.1 in tests
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture
def public_server(synthetic_result):
    app, gate = public_app(synthetic_result, limits=Limits(per_visitor_hour=1))
    server = serve(app)
    yield server.server_address[1], app
    server.shutdown()
    server.server_close()


@pytest.fixture
def true_client_ip_server(synthetic_result):
    app, _ = public_app(synthetic_result, limits=Limits(per_visitor_hour=1),
                        client_ip_header="True-Client-IP")
    server = serve(app)
    yield server.server_address[1], app
    server.shutdown()
    server.server_close()


def get(port, path, headers):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", path, headers=headers)
    reply = conn.getresponse()
    result = reply.status, reply.read()
    conn.close()
    return result


def post(port, headers):
    data = body({"question": QUESTION})
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("POST", "/api/ask", body=data, headers={
        "Content-Type": "application/json", "Content-Length": str(len(data)), **headers})
    reply = conn.getresponse()
    result = reply.status, reply.getheader("Content-Security-Policy"), json.loads(reply.read())
    conn.close()
    return result


def test_the_visitor_is_the_last_forwarded_address(public_server):
    port, _ = public_server
    host = {"Host": "legal-rag-live.hf.space", "Origin": "https://legal-rag-live.hf.space"}
    status, csp, _ = post(port, {**host, "X-Forwarded-For": "198.51.100.1, 203.0.113.7"})
    assert status == 200 and "frame-ancestors 'self' https://huggingface.co" in csp
    # A client can prepend any address; the one the proxy appended still counts.
    status, _, payload = post(port, {**host, "X-Forwarded-For": "198.51.100.99, 203.0.113.7"})
    assert (status, payload["error"]["code"]) == (429, "visitor_hourly_limit")
    status, _, _ = post(port, {**host, "X-Forwarded-For": "203.0.113.8"})
    assert status == 200  # another visitor


def test_the_visitor_report_shows_how_a_request_is_counted_without_an_address(public_server):
    port, app = public_server
    status, raw = get(port, "/api/visitor", {"Host": "legal-rag-live.onrender.com",
                                             "X-Forwarded-For": "198.51.100.1, 203.0.113.7"})
    report = json.loads(raw)
    assert status == 200 and report == {
        "visitor": app.visitor("203.0.113.7"), "client_ip_header": "X-Forwarded-For",
        "header_present": True, "x_forwarded_for_entries": 2,
        "forwarding_headers": ["X-Forwarded-For"]}
    assert b"203.0.113" not in raw and b"198.51.100" not in raw


def test_another_header_can_name_the_visitor(true_client_ip_server):
    port, app = true_client_ip_server
    host = {"Host": "legal-rag-live.onrender.com"}
    # The visitor is the whole True-Client-IP value; X-Forwarded-For no longer matters.
    status, _, _ = post(port, {**host, "True-Client-IP": "203.0.113.9",
                               "X-Forwarded-For": "10.0.0.1"})
    assert status == 200
    status, _, payload = post(port, {**host, "True-Client-IP": "203.0.113.9",
                                     "X-Forwarded-For": "10.0.0.2"})
    assert (status, payload["error"]["code"]) == (429, "visitor_hourly_limit")
    _, raw = get(port, "/api/visitor", {**host, "True-Client-IP": "203.0.113.9"})
    assert json.loads(raw)["visitor"] == app.visitor("203.0.113.9")


def test_the_visitor_report_exists_in_public_mode_only(synthetic_result):
    server = serve(web.DemoApp(Pipeline(synthetic_result), INFO))
    port = server.server_address[1]
    try:
        status, _ = get(port, "/api/visitor", {"Host": f"127.0.0.1:{port}"})
        assert status == 404
    finally:
        server.shutdown()
        server.server_close()


def test_the_client_ip_header_setting():
    assert load_settings({}).live_client_ip_header == "X-Forwarded-For"
    assert load_settings({"LIVE_CLIENT_IP_HEADER": "True-Client-IP"}).live_client_ip_header == (
        "True-Client-IP")
    from src.config import ConfigError
    with pytest.raises(ConfigError, match="LIVE_CLIENT_IP_HEADER must be a header name"):
        load_settings({"LIVE_CLIENT_IP_HEADER": "X Forwarded For"})


def test_public_mode_refuses_requests_from_other_sites(public_server):
    port, _ = public_server
    status, _, payload = post(port, {"Host": "legal-rag-live.hf.space",
                                     "Origin": "https://evil.example"})
    assert (status, payload["error"]["code"]) == (403, "forbidden_origin")


# --- The page -----------------------------------------------------------------------------------


def test_the_page_says_where_questions_go_and_links_the_replay():
    page = (web.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    js = (web.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    notice = page[page.index('<aside id="public-notice"'):page.index("</aside>",
                                                                   page.index('id="public-notice"'))]
    assert "hidden" in notice.split(">")[0]  # shown by the page in public mode only
    assert "sent to Anthropic's API" in notice and "Do not include personal data" in notice
    assert "if (info.public) applyPublicMode();" in js
    assert '$(".modes").hidden = true;' in js  # research mode only
    assert "$(\"#public-replay\").href = info.replay_url;" in js
    assert "showError(message, payload && payload.error ? payload.error.replay_url : null);" in js
    assert "Open the replay of saved answers" in js

