"""Benchmark v0 for end-to-end answers: data/evaluation/answers-v0/ and src/answer_benchmark.py.

Offline: no test runs the pipeline against a model. The metric tests use hand-made results
shaped like AnswerResult.to_dict(), and one contract test uses the offline synthetic run of
src/demo.py. Tests marked "recorded build" read the real corpus and skip without it.
"""

import copy
import dataclasses
import datetime
import json
import re
import shutil

import pytest

import src.answer_benchmark as ab
import src.demo as demo
from src.provision_eval import Provenance
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build

G, C = "eu-reg-2016-679", "it-dlgs-2003-196"
TODAY = datetime.date(2026, 11, 16)
SHEET = ab.DEFAULT_BENCHMARK / "REVIEW_SHEET.md"


@pytest.fixture(scope="module")
def bench():
    return ab.load_benchmark()


def rows_of(bench, qid, role=None):
    return [(e.instrument, e.article, e.unit) for e in bench.rows(qid)
            if role is None or e.role == role]


# --- The shipped files ---------------------------------------------------------------------------


def test_the_shipped_benchmark_loads_with_its_manifest(bench):
    assert (bench.benchmark_id, bench.version, bench.kind, bench.schema_version) == (
        "answers", "0-draft", "end_to_end", 1)
    assert bench.build_id == "build-f76ff6031f2fc82c4852f0a2bde27807"
    assert (len(bench.questions), len(bench.expectations)) == (22, 81)
    assert set(bench.files) == set(ab.FILES)


def test_ids_and_splits(bench):
    assert [q.query_id for q in bench.questions] == [f"a{n:02d}" for n in range(1, 23)]
    assert [q.query_id for q in bench.questions if q.split == "dev"] == [
        f"a{n:02d}" for n in range(1, 13)]


def test_nothing_is_marked_reviewed(bench):
    for record in (*bench.questions, *bench.expectations):
        assert record.provenance.review_status == "candidate"
        assert (record.provenance.reviewed_by, record.provenance.reviewed_on) == (None, None)


def test_outcomes_and_reasons(bench):
    by_id = {q.query_id: q for q in bench.questions}
    assert {q.query_id for q in bench.questions if q.expected_outcome == "abstain"} == {
        "a09", "a19"}
    assert by_id["a09"].expected_reason == by_id["a19"].expected_reason == "out_of_scope"
    assert (by_id["a18"].expected_outcome, by_id["a18"].expected_reason) == (
        "answer_limited", None)
    assert "25 May 2018" in by_id["a18"].notes
    for q in bench.questions:
        assert (q.expected_reason is None) == (q.expected_outcome != "abstain")
        assert bool(rows_of(bench, q.query_id, "core")) == (q.expected_outcome != "abstain")


def test_the_owner_corrections_are_applied(bench):
    unit = ab.Unit
    assert rows_of(bench, "a18", "core") == [(G, "99", unit("2"))]
    assert rows_of(bench, "a22", "core") == [(G, "77", None), (C, "141", None), (C, "142", None)]
    assert rows_of(bench, "a22", "supporting") == [(C, "143", None)]
    assert rows_of(bench, "a01", "core") == [(G, "33", unit("1"))]
    assert (G, "55", unit("1")) in rows_of(bench, "a01", "supporting")
    for qid in ("a01", "a10"):  # the same role in both
        assert (C, "2-bis", None) in rows_of(bench, qid, "supporting")
    assert (G, "7", unit("3")) in rows_of(bench, "a06", "supporting")
    assert (G, "28", unit("3", None, "f")) in rows_of(bench, "a11", "supporting")
    # a07: general and conditional controller obligations are core, not every obligation
    # (owner, 2026-11-16).
    assert [a for _, a, _ in rows_of(bench, "a07", "core")] == [
        "5", "24", "25", "30", "32", "33", "34", "35", "37"]
    assert [a for _, a, _ in rows_of(bench, "a07", "supporting")] == [
        "26", "28", "12", "13", "14"]
    assert "does not require exhaustive coverage" in next(
        q.notes for q in bench.questions if q.query_id == "a07")
    for qid in ("a06", "a07"):  # the information duties are supporting in both
        assert {(G, a, None) for a in ("12", "13", "14")} <= set(
            rows_of(bench, qid, "supporting"))
    assert "Garante's own list is not in the corpus" in next(
        e.rationale for e in bench.rows("a14") if e.unit == unit("4"))
    for e in bench.expectations:
        if e.instrument == C:
            assert "user transcription, not verified" in e.rationale


