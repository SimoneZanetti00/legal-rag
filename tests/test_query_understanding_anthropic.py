"""The query understanding layer and its experiment with LLM_PROVIDER=anthropic.

No test sends a request or needs a real key. AnthropicLLM is given a stand-in SDK client
(tests/test_llm.py FakeClient) that returns scripted Messages API responses or raises the SDK's
own exception classes. Settings are built with load_settings({...}), which does not read .env,
so a real key in a local .env can never reach these tests.
"""

import json
import re

import pytest

import src.query_understanding as qu
import src.query_understanding_demo as demo
import src.query_understanding_eval as qe
from src.config import ConfigError, load_settings
from src.llm import (
    AnthropicLLM,
    LLMAuthenticationError,
    LLMConfigError,
    LLMMalformedOutputError,
    LLMRateLimitError,
    LLMRequestError,
    LLMTimeoutError,
    LLMTransportError,
    LLMTruncatedError,
    MockLLM,
    make_llm,
)
from src.provision_eval import DEFAULT_BENCHMARK, load_benchmark
from src.provision_explorer import ExplorerError, find_recorded_build
from src.query_understanding import (
    PROMPT_VERSION,
    SCHEMA,
    SYSTEM_PROMPT,
    TASK,
    UnderstandingCache,
    build_user_message,
    generation_settings,
    understand,
)
from tests.test_llm import KEY, FakeClient, api_response, connection_error, status_error
from tests.test_query_fusion import GRADES, QUESTIONS, TABLE, FakeExplorer
from tests.test_query_understanding import QUESTION, REPLY, reply

ANTHROPIC = {"LLM_PROVIDER": "anthropic", "LLM_MODEL": "test-model", "ANTHROPIC_API_KEY": KEY}


@pytest.fixture
def sdk():
    return pytest.importorskip("anthropic")


def claude(*outcomes, retries=1):
    """AnthropicLLM over a stand-in SDK client; returns (llm, client)."""
    client = FakeClient(*outcomes)
    return AnthropicLLM(api_key=None, model="test-model", client=client,
                        max_schema_retries=retries), client


def response(data):
    return api_response(json.dumps(data, ensure_ascii=False))


def reply_for(question):
    """A reply that passes the rules for any question (test data, not model output)."""
    numbers = " ".join(re.findall(r"\d+", question))
    tail = (f" {numbers}" if numbers else "") + (
        " non" if qu._NEGATION_IN_QUESTION.search(question) else "")
    return {"legal_query": f"trattamento dei dati personali{tail}",
            "semantic_query": f"uso dei dati delle persone{tail}", "legal_concepts": [],
            "entities": [], "relationships": [], "conditions": [], "ambiguities": [],
            "clarification_needed": False}


# --- Configuration -----------------------------------------------------------------------------


def test_settings_build_an_anthropic_client_without_sending_anything(sdk):
    llm = make_llm(load_settings(ANTHROPIC))
    assert isinstance(llm, AnthropicLLM)
    assert (llm.provider, llm.model) == ("anthropic", "test-model")
    settings = generation_settings(llm)
    assert settings["max_schema_retries"] == 1 and settings["timeout_seconds"] == 120.0
    assert KEY not in json.dumps(settings) + repr(llm)


def test_a_missing_key_is_a_configuration_error():
    settings = load_settings({**ANTHROPIC, "ANTHROPIC_API_KEY": "", "LLM_API_KEY": KEY})
    with pytest.raises(LLMConfigError, match="ANTHROPIC_API_KEY is required") as exc_info:
        make_llm(settings)
    assert KEY not in str(exc_info.value)


@pytest.mark.parametrize("model", ["", "   "])
def test_a_missing_model_is_a_configuration_error(model):
    with pytest.raises(ConfigError, match="LLM_MODEL must be set"):
        load_settings({**ANTHROPIC, "LLM_MODEL": model})
    with pytest.raises(LLMConfigError, match="LLM_MODEL"):
        AnthropicLLM(api_key=KEY, model=model, client=FakeClient())


def test_the_mock_provider_is_still_the_default():
    llm = make_llm(load_settings({}))
    assert isinstance(llm, MockLLM)
    assert understand(QUESTION, MockLLM({TASK: [REPLY]})).provenance.provider == "mock"


# --- Requests and replies ----------------------------------------------------------------------


