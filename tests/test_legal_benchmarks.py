"""The real benchmarks in data/evaluation/ (M4; docs/evaluation/legal-v2-implementation-plan.md).

legal-v1 is kept byte for byte: its five files are pinned. legal-v2 was frozen at Gate 3
(2026-11-12): its six files are pinned too (C10), and any change makes legal-v3. These tests check
the data. Only C8 evaluates legal-v2, and it compares two reports for equality: no test here
asserts, prints or records a metric value of a real benchmark.
"""

import hashlib
import json
import re

import pytest

import src.provision_eval as pe
from src.config import PROJECT_ROOT
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build

LEGAL_V1 = PROJECT_ROOT / "data" / "evaluation" / "legal-v1"
LEGAL_V2 = PROJECT_ROOT / "data" / "evaluation" / "legal-v2"
G, C = "eu-reg-2016-679", "it-dlgs-2003-196"
LEGAL_V1_SHA256 = {  # recorded when legal-v1 was written (M4 P2); any change makes a new version
    "README.md": "ef0fd2e54c69b9d7a8aecd693444926e80fb57d69683fdf7505bcf8e31c01c17",
    "benchmark.json": "a7cf326089e2d93b2552de2a4333a8df89fe2689dbb50eec755c8723870ad6c7",
    "judgments.jsonl": "293fdfa976b49f08cd2ac378c32eb49e575899cdf00d42b56d1a106042f64c0f",
    "pool.jsonl": "7e7ec00d90618a76f7cf3f161801223ec73e1423c2177cc2c7f0bfc77165949f",
    "questions.jsonl": "3c4e118f80f5cd5cda7d7af12aa8cbddff1092785bbc5cd5513ce09780f8151d",
}
LEGAL_V2_SHA256 = {  # pinned at the freeze (Gate 3, 2026-11-12); any change makes legal-v3
    "README.md": "7c694958ac98dc52198361f53bb9e9f000ecb863e59c610d2508dedb5a1d2eb6",
    "benchmark.json": "8e0c30617e74f019d81dab2c452ae50136816b83ac4cf79596d1631b7ef5e6e0",
    "changes.jsonl": "05045815cd03390206659d50977763c8a991345739e72d71f5ce602c025a9dfb",
    "judgments.jsonl": "ec0af92cfc1d0bbaf8f0a839507208685b0ab8fb5d9b489104a0559cf045666c",
    "pool.jsonl": "b193f7fea7bc70f2f94e7fb9cba3e43d8d643c20fc96f0f51196ddcc05e93ce5",
    "questions.jsonl": "d3276d2d20c8232de92b6c8858a96f943839f3cb1b5c27363a0d91020f5f5038",
}


# --- legal-v1: frozen ---------------------------------------------------------------------------


def test_legal_v1_files_are_unchanged():
    assert sorted(p.name for p in LEGAL_V1.iterdir()) == sorted(LEGAL_V1_SHA256)
    for name, digest in LEGAL_V1_SHA256.items():
        assert hashlib.sha256((LEGAL_V1 / name).read_bytes()).hexdigest() == digest, name


def test_the_default_benchmark_is_legal_v2():
    # Moved from legal-v1 at Gate 3 (2026-11-12), after legal-v2 was reviewed and frozen. The
    # legal-v1 tests use the explicit LEGAL_V1 path.
    assert pe.DEFAULT_BENCHMARK == LEGAL_V2


def test_legal_v1_is_read_as_schema_1_with_the_technical_scenario_only():
    benchmark = pe.load_benchmark(LEGAL_V1)
    assert (benchmark.schema_version, benchmark.query_scenarios) == (1, ("technical",))
    assert all(q.search_queries_it_natural == () for q in benchmark.questions)


