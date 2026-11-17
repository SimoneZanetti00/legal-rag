"""Runner for benchmark answers-v0 (data/evaluation/answers-v0/): run, save, replay, report.

    python -m src.answer_benchmark_run run --run-id ID --split dev [--mode research]
    python -m src.answer_benchmark_run rerun --from ID --run-id NEW --split dev [--mode research]
    python -m src.answer_benchmark_run report --run-id ID [--json]

`run` answers each question of the split with the real pipeline (answer_generation.answer_question)
on the configured LLM and the recorded build. Every model call (query analysis, generation, the
support check) goes through RecordingLLM, which keeps the accepted reply with SHA-256 values of
the system prompt, the user message and the schema; the messages themselves are not stored.
Each question is saved once, as runs/<run-id>/<query_id>.json (its result, AnswerResult.to_dict(),
and its model calls); a saved question is never overwritten. runs/<run-id>/run.json records the
run: id, mode, model, prompt versions, build, code version (commit, clean or dirty, and the
changed paths), settings and splits.

`rerun` answers again with ReplayLLM: a call whose task, prompt, message and schema hashes equal a
saved call gets the saved reply; any other call goes to the configured LLM. With unchanged
retrieval the query analysis is always replayed, so a change in evidence selection is measured on
the same analysis, and only generation and the support check are called again where the
evidence (and so the message) changed.

`report` scores a saved run offline and deterministically (stage_metrics, built on
answer_benchmark.score_question), in two scopes reported apart:
- all rows: every question and expectation, review status ignored. These are candidate
  expectations, not owner-reviewed: diagnostics, not results;
- owner-reviewed rows only: the questions whose record and every row are owner_reviewed or
  expert_reviewed (answer_benchmark.is_reviewed). Empty until the review sheet is applied, and
  then reported as empty, never as zeros.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from src import answer_benchmark as ab
from src.answer_generation import PROMPT_VERSION as GENERATION_PROMPT_VERSION
from src.answer_generation import Mode, answer_question
from src.config import PROJECT_ROOT, ConfigError, Settings, load_settings
from src.corpus_identity import CodeVersionError, canonical_json, detect_code_version
from src.llm import (
    JSONCheck,
    JSONResult,
    LLMClient,
    LLMConfigError,
    LLMError,
    check_schema,
    make_llm,
    validate_json,
)
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.query_analysis import PROMPT_VERSION as ANALYSIS_PROMPT_VERSION
from src.support_verification import PROMPT_VERSION as SUPPORT_PROMPT_VERSION

RUN_SCHEMA = 1
RUNS_DIR = ab.DEFAULT_BENCHMARK / "runs"
RUN_RECORD = "run.json"
REPORT_FILE = "report.json"
IN_ANSWER = ("SUPPORTED", "NOT_VERIFIED")  # answer_generation.in_answer(), on serialised claims
SCOPE_ALL = "all rows: candidate expectations, not owner-reviewed"
SCOPE_REVIEWED = "owner-reviewed rows only"
_RUN_ID = re.compile(r"[a-z0-9][a-z0-9.-]{0,63}")


class RunError(ValueError):
    """The run cannot be made or read as asked."""


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _call_key(task: str, system: str, user: str, schema: Mapping[str, Any]) -> tuple[str, ...]:
    return (task, sha256(system), sha256(user), hashlib.sha256(canonical_json(dict(schema)))
            .hexdigest())


# --- Recording and replaying model calls ---------------------------------------------------------


class RecordingLLM:
    """An LLMClient that passes each call on and keeps the accepted reply (not the messages)."""

    def __init__(self, inner: LLMClient) -> None:
        self.inner = inner
        self.provider, self.model = inner.provider, inner.model
        self.calls: list[dict[str, Any]] = []

    def complete_json(self, task: str, system: str, user: str, schema: Mapping[str, Any], *,
                      check: JSONCheck | None = None) -> JSONResult:
        result = self.inner.complete_json(task, system, user, schema, check=check)
        task_, system_sha, user_sha, schema_sha = _call_key(task, system, user, schema)
        self.calls.append({
            "task": task_, "system_sha256": system_sha, "user_sha256": user_sha,
            "schema_sha256": schema_sha, "data": result.data, "provider": result.provider,
            "model": result.model, "served_by": result.served_by, "attempts": result.attempts,
            "fallback_used": result.fallback_used, "request_ids": list(result.request_ids),
            "replayed": bool(getattr(self.inner, "last_replayed", False)),
        })
        return result


class ReplayLLM:
    """Saved replies for calls whose task and hashes match; `live` (if any) for the others."""

    def __init__(self, saved: Sequence[Mapping[str, Any]], *, live: LLMClient | None,
                 provider: str, model: str) -> None:
        self._saved = {}
        for call in saved:
            key = (call["task"], call["system_sha256"], call["user_sha256"], call["schema_sha256"])
            self._saved.setdefault(key, call)
        self.live = live
        self.provider = live.provider if live else provider
        self.model = live.model if live else model
        self.last_replayed = False
        self.replayed = self.called = 0

    def complete_json(self, task: str, system: str, user: str, schema: Mapping[str, Any], *,
                      check: JSONCheck | None = None) -> JSONResult:
        saved = self._saved.get(_call_key(task, system, user, schema))
        if saved is None:
            if self.live is None:
                raise LLMConfigError(f"no saved reply for task {task!r} with this message, and "
                                     "no live model to ask")
            self.last_replayed = False
            self.called += 1
            return self.live.complete_json(task, system, user, schema, check=check)
        check_schema(schema)
        validate_json(saved["data"], schema)
        if check is not None:
            check(saved["data"])
        self.last_replayed = True
        self.replayed += 1
        return JSONResult(data=saved["data"], task=task, provider=saved["provider"],
                          model=saved["model"], served_by=saved["served_by"],
                          attempts=saved["attempts"], fallback_used=saved["fallback_used"],
                          request_ids=tuple(saved["request_ids"]))


# --- Running -------------------------------------------------------------------------------------

Answer = Callable[[str, LLMClient], Mapping[str, Any]]  # (question, llm) -> AnswerResult.to_dict()


def check_run_id(run_id: str) -> str:
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise RunError(f"run id must be lower-case letters, digits, '.' or '-' (got {run_id!r})")
    return run_id


def code_record(repo: Path = PROJECT_ROOT) -> dict[str, Any]:
    """The code version (corpus_identity) and, when dirty, the changed paths, for the record."""
    try:
        record = detect_code_version(repo).to_record()
    except CodeVersionError as exc:
        return {"error": str(exc)}
    if record["state"] != "clean":
        status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain=v1", "-uall"],
                                capture_output=True, text=True, check=False).stdout
        record["changed_paths"] = [line for line in status.splitlines() if line.strip()]
    return record


def run_questions(benchmark: ab.Benchmark, run_dir: Path, splits: Sequence[str],
                  answer: Answer, llm_for: Callable[[str], LLMClient],
                  record: Mapping[str, Any], *, log: Callable[[str], None] = print) -> list[str]:
    """Answer every question of `splits` not yet saved in `run_dir`; return the IDs answered.

    `llm_for(query_id)` gives the client for one question; its calls are recorded. A provider
    or model error is saved as the question's error and the run goes on.
    """
    unknown = sorted(set(splits) - set(ab.SPLITS))
    if unknown:
        raise RunError(f"unknown split(s): {unknown}")
    run_dir.mkdir(parents=True, exist_ok=True)
    done = []
    for question in benchmark.questions:
        if question.split not in splits:
            continue
        path = run_dir / f"{question.query_id}.json"
        if path.exists():
            log(f"{question.query_id}: already saved, skipped")
            continue
        llm = RecordingLLM(llm_for(question.query_id))
        saved: dict[str, Any] = {"query_id": question.query_id, "question": question.question,
                                 "split": question.split}
        try:
            saved["result"] = json.loads(json.dumps(answer(question.question, llm)))
        except LLMError as exc:
            saved["error"] = f"{type(exc).__name__}: {exc}"
        saved["llm_calls"] = llm.calls
        path.write_text(json.dumps(saved, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
        state = saved.get("error") or saved["result"]["outcome"]
        log(f"{question.query_id}: {state} ({len(llm.calls)} model call(s))")
        done.append(question.query_id)
    _update_record(run_dir, record, splits)
    return done


def _update_record(run_dir: Path, record: Mapping[str, Any], splits: Sequence[str]) -> None:
    path = run_dir / RUN_RECORD
    current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else dict(record)
    current["invocations"] = current.get("invocations", []) + [
        {"splits": list(splits), "at": datetime.datetime.now().astimezone().isoformat(
            timespec="seconds"), "code": record["code"]}]
    path.write_text(json.dumps(current, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def run_record(run_id: str, *, mode: Mode, settings: Settings, build_id: str,
               replay_of: str | None = None) -> dict[str, Any]:
    return {
        "schema": RUN_SCHEMA, "kind": "answers-v0-run", "run_id": run_id, "mode": mode.value,
        "replay_of": replay_of, "build_id": build_id, "code": code_record(),
        "provider": settings.llm_provider, "model": settings.llm_model,
        "prompt_versions": {"query_analysis": ANALYSIS_PROMPT_VERSION,
                            "answer_generation": GENERATION_PROMPT_VERSION,
                            "claim_verification": SUPPORT_PROMPT_VERSION},
        "settings": {"final_evidence_count": settings.final_evidence_count,
                     "context_token_budget": settings.context_token_budget,
                     "semantic_verification": settings.semantic_verification,
                     "max_generation_retries": settings.max_generation_retries},
    }


# --- Stage metrics (deterministic) ---------------------------------------------------------------


def load_run(run_dir: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """(run record, {query_id: saved question}) of a saved run."""
    path = run_dir / RUN_RECORD
    if not path.is_file():
        raise RunError(f"{run_dir}: no {RUN_RECORD}; not a saved run")
    record = json.loads(path.read_text(encoding="utf-8"))
    saved = {p.stem: json.loads(p.read_text(encoding="utf-8"))
             for p in sorted(run_dir.glob("a[0-9][0-9].json"))}
    return record, saved


def _article(provision_id: str) -> tuple[str, str]:
    """(instrument, label) of an article ID such as "eu-reg-2016-679@.../body/article:33"."""
    return provision_id.split("@", 1)[0], provision_id.rsplit("article:", 1)[-1]


def stage_metrics(question: ab.Question, rows: Sequence[ab.Expectation],
                  result: Mapping[str, Any], article_text: ab.ArticleText) -> dict[str, Any]:
    """One question's stage metrics: core recall in candidates, in final evidence (with the reason
    for each core row missing there) and in the citations of the main answer; claims removed by
    reason; claims held apart; outcome agreement."""
    main = dict(result, claims=[c for c in result.get("claims", ())
                                if c["verification"] in IN_ANSWER])
    scored = ab.score_question(question, rows, main, article_text)
    evidence = result.get("evidence") or {"items": [], "dropped": []}
    dropped = {_article(d["provision_id"]): d["reason"] for d in evidence["dropped"]}
    in_items = {(i["instrument_id"], i["label"]) for i in evidence["items"]}
    missing = []
    core_rows = [r for r in rows if r.role == "core"]
    for row, entry in zip(core_rows, scored["core"]["rows"]):
        if entry["evidence"]:
            continue
        article = (row.instrument, row.article)
        reason = ("unit_not_located" if not entry["unit_found"]
                  else f"dropped_{dropped[article]}" if article in dropped
                  else "unit_outside_excerpt" if article in in_items
                  else "not_a_candidate")
        missing.append({"provision": entry["provision"], "reason": reason})
    removed = Counter(reason.split(":", 1)[0] for r in result.get("rejected_claims", ())
                      for reason in r["reasons"])
    claims = result.get("claims", ())
    return {
        "query_id": question.query_id, "split": question.split,
        "expected_outcome": question.expected_outcome, "outcome": scored["outcome"],
        "outcome_match": scored["outcome_match"], "abstention_reason": scored["abstention_reason"],
        "reason_match": scored["reason_match"],
        "time_sensitive": question.time_sensitive is not None,
        "core_rows": len(core_rows),
        "core_candidate_recall": scored["core"]["candidate_recall"],
        "core_evidence_recall": scored["core"]["evidence_recall"],
        "core_citation_recall": scored["core"]["citation_recall"],
        "missing_from_evidence": missing,
        "claims_in_answer": sum(c["verification"] in IN_ANSWER for c in claims),
        "claims_held_apart": sum(c["verification"] not in IN_ANSWER for c in claims),
        "claims_removed": dict(sorted(removed.items())),
        "evidence_items": len(evidence["items"]), "dropped_candidates": len(evidence["dropped"]),
        "unlisted_citations": scored["unlisted_citations"],
    }


def aggregate(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    def mean(key: str) -> float | None:
        values = [e[key] for e in entries if e[key] is not None]
        return sum(values) / len(values) if values else None

    removed: Counter = Counter()
    missing: Counter = Counter()
    for e in entries:
        removed.update(e["claims_removed"])
        missing.update(m["reason"] for m in e["missing_from_evidence"])
    return {
        "questions": len(entries),
        "core_candidate_recall": mean("core_candidate_recall"),
        "core_evidence_recall": mean("core_evidence_recall"),
        "core_citation_recall": mean("core_citation_recall"),
        "outcome_matches": sum(e["outcome_match"] for e in entries),
        "abstained": sum(e["outcome"] == "abstain" for e in entries),
        "claims_in_answer": sum(e["claims_in_answer"] for e in entries),
        "claims_held_apart": sum(e["claims_held_apart"] for e in entries),
        "claims_removed": dict(sorted(removed.items())),
        "missing_from_evidence": dict(sorted(missing.items())),
    }


def report(benchmark: ab.Benchmark, run_dir: Path, article_text: ab.ArticleText) -> dict[str, Any]:
    """Both scopes of a saved run. Deterministic: the same saved run gives the same report."""
    record, saved = load_run(run_dir)
    entries, errors = [], {}
    for question in benchmark.questions:
        item = saved.get(question.query_id)
        if item is None:
            continue
        if "error" in item:
            errors[question.query_id] = item["error"]
            continue
        entries.append(stage_metrics(question, benchmark.rows(question.query_id), item["result"],
                                     article_text))
    reviewed = {q.query_id for q in benchmark.questions
                if ab.is_reviewed(q.provenance)
                and all(ab.is_reviewed(r.provenance) for r in benchmark.rows(q.query_id))}
    reviewed_entries = [e for e in entries if e["query_id"] in reviewed]
    scopes = {SCOPE_ALL: {"per_question": entries, "aggregate": aggregate(entries)}}
    scopes[SCOPE_REVIEWED] = (
        {"per_question": reviewed_entries, "aggregate": aggregate(reviewed_entries)}
        if reviewed_entries else
        {"empty": "no question has its record and every row owner_reviewed or expert_reviewed; "
                  "nothing is scored in this scope"})
    return {"run": {k: record.get(k) for k in ("run_id", "mode", "model", "prompt_versions",
                                                "build_id", "replay_of", "settings")},
            "benchmark": {"version": benchmark.version, "files": benchmark.files},
            "errors": errors, "scopes": scopes}


def _pct(value: float | None) -> str:
    return "  —" if value is None else f"{round(100 * value):3d}"


def format_report(data: Mapping[str, Any]) -> str:
    run = data["run"]
    pv = run["prompt_versions"]
    lines = [f"run {run['run_id']} · mode {run['mode']} · model {run['model']} · build "
             f"{run['build_id']}",
             f"prompts {pv['query_analysis']}, {pv['answer_generation']}, "
             f"{pv['claim_verification']} · evidence {run['settings']['final_evidence_count']} "
             f"items / {run['settings']['context_token_budget']} tokens"]
    for scope, body in data["scopes"].items():
        lines += ["", f"== {scope}"]
        if "empty" in body:
            lines.append(f"   empty: {body['empty']}")
            continue
        lines.append("id  split outcome (expected)            cand evid cite  in/held  removed; "
                     "missing from evidence")
        for e in body["per_question"]:
            mark = "=" if e["outcome_match"] else "≠"
            outcome = f"{e['outcome']}{mark}{e['expected_outcome']}"
            removed = ",".join(f"{k}×{v}" for k, v in e["claims_removed"].items()) or "-"
            missing = ",".join(f"{m['provision']}:{m['reason']}"
                               for m in e["missing_from_evidence"]) or "-"
            lines.append(f"{e['query_id']} {e['split']:<5} {outcome:<34} "
                         f"{_pct(e['core_candidate_recall'])} {_pct(e['core_evidence_recall'])} "
                         f"{_pct(e['core_citation_recall'])}  {e['claims_in_answer']:>2}/"
                         f"{e['claims_held_apart']:<2}    {removed}; {missing}"
                         + (" [time-sensitive]" if e["time_sensitive"] else ""))
        a = body["aggregate"]
        lines.append(f"ALL {a['questions']} questions: core recall cand {_pct(a['core_candidate_recall'])}% "
                     f"evid {_pct(a['core_evidence_recall'])}% cite {_pct(a['core_citation_recall'])}%; "
                     f"outcome {a['outcome_matches']}/{a['questions']}; abstained {a['abstained']}; "
                     f"claims in answer {a['claims_in_answer']}, held apart {a['claims_held_apart']}; "
                     f"removed {a['claims_removed'] or '{}'}; missing {a['missing_from_evidence'] or '{}'}")
    if data["errors"]:
        lines += ["", "errors: " + "; ".join(f"{k}: {v}" for k, v in data["errors"].items())]
    return "\n".join(lines)


def explorer_article_text(explorer: ProvisionExplorer) -> ab.ArticleText:
    def text(instrument: str, article: str) -> str:
        return "".join(p["text"] for p in explorer.lookup(instrument, article)["provision"]["text"])

    return text


# --- Command line --------------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m src.answer_benchmark_run",
                                     description="Run, replay and report benchmark answers-v0.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "rerun"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--run-id", required=True)
        cmd.add_argument("--split", action="append", choices=ab.SPLITS, required=True)
        cmd.add_argument("--mode", choices=[m.value for m in Mode], default=Mode.RESEARCH.value)
        if name == "rerun":
            cmd.add_argument("--from", dest="source", required=True,
                             help="the saved run whose replies are replayed")
            cmd.add_argument("--offline", action="store_true",
                             help="replay only: no model is called, and a call with no saved "
                                  "reply fails that question")
    rep = sub.add_parser("report")
    rep.add_argument("--run-id", required=True)
    rep.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        run_dir = RUNS_DIR / check_run_id(args.run_id)
        benchmark = ab.load_benchmark()
        explorer = ProvisionExplorer.open(find_recorded_build())
        if explorer.identity()["build_id"] != benchmark.build_id:
            raise RunError("the recorded build is not the one the benchmark names")
        if args.command == "report":
            data = report(benchmark, run_dir, explorer_article_text(explorer))
            (run_dir / REPORT_FILE).write_text(
                json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                encoding="utf-8", newline="\n")
            print(json.dumps(data, ensure_ascii=False, indent=1) if args.json
                  else format_report(data))
            return 0
        settings = load_settings()
        mode = Mode(args.mode)
        offline = args.command == "rerun" and args.offline
        live = None if offline else make_llm(settings)
        if live is not None and live.provider == "mock":
            raise RunError("the runner needs a real LLM provider (LLM_PROVIDER)")
        replay_of = None
        if args.command == "rerun":
            replay_of = check_run_id(args.source)
            source_record, source = load_run(RUNS_DIR / replay_of)
            provider = live.provider if live else source_record["provider"]
            model = live.model if live else source_record["model"]

            def llm_for(query_id: str) -> LLMClient:
                calls = source.get(query_id, {}).get("llm_calls", [])
                return ReplayLLM(calls, live=live, provider=provider, model=model)
        else:
            def llm_for(query_id: str) -> LLMClient:
                return live
        record = run_record(args.run_id, mode=mode, settings=settings,
                            build_id=explorer.identity()["build_id"], replay_of=replay_of)
        record["offline"] = offline  # True: every reply is a saved one; no model was called

        def answer(question: str, llm: LLMClient) -> Mapping[str, Any]:
            return answer_question(question, llm, explorer, settings=settings, mode=mode).to_dict()

        run_questions(benchmark, run_dir, args.split, answer, llm_for, record)
        return 0
    except (RunError, ab.BenchmarkError, ExplorerError, ConfigError, LLMConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