def test_time_sensitive_questions(bench):
    timed = {q.query_id: q.time_sensitive for q in bench.questions if q.time_sensitive}
    assert set(timed) == {"a01", "a10", "a12"}
    for t in timed.values():
        assert t.valid_as_of == "2026-11-08" and "COM(2025) 837" in t.basis
        assert (t.verified_by, t.verified_on) == (None, None)  # not re-verified
    q = next(q for q in bench.questions if q.query_id == "a01")
    # Unverified: apart under any window, although valid_as_of is within 30 days of TODAY.
    for window in (None, 30, 3650):
        assert ab.time_status(q, TODAY, window) == "unverified"
    checked = dataclasses.replace(q, time_sensitive=dataclasses.replace(
        q.time_sensitive, verified_by="A Reviewer", verified_on="2026-11-10"))
    assert ab.time_status(checked, TODAY, None) == "no_window"
    assert ab.time_status(checked, TODAY, 30) == "fresh"
    assert ab.time_status(checked, datetime.date(2026, 12, 11), 30) == "stale"
    assert ab.time_status(next(q for q in bench.questions if q.query_id == "a02"), TODAY,
                          30) is None


def test_units_are_structured_objects():
    for line in (ab.DEFAULT_BENCHMARK / "expectations.jsonl").read_text(
            encoding="utf-8").splitlines():
        unit = json.loads(line)["unit"]
        assert unit is None or set(unit) == {"paragraph", "point", "letter"}


def parse_sheet():
    short = {"GDPR": G, "Codice": C}
    table = {}
    for line in SHEET.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 8 and re.fullmatch(r"a\d\d", cells[0]):
            table[cells[0]] = cells

    def parse(cell):
        out = []
        for m in re.finditer(r"(GDPR|Codice) ([\w-]+)(?: \(([^)]*)\))?", cell):
            unit = None
            if m.group(3):
                fields = dict(re.findall(r"(par\.|point|letter) (\w+)", m.group(3)))
                unit = ab.Unit(fields.get("par."), fields.get("point"), fields.get("letter"))
            out.append((short[m.group(1)], m.group(2), unit))
        return out

    return table, parse


def test_the_review_sheet_table_matches_the_files(bench):
    table, parse = parse_sheet()
    assert sorted(table) == [q.query_id for q in bench.questions]
    for q in bench.questions:
        _, split, category, outcome, text, core, supporting, _ = table[q.query_id]
        expected = q.expected_outcome + (f" ({q.expected_reason})" if q.expected_reason else "")
        assert (split, category, outcome, text) == (q.split, q.category, expected, q.question)
        assert parse(core) == rows_of(bench, q.query_id, "core"), q.query_id
        assert parse(supporting) == rows_of(bench, q.query_id, "supporting"), q.query_id


# --- Units in the recorded build -----------------------------------------------------------------


@pytest.fixture(scope="module")
def explorer():
    try:
        return ProvisionExplorer.open(find_recorded_build())
    except ExplorerError as exc:
        pytest.skip(f"recorded build unavailable: {exc}")


@pytest.fixture(scope="module")
def article_text(explorer):
    def text(instrument, article):
        return "".join(p["text"] for p in explorer.lookup(instrument, article)["provision"]["text"])

    return text


def test_recorded_build_is_the_one_the_manifest_names(bench, explorer):
    assert explorer.identity()["build_id"] == bench.build_id


def test_recorded_build_every_expected_unit_is_found(bench, article_text):
    for e in bench.expectations:
        found = ab.unit_text(article_text(e.instrument, e.article), e.unit)
        assert found and found.strip(), e.describe()