def test_the_natural_scenario_on_legal_v1_stops_before_any_build_is_opened(monkeypatch, capsys):
    def must_not_run(*args, **kwargs):
        raise AssertionError("no build or store may be opened for this run")

    monkeypatch.setattr(pe, "find_recorded_build", must_not_run)
    monkeypatch.setattr(pe, "load_store", must_not_run)
    monkeypatch.setattr(pe.ProvisionExplorer, "open", must_not_run)
    assert pe.main(["--benchmark", str(LEGAL_V1), "--scenario", "natural"]) == 2
    assert ("benchmark legal v1 (schema 1) has no 'natural' queries"
            in capsys.readouterr().err)


# --- legal-v2: open, unreviewed (Phase 2 of the plan) ------------------------------------------


def records(directory, name):
    text = (directory / name).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def judgment_key(record):
    return (record["query_id"], record["instrument"], record["article"], record.get("point"))


def recorded_explorer():
    try:
        return ProvisionExplorer.open(find_recorded_build())
    except ExplorerError as exc:
        pytest.skip(f"recorded build unavailable: {exc}")


# C1: schema and references


def test_legal_v2_is_schema_2_with_the_v1_questions():
    v1, v2 = pe.load_benchmark(LEGAL_V1), pe.load_benchmark(LEGAL_V2)  # validates the schema
    assert (v2.benchmark_id, v2.version, v2.kind, v2.schema_version) == ("legal", "2", "real", 2)
    assert v2.query_scenarios == ("technical", "natural")
    assert ([(q.query_id, q.split, q.question, q.search_queries_it) for q in v2.questions]
            == [(q.query_id, q.split, q.question, q.search_queries_it) for q in v1.questions])
    assert sorted(p.name for p in LEGAL_V2.iterdir()) == [
        "README.md", "benchmark.json", "changes.jsonl", "judgments.jsonl", "pool.jsonl",
        "questions.jsonl"]
    for path in LEGAL_V2.iterdir():
        assert b"\r" not in path.read_bytes(), path.name  # LF line endings


def test_legal_v2_resolves_on_the_recorded_build():
    explorer = recorded_explorer()
    benchmark = pe.load_benchmark(LEGAL_V2)
    grades = pe.resolve_judgments(benchmark.judgments, explorer)  # raises on any unknown reference
    # Counted per article: q17 judges three points of GDPR Art. 4.
    articles = {(j.query_id, j.instrument, j.article) for j in benchmark.judgments}
    assert sum(len(found) for found in grades.values()) == len(articles) == len(
        benchmark.judgments) - 2


# C2: v2 is v1 plus its change log


def test_legal_v2_is_legal_v1_plus_its_change_log():
    changes = records(LEGAL_V2, "changes.jsonl")
    assert [c["change_id"] for c in changes] == [f"c{i:02d}" for i in range(1, len(changes) + 1)]
    for c in changes:
        # D1-D8, or "review" for a change made at the owner's review (plan §3.5).
        assert c["decision"] in {f"D{n}" for n in range(1, 9)} or (
            c["decision"] == "review" and c["basis"] == "owner"), c["change_id"]
        assert c["basis"] in ("owner", "derived", "natural_pool"), c["change_id"]
        assert c["reason"].strip(), c["change_id"]
        # The owner has decided every change except the natural-pool judgments.
        assert (c["owner_decision"] is None) == (c["basis"] == "natural_pool"), c["change_id"]

    expected = {judgment_key(j): {k: v for k, v in j.items() if k != "provenance"}
                for j in records(LEGAL_V1, "judgments.jsonl")}
    questions = {q["query_id"]: {k: v for k, v in q.items() if k != "provenance"}
                 for q in records(LEGAL_V1, "questions.jsonl")}
    for c in changes:
        if c["record"] == "question":
            current = questions[c["query_id"]]
            assert {k: current.get(k) for k in c["before"]} == c["before"], c["change_id"]
            current.update(c["after"])
            continue
        key = (c["query_id"], c["instrument"], c["article"], c["point"])
        if c["before"] is None:  # an added judgment
            assert key not in expected, c["change_id"]
            expected[key] = {"query_id": c["query_id"], "instrument": c["instrument"],
                             "article": c["article"],
                             **({"point": c["point"]} if c["point"] else {}), **c["after"]}
            continue
        assert {k: expected[key][k] for k in c["before"]} == c["before"], c["change_id"]
        if c["after"] is None:  # a removed judgment
            del expected[key]
        else:
            expected[key].update(c["after"])
    actual = {judgment_key(j): {k: v for k, v in j.items() if k != "provenance"}
              for j in records(LEGAL_V2, "judgments.jsonl")}
    assert actual == expected
    assert {q["query_id"]: {k: v for k, v in q.items() if k != "provenance"}
            for q in records(LEGAL_V2, "questions.jsonl")} == questions


