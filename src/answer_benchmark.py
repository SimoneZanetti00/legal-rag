"""Benchmark v0 for end-to-end answers (data/evaluation/answers-v0/): format, checks and
deterministic metrics. It scores results it is given; it does not run the pipeline or call a
model (no runner exists yet).

Files: benchmark.json (the manifest), questions.jsonl, expectations.jsonl, and REVIEW_SHEET.md
(the human-readable sheet, kept in step with the two JSONL files by tests).

An expectation names a provision a correct answer rests on: an instrument, an article label as
printed, and optionally a unit inside it ({"paragraph", "point", "letter"}, any of them null).
Its role is "core" (a complete answer must rest on it), "supporting" (useful, not required) or
"must_not_cite".

Metrics, per expected row, reported apart for core and supporting rows:
- candidate: the row's article is among the recorded candidates of the result (the evidence
  items and the candidates dropped by the evidence limits). Search results below the per-query
  cutoff are not recorded by the pipeline, so a miss cannot tell "not retrieved" from "ranked
  too low";
- evidence: the row's unit text is inside an evidence item sent to the model (a whole-article
  row: the article is in the evidence; whether whole or an excerpt is reported);
- cited: a surviving claim quotes text inside the row's unit (a whole-article row: anywhere in
  the article). Quotations are compared in the shared normalised form (src/text_normalization).
Per question: the exact outcome match, whether the system abstained, the reason match for an
expected abstention, and the citations no row lists (a diagnostic, not a penalty).

Eligibility: a question is scored only when it and every one of its rows are reviewed
(owner_reviewed or expert_reviewed); otherwise it is listed as excluded and gets no metrics,
unless include_unreviewed is asked for, which reports them apart, labelled, and never in the
summary. A time-sensitive question is reported apart unless someone re-verified it (verified_on)
within `freshness_days` of `today`: DEFAULT_FRESHNESS_DAYS unless overridden, and None means no
window, so every time-sensitive question is apart. An unverified one is apart under any window.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.answer_generation import (
    ANALYSIS_FAILED,
    GENERATION_FAILED,
    MODEL_ABSTAINED,
    MODEL_REFUSED,
    NEEDS_CLARIFICATION,
    NO_CITABLE_EVIDENCE,
    NO_EVIDENCE,
    NO_SUPPORTED_CLAIMS,
    OUT_OF_SCOPE,
    Outcome,
)
from src.config import PROJECT_ROOT
from src.provision_eval import Provenance
from src.query_analysis import CORPUS_INSTRUMENTS
from src.text_normalization import normalise

SCHEMA_VERSION = 1
KIND = "end_to_end"
DEFAULT_FRESHNESS_DAYS = 30  # days since a time-sensitive question was re-verified
DEFAULT_BENCHMARK = PROJECT_ROOT / "data" / "evaluation" / "answers-v0"
FILES = ("benchmark.json", "questions.jsonl", "expectations.jsonl")
SPLITS = ("dev", "test")
LANGUAGES = ("it", "en")
ROLES = ("core", "supporting", "must_not_cite")
OUTCOMES = tuple(outcome.value for outcome in Outcome)
# Abstention reasons the pipeline can produce (answer_generation); no other code is accepted.
REASONS = (OUT_OF_SCOPE, NEEDS_CLARIFICATION, NO_EVIDENCE, NO_CITABLE_EVIDENCE, ANALYSIS_FAILED,
           MODEL_REFUSED, GENERATION_FAILED, MODEL_ABSTAINED, NO_SUPPORTED_CLAIMS)
REVIEW_STATUSES = ("candidate", "owner_reviewed", "expert_reviewed")  # provision_eval's, less
REVIEWED = ("owner_reviewed", "expert_reviewed")                       # "synthetic"
# Human legal review of an answer (one record per reviewed answer).
VERDICTS = ("correct", "partial", "incorrect", "unsafe")
ERROR_TYPES = ("wrong_law", "missing_condition", "premise_accepted", "temporal_error", "other")

MANIFEST_KEYS = {"schema_version", "benchmark_id", "version", "kind", "build_id", "description"}
QUESTION_KEYS = {"query_id", "question", "language", "category", "expected_outcome",
                 "expected_reason", "notes", "time_sensitive", "split", "provenance"}
EXPECTATION_KEYS = {"query_id", "instrument", "article", "unit", "role", "rationale",
                    "provenance"}
UNIT_KEYS = {"paragraph", "point", "letter"}
TIME_KEYS = {"valid_as_of", "basis", "verified_by", "verified_on"}
PROVENANCE_KEYS = {"drafted_by", "drafted_on", "review_status", "reviewed_by", "reviewed_on"}
REVIEW_RECORD_KEYS = {"query_id", "run_id", "answer_sha256", "reviewer", "review_date",
                      "verdict", "error_type", "notes"}

_QUERY_ID = re.compile(r"a\d{2}")
_BUILD_ID = re.compile(r"build-[0-9a-f]{32}")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CATEGORY = re.compile(r"[a-z][a-z_]*")
_LABEL = re.compile(r"\d+(?:-[a-z]+)*")


class BenchmarkError(ValueError):
    """The benchmark files are malformed or inconsistent; the message says where."""


# --- Data ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Unit:
    paragraph: str | None = None  # "N." at the start of a line
    point: str | None = None  # "N)" at the start of a line (e.g. the definitions of GDPR Art. 4)
    letter: str | None = None  # "x)" at the start of a line, inside the paragraph or point

    def label(self) -> str:
        parts = [f"par. {self.paragraph}" if self.paragraph else "",
                 f"point {self.point}" if self.point else "",
                 f"letter {self.letter}" if self.letter else ""]
        return ", ".join(p for p in parts if p)


@dataclass(frozen=True)
class TimeSensitivity:
    valid_as_of: str  # the date the expectation was last known to hold
    basis: str  # why it may change
    verified_by: str | None  # who last re-checked it, once someone has
    verified_on: str | None  # when; the freshness window counts from this date


@dataclass(frozen=True)
class Question:
    query_id: str
    question: str
    language: str
    category: str
    expected_outcome: str  # an Outcome value
    expected_reason: str | None  # a REASONS code, for an expected abstention only
    notes: str | None
    time_sensitive: TimeSensitivity | None
    split: str
    provenance: Provenance


@dataclass(frozen=True)
class Expectation:
    query_id: str
    instrument: str
    article: str
    unit: Unit | None  # None: the whole article
    role: str
    rationale: str
    provenance: Provenance

    def describe(self) -> str:
        unit = f" ({self.unit.label()})" if self.unit else ""
        return f"{self.instrument} art. {self.article}{unit}"


@dataclass(frozen=True)
class Benchmark:
    benchmark_id: str
    version: str
    kind: str
    build_id: str
    description: str
    schema_version: int
    questions: tuple[Question, ...]
    expectations: tuple[Expectation, ...]
    files: dict[str, str]  # file name -> sha256

    def rows(self, query_id: str) -> tuple[Expectation, ...]:
        return tuple(e for e in self.expectations if e.query_id == query_id)


# --- Loading and checks --------------------------------------------------------------------------


def load_benchmark(directory: Path = DEFAULT_BENCHMARK) -> Benchmark:
    """Load and check the benchmark in `directory`. Raises BenchmarkError on any problem."""
    directory = Path(directory)
    for name in FILES:
        if not (directory / name).is_file():
            raise BenchmarkError(f"{directory}: {name} is missing")
    manifest = _load_manifest(directory / "benchmark.json")
    questions = tuple(_question(record, where)
                      for where, record in _jsonl(directory / "questions.jsonl"))
    ids = [q.query_id for q in questions]
    if len(set(ids)) != len(ids):
        raise BenchmarkError(f"questions.jsonl: duplicate query IDs "
                             f"{sorted({i for i in ids if ids.count(i) > 1})}")
    expectations = tuple(_expectation(record, where, set(ids))
                         for where, record in _jsonl(directory / "expectations.jsonl"))
    keys = [(e.query_id, e.instrument, e.article, e.unit) for e in expectations]
    if len(set(keys)) != len(keys):
        raise BenchmarkError("expectations.jsonl: a row is repeated for the same unit")
    for q in questions:
        core = [e for e in expectations if e.query_id == q.query_id and e.role == "core"]
        if q.expected_outcome == Outcome.ABSTAIN and core:
            raise BenchmarkError(f"{q.query_id}: an expected abstention has core rows")
        if q.expected_outcome != Outcome.ABSTAIN and not core:
            raise BenchmarkError(f"{q.query_id}: an expected answer has no core row")
    files = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in FILES}
    return Benchmark(manifest["benchmark_id"], manifest["version"], manifest["kind"],
                     manifest["build_id"], manifest["description"], manifest["schema_version"],
                     questions, expectations, files)


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise BenchmarkError(f"{path.name}: invalid JSON ({exc})") from None
    _keys(data, MANIFEST_KEYS, path.name)
    if data["schema_version"] != SCHEMA_VERSION or type(data["schema_version"]) is not int:
        raise BenchmarkError(f"{path.name}: schema_version must be {SCHEMA_VERSION}")
    if data["kind"] != KIND:
        raise BenchmarkError(f"{path.name}: kind must be {KIND!r}")
    if not isinstance(data["build_id"], str) or not _BUILD_ID.fullmatch(data["build_id"]):
        raise BenchmarkError(f"{path.name}: build_id must look like build-<32 hex>")
    for key in ("benchmark_id", "version", "description"):
        _text(data, key, path.name)
    return data


def _jsonl(path: Path) -> Iterable[tuple[str, dict[str, Any]]]:
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        where = f"{path.name}:{n}"
        try:
            record = json.loads(line)
        except ValueError as exc:
            raise BenchmarkError(f"{where}: invalid JSON ({exc})") from None
        if not isinstance(record, dict):
            raise BenchmarkError(f"{where}: expected a JSON object")
        yield where, record


def _question(r: dict[str, Any], where: str) -> Question:
    _keys(r, QUESTION_KEYS, where)
    if not isinstance(r["query_id"], str) or not _QUERY_ID.fullmatch(r["query_id"]):
        raise BenchmarkError(f"{where}: query_id must be a01, a02, ...")
    _text(r, "question", where)
    _choice(r, "language", LANGUAGES, where)
    if not isinstance(r["category"], str) or not _CATEGORY.fullmatch(r["category"]):
        raise BenchmarkError(f"{where}: category must be a lower-case identifier")
    _choice(r, "expected_outcome", OUTCOMES, where)
    if r["expected_outcome"] == Outcome.ABSTAIN:
        _choice(r, "expected_reason", REASONS, where)
    elif r["expected_reason"] is not None:
        raise BenchmarkError(f"{where}: expected_reason is for an expected abstention only")
    if r["notes"] is not None:
        _text(r, "notes", where)
    _choice(r, "split", SPLITS, where)
    return Question(r["query_id"], r["question"], r["language"], r["category"],
                    r["expected_outcome"], r["expected_reason"], r["notes"],
                    _time(r["time_sensitive"], where), r["split"],
                    _provenance(r["provenance"], where))


def _time(raw: Any, where: str) -> TimeSensitivity | None:
    if raw is None:
        return None
    where = f"{where}: time_sensitive"
    _keys(raw, TIME_KEYS, where)
    _date(raw, "valid_as_of", where)
    _text(raw, "basis", where)
    if (raw["verified_by"] is None) != (raw["verified_on"] is None):
        raise BenchmarkError(f"{where}: verified_by and verified_on are set together")
    if raw["verified_by"] is not None:
        _text(raw, "verified_by", where)
        _date(raw, "verified_on", where)
    return TimeSensitivity(raw["valid_as_of"], raw["basis"], raw["verified_by"],
                           raw["verified_on"])


def _expectation(r: dict[str, Any], where: str, query_ids: set[str]) -> Expectation:
    _keys(r, EXPECTATION_KEYS, where)
    if r["query_id"] not in query_ids:
        raise BenchmarkError(f"{where}: unknown query_id {r['query_id']!r}")
    _choice(r, "instrument", tuple(CORPUS_INSTRUMENTS), where)
    if not isinstance(r["article"], str) or not _LABEL.fullmatch(r["article"]):
        raise BenchmarkError(f"{where}: article must be a label as printed, e.g. 6 or 2-bis")
    _choice(r, "role", ROLES, where)
    _text(r, "rationale", where)
    return Expectation(r["query_id"], r["instrument"], r["article"], _unit(r["unit"], where),
                       r["role"], r["rationale"], _provenance(r["provenance"], where))


def _unit(raw: Any, where: str) -> Unit | None:
    if raw is None:
        return None
    where = f"{where}: unit"
    _keys(raw, UNIT_KEYS, where)
    for key, pattern in (("paragraph", r"\d{1,3}"), ("point", r"\d{1,3}"), ("letter", r"[a-z]")):
        value = raw[key]
        if value is not None and (not isinstance(value, str) or not re.fullmatch(pattern, value)):
            raise BenchmarkError(f"{where}: {key} must be null or match {pattern}")
    if all(raw[key] is None for key in UNIT_KEYS):
        raise BenchmarkError(f"{where}: use null for the whole article, not an empty unit")
    return Unit(raw["paragraph"], raw["point"], raw["letter"])


def _provenance(raw: Any, where: str) -> Provenance:
    where = f"{where}: provenance"
    _keys(raw, PROVENANCE_KEYS, where)
    _text(raw, "drafted_by", where)
    _date(raw, "drafted_on", where)
    _choice(raw, "review_status", REVIEW_STATUSES, where)
    if raw["review_status"] in REVIEWED:
        _text(raw, "reviewed_by", where)
        _date(raw, "reviewed_on", where)
        if raw["reviewed_on"] < raw["drafted_on"]:
            raise BenchmarkError(f"{where}: reviewed_on is before drafted_on")
    elif raw["reviewed_by"] is not None or raw["reviewed_on"] is not None:
        raise BenchmarkError(f"{where}: a candidate has no reviewer or review date")
    return Provenance(raw["drafted_by"], raw["drafted_on"], raw["review_status"],
                      raw["reviewed_by"], raw["reviewed_on"])


def _keys(record: Any, expected: set[str], where: str) -> None:
    if not isinstance(record, dict):
        raise BenchmarkError(f"{where}: expected an object")
    if set(record) != expected:
        missing, extra = sorted(expected - set(record)), sorted(set(record) - expected)
        raise BenchmarkError(f"{where}: fields differ (missing {missing}, unknown {extra})")


def _text(record: Mapping[str, Any], key: str, where: str) -> None:
    if not isinstance(record[key], str) or not record[key].strip():
        raise BenchmarkError(f"{where}: {key} must be non-empty text")


def _choice(record: Mapping[str, Any], key: str, choices: Sequence[str], where: str) -> None:
    if record[key] not in choices:
        raise BenchmarkError(f"{where}: {key} must be one of {list(choices)}")


def _date(record: Mapping[str, Any], key: str, where: str) -> None:
    value = record[key]
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        raise BenchmarkError(f"{where}: {key} must be a YYYY-MM-DD date")
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        raise BenchmarkError(f"{where}: {key} is not a real date") from None


# --- Units ---------------------------------------------------------------------------------------


def _marker(label: str, close: str) -> re.Pattern[str]:
    """A paragraph "N." or a point/letter "N)" / "x)" at the start of a line."""
    if close == ".":  # a paragraph number is followed by a line break or by text in capitals
        return re.compile(rf"(?m)^[ \t]*{re.escape(label)}\.(?=[ \t]*\n|[ \t]+[A-ZÀ-Þ«(])")
    return re.compile(rf"(?m)^[ \t]*{re.escape(label)}\)[ \t]")


def _next_label(label: str) -> str:
    return str(int(label) + 1) if label.isdigit() else chr(ord(label) + 1)


def _span(text: str, start: int, end: int, label: str, close: str) -> tuple[int, int] | None:
    found = _marker(label, close).search(text, start, end)
    if found is None:
        return None
    following = _marker(_next_label(label), close).search(text, found.end(), end)
    return found.start(), following.start() if following else end


def locate_unit(text: str, unit: Unit | None) -> tuple[int, int] | None:
    """(start, end) of `unit` in an article's stored text, or None if it is not found. A letter
    is looked for inside the paragraph or point, if one is given."""
    span: tuple[int, int] | None = (0, len(text))
    if unit is None:
        return span
    for value, close in ((unit.paragraph, "."), (unit.point, ")"), (unit.letter, ")")):
        if value is not None and span is not None:
            span = _span(text, span[0], span[1], value, close)
    return span


def unit_text(text: str, unit: Unit | None) -> str | None:
    span = locate_unit(text, unit)
    return None if span is None else text[span[0]:span[1]]


# --- Metrics -------------------------------------------------------------------------------------

ArticleText = Callable[[str, str], str]  # (instrument, article label) -> stored article text


def is_reviewed(provenance: Provenance) -> bool:
    return provenance.review_status in REVIEWED


def time_status(question: Question, today: datetime.date,
                freshness_days: int | None) -> str | None:
    """None if not time-sensitive; "unverified" until someone has re-checked it; "no_window" when
    no window is given; then "fresh" if verified_on is within the window, otherwise "stale".
    Only "fresh" ones join the summary."""
    if question.time_sensitive is None:
        return None
    if question.time_sensitive.verified_on is None:
        return "unverified"
    if freshness_days is None:
        return "no_window"
    age = (today - datetime.date.fromisoformat(question.time_sensitive.verified_on)).days
    return "fresh" if 0 <= age <= freshness_days else "stale"


def _article_of(provision_id: str) -> tuple[str, str]:
    """(instrument, label) of an article ID such as "eu-reg-2016-679@.../body/article:33"."""
    return provision_id.split("@", 1)[0], provision_id.rsplit("article:", 1)[-1]


def score_question(question: Question, rows: Sequence[Expectation], result: Mapping[str, Any],
                   article_text: ArticleText) -> dict[str, Any]:
    """The metrics of one question from one result (AnswerResult.to_dict(), as /api/ask returns
    it). No eligibility rule is applied here: see score()."""
    evidence = result.get("evidence") or {"items": [], "dropped": []}
    items = evidence["items"]
    candidates = {(i["instrument_id"], i["label"]) for i in items}
    candidates |= {_article_of(d["provision_id"]) for d in evidence["dropped"]}
    by_id = {i["evidence_id"]: i for i in items}
    quotes = [(by_id[q["evidence_id"]], q["text"]) for claim in result.get("claims", ())
              for q in claim["quotes"] if q["evidence_id"] in by_id]

    def row_entry(row: Expectation) -> dict[str, Any]:
        article = (row.instrument, row.article)
        target = unit_text(article_text(*article), row.unit)
        entry: dict[str, Any] = {"provision": row.describe(), "role": row.role,
                                 "candidate": article in candidates, "evidence": False,
                                 "evidence_extent": None, "cited": False,
                                 "unit_found": target is not None}
        if target is None:
            return entry
        wanted = normalise(target)
        for item in items:
            if (item["instrument_id"], item["label"]) != article:
                continue
            if row.unit is None or wanted in normalise(item["text"]):
                entry["evidence"] = True
                entry["evidence_extent"] = ("whole" if item["whole_provision"] else
                                            f"point {item['point']}" if item["point"] else
                                            "excerpt")
        entry["cited"] = any((item["instrument_id"], item["label"]) == article
                             and normalise(text) in wanted for item, text in quotes)
        return entry

    def block(role: str) -> dict[str, Any]:
        entries = [row_entry(r) for r in rows if r.role == role]
        recall = {metric: (sum(e[metric] for e in entries) / len(entries) if entries else None)
                  for metric in ("candidate", "evidence", "cited")}
        return {"rows": entries, "candidate_recall": recall["candidate"],
                "evidence_recall": recall["evidence"], "citation_recall": recall["cited"]}

    listed = {(r.instrument, r.article) for r in rows}
    forbidden = {(r.instrument, r.article) for r in rows if r.role == "must_not_cite"}
    cited = [(c["instrument_id"], c["label"]) for c in result.get("citations", ())]
    outcome = result.get("outcome")
    return {
        "query_id": question.query_id,
        "split": question.split,
        "expected_outcome": question.expected_outcome,
        "outcome": outcome,
        "outcome_match": outcome == question.expected_outcome,
        "abstained": outcome == Outcome.ABSTAIN,
        "expected_reason": question.expected_reason,
        "abstention_reason": result.get("abstention_reason"),
        "reason_match": (result.get("abstention_reason") == question.expected_reason
                         if question.expected_outcome == Outcome.ABSTAIN else None),
        "core": block("core"),
        "supporting": block("supporting"),
        "unlisted_citations": sorted(f"{i} art. {a}" for i, a in cited if (i, a) not in listed),
        "must_not_cite_cited": sorted(f"{i} art. {a}" for i, a in cited if (i, a) in forbidden),
    }


def score(benchmark: Benchmark, results: Mapping[str, Mapping[str, Any]],
          article_text: ArticleText, *, today: datetime.date,
          freshness_days: int | None = DEFAULT_FRESHNESS_DAYS,
          include_unreviewed: bool = False) -> dict[str, Any]:
    """Score `results` ({query_id: AnswerResult.to_dict()}) under the eligibility rules."""
    scored, separate, unreviewed = [], [], []
    excluded: dict[str, str] = {}
    for q in benchmark.questions:
        rows = benchmark.rows(q.query_id)
        reviewed = is_reviewed(q.provenance) and all(is_reviewed(r.provenance) for r in rows)
        if not reviewed and not include_unreviewed:
            excluded[q.query_id] = "not reviewed: the question or one of its rows is a candidate"
            continue
        if q.query_id not in results:
            excluded[q.query_id] = "no result"
            continue
        entry = score_question(q, rows, results[q.query_id], article_text)
        status = time_status(q, today, freshness_days)
        entry["time_sensitive"] = status
        if not reviewed:
            entry["unreviewed"] = True
            unreviewed.append(entry)
        elif status not in (None, "fresh"):
            separate.append(entry)
        else:
            scored.append(entry)
    return {
        "benchmark": {"benchmark_id": benchmark.benchmark_id, "version": benchmark.version,
                      "build_id": benchmark.build_id, "files": benchmark.files},
        "today": today.isoformat(),
        "freshness_days": freshness_days,
        "summary": summarise(scored),
        "scored": scored,
        "time_sensitive_separate": separate,
        "excluded": excluded,
        "unreviewed_diagnostics": unreviewed,  # only with include_unreviewed; never summarised
    }


def summarise(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Means over questions (each question counts once); a recall is averaged over the
    questions that have rows of that role."""
    def mean(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    out: dict[str, Any] = {"questions": len(entries)}
    for role in ("core", "supporting"):
        out[role] = {metric: mean([e[role][metric] for e in entries
                                   if e[role][metric] is not None])
                     for metric in ("candidate_recall", "evidence_recall", "citation_recall")}
    out["outcome_exact_match"] = mean([float(e["outcome_match"]) for e in entries])
    out["abstained"] = sum(e["abstained"] for e in entries)
    out["unlisted_citations"] = sum(len(e["unlisted_citations"]) for e in entries)
    return out


# --- Human legal review --------------------------------------------------------------------------


def answer_sha256(result: Mapping[str, Any]) -> str:
    """The SHA-256 of a result in canonical JSON: the answer a review record refers to."""
    return hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def check_legal_review(record: Mapping[str, Any], *, query_ids: Iterable[str],
                       today: datetime.date) -> None:
    """Raise BenchmarkError unless `record` is a well-formed human review of one answer.

    {"query_id", "run_id", "answer_sha256", "reviewer", "review_date", "verdict",
     "error_type", "notes"}: verdict one of VERDICTS; error_type null for a correct answer and
    one of ERROR_TYPES otherwise; "other" needs notes saying what the error is."""
    where = "legal review"
    _keys(dict(record), REVIEW_RECORD_KEYS, where)
    if record["query_id"] not in set(query_ids):
        raise BenchmarkError(f"{where}: unknown query_id {record['query_id']!r}")
    _text(record, "run_id", where)
    if not isinstance(record["answer_sha256"], str) or not _SHA256.fullmatch(
            record["answer_sha256"]):
        raise BenchmarkError(f"{where}: answer_sha256 must be 64 lower-case hex digits")
    _text(record, "reviewer", where)
    _date(record, "review_date", where)
    if datetime.date.fromisoformat(record["review_date"]) > today:
        raise BenchmarkError(f"{where}: review_date is in the future")
    _choice(record, "verdict", VERDICTS, where)
    if record["verdict"] == "correct":
        if record["error_type"] is not None:
            raise BenchmarkError(f"{where}: a correct answer has no error_type")
    else:
        _choice(record, "error_type", ERROR_TYPES, where)
    if record["notes"] is not None:
        _text(record, "notes", where)
    if record["error_type"] == "other" and record["notes"] is None:
        raise BenchmarkError(f"{where}: error_type 'other' needs notes")