def test_understanding_sends_the_v1_prompt_and_schema_and_parses_the_reply(sdk):
    llm, client = claude(response(REPLY))
    reading = understand(QUESTION, llm)
    [(endpoint, request)] = client.requests
    assert endpoint == "messages"
    assert request["model"] == "test-model"
    assert request["system"] == SYSTEM_PROMPT
    assert request["messages"] == [{"role": "user", "content": build_user_message(QUESTION)}]
    assert request["output_config"] == {"format": {"type": "json_schema", "schema": SCHEMA}}
    assert "temperature" not in request  # not sent: the provider default applies
    assert reading.original_query == QUESTION
    assert reading.legal_query == REPLY["legal_query"]
    p = reading.provenance
    assert (p.task, p.prompt_version, p.provider, p.model) == (TASK, PROMPT_VERSION,
                                                               "anthropic", "test-model")
    assert (p.served_by, p.attempts, p.request_ids) == ("test-model", 1, ("req_ok",))


def test_a_reply_breaking_the_rules_is_retried_once_on_the_same_model(sdk):
    llm, client = claude(response(reply(legal_query="conservazione per 99 anni")),
                         response(REPLY))
    reading = understand(QUESTION, llm)
    assert reading.provenance.attempts == 2 and len(client.requests) == 2
    assert "adds numbers" in client.requests[1][1]["messages"][0]["content"]  # the feedback


