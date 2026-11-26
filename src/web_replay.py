"""Static replay of a saved benchmark run, for hosting the web page without a model:
`python -m src.web_replay`.

    python -m src.web_replay [--run RUN_DIR] [--question a01 ...] [--out dist/replay]
                             [--build-dir DIR]

Writes a static site to --out: the page of the local demo (src/web_static/) in replay mode, and
replay.json with the saved answers of one run of the answers-v0 benchmark
(src/answer_benchmark_run.py). A visitor chooses one of the run's questions and the page shows its
saved answer, rendered by the same code that renders a live one. Nothing can be asked: there is no
server, no model call and no API key, and any static host can serve the folder.

The questions: the dev split of the benchmark, or --question. The run: --run, or the most recent
saved run that has every one of those questions. The page's label names the date the answers were
generated (a re-score or an offline re-run takes it from the run it re-uses) and the model.

replay.json holds, for each question, AnswerResult.to_dict() as the run saved it, plus what the
live server adds to it: "source_status", from the corpus build the run used (the export refuses
another build), and "display_qualifications". It holds no prompt and no raw model reply.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from src.answer_generation import corpus_preflight, qualifications_in
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.provisions import ProvisionError
from src.source_status import evidence_status
from src.web_demo import STATIC_DIR, page_info

ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_DIR = ROOT / "data" / "evaluation" / "answers-v0"
RUNS_DIR = BENCHMARK_DIR / "runs"
QUESTIONS_FILE = BENCHMARK_DIR / "questions.jsonl"
DEFAULT_OUT = ROOT / "dist" / "replay"
REPLAY_FILE = "replay.json"

REPLAY_LABEL = ("Replay of saved answers generated on {date} with {model}. "
                "No live model calls.")
# The public live demo (render.yaml), linked from the top of the replay page.
LIVE_URL = "https://legal-rag-live.onrender.com"
# The questions the landing page features, in order, with one line on what each shows; the
# other questions are listed under "More questions".
FEATURED = (("a12", "Answers a false premise with the text in force (72 hours) and flags the 96-hour proposal"),
            ("a10", "Links the GDPR to the Italian Code (Garante)"),
            ("a09", "Abstains outside its scope"),
            ("a06", "Says honestly what it could not establish"))
LIVE_FOOTER = ("Local server. Questions and evidence are sent to Anthropic's API for analysis, "
               "generation and verification.")
REPLAY_FOOTER = ("Static replay: nothing you do on this page is sent to a server or a model. The "
                 "answers were generated earlier with Anthropic's API and saved.")
# A static host sends no security headers of its own; the page carries the policy the local
# server sends (web_demo.SECURITY_HEADERS) apart from frame-ancestors, which a <meta> cannot set.
REPLAY_CSP = "default-src 'self'; base-uri 'none'; form-action 'none'; object-src 'none'"
# The Hugging Face Space card: a static Space serves index.html from the repository root.
SPACE_README = """\
---
title: Legal RAG (replay)
emoji: ⚖️
colorFrom: blue
colorTo: gray
sdk: static
app_file: index.html
pinned: false
---

Replay of saved answers of an evidence-grounded legal research prototype (GDPR and the Italian
Privacy Code). No live model calls. Experimental prototype; not legal advice.
"""

Describe = Callable[[Mapping[str, Any]], dict[str, Any]]  # saved result -> source status


class ReplayError(Exception):
    """The run, the questions or the build cannot make a replay."""


def dev_questions(path: Path = QUESTIONS_FILE) -> list[str]:
    """The query IDs of the benchmark's dev split, in file order."""
    with path.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    return [row["query_id"] for row in rows if row["split"] == "dev"]


def load_run(run_dir: Path) -> dict[str, Any]:
    try:
        return json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReplayError(f"{run_dir} is not a saved run (no readable run.json)") from exc


def missing(run_dir: Path, ids: Sequence[str]) -> list[str]:
    return [qid for qid in ids if not (run_dir / f"{qid}.json").is_file()]


def latest_run(runs_dir: Path, ids: Sequence[str]) -> Path:
    """The saved run with every one of `ids` whose latest invocation is the most recent."""
    complete = []
    for run_dir in sorted(p for p in runs_dir.iterdir() if (p / "run.json").is_file()):
        if not missing(run_dir, ids):
            invocations = load_run(run_dir).get("invocations") or [{"at": ""}]
            complete.append((max(i["at"] for i in invocations), run_dir.name, run_dir))
    if not complete:
        raise ReplayError(f"no saved run in {runs_dir} has every question ({', '.join(ids)})")
    return max(complete)[2]


def generation_dates(run_dir: Path, run: Mapping[str, Any]) -> list[str]:
    """The dates the run's answers were generated: its invocations' dates; for a re-score or an
    offline re-run, those of the run whose model replies it re-uses; for a re-run that replayed
    some replies and asked the model for others, both."""
    own = sorted({i["at"][:10] for i in run.get("invocations", ())})
    source = run.get("rescore_of") or run.get("replay_of")
    if not source:
        return own
    source_dir = run_dir.parent / source
    earlier = generation_dates(source_dir, load_run(source_dir))
    if run.get("rescore_of") or run.get("offline"):
        return earlier
    return sorted(set(earlier) | set(own))