@pytest.mark.parametrize(("article", "unit", "contains"), [
    ("6", ab.Unit("1", None, "b"), "esecuzione di un contratto"),
    ("28", ab.Unit("3", None, "f"), "articoli da 32 a 36"),
    ("99", ab.Unit("2"), "25 maggio 2018"),
    ("33", ab.Unit("2"), "Il responsabile del trattamento informa"),
    ("4", ab.Unit(None, "12"), "«violazione dei dati personali»"),
    ("7", ab.Unit("3"), "revocare il proprio consenso"),
])
def test_recorded_build_units_cover_the_right_text(article_text, article, unit, contains):
    found = " ".join(ab.unit_text(article_text(G, article), unit).split())
    assert contains in found
    # A unit is a slice of its article, never the whole article (except when no unit is given).
    assert len(found) < len(" ".join(article_text(G, article).split()))


def test_recorded_build_letter_b_is_not_letter_c(article_text):
    b = ab.unit_text(article_text(G, "6"), ab.Unit("1", None, "b"))
    assert "esecuzione di un contratto" in b and "obbligo legale" not in b


# --- The validator rejects malformed files -------------------------------------------------------


def write_copy(tmp_path, change):
    target = tmp_path / "bench"
    shutil.copytree(ab.DEFAULT_BENCHMARK, target)
    manifest = json.loads((target / "benchmark.json").read_text(encoding="utf-8"))
    questions = [json.loads(l) for l in (target / "questions.jsonl").read_text(
        encoding="utf-8").splitlines()]
    expectations = [json.loads(l) for l in (target / "expectations.jsonl").read_text(
        encoding="utf-8").splitlines()]
    change(manifest, questions, expectations)
    (target / "benchmark.json").write_text(json.dumps(manifest), encoding="utf-8")
    for name, records in (("questions.jsonl", questions), ("expectations.jsonl", expectations)):
        (target / name).write_text("".join(json.dumps(r) + "\n" for r in records),
                                   encoding="utf-8")
    return target


def reviewed(provenance, **changes):
    provenance.update({"review_status": "owner_reviewed", "reviewed_by": "A Reviewer",
                       "reviewed_on": "2026-11-16", **changes})


def core_row_for(query_id):
    def change(m, q, e):
        e.append({**copy.deepcopy(next(r for r in e if r["role"] == "core")),
                  "query_id": query_id})
    return change


def drop_rows_of(query_id):
    def change(m, q, e):
        e[:] = [r for r in e if r["query_id"] != query_id]
    return change