def test_the_q14_article_55_decision_is_on_record():
    [c14] = [c for c in records(LEGAL_V2, "changes.jsonl") if c["change_id"] == "c14"]
    assert (c14["query_id"], c14["instrument"], c14["article"], c14["after"]["grade"]) == (
        "q14", G, "55", 0)
    assert "grade 0" in c14["owner_decision"] and c14["reason"].strip()


# C3: grade consistency

GRADES = {  # the approved v2 grades (plan sections 0 and 2): question, instrument, article, point
    ("q02", G, "32", None): 0, ("q02", G, "33", None): 0, ("q02", G, "34", None): 0,  # c01-c03
    ("q03", G, "6", None): 0, ("q05", G, "33", None): 0, ("q06", G, "36", None): 0,  # c04-c06
    ("q11", G, "12", None): 1, ("q11", G, "19", None): 0, ("q13", G, "6", None): 1,  # c07-c09
    ("q20", G, "84", None): 0,  # c10
    ("q04", G, "55", None): 1, ("q05", G, "4", "12"): 1, ("q13", G, "12", None): 1,  # c11-c13
    ("q14", G, "55", None): 0,  # c14
    ("q17", G, "4", "13"): 1, ("q17", G, "4", "14"): 1, ("q17", G, "4", "15"): 1,  # c16-c18
    ("q03", G, "9", None): 0, ("q04", G, "34", None): 0, ("q17", C, "107", None): 0,  # D3, D5
    ("q18", G, "8", None): 2, ("q18", C, "2-quinquies", None): 2, ("q20", C, "167", None): 0,
    ("q03", G, "8", None): 1, ("q03", C, "2-quinquies", None): 1,  # U4
    ("q17", C, "2-sexies", None): 1, ("q17", C, "2-septies", None): 1,  # U5
    # Gate 2 (2026-11-12): the 12 uncertain judgments, q15 Code Art. 154-bis, the restrictions
    ("q06", G, "9", None): 1, ("q06", C, "110", None): 1, ("q13", C, "2-undecies", None): 1,
    ("q15", C, "166", None): 1, ("q15", C, "144", None): 0, ("q15", C, "143", None): 0,
    ("q15", C, "154-ter", None): 0, ("q04", G, "51", None): 0, ("q09", C, "111-bis", None): 0,
    ("q17", C, "75", None): 0, ("q19", G, "12", None): 0, ("q20", G, "58", None): 0,
    ("q15", C, "154-bis", None): 0, ("q05", G, "23", None): 1,
    ("q15", G, "58", None): 2, ("q15", G, "83", None): 1, ("q15", C, "157", None): 1,
    ("q15", C, "158", None): 1,  # the other q15 judgments, unchanged
    **{(q, G, "23", None): 1 for q in ("q09", "q10", "q11", "q12", "q13")},
    **{(q, C, "2-undecies", None): 1 for q in ("q10", "q11", "q12")},
    **{(q, C, "2-duodecies", None): 1 for q in ("q05", "q09", "q10", "q11", "q12", "q13")},
}