def replay_data(run_dir: Path, ids: Sequence[str], *, describe: Describe,
                info: Mapping[str, Any]) -> dict[str, Any]:
    """The content of replay.json: the label's facts, the page's info (as /api/health reports
    it), the questions and, for each, the saved result as /api/ask would have returned it."""
    run = load_run(run_dir)
    absent = missing(run_dir, ids)
    if absent:
        raise ReplayError(f"run {run_dir.name} has no saved answer for {', '.join(absent)}")
    dates = generation_dates(run_dir, run)
    if not dates:
        raise ReplayError(f"run {run_dir.name} records no date")
    date = (dates[0] if len(dates) == 1 else f"{dates[0]} and {dates[1]}" if len(dates) == 2
            else f"{dates[0]} to {dates[-1]}")
    questions, answers = [], {}
    for qid in ids:
        record = json.loads((run_dir / f"{qid}.json").read_text(encoding="utf-8"))
        result = record["result"]
        language = (result.get("analysis") or {}).get("language")
        answers[qid] = {**result, "source_status": describe(result),
                        "display_qualifications": list(
                            qualifications_in(result["qualifications"], language))}
        questions.append({"id": qid, "question": record["question"]})
    replay = {
        "label": REPLAY_LABEL.format(date=date, model=run["model"]),
        "generated_on": date, "provider": run["provider"], "model": run["model"],
        "mode": run["mode"], "run_id": run["run_id"], "build_id": run["build_id"],
        "prompt_versions": run["prompt_versions"], "live_url": LIVE_URL,
    }
    featured = [{"id": qid, "note": note} for qid, note in FEATURED if qid in ids]
    return {"replay": replay, "info": dict(info), "questions": questions, "featured": featured,
            "answers": answers}


def replay_page(index_html: str) -> str:
    """The local demo's page in replay mode: assets by relative path (so the folder can be served
    under any path), the security policy, and what the page says about where data goes."""
    replacements = (
        ('<html lang="en">', '<html lang="en" data-replay="replay.json">'),
        ('<meta charset="utf-8">',
         f'<meta charset="utf-8">\n  <meta http-equiv="Content-Security-Policy" '
         f'content="{REPLAY_CSP}">'),
        ('href="/app.css"', 'href="app.css"'),
        ('src="/app.js"', 'src="app.js"'),
        ("Connecting to the local server…", "Loading the saved answers…"),
        (LIVE_FOOTER, REPLAY_FOOTER),
    )
    for old, new in replacements:
        if index_html.count(old) != 1:
            raise ReplayError(f"the page has changed: {old!r} does not occur exactly once")
        index_html = index_html.replace(old, new)
    return index_html


def write_site(out_dir: Path, data: Mapping[str, Any], static_dir: Path = STATIC_DIR) -> list[Path]:
    """Write the static site to `out_dir` (created if needed; other files there are left alone)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    page = replay_page((static_dir / "index.html").read_text(encoding="utf-8"))
    written = [out_dir / "index.html", out_dir / "app.css", out_dir / "app.js",
               out_dir / REPLAY_FILE, out_dir / "README.md"]
    written[0].write_text(page, encoding="utf-8", newline="\n")
    shutil.copyfile(static_dir / "app.css", written[1])
    shutil.copyfile(static_dir / "app.js", written[2])
    written[3].write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                          encoding="utf-8", newline="\n")
    written[4].write_text(SPACE_README, encoding="utf-8", newline="\n")
    return written


def build_describe(explorer: ProvisionExplorer) -> Describe:
    """source_status for a saved result, as web_demo's describe gives it for a live one."""
    def describe(result: Mapping[str, Any]) -> dict[str, Any]:
        evidence = result.get("evidence")
        if not evidence:
            return {}
        items = [SimpleNamespace(**item) for item in evidence["items"]]
        return evidence_status(SimpleNamespace(items=items), explorer.store)  # type: ignore[arg-type]
    return describe


def export(run_dir: Path | None, ids: Sequence[str], out_dir: Path, *,
           build_dir: Path | None = None, runs_dir: Path = RUNS_DIR) -> tuple[Path, list[Path]]:
    run_dir = run_dir or latest_run(runs_dir, ids)
    run = load_run(run_dir)
    explorer = ProvisionExplorer.open(build_dir or find_recorded_build())
    preflight = corpus_preflight(explorer)
    if preflight.build_id != run["build_id"]:
        raise ReplayError(f"run {run_dir.name} used {run['build_id']}, not {preflight.build_id}; "
                          "the sources' status would come from another build")
    info = page_info(preflight, provider=run["provider"], model=run["model"],
                     semantic_verification=run["settings"]["semantic_verification"])
    data = replay_data(run_dir, ids, describe=build_describe(explorer), info=info)
    return run_dir, write_site(out_dir, data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.web_replay",
        description="Export a saved benchmark run as a static replay of the web page.")
    parser.add_argument("--run", type=Path,
                        help="saved run directory (default: the most recent run with every "
                             "question)")
    parser.add_argument("--question", action="append", metavar="ID",
                        help="a question to include (repeatable; default: the dev split)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help=f"output directory (default: {DEFAULT_OUT.relative_to(ROOT)})")
    parser.add_argument("--build-dir", type=Path,
                        help="corpus build (default: the recorded build in data/processed/builds/)")
    args = parser.parse_args(argv)
    ids = args.question or dev_questions()
    try:
        run_dir, written = export(args.run, ids, args.out, build_dir=args.build_dir)
    except (ReplayError, ExplorerError, ProvisionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"replay of run {run_dir.name}: {len(ids)} question(s) -> {args.out}")
    for path in written:
        print(f"  {path.name} ({path.stat().st_size:,} bytes)")
    print(f"preview: python -m http.server --bind 127.0.0.1 --directory {args.out} 8001")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
