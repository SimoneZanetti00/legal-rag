"""Static replay of a saved run (src/web_replay.py): offline, no model and no server."""

import json
import re

import pytest

import src.demo as demo
import src.web_replay as replay
from src.answer_generation import display_qualifications
from src.provision_explorer import ExplorerError, find_recorded_build
from src.web_demo import STATIC_DIR
from tests.test_web_demo import INFO, SECRET

APP_JS = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
INDEX = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
STATUS = {"E1": {"category": "unofficial_transcription", "human_review": "pending"}}


@pytest.fixture(scope="module")
def synthetic_result():
    return demo.synthetic(lambda line: None).result


def save_run(runs_dir, run_id, results, *, at="2026-11-17T12:00:00+01:00", **extra):
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    run = {"schema": 1, "kind": "answers-v0-run", "run_id": run_id, "mode": "research",
           "build_id": "build-test", "provider": "anthropic", "model": "test-model",
           "prompt_versions": {"answer_generation": "answer-generation-v5"},
           "settings": {"semantic_verification": True}, "invocations": [{"at": at}], **extra}
    (run_dir / "run.json").write_text(json.dumps(run), encoding="utf-8")
    for qid, result in results.items():
        record = {"query_id": qid, "question": result.question, "split": "dev",
                  "result": result.to_dict(), "rendered": "…",
                  "llm_calls": [{"reply": SECRET, "system_sha256": "0" * 64}]}
        (run_dir / f"{qid}.json").write_text(json.dumps(record), encoding="utf-8")
    return run_dir


def test_the_page_in_replay_mode_names_the_replay_and_says_nothing_is_sent():
    page = replay.replay_page(INDEX)
    assert '<html lang="en" data-replay="replay.json">' in page
    assert 'href="app.css"' in page and 'src="app.js"' in page and '"/app.' not in page
    assert f'<meta http-equiv="Content-Security-Policy" content="{replay.REPLAY_CSP}">' in page
    assert replay.REPLAY_FOOTER in page and replay.LIVE_FOOTER not in page
    assert "/api/" not in page and "local server" not in page.lower()
    assert replay.REPLAY_LABEL == ("Replay of saved answers generated on {date} with {model}. "
                                   "No live model calls.")


def test_a_changed_page_is_refused_rather_than_exported_half_converted():
    with pytest.raises(replay.ReplayError, match="does not occur exactly once"):
        replay.replay_page(INDEX.replace(replay.LIVE_FOOTER, "Something else."))


def test_the_replay_holds_each_saved_answer_as_the_server_would_return_it(tmp_path,
                                                                         synthetic_result):
    run_dir = save_run(tmp_path, "run-a", {"a01": synthetic_result, "a02": synthetic_result})
    data = replay.replay_data(run_dir, ["a02", "a01"], describe=lambda result: STATUS, info=INFO)
    assert data["replay"] == {
        "label": "Replay of saved answers generated on 2026-11-17 with test-model. "
                 "No live model calls.",
        "generated_on": "2026-11-17", "provider": "anthropic", "model": "test-model",
        "mode": "research", "run_id": "run-a", "build_id": "build-test",
        "prompt_versions": {"answer_generation": "answer-generation-v5"},
        "live_url": "https://legal-rag-live.onrender.com"}
    assert data["info"] == INFO
    assert data["questions"] == [{"id": "a02", "question": synthetic_result.question},
                                 {"id": "a01", "question": synthetic_result.question}]
    assert data["answers"]["a01"] == {
        **synthetic_result.to_dict(), "source_status": STATUS,
        "display_qualifications": list(display_qualifications(synthetic_result))}
    text = json.dumps(data)
    assert SECRET not in text and "llm_calls" not in text and "system_sha256" not in text


def test_a_run_without_every_question_is_refused(tmp_path, synthetic_result):
    run_dir = save_run(tmp_path, "run-a", {"a01": synthetic_result})
    with pytest.raises(replay.ReplayError, match="no saved answer for a02"):
        replay.replay_data(run_dir, ["a01", "a02"], describe=lambda r: {}, info=INFO)