# The records the owner reviewed at Gate 2 (2026-11-12), and only these, are owner_reviewed.
GATE2_REVIEWED = {
    ("q06", G, "9"), ("q06", C, "110"), ("q13", C, "2-undecies"), ("q15", C, "166"),
    ("q15", C, "144"), ("q15", C, "143"), ("q15", C, "154-ter"), ("q04", G, "51"),
    ("q09", C, "111-bis"), ("q17", C, "75"), ("q19", G, "12"), ("q20", G, "58"),  # the 12
    ("q15", C, "154-bis"), ("q05", G, "23"),
    *((q, G, "23") for q in ("q09", "q10", "q11", "q12", "q13")),
    *((q, C, "2-undecies") for q in ("q10", "q11", "q12")),
    *((q, C, "2-duodecies") for q in ("q05", "q09", "q10", "q11", "q12", "q13")),
}


def test_legal_v2_has_the_approved_grades():
    grades = {judgment_key(j): j["grade"] for j in records(LEGAL_V2, "judgments.jsonl")}
    assert {key: grades.get(key) for key in GRADES} == GRADES
    assert ("q17", G, "4", None) not in grades  # c15: recorded as its points
    # Rule 4: the same provision, the same kind of question, the same grade.
    assert [grades[(q, G, "12", None)] for q in ("q10", "q11", "q12", "q13")] == [1, 1, 1, 1]
    assert grades[("q04", G, "4", "12")] == grades[("q05", G, "4", "12")] == 1


def test_legal_v2_never_says_article_55_names_the_garante():
    for j in records(LEGAL_V2, "judgments.jsonl"):
        if (j["instrument"], j["article"]) == (G, "55"):
            assert "Garante" not in j["rationale"], j["query_id"]


def test_legal_v2_expected_outcomes_agree_with_the_judgments():
    best = {}
    for j in records(LEGAL_V2, "judgments.jsonl"):
        best[j["query_id"]] = max(best.get(j["query_id"], 0), j["grade"])
    for q in records(LEGAL_V2, "questions.jsonl"):
        assert (best[q["query_id"]] == 2) == (q["expected_outcome"] == "answerable"), q["query_id"]
        if q["expected_outcome"] != "answerable":
            assert best[q["query_id"]] == 0, q["query_id"]


# C4: the pool


def test_legal_v2_judges_exactly_its_pool():
    v1_pool = {r["query_id"]: r for r in records(LEGAL_V1, "pool.jsonl")}
    judged = {}
    for j in records(LEGAL_V2, "judgments.jsonl"):
        judged.setdefault(j["query_id"], set()).add(f"{j['instrument']}:{j['article']}")
    for row in records(LEGAL_V2, "pool.jsonl"):
        q, v1 = row["query_id"], v1_pool[row["query_id"]]
        assert set(row) == {"query_id", "bm25", "dense", "hybrid", "judge_added", "natural"}, q
        assert set(row["natural"]) == {"bm25", "dense", "hybrid"}, q
        assert all(row[m] == v1[m] for m in ("bm25", "dense", "hybrid")), q  # technical, unchanged
        assert row["judge_added"][:len(v1["judge_added"])] == v1["judge_added"], q
        assert all(0 < len(row["natural"][m]) <= 10 for m in ("bm25", "dense", "hybrid")), q
        pooled = {*row["bm25"], *row["dense"], *row["hybrid"],
                  *(a for m in ("bm25", "dense", "hybrid") for a in row["natural"][m]),
                  *(added.split(" point ")[0] for added in row["judge_added"])}
        assert judged[q] == pooled, q
    added = {r["query_id"]: r["judge_added"][len(v1_pool[r["query_id"]]["judge_added"]):]
             for r in records(LEGAL_V2, "pool.jsonl")}
    assert {q: a for q, a in added.items() if a} == {  # Phase 2 additions, then Gate 2 additions
        "q04": [f"{G}:55"], "q05": [f"{G}:4 point 12", f"{C}:2-duodecies"],
        "q09": [f"{G}:23", f"{C}:2-duodecies"],
        **{q: [f"{G}:23", f"{C}:2-undecies", f"{C}:2-duodecies"] for q in ("q10", "q11", "q12")},
        "q13": [f"{G}:12", f"{G}:23", f"{C}:2-duodecies"], "q14": [f"{G}:55"]}


# C5: scenario isolation, and the no-copying check N1-N6