def test_a_reply_breaking_the_rules_twice_is_an_error_not_a_reading(sdk, tmp_path):
    bad = response(reply(entities=[{"mention": "il Garante", "type": "public_authority"}],
                         relationships=[]))
    llm, _ = claude(bad, bad)
    with pytest.raises(qu.LLMSchemaError, match="not copied"):
        understand(QUESTION, llm, cache=UnderstandingCache(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_malformed_and_cut_off_api_replies_are_errors(sdk):
    llm, _ = claude(api_response("not json"), api_response("{"))
    with pytest.raises(LLMMalformedOutputError):
        understand(QUESTION, llm)
    llm, client = claude(api_response('{"legal_query": "dati', stop_reason="max_tokens"))
    with pytest.raises(LLMTruncatedError):
        understand(QUESTION, llm)
    assert len(client.requests) == 1  # a cut-off reply is not retried


@pytest.mark.parametrize(("cls_name", "status", "expected"), [
    ("AuthenticationError", 401, LLMAuthenticationError),
    ("PermissionDeniedError", 403, LLMAuthenticationError),
    ("NotFoundError", 404, LLMRequestError),
    ("BadRequestError", 400, LLMRequestError),
    ("RateLimitError", 429, LLMRateLimitError),
    ("InternalServerError", 500, LLMTransportError),
    ("OverloadedError", 529, LLMTransportError),
])
def test_api_errors_reach_the_caller_typed_and_nothing_is_cached(sdk, tmp_path, cls_name,
                                                                 status, expected):
    llm, client = claude(status_error(sdk, getattr(sdk, cls_name), status))
    with pytest.raises(expected) as exc_info:
        understand(QUESTION, llm, cache=UnderstandingCache(tmp_path))
    assert type(exc_info.value) is expected
    assert len(client.requests) == 1 and list(tmp_path.iterdir()) == []


def test_timeouts_and_connection_failures_reach_the_caller_typed(sdk):
    llm, _ = claude(connection_error(sdk, sdk.APITimeoutError))
    with pytest.raises(LLMTimeoutError):
        understand(QUESTION, llm)
    llm, _ = claude(connection_error(sdk, sdk.APIConnectionError))
    with pytest.raises(LLMTransportError, match="could not reach"):
        understand(QUESTION, llm)


def test_an_unknown_model_names_the_setting(sdk):
    llm, _ = claude(status_error(sdk, sdk.NotFoundError, 404, "model: no-such-model"))
    with pytest.raises(LLMRequestError, match="check LLM_MODEL"):
        understand(QUESTION, llm)


# --- Experiment: failures ----------------------------------------------------------------------


@pytest.mark.parametrize(("cls_name", "status", "expected"), [
    ("AuthenticationError", 401, LLMAuthenticationError),
    ("PermissionDeniedError", 403, LLMAuthenticationError),
    ("NotFoundError", 404, LLMRequestError),
    ("BadRequestError", 400, LLMRequestError),
])
def test_a_configuration_failure_stops_the_experiment(sdk, cls_name, status, expected):
    llm, client = claude(status_error(sdk, getattr(sdk, cls_name), status))
    with pytest.raises(expected):
        qe.read_questions(QUESTIONS, llm)
    assert len(client.requests) == 1  # the second question is not tried


def test_per_question_failures_fall_back_to_the_original_and_are_listed(sdk):
    llm, _ = claude(status_error(sdk, sdk.RateLimitError, 429),
                    response(reply_for(QUESTIONS[1].question)))
    readings = qe.read_questions(QUESTIONS, llm)
    assert readings["d1"] == {"status": "failed", "error": {
        "type": "LLMRateLimitError", "message": readings["d1"]["error"]["message"]}}
    assert readings["d2"]["status"] == "ok"
    out = qe.evaluate_strategies(QUESTIONS, GRADES, FakeExplorer(TABLE),
                                 strategies=["A", "B", "D"], readings=readings, controls=[])
    b, d = out["strategies"]["B"], out["strategies"]["D"]
    assert b["fallbacks"] == d["fallbacks"] == ["d1"]
    assert [v["kind"] for v in b["per_query"][0]["variants"]] == ["original"]
    assert [v["kind"] for v in d["per_query"][1]["variants"]] == ["original", "legal",
                                                                  "semantic"]


def test_a_timeout_on_one_question_is_listed_not_fatal(sdk):
    llm, _ = claude(connection_error(sdk, sdk.APITimeoutError),
                    response(reply_for(QUESTIONS[1].question)))
    readings = qe.read_questions(QUESTIONS, llm)
    assert readings["d1"]["error"]["type"] == "LLMTimeoutError"
    assert readings["d2"]["reading"].provenance.provider == "anthropic"


def test_the_demo_falls_back_and_says_so(sdk):
    llm, _ = claude(connection_error(sdk, sdk.APITimeoutError))
    explorer = FakeExplorer({demo.DEFAULT_QUESTION: [("c:37", 1)]})
    data = demo.run_demo(demo.DEFAULT_QUESTION, explorer, llm)
    assert data["understanding"] is None
    assert data["reading_source"]["kind"] == "model"
    assert data["reading_source"]["failure"]["type"] == "LLMTimeoutError"
    assert [v["kind"] for v in data["search"]["variants"]] == ["original"]
    assert "SCRIPTED" not in demo.format_demo(data)


def test_the_demo_labels_a_model_reading_by_provider(sdk):
    llm, _ = claude(response(demo.SCRIPTED_REPLY))
    explorer = FakeExplorer({demo.DEFAULT_QUESTION: [("c:37", 1)]})
    data = demo.run_demo(demo.DEFAULT_QUESTION, explorer, llm)
    assert data["reading_source"] == {"kind": "model", "provider": "anthropic",
                                      "model": "test-model"}
    assert "Reading by: anthropic/test-model" in demo.format_demo(data)


# --- Experiment: recorded build ----------------------------------------------------------------


@pytest.fixture(scope="module")
def benchmark():
    try:
        find_recorded_build()
    except ExplorerError as exc:
        pytest.skip(f"recorded build unavailable: {exc}")
    return load_benchmark(DEFAULT_BENCHMARK)


def dev_responses(benchmark):
    return [response(reply_for(q.question)) for q in qe.dev_questions(benchmark)]


def test_a_run_records_provider_model_and_prompt_and_no_credential(sdk, benchmark, tmp_path):
    llm = make_llm(load_settings(ANTHROPIC))  # a real SDK client holding KEY...
    llm._client = client = FakeClient(*dev_responses(benchmark))  # ...that sends nothing
    cache = UnderstandingCache(tmp_path / "cache")
    report = qe.run(strategies=list(qe.STRATEGIES), llm=llm, cache=cache)
    u = report["understanding"]
    assert (u["status"], u["provider"], u["model"]) == ("run", "anthropic", "test-model")
    assert (u["task"], u["prompt_version"], u["prompt_sha256"]) == (
        TASK, PROMPT_VERSION, qu.PROMPT_SHA256)
    assert u["real_model"] is True and u["source"] == "Anthropic API: real model calls"
    assert u["sdk"]["anthropic"] == sdk.__version__
    assert (u["generated_this_run"], u["requests_for_generated"], u["failures"]) == (16, 16, [])
    assert set(report["strategies"]) == {"A", "B", "C", "D"}
    assert report["checks"] == {"A_equals_rank_articles": True}
    assert report["experiment"]["split"] == "dev"
    assert len(report["representations"]) == 16
    # Only dev questions were sent; nothing anywhere holds the key.
    held_out = [q.question for q in benchmark.questions if q.split == "test"]
    sent = [r["messages"][0]["content"] for _, r in client.requests]
    assert len(sent) == 16 and not any(t in s for t in held_out for s in sent)
    stored = "".join(p.read_text(encoding="utf-8") for p in cache.directory.iterdir())
    assert KEY not in json.dumps(report) and KEY not in stored


def test_a_second_run_reads_the_cache_and_sends_nothing(sdk, benchmark, tmp_path):
    cache = UnderstandingCache(tmp_path)
    first, _ = claude(*dev_responses(benchmark))
    qe.run(strategies=["A", "B"], llm=first, cache=cache, controls=[])
    second, client = claude()
    report = qe.run(strategies=["A", "B"], llm=second, cache=cache, controls=[])
    u = report["understanding"]
    assert client.requests == []
    assert (u["from_cache"], u["generated_this_run"], u["real_model_calls_this_run"]) == (
        16, 0, False)


@pytest.fixture
def anthropic_main(sdk, monkeypatch):
    """qe.main with ANTHROPIC settings and a stand-in SDK client; yields the client setter."""
    clients = []

    def fake_make_llm(settings):
        llm = make_llm(settings)
        llm._client = clients[0]
        return llm

    monkeypatch.setattr(qe, "load_settings", lambda: load_settings(ANTHROPIC))
    monkeypatch.setattr(qe, "make_llm", fake_make_llm)
    return clients


def test_check_sends_nothing_and_prints_no_key(anthropic_main, benchmark, tmp_path, capsys):
    anthropic_main.append(client := FakeClient())
    assert qe.main(["--check", "--cache-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    u = data["understanding"]
    assert (u["status"], u["provider"], u["model"], u["source"]) == (
        "would run", "anthropic", "test-model", "Anthropic API: real model calls")
    assert (u["readings_to_generate"], u["max_requests"]) == (16, 32)
    assert data["benchmark"]["files"]["judgments.jsonl"]["sha256"]
    assert client.requests == [] and KEY not in out


def test_main_stops_on_a_rejected_key_and_writes_no_report(sdk, anthropic_main, benchmark,
                                                           tmp_path, capsys):
    anthropic_main.append(FakeClient(status_error(sdk, sdk.AuthenticationError, 401)))
    output = tmp_path / "report.json"
    assert qe.main(["--output", str(output), "--cache-dir", str(tmp_path / "c")]) == 2
    err = capsys.readouterr().err
    assert "ANTHROPIC_API_KEY" in err and "no report was written" in err
    assert KEY not in err and not output.exists()


def test_main_lists_failed_readings_and_exits_1(sdk, anthropic_main, benchmark, tmp_path,
                                                capsys):
    responses = dev_responses(benchmark)
    responses[0] = status_error(sdk, sdk.RateLimitError, 429)
    anthropic_main.append(FakeClient(*responses))
    output = tmp_path / "report.json"
    assert qe.main(["--output", str(output), "--cache-dir", str(tmp_path / "c")]) == 1
    captured = capsys.readouterr()
    first = qe.dev_questions(benchmark)[0].query_id
    assert f"1 reading(s) failed ({first})" in captured.err
    assert "readings from: ANTHROPIC API: REAL MODEL CALLS" in captured.out
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["understanding"]["failures"] == [first]
    assert report["strategies"]["B"]["fallbacks"] == [first]


def test_main_with_the_mock_provider_runs_the_baseline_only(monkeypatch, benchmark, capsys):
    monkeypatch.setattr(qe, "load_settings", lambda: load_settings({}))
    assert qe.main(["--no-cache", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["understanding"]["status"].startswith("not run: no model configured")
    assert set(report["strategies"]) == {"A"}
    assert set(report["not_run"]) == {"B", "C", "D", "E"}


def test_main_without_a_model_setting_is_an_error(monkeypatch, capsys):
    def no_model():
        return load_settings({**ANTHROPIC, "LLM_MODEL": ""})

    monkeypatch.setattr(qe, "load_settings", no_model)
    assert qe.main(["--check"]) == 2
    err = capsys.readouterr().err
    assert "LLM_MODEL must be set" in err and KEY not in err