def test_the_default_run_is_the_latest_with_every_question(tmp_path, synthetic_result):
    save_run(tmp_path, "old-complete", {"a01": synthetic_result, "a02": synthetic_result},
             at="2026-11-16T09:00:00+01:00")
    save_run(tmp_path, "new-complete", {"a01": synthetic_result, "a02": synthetic_result},
             at="2026-11-17T09:00:00+01:00")
    save_run(tmp_path, "newest-partial", {"a01": synthetic_result},
             at="2026-11-17T18:00:00+01:00")
    assert replay.latest_run(tmp_path, ["a01", "a02"]).name == "new-complete"
    with pytest.raises(replay.ReplayError, match="no saved run"):
        replay.latest_run(tmp_path, ["a03"])


def test_a_rescored_run_is_dated_by_the_run_whose_answers_it_reuses(tmp_path, synthetic_result):
    save_run(tmp_path, "live", {"a01": synthetic_result}, at="2026-11-16T09:00:00+01:00")
    rescored = save_run(tmp_path, "rescored", {"a01": synthetic_result},
                        at="2026-11-18T09:00:00+01:00", rescore_of="live")
    offline = save_run(tmp_path, "offline", {"a01": synthetic_result},
                       at="2026-11-19T09:00:00+01:00", replay_of="live", offline=True)
    for run_dir in (rescored, offline):
        data = replay.replay_data(run_dir, ["a01"], describe=lambda r: {}, info=INFO)
        assert data["replay"]["generated_on"] == "2026-11-16"


def test_a_partly_replayed_run_is_dated_by_both_runs(tmp_path, synthetic_result):
    save_run(tmp_path, "live", {"a01": synthetic_result}, at="2026-11-16T09:00:00+01:00")
    rerun = save_run(tmp_path, "rerun", {"a01": synthetic_result},
                     at="2026-11-24T09:00:00+01:00", replay_of="live", offline=False)
    data = replay.replay_data(rerun, ["a01"], describe=lambda r: {}, info=INFO)
    assert data["replay"]["generated_on"] == "2026-11-16 and 2026-11-24"
    assert data["replay"]["label"].startswith(
        "Replay of saved answers generated on 2026-11-16 and 2026-11-24 with test-model.")


def test_the_site_is_the_page_its_assets_the_replay_and_a_space_card(tmp_path, synthetic_result):
    data = replay.replay_data(save_run(tmp_path, "run-a", {"a01": synthetic_result}),
                              ["a01"], describe=lambda r: {}, info=INFO)
    out = tmp_path / "site"
    written = replay.write_site(out, data)
    assert sorted(p.name for p in written) == sorted(p.name for p in out.iterdir()) == [
        "README.md", "app.css", "app.js", "index.html", "replay.json"]
    assert (out / "app.js").read_text(encoding="utf-8") == APP_JS
    assert json.loads((out / "replay.json").read_text(encoding="utf-8")) == data
    card = (out / "README.md").read_text(encoding="utf-8")
    assert "sdk: static" in card and "app_file: index.html" in card


def test_the_dev_questions_are_a01_to_a12():
    assert replay.dev_questions() == [f"a{n:02d}" for n in range(1, 13)]


# --- The page ----------------------------------------------------------------------------------


def used(name):
    return set(re.findall(rf"(?<![\w.]){name}\.([a-z_]+)\b", APP_JS))


def test_the_page_reads_only_fields_the_replay_provides(tmp_path, synthetic_result):
    data = replay.replay_data(save_run(tmp_path, "run-a", {"a01": synthetic_result}),
                              ["a01"], describe=lambda r: {}, info=INFO)
    assert used("saved") <= set(data)
    assert used("replay") <= set(data["replay"])
    assert used("question") <= set(data["questions"][0])
    assert used("pick") <= {"id", "note"}