def words(text):
    text = (text or "").lower().replace("’", "'").replace("'", " ")
    return re.findall(r"[a-zà-ù0-9]+", text)


def grams(tokens, n=4):
    return {tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def test_legal_v2_natural_queries_are_distinct_from_the_technical_ones():
    questions = {q.query_id: q for q in pe.load_benchmark(LEGAL_V2).questions}
    for q in questions.values():
        natural, technical = q.queries("natural"), q.queries("technical")
        assert len(natural) == len(technical), q.query_id  # N6 (the count)
        for text in natural:
            assert text not in technical, q.query_id  # N4
            assert not any(grams(words(text)) & grams(words(t)) for t in technical), q.query_id
            assert set(re.findall(r"\d+", text)) <= set(re.findall(r"\d+", q.question)), (
                q.query_id)  # N5
    # The two queries the owner edited at Gate 1.
    assert questions["q19"].search_queries_it_natural[1] == (
        "chi può esercitare i diritti privacy dopo la morte di una persona")
    assert questions["q20"].search_queries_it_natural[1] == (
        "criteri per stabilire l'importo di una sanzione privacy")


def test_legal_v2_natural_queries_copy_no_heading_or_judged_point():
    explorer = recorded_explorer()
    benchmark = pe.load_benchmark(LEGAL_V2)
    store = explorer.store

    def point_text(instrument, article, point):
        provision = store.lookup(instrument, article)
        text = "".join(p["text"] for p in explorer.provision_view(provision)["text"])
        found = re.search(rf"(?m)^\s*{point}\)\s(.*?)(?=^\s*\d+\)\s|\Z)", text, re.S)
        assert found, (instrument, article, point)
        return found.group(1)

    for q in benchmark.questions:
        judgments = [j for j in benchmark.judgments if j.query_id == q.query_id]
        headings = [words(re.sub(r"[()]", " ", store.lookup(j.instrument, j.article).title or ""))
                    for j in judgments if j.grade >= 1]
        points = [words(point_text(j.instrument, j.article, j.point)) for j in judgments if j.point]
        for text in q.search_queries_it_natural:
            tokens = words(text)
            for heading in headings:
                if len(heading) >= 4:  # N1
                    assert not grams(tokens) & grams(heading), (q.query_id, text)
                elif len(heading) >= 2:  # N2
                    assert not any(tokens[i:i + len(heading)] == heading
                                   for i in range(len(tokens))), (q.query_id, text)
            for point in points:  # N3
                assert not grams(tokens) & grams(point), (q.query_id, text)


# C6: provenance and review status


def test_only_the_gate_2_records_are_owner_reviewed():
    assert len(GATE2_REVIEWED) == 28
    for j in records(LEGAL_V2, "judgments.jsonl"):
        provenance, key = j["provenance"], (j["query_id"], j["instrument"], j["article"])
        if key in GATE2_REVIEWED and "point" not in j:
            assert (provenance["review_status"], provenance["reviewed_by"],
                    provenance["reviewed_on"]) == ("owner_reviewed", "Simone Zanetti", "2026-11-12"), key
        else:  # every other record is still an unreviewed candidate
            assert provenance["review_status"] == "candidate", key
            assert provenance.get("reviewed_by") is None and provenance.get("reviewed_on") is None
    for q in records(LEGAL_V2, "questions.jsonl"):
        assert q["provenance"]["review_status"] == "candidate", q["query_id"]


def test_legal_v2_provenance_follows_its_changes():
    review_fields = ("review_status", "reviewed_by", "reviewed_on")
    v1 = {judgment_key(j): j for j in records(LEGAL_V1, "judgments.jsonl")}
    changed = {}
    for c in records(LEGAL_V2, "changes.jsonl"):
        if c["record"] == "judgment":
            changed.setdefault((c["query_id"], c["instrument"], c["article"], c["point"]), []).append(c)
    unchanged = 0
    for j in records(LEGAL_V2, "judgments.jsonl"):
        provenance, key = j["provenance"], judgment_key(j)
        lines = changed.get(key)
        if not lines:  # carried over from v1: its drafting fields unchanged
            drafting = {k: v for k, v in provenance.items() if k not in review_fields}
            assert drafting == {k: v for k, v in v1[key]["provenance"].items()
                                if k not in review_fields}, key
            if key[:3] not in GATE2_REVIEWED:
                assert provenance == v1[key]["provenance"], key  # the v1 object, unchanged
            unchanged += 1
        elif lines[-1]["decision"] == "review":
            assert "at Gate 2" in provenance["drafted_by"], key
        elif lines[-1]["basis"] == "natural_pool":
            assert "natural-query pool" in provenance["drafted_by"], key
        else:
            assert "revised from legal v1" in provenance["drafted_by"], key
    assert unchanged == 388 - 10 - 21 - 1  # less the regraded, reworded and removed records
    for q in records(LEGAL_V2, "questions.jsonl"):
        assert "natural queries and v2 changes" in q["provenance"]["drafted_by"], q["query_id"]


def test_the_gate_2_review_lines():
    review = [c for c in records(LEGAL_V2, "changes.jsonl") if c["decision"] == "review"]
    assert [c["change_id"] for c in review] == [f"c{n}" for n in range(332, 349)]
    assert all(c["basis"] == "owner" and "Gate 2" in c["owner_decision"] for c in review)
    regrades = {(c["query_id"], c["article"]): (c["before"]["grade"], c["after"]["grade"])
                for c in review if c["before"] and "grade" in c["before"]}
    assert regrades == {("q06", "110"): (0, 1), ("q15", "154-bis"): (1, 0)}
    added = [(c["query_id"], c["instrument"], c["article"]) for c in review if c["before"] is None]
    assert len(added) == len(set(added)) == 14 and all(
        c["after"]["grade"] == 1 for c in review if c["before"] is None)
    [q09_23] = [c for c in review if (c["query_id"], c["article"]) == ("q09", "23")]
    assert "Arts. 12-22, the scope of Art. 23(1)" in q09_23["reason"]
    judgments = records(LEGAL_V2, "judgments.jsonl")
    assert len(judgments) == 673
    assert {g: sum(j["grade"] == g for j in judgments) for g in (0, 1, 2)} == {0: 603, 1: 47, 2: 23}


# C7: D6, textual relevance of the transcription, not legal validity


def test_legal_v2_rationales_keep_relevance_apart_from_validity():
    for j in records(LEGAL_V2, "judgments.jsonl"):
        if j["instrument"] == C and j["grade"] >= 1:
            assert j["rationale"].startswith("In the transcription:"), judgment_key(j)
        assert not re.search(r"verified|current law|vigente|is in force", j["rationale"],
                             re.I), judgment_key(j)


# C9: the v1 hashes v2 derives from


def test_the_legal_v2_readme_names_the_v1_files_it_derives_from():
    readme = (LEGAL_V2 / "README.md").read_text(encoding="utf-8")
    for digest in LEGAL_V1_SHA256.values():
        assert digest in readme


# C10: legal-v2 is frozen (Gate 3, 2026-11-12)


def test_legal_v2_files_are_unchanged():
    assert sorted(p.name for p in LEGAL_V2.iterdir()) == sorted(LEGAL_V2_SHA256)
    for name, digest in LEGAL_V2_SHA256.items():
        assert hashlib.sha256((LEGAL_V2 / name).read_bytes()).hexdigest() == digest, name


# C8: deterministic real reports (after the freeze)


@pytest.mark.parametrize("scenario", ["technical", "natural"])
def test_legal_v2_reports_are_deterministic(scenario):
    try:
        find_recorded_build()
    except ExplorerError as exc:
        pytest.skip(f"recorded build unavailable: {exc}")
    first = pe.run(LEGAL_V2, scenario=scenario)
    second = pe.run(LEGAL_V2, scenario=scenario)
    same = first == second  # the whole report; no field is excluded
    assert same, f"two {scenario} reports of legal-v2 differ"  # equality only: no value is shown