CASES = {
    "schema_version": (lambda m, q, e: m.update(schema_version=2), "schema_version"),
    "kind": (lambda m, q, e: m.update(kind="retrieval"), "kind"),
    "build_id": (lambda m, q, e: m.update(build_id="latest"), "build_id"),
    "manifest key": (lambda m, q, e: m.pop("description"), "fields differ"),
    "duplicate id": (lambda m, q, e: q[1].update(query_id="a01"), "duplicate query IDs"),
    "id form": (lambda m, q, e: q[0].update(query_id="q01"), "a01, a02"),
    "language": (lambda m, q, e: q[0].update(language="de"), "language"),
    "outcome": (lambda m, q, e: q[0].update(expected_outcome="answered"), "expected_outcome"),
    "reason on an answer": (lambda m, q, e: q[0].update(expected_reason="out_of_scope"),
                            "expected abstention only"),
    "unsupported reason": (lambda m, q, e: q[8].update(expected_reason="outside_source_coverage"),
                           "expected_reason"),
    "extra field": (lambda m, q, e: q[0].update(verified=True), "fields differ"),
    "half a verification": (lambda m, q, e: q[0]["time_sensitive"].update(verified_by="X"),
                            "set together"),
    "reviewed without reviewer": (
        lambda m, q, e: q[0]["provenance"].update(review_status="owner_reviewed"),
        "reviewed_by must be non-empty"),
    "candidate with reviewer": (
        lambda m, q, e: q[0]["provenance"].update(reviewed_by="A Reviewer"),
        "a candidate has no reviewer"),
    "review before drafting": (
        lambda m, q, e: reviewed(q[0]["provenance"], reviewed_on="2026-11-01"),
        "before drafted_on"),
    "unknown status": (lambda m, q, e: e[0]["provenance"].update(review_status="pending"),
                       "review_status"),
    "unknown question": (lambda m, q, e: e[0].update(query_id="a99"), "unknown query_id"),
    "unknown instrument": (lambda m, q, e: e[0].update(instrument="eu-dir-2002-58"),
                           "instrument"),
    "article label": (lambda m, q, e: e[0].update(article="Art. 33"), "label as printed"),
    "empty unit": (lambda m, q, e: e[0].update(unit={"paragraph": None, "point": None,
                                                     "letter": None}), "empty unit"),
    "letter form": (lambda m, q, e: e[0].update(unit={"paragraph": "1", "point": None,
                                                      "letter": "B"}), "letter"),
    "free-text unit": (lambda m, q, e: e[0].update(unit="par. 1"), "expected an object"),
    "role": (lambda m, q, e: e[0].update(role="primary"), "role"),
    "duplicate row": (lambda m, q, e: e.append(copy.deepcopy(e[0])), "repeated"),
    "abstention with core": (core_row_for("a09"), "abstention has core rows"),
    "answer without core": (drop_rows_of("a02"), "a02: an expected answer has no core row"),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_the_validator_rejects(tmp_path, case):
    change, message = CASES[case]
    with pytest.raises(ab.BenchmarkError, match=message):
        ab.load_benchmark(write_copy(tmp_path, change))


def test_a_reviewed_record_is_accepted(tmp_path):
    def change(m, q, e):
        reviewed(q[1]["provenance"])
        reviewed(e[6]["provenance"])

    bench = ab.load_benchmark(write_copy(tmp_path, change))
    assert ab.is_reviewed(bench.questions[1].provenance)


# --- Metrics -------------------------------------------------------------------------------------

ARTICLE = ("Articolo 9\n\n1.\nPrimo paragrafo con il testo del primo comma.\n\n"
           "2.\nSecondo paragrafo:\n\na)  la lettera a del secondo comma;\n\n"
           "b)  la lettera b del secondo comma.\n")
TEXTS = {(G, "9"): ARTICLE, (G, "10"): "Articolo 10\n\nUn articolo breve senza paragrafi.\n"}
DONE = Provenance("test", "2026-11-16", "owner_reviewed", "A Reviewer", "2026-11-16")
OPEN = Provenance("test", "2026-11-16", "candidate", None, None)


def text_of(instrument, article):
    return TEXTS[(instrument, article)]


def question(qid="a01", outcome="answer", reason=None, provenance=DONE, time_sensitive=None):
    return ab.Question(qid, "Domanda?", "it", "test", outcome, reason, None, time_sensitive,
                       "dev", provenance)


def row(article, unit=None, role="core", qid="a01", provenance=DONE):
    return ab.Expectation(qid, G, article, unit, role, "r", provenance)


def item(eid, article, text, whole=True, point=None):
    return {"evidence_id": eid, "instrument_id": G, "label": article, "text": text,
            "whole_provision": whole, "point": point}


def result(items=(), dropped=(), quotes=(), citations=(), outcome="answer", reason=None):
    return {"outcome": outcome, "abstention_reason": reason,
            "evidence": {"items": list(items), "dropped": [
                {"provision_id": f"{G}@v/body/article:{a}"} for a in dropped]},
            "claims": [{"quotes": [{"evidence_id": e, "text": t} for e, t in quotes]}],
            "citations": [{"instrument_id": G, "label": a} for a in citations]}


def bench_of(questions, rows):
    return ab.Benchmark("answers", "0-test", "end_to_end", "build-" + "0" * 32, "test", 1,
                        tuple(questions), tuple(rows), {})


def test_the_three_recalls_are_measured_per_unit():
    rows = [row("9", ab.Unit("2", None, "b")), row("9", ab.Unit("1")), row("10")]
    excerpt = "2.\nSecondo paragrafo:\n\na)  la lettera a del secondo comma;\n\n" \
              "b)  la lettera b del secondo comma."
    entry = ab.score_question(question(), rows, result(
        items=[item("E1", "9", excerpt, whole=False)], dropped=["10"],
        quotes=[("E1", "la lettera b del secondo comma")], citations=["9"]), text_of)
    letter_b, par_1, art_10 = entry["core"]["rows"]
    assert (letter_b["candidate"], letter_b["evidence"], letter_b["cited"]) == (True, True, True)
    assert letter_b["evidence_extent"] == "excerpt"
    # Paragraph 1 is not in the excerpt: retrieved, but not sent and not cited.
    assert (par_1["candidate"], par_1["evidence"], par_1["cited"]) == (True, False, False)
    # Art. 10 was a candidate dropped by the limits.
    assert (art_10["candidate"], art_10["evidence"], art_10["cited"]) == (True, False, False)
    assert entry["core"]["candidate_recall"] == 1.0
    assert entry["core"]["evidence_recall"] == entry["core"]["citation_recall"] == 1 / 3


def test_a_quotation_counts_only_inside_its_unit():
    rows = [row("9", ab.Unit("1")), row("9", role="supporting")]
    entry = ab.score_question(question(), rows, result(
        items=[item("E1", "9", ARTICLE)], quotes=[("E1", "la lettera a del secondo comma")]),
        text_of)
    assert entry["core"]["rows"][0]["evidence"] and not entry["core"]["rows"][0]["cited"]
    assert entry["supporting"]["rows"][0]["cited"]  # anywhere in the article
    assert entry["supporting"]["citation_recall"] == 1.0


def test_outcome_abstention_and_unlisted_citations():
    entry = ab.score_question(question(), [row("9")], result(
        items=[item("E1", "9", ARTICLE), item("E2", "10", TEXTS[(G, "10")])],
        citations=["9", "10"], outcome="answer_limited"), text_of)
    assert (entry["outcome_match"], entry["abstained"], entry["reason_match"]) == (
        False, False, None)
    assert entry["unlisted_citations"] == [f"{G} art. 10"]
    abstention = ab.score_question(question("a02", "abstain", "out_of_scope"), [], result(
        outcome="abstain", reason="out_of_scope"), text_of)
    assert (abstention["outcome_match"], abstention["abstained"],
            abstention["reason_match"]) == (True, True, True)
    assert abstention["core"]["candidate_recall"] is None


def test_must_not_cite_rows_are_reported():
    entry = ab.score_question(question(), [row("9"), row("10", role="must_not_cite")], result(
        items=[item("E1", "9", ARTICLE)], citations=["9", "10"]), text_of)
    assert entry["must_not_cite_cited"] == [f"{G} art. 10"] and entry["unlisted_citations"] == []


def test_only_reviewed_questions_are_scored_and_supporting_stays_apart():
    questions = [question("a01"), question("a02", provenance=OPEN), question("a03")]
    rows = [row("9", qid="a01"), row("10", role="supporting", qid="a01"),
            row("9", qid="a02"), row("9", qid="a03"), row("10", qid="a03", provenance=OPEN)]
    results = {qid: result(items=[item("E1", "9", ARTICLE)], quotes=[("E1", "Primo paragrafo")])
               for qid in ("a01", "a02", "a03")}
    report = ab.score(bench_of(questions, rows), results, text_of, today=TODAY)
    assert [e["query_id"] for e in report["scored"]] == ["a01"]
    assert set(report["excluded"]) == {"a02", "a03"}  # a03 has one candidate row
    assert report["unreviewed_diagnostics"] == []
    summary = report["summary"]
    assert summary["core"]["citation_recall"] == 1.0
    assert summary["supporting"]["evidence_recall"] == 0.0  # reported apart
    assert summary["questions"] == 1

    diagnostic = ab.score(bench_of(questions, rows), results, text_of, today=TODAY,
                          include_unreviewed=True)
    assert [e["query_id"] for e in diagnostic["unreviewed_diagnostics"]] == ["a02", "a03"]
    assert all(e["unreviewed"] for e in diagnostic["unreviewed_diagnostics"])
    assert diagnostic["summary"] == summary  # never summarised


def test_time_sensitive_questions_are_reported_apart_unless_fresh():
    timed = ab.TimeSensitivity("2026-11-08", "a pending proposal", "A Reviewer", "2026-11-10")
    unverified = ab.TimeSensitivity("2026-11-08", "a pending proposal", None, None)
    questions = [question("a01", time_sensitive=timed), question("a02"),
                 question("a03", time_sensitive=unverified)]
    rows = [row("9", qid=q.query_id) for q in questions]
    results = {q.query_id: result(items=[item("E1", "9", ARTICLE)]) for q in questions}
    bench = bench_of(questions, rows)

    def split(report):
        return ([e["query_id"] for e in report["scored"]],
                {e["query_id"]: e["time_sensitive"] for e in report["time_sensitive_separate"]})

    assert ab.DEFAULT_FRESHNESS_DAYS == 30
    default = ab.score(bench, results, text_of, today=TODAY)
    assert default["freshness_days"] == 30
    assert split(default) == (["a01", "a02"], {"a03": "unverified"})
    assert split(ab.score(bench, results, text_of, today=TODAY, freshness_days=None)) == (
        ["a02"], {"a01": "no_window", "a03": "unverified"})
    assert split(ab.score(bench, results, text_of, today=TODAY, freshness_days=3)) == (
        ["a02"], {"a01": "stale", "a03": "unverified"})  # an override, both ways
    assert split(ab.score(bench, results, text_of, today=datetime.date(2026, 12, 11))) == (
        ["a02"], {"a01": "stale", "a03": "unverified"})


def test_a_missing_result_is_listed_not_scored():
    report = ab.score(bench_of([question()], [row("9")]), {}, text_of, today=TODAY)
    assert report["excluded"] == {"a01": "no result"} and report["scored"] == []


def test_the_metrics_read_a_real_answer_result():
    """Contract: score_question reads only fields AnswerResult.to_dict() provides."""
    run = demo.synthetic(lambda line: None)
    data = run.result.to_dict()
    rows = [dataclasses.replace(row("1"), instrument=demo.INSTRUMENT_ID),
            dataclasses.replace(row("2", role="supporting"), instrument=demo.INSTRUMENT_ID)]
    texts = {i["label"]: i["text"] for i in data["evidence"]["items"]}
    entry = ab.score_question(question(), rows, data, lambda instrument, label: texts[label])
    assert entry["core"]["rows"][0]["cited"] is True  # Art. 1 is quoted by a kept claim
    assert entry["supporting"]["rows"][0]["evidence"] is True  # Art. 2 was in the evidence
    assert entry["supporting"]["rows"][0]["cited"] is False  # its claim was removed
    assert entry["outcome"] == data["outcome"]


# --- Human legal review --------------------------------------------------------------------------

RECORD = {"query_id": "a01", "run_id": "run-1", "answer_sha256": "a" * 64,
          "reviewer": "A Reviewer", "review_date": "2026-11-16", "verdict": "partial",
          "error_type": "missing_condition", "notes": None}


def test_a_well_formed_review_record_is_accepted():
    ab.check_legal_review(RECORD, query_ids={"a01"}, today=TODAY)
    ab.check_legal_review({**RECORD, "verdict": "correct", "error_type": None},
                          query_ids={"a01"}, today=TODAY)


@pytest.mark.parametrize(("change", "message"), [
    ({"verdict": "wrong"}, "verdict"),
    ({"verdict": "correct"}, "no error_type"),
    ({"error_type": None}, "error_type"),
    ({"error_type": "typo"}, "error_type"),
    ({"error_type": "other"}, "needs notes"),
    ({"review_date": "2026-12-01"}, "future"),
    ({"answer_sha256": "abc"}, "64 lower-case hex"),
    ({"query_id": "a99"}, "unknown query_id"),
    ({"reviewer": ""}, "reviewer"),
])
def test_a_malformed_review_record_is_refused(change, message):
    with pytest.raises(ab.BenchmarkError, match=message):
        ab.check_legal_review({**RECORD, **change}, query_ids={"a01"}, today=TODAY)


def test_the_answer_hash_ignores_key_order():
    assert ab.answer_sha256({"a": 1, "b": [1, 2]}) == ab.answer_sha256({"b": [1, 2], "a": 1})
    assert ab.answer_sha256({"a": 1}) != ab.answer_sha256({"a": 2})