def test_the_landing_page_features_four_questions(tmp_path, synthetic_result):
    ids = ["a01", "a06", "a09", "a10", "a12"]
    data = replay.replay_data(save_run(tmp_path, "run-a", {q: synthetic_result for q in ids}),
                              ids, describe=lambda r: {}, info=INFO)
    assert data["featured"] == [
        {"id": "a12", "note": "Answers a false premise with the text in force (72 hours) and flags the 96-hour proposal"},
        {"id": "a10", "note": "Links the GDPR to the Italian Code (Garante)"},
        {"id": "a09", "note": "Abstains outside its scope"},
        {"id": "a06", "note": "Holds apart a statement its sources do not fully support (portability)"}]
    assert 'el("summary", {}, `More questions (${others.length})`)' in APP_JS
    assert "select" not in APP_JS[APP_JS.index("const REPLAY_FILE"):]  # no dropdown


def test_the_replay_links_to_the_live_demo_and_says_it_may_need_to_wake_up():
    card = APP_JS[APP_JS.index('class: "replay-label"'):APP_JS.index('"Choose a question"')]
    assert 'el("a", { href: replay.live_url, target: "_blank", rel: "noopener" }' in card
    assert "Ask your own question: live demo (limited)" in card
    assert "may take about a minute to wake up" in card
    assert replay.LIVE_URL == "https://legal-rag-live.onrender.com"


def test_in_replay_mode_the_page_asks_nothing():
    wiring = APP_JS[APP_JS.index('document.addEventListener("DOMContentLoaded"'):]
    replay_branch = wiring[:wiring.index("loadReplay();\n    return;\n  }")]
    assert "if (REPLAY_FILE) {" in replay_branch  # it returns before anything is wired
    assert "addEventListener(" not in replay_branch.split("if (REPLAY_FILE) {")[1]
    assert wiring.index("loadReplay();") < wiring.index("loadHealth();")
    replay_code = APP_JS[APP_JS.index("const REPLAY_FILE"):APP_JS.index("// --- Wiring")]
    assert "/api/" not in replay_code and "renderResult(saved.answers[id])" in replay_code


# --- The recorded build ------------------------------------------------------------------------


def test_the_export_of_a_saved_run_on_the_recorded_build(tmp_path):
    try:
        find_recorded_build()
    except ExplorerError as exc:
        pytest.skip(f"recorded build unavailable: {exc}")
    run_dir = replay.RUNS_DIR / "2026-11-17-research-t9b"
    _, written = replay.export(run_dir, ["a01", "a10"], tmp_path)
    data = json.loads((tmp_path / replay.REPLAY_FILE).read_text(encoding="utf-8"))
    assert len(written) == 5 and [q["id"] for q in data["questions"]] == ["a01", "a10"]
    for answer in data["answers"].values():
        ids = {item["evidence_id"] for item in answer["evidence"]["items"]}
        assert set(answer["source_status"]) == ids
    assert data["answers"]["a10"]["display_qualifications"][0].startswith(
        "MODALITÀ DIMOSTRATIVA DI RICERCA")
    assert data["info"]["build_id"] == data["replay"]["build_id"]


def test_the_committed_replay_matches_the_page_and_the_final_run():
    site = replay.ROOT / "demo" / "replay"
    if not site.is_dir():
        pytest.skip("no committed replay")
    assert (site / "app.js").read_text(encoding="utf-8") == APP_JS
    assert (site / "app.css").read_text(encoding="utf-8") == (
        STATIC_DIR / "app.css").read_text(encoding="utf-8")
    assert (site / "index.html").read_text(encoding="utf-8") == replay.replay_page(INDEX)
    data = json.loads((site / replay.REPLAY_FILE).read_text(encoding="utf-8"))
    assert data["replay"]["run_id"] == "2026-11-26-direct-answer"
    assert [q["id"] for q in data["questions"]] == replay.dev_questions()
    run_dir = replay.RUNS_DIR / data["replay"]["run_id"]
    for qid, answer in data["answers"].items():
        saved = json.loads((run_dir / f"{qid}.json").read_text(encoding="utf-8"))["result"]
        assert {k: v for k, v in answer.items()
                if k not in ("source_status", "display_qualifications")} == saved
