"""Provision-level retrieval evaluation (src/provision_eval.py), on a SYNTHETIC act.

The act, the Atto sintetico di Corvalle, is invented. It is built in a temporary directory by
the project's own build, anchor and link steps, and its benchmark is
tests/fixtures/synthetic_provision_eval/. Every number here tests the evaluator, not legal
retrieval quality. One test reads the recorded build, with a small test-only benchmark.
"""

import hashlib
import json
import math
import re
import shutil
from pathlib import Path

import pymupdf
import pytest

import src.provision_eval as pe
from src.config import PROJECT_ROOT
from src.corpus_build import parse_spec, run_build
from src.corpus_identity import (
    CodeVersion,
    CodeVersionError,
    current_dependency_versions,
    file_sha256,
)
from src.provision_anchors import write_passage_links, write_segment_maps
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.provisions import (
    Instrument,
    Marker,
    Provision,
    ProvisionStore,
    Registry,
    Review,
    SegmentationRules,
    SourceStatus,
    StructuralStatus,
    Version,
)
from src.retrieval_eval import EvaluationDataError

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_provision_eval"
INSTRUMENT = "syn-corvalle"
VERSION = f"{INSTRUMENT}@synthetic-v1"
CLEAN = CodeVersion.clean("0" * 40)
PAGES = [
    ["CORVALLE 1", "ATTO SINTETICO DI CORVALLE (ATTO FITTIZIO)", "IL CONSIGLIO DI CORVALLE,",
     "considerando quanto segue:",
     "(1) La segnalazione tempestiva degli incidenti nel registro tutela gli utenti.",
     "(2) Il registro pubblico dei fari deve essere custodito con cura.",
     "(3) Le sanzioni per la mancata segnalazione devono essere proporzionate.",
     "HA ADOTTATO IL PRESENTE ATTO:"],
    ["CORVALLE 2", "Art. 1", "(Segnalazione degli incidenti)",
     "1. Il custode del registro segnala ogni incidente all'Ufficio dei fari.",
     "2. La segnalazione avviene entro quarantotto ore dalla scoperta.",
     "3. La segnalazione indica la natura dell'incidente e le misure adottate.",
     "4. Il custode conserva una copia della segnalazione per cinque anni.",
     "5. La segnalazione non è dovuta per gli incidenti senza conseguenze."],
    ["CORVALLE 3", "Art. 2", "(Avviso agli utenti)",
     "1. Se l'incidente espone dati riservati, il custode avvisa gli utenti.",
     "Art. 3", "(Ufficio dei fari)",
     "1. L'Ufficio dei fari riceve le segnalazioni e vigila sul registro.",
     "Art. 4", "(Sanzioni)", "1. La mancata segnalazione è punita con una sanzione pecuniaria."],
    ["CORVALLE 4", "Art. 5", "(Definizioni)",
     "1) «registro»: l'elenco pubblico dei fari di Corvalle;",
     "2) «incidente»: ogni guasto che spegne un faro."],
]
ARTICLES = (("1", 2), ("2", 3), ("3", 3), ("4", 3), ("5", 4))  # label, page


def art(label):
    return f"{VERSION}/body/article:{label}"


def _provision(label, page, sha):
    return Provision(
        provision_id=art(label), version_id=VERSION, instrument_id=INSTRUMENT, kind="article",
        label_as_printed=label, normalised_label=label, heading_as_printed=f"Art. {label}",
        title=None, status_marker=None, parent_id=None, path=f"Art. {label}", page_start=page,
        page_end=page, structural_status=StructuralStatus.AUTO_UNREVIEWED,
        review=Review("pending_human_review"),
        source_status_representation=SourceStatus.NO_STATUS_REPRESENTATION,
        inventory_id="synthetic", inventory_ref=f"synthetic:art:{label}",
        inventory_sha256="0" * 64, source_sha256=sha, doc_id="doc-" + sha[:16], notes=())


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    """(build directory, store) of the synthetic act."""
    root = tmp_path_factory.mktemp("corvalle")
    pdf = pymupdf.open()
    for lines in PAGES:
        page = pdf.new_page()
        for i, line in enumerate(lines):
            page.insert_text((72, 72 + 60 * i), line)  # far apart: one text block per line
    (root / "src").mkdir()
    pdf.save(root / "src" / "act.pdf")
    pdf.close()
    sha = file_sha256(root / "src" / "act.pdf")
    markers = (Marker("preamble", "IL CONSIGLIO DI CORVALLE,"),
               Marker("recitals", "considerando quanto segue:"),
               Marker("enacting_formula", "HA ADOTTATO IL PRESENTE ATTO:"))
    version = Version(VERSION, INSTRUMENT, "original_publication", "synthetic act", "it", None,
                      None, None, SourceStatus.NO_STATUS_REPRESENTATION, "synthetic", sha,
                      SegmentationRules((r"CORVALLE \d+",), len(PAGES), markers, None, None))
    registry = Registry((Instrument(INSTRUMENT, "law", "fictional",
                                    ("atto sintetico di corvalle",), None),), (version,), "1" * 64)
    store = ProvisionStore(registry, [_provision(label, page, sha) for label, page in ARTICLES],
                           ())
    spec = parse_spec({
        "schema_version": 1, "name": "corvalle", "description": "synthetic", "chunk_size": 200,
        "chunk_overlap": 30, "assembly_format": "concatenated-jsonl/1",
        "sources": [{"version_id": VERSION, "path": "src/act.pdf", "sha256": sha,
                     "end_before": None}],
    }, "corvalle.json")
    build = run_build(spec, detect_code=lambda: CLEAN, output_root=root / "builds",
                      recorded_root=root / "builds", base_dir=root,
                      dependencies=current_dependency_versions())
    write_segment_maps(build.directory, store=store, registry=registry, detect_code=lambda: CLEAN,
                       base_dir=root)
    write_passage_links(build.directory, store=store, registry=registry, base_dir=root)
    return build.directory, store


@pytest.fixture(scope="module")
def explorer(corpus):
    build_dir, store = corpus
    return ProvisionExplorer.open(build_dir, store=store)


@pytest.fixture(scope="module")
def report(corpus):
    build_dir, store = corpus
    return pe.run(FIXTURE, build_dir, store=store, detect_code=lambda: CLEAN)


def entry(report, query_id):
    [found] = [e for e in report["per_query"] if e["query_id"] == query_id]
    return found


def labels(e):
    return [r["label"] for r in e["ranking"]]


# --- The fixture -------------------------------------------------------------------------------


def test_the_fixture_is_a_synthetic_benchmark():
    benchmark = pe.load_benchmark(FIXTURE)
    assert (benchmark.kind, len(benchmark.questions), len(benchmark.judgments)) == (
        "synthetic", 8, 16)
    assert {x.provenance.review_status for x in (*benchmark.questions, *benchmark.judgments)} == {
        "synthetic"}
    for name, info in benchmark.files.items():
        assert info["sha256"] == hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest()


def test_the_report_is_labelled_synthetic(report):
    assert report["label"] == pe.SYNTHETIC_LABEL
    assert report["benchmark"]["kind"] == "synthetic"
    assert "SYNTHETIC BENCHMARK" in pe.format_summary(report)


# --- Ranking: the production search, mapped to articles ----------------------------------------


def test_a_single_query_ranking_is_the_search_result_unchanged(explorer):
    query = "segnalazione incidente entro quarantotto ore"
    ranking, _ = pe.rank_articles(explorer, [query], 20)
    assert [r.provision_id for r in ranking] == [
        p["provision_id"] for p in explorer.search(query, top_k=20)["provisions"]]


def test_an_article_in_several_chunks_counts_once_at_its_best_rank(report, explorer):
    chunks = explorer.search("segnalazione incidente entro quarantotto ore", top_k=20)["results"]
    assert [r["rank"] for r in chunks if [e["label"] for e in r["evidence"]] == ["1"]] == [1, 2, 5]
    e = entry(report, "s01")
    assert labels(e) == ["1", "2", "5", "4"]
    assert (e["ranking"][0]["chunk_rank"], labels(e).count("1")) == (1, 1)


def test_recitals_and_other_context_take_no_position(report):
    e = entry(report, "s04")  # the top chunk is a recital
    assert e["searches"][0]["context_only_chunks"] >= 1
    assert e["ranking"][0] == {"position": 1, "provision_id": art("5"),
                               "instrument_id": INSTRUMENT, "label": "5", "query": 1,
                               "chunk_rank": 2, "grade": 2}
    assert all(r["provision_id"].startswith(f"{VERSION}/body/article:")
               for q in report["per_query"] for r in q["ranking"])


def test_several_queries_are_interleaved_by_rank(report):
    e = entry(report, "s03")
    assert [(r["label"], r["query"], r["chunk_rank"]) for r in e["ranking"]] == [
        ("1", 1, 1), ("2", 1, 2), ("3", 1, 4), ("4", 2, 4), ("5", 1, 5)]


def test_an_empty_retrieval_scores_zero(report):
    e = entry(report, "s07")
    assert e["ranking_length"] == 0 and e["searches"][0]["chunks"] == 0
    assert set(e["metrics"].values()) == {0.0}


# --- Metrics -----------------------------------------------------------------------------------

L2, L3, L4, L5 = (math.log2(n) for n in (2, 3, 4, 5))
EXPECTED = {
    # ranking [1, 2, 5, 4]; relevant Art. 1 (2) and Art. 3 (1, not retrieved)
    "s01": (1 / 2, 1 / 2, 1 / 2, 1.0, (2 / L2) / (2 / L2 + 1 / L3)),
    # ranking [3, 1, 5]; Art. 3 (2), Art. 1 (1), Art. 4 (0)
    "s02": (1 / 2, 1.0, 1.0, 1.0, 1.0),
    # ranking [1, 2, 3, 4, 5]; Art. 1 (2), Art. 2 (2), Art. 4 (1); Art. 3 unjudged
    "s03": (1 / 3, 1.0, 1.0, 1.0,
            (2 / L2 + 2 / L3 + 1 / L5) / (2 / L2 + 2 / L3 + 1 / L4)),
    # ranking [5, 3, 1]; Art. 5 (2, from its point judgment), Art. 3 (0)
    "s04": (1.0, 1.0, 1.0, 1.0, 1.0),
    # empty ranking; Art. 2 (2)
    "s07": (0.0, 0.0, 0.0, 0.0, 0.0),
    # ranking [5, 2, 1]; Art. 5 (2), Art. 1 (1); Art. 2 unjudged
    "s08": (1 / 2, 1.0, 1.0, 1.0, (2 / L2 + 1 / L4) / (2 / L2 + 1 / L3)),
}
NAMES = ("recall@1", "recall@5", "recall@10", "mrr@10", "ndcg@10")


@pytest.mark.parametrize("query_id", sorted(EXPECTED))
def test_metrics_match_hand_computed_values(report, query_id):
    assert entry(report, query_id)["metrics"] == pytest.approx(
        dict(zip(NAMES, EXPECTED[query_id])))


def test_means_are_over_scored_questions_overall_and_by_split(report):
    def mean(ids):
        return {name: pytest.approx(sum(EXPECTED[q][i] for q in ids) / len(ids))
                for i, name in enumerate(NAMES)}

    assert report["means"] == {"questions": 6, **mean(sorted(EXPECTED))}
    assert report["means_by_split"] == {"dev": {"questions": 4, **mean(["s01", "s02", "s03",
                                                                          "s04"])},
                                        "test": {"questions": 2, **mean(["s07", "s08"])}}


def test_a_point_and_its_article_count_once_at_the_higher_grade(report):
    e = entry(report, "s04")
    assert e["judged_articles"] == 2 and e["relevant_articles"] == 1
    assert e["ranking"][0]["grade"] == 2


def test_questions_without_relevant_judgments_are_listed_not_scored(report):
    assert report["questions_skipped"] == ["s05", "s06"]
    assert entry(report, "s05")["skipped"] == "no judgment with grade >= 1"
    assert entry(report, "s06")["skipped"] == "no judgments for this question"
    assert "metrics" not in entry(report, "s05") and entry(report, "s05")["ranking"]


def test_short_rankings_and_unjudged_articles_are_warned_about(report):
    [short, unjudged] = report["warnings"]
    assert short.startswith("6 of 6 scored questions rank fewer than 10 articles")
    assert unjudged.startswith("8 retrieved articles in the top 10 of scored questions have no "
                               "judgment")
    assert entry(report, "s01")["unjudged_in_top10"] == 3


# --- Validation --------------------------------------------------------------------------------


def records(name):
    text = (FIXTURE / name).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def copy_with(tmp_path, *, manifest=None, questions=None, judgments=None):
    directory = tmp_path / "benchmark"
    shutil.copytree(FIXTURE, directory)
    if manifest is not None:
        (directory / "benchmark.json").write_text(json.dumps(manifest), encoding="utf-8")
    for name, rows in (("questions.jsonl", questions), ("judgments.jsonl", judgments)):
        if rows is not None:
            (directory / name).write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return directory


def changed(rows, index, **fields):
    rows = [dict(r) for r in rows]
    rows[index].update(fields)
    return rows


REVIEWED = {"drafted_by": "x", "drafted_on": "2026-11-11", "review_status": "owner_reviewed",
            "reviewed_by": "A. Owner", "reviewed_on": "2026-11-12"}


@pytest.mark.parametrize(("kind", "rows", "message"), [
    ("questions", lambda q: q + [q[0]], "duplicate query_id 's01'"),
    ("questions", lambda q: changed(q, 0, search_queries_it=["notification of the breach"]),
     "is English, not Italian"),
    ("questions", lambda q: changed(q, 0, search_queries_it=[]), "non-empty list"),
    ("questions", lambda q: changed(q, 0, category="tax"), "'category' must be one of"),
    ("questions", lambda q: changed(q, 0, split="train"), "'split' must be one of"),
    ("questions", lambda q: changed(q, 0, expected_outcome="maybe"), "'expected_outcome'"),
    ("questions", lambda q: changed(q, 0, query_id="s 01"), "may contain only"),
    ("judgments", lambda j: changed(j, 0, query_id="s99"), "unknown query_id 's99'"),
    ("judgments", lambda j: changed(j, 0, grade=3), "'grade' must be one of [0, 1, 2]"),
    ("judgments", lambda j: changed(j, 0, grade=True), "'grade' must be one of"),
    ("judgments", lambda j: changed(j, 0, point=2), "'point' must be null or"),
    ("judgments", lambda j: j + [j[0]], "duplicate judgment"),
    ("judgments", lambda j: changed(j, 0, rationale=" "), "'rationale' must be a non-empty"),
    ("judgments", lambda j: changed(j, 0, chunk_id="doc-1"), "unknown key(s) ['chunk_id']"),
    ("judgments", lambda j: changed(j, 0, provenance={**j[0]["provenance"],
                                                      "reviewed_by": "A. Owner"}),
     "'reviewed_by' must be null for 'synthetic'"),
    ("judgments", lambda j: changed(j, 0, provenance=REVIEWED),
     "review_status 'synthetic' is required in a synthetic benchmark"),
    ("judgments", lambda j: changed(j, 0, provenance={**j[0]["provenance"],
                                                      "drafted_on": "11/11/2026"}),
     "'drafted_on' must be a date"),
])
def test_malformed_benchmarks_are_rejected(tmp_path, kind, rows, message):
    directory = copy_with(tmp_path, **{kind: rows(records(f"{kind}.jsonl"))})
    with pytest.raises(EvaluationDataError, match=message.replace("[", r"\[").replace("(", r"\(")
                       .replace(")", r"\)")):
        pe.load_benchmark(directory)


def test_review_statuses_must_match_the_benchmark_kind(tmp_path):
    manifest = {**json.loads((FIXTURE / "benchmark.json").read_text()), "kind": "real"}
    with pytest.raises(EvaluationDataError, match="allowed only there"):
        pe.load_benchmark(copy_with(tmp_path, manifest=manifest))


def test_reviewed_records_need_a_reviewer_and_a_date(tmp_path):
    manifest = {**json.loads((FIXTURE / "benchmark.json").read_text()), "kind": "real"}
    questions = [{**q, "provenance": REVIEWED} for q in records("questions.jsonl")]
    judgments = [{**j, "provenance": {k: v for k, v in REVIEWED.items() if k != "reviewed_on"}}
                 for j in records("judgments.jsonl")]
    directory = copy_with(tmp_path, manifest=manifest, questions=questions, judgments=judgments)
    with pytest.raises(EvaluationDataError, match="'owner_reviewed' requires 'reviewed_on'"):
        pe.load_benchmark(directory)


@pytest.mark.parametrize("version", [3, True, "2"])  # schema 2 is valid since P2.2
def test_the_manifest_is_checked(tmp_path, version):
    manifest = {**json.loads((FIXTURE / "benchmark.json").read_text()), "schema_version": version}
    with pytest.raises(EvaluationDataError, match=re.escape("schema_version must be one of [1, 2]")):
        pe.load_benchmark(copy_with(tmp_path, manifest=manifest))
    with pytest.raises(FileNotFoundError, match="no benchmark at"):
        pe.load_benchmark(tmp_path / "nowhere")


def test_unknown_references_are_all_reported_at_once(tmp_path, explorer):
    judgments = records("judgments.jsonl")
    judgments[0]["instrument"] = "atto sintetico di corvalle"  # an alias, not the ID
    judgments[1]["instrument"] = "gdpr"  # not in this store
    judgments[2]["article"] = "99"
    judgments[3]["article"] = "1."  # found by normalisation, but not as printed
    judgments[8]["point"] = "7"  # Art. 5 has points 1) and 2) only
    benchmark = pe.load_benchmark(copy_with(tmp_path, judgments=judgments))
    with pytest.raises(EvaluationDataError) as caught:
        pe.evaluate(benchmark, explorer)
    message = str(caught.value)
    for expected in ("line 1: unknown instrument 'atto sintetico di corvalle'; use its "
                     "instrument ID 'syn-corvalle'",
                     "line 2: unknown instrument 'gdpr'",
                     "line 3: syn-corvalle has no article '99'",
                     "line 4: write the article label as printed, '1', not '1.'",
                     "line 9: syn-corvalle art. 5 has no point 7)"):
        assert expected in message


def test_the_chunk_depth_must_be_positive(explorer):
    with pytest.raises(ValueError, match="chunk_depth"):
        pe.evaluate(pe.load_benchmark(FIXTURE), explorer, chunk_depth=0)


# --- Reproducibility ---------------------------------------------------------------------------


def test_the_report_records_what_the_result_rests_on(report, explorer):
    identity = explorer.identity()
    assert report["report"] == pe.REPORT
    assert report["benchmark"]["files"] == pe.load_benchmark(FIXTURE).files
    assert report["benchmark"]["version"] == "1"
    assert (report["corpus"]["build_id"], report["corpus"]["corpus_sha256"]) == (
        identity["build_id"], identity["corpus_sha256"])
    assert report["code"] == {"available": True, **CLEAN.to_record()}
    assert (report["retrieval"]["chunk_depth"], report["retrieval"]["ask_chunk_depth"]) == (20, 5)
    assert report["metrics"]["names"] == list(NAMES)


def test_a_missing_code_version_is_reported_not_invented(corpus):
    def no_git():
        raise CodeVersionError("not a Git repository")

    build_dir, store = corpus
    result = pe.run(FIXTURE, build_dir, store=store, detect_code=no_git)
    assert result["code"] == {"available": False, "reason": "not a Git repository"}


def test_the_evaluation_is_deterministic_and_changes_nothing(corpus, report):
    build_dir, store = corpus

    def digest():
        return {p.relative_to(build_dir).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(build_dir.rglob("*")) if p.is_file()}

    before = digest()
    assert pe.run(FIXTURE, build_dir, store=store, detect_code=lambda: CLEAN) == report
    assert digest() == before


# --- Command line ------------------------------------------------------------------------------


@pytest.fixture
def cli_store(corpus, monkeypatch):
    build_dir, store = corpus
    monkeypatch.setattr(pe, "load_store", lambda: store)
    monkeypatch.setattr(pe, "detect_code_version", lambda root: CLEAN)
    return build_dir


def test_the_cli_writes_json_and_prints_a_labelled_summary(cli_store, tmp_path, capsys, report):
    out = tmp_path / "eval" / "report.json"
    code = pe.main(["--benchmark", str(FIXTURE), "--build-dir", str(cli_store),
                    "--output", str(out)])
    printed = capsys.readouterr().out
    assert code == 0
    assert json.loads(out.read_text(encoding="utf-8")) == report
    assert pe.SYNTHETIC_LABEL in printed and "all (6)" in printed
    assert "s05        test  not scored: no judgment with grade >= 1" in printed


def test_the_cli_can_print_the_json_report(cli_store, capsys, report):
    assert pe.main(["--benchmark", str(FIXTURE), "--build-dir", str(cli_store), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == report


def test_the_cli_exits_1_when_nothing_can_be_scored(cli_store, tmp_path, capsys):
    judgments = [{**j, "grade": 0} for j in records("judgments.jsonl")]
    directory = copy_with(tmp_path, judgments=judgments)
    assert pe.main(["--benchmark", str(directory), "--build-dir", str(cli_store)]) == 1
    assert "scored: 0 of 8" in capsys.readouterr().out


def test_the_cli_exits_2_on_a_missing_benchmark(cli_store, tmp_path, capsys):
    assert pe.main(["--benchmark", str(tmp_path / "none"), "--build-dir", str(cli_store)]) == 2
    assert "error: no benchmark at" in capsys.readouterr().err


# --- Query scenarios (schema 2) ----------------------------------------------------------------

# A second wording of each question's search, as invented as the act. s07's technical query finds
# nothing; its natural one finds Art. 2, the article the question needs.
NATURAL = {
    "s01": ["termine per segnalare un guasto"],
    "s02": ["chi raccoglie le segnalazioni"],
    "s03": ["doveri del custode", "copia da conservare"],
    "s04": ["nozione di registro"],
    "s05": ["tasse sui fari"],
    "s06": ["basilico in vaso"],
    "s07": ["avviso agli utenti se i dati riservati sono esposti"],
    "s08": ["nozione di incidente"],
}


def schema_2(tmp_path, *, schema_version=2, question=lambda q: q):
    """The fixture as a schema-2 benchmark: each question also has NATURAL queries."""
    manifest = {**json.loads((FIXTURE / "benchmark.json").read_text(encoding="utf-8")),
                "schema_version": schema_version}
    questions = [{**q, "search_queries_it_natural": NATURAL[q["query_id"]]}
                 for q in records("questions.jsonl")]
    questions[0] = question(questions[0])
    return copy_with(tmp_path, manifest=manifest, questions=questions)


@pytest.fixture(scope="module")
def schema_2_dir(tmp_path_factory):
    return schema_2(tmp_path_factory.mktemp("schema-2"))


@pytest.fixture(scope="module")
def technical_report(corpus, schema_2_dir):
    build_dir, store = corpus
    return pe.run(schema_2_dir, build_dir, store=store, detect_code=lambda: CLEAN,
                  scenario="technical")


@pytest.fixture(scope="module")
def natural_report(corpus, schema_2_dir):
    build_dir, store = corpus
    return pe.run(schema_2_dir, build_dir, store=store, detect_code=lambda: CLEAN,
                  scenario="natural")


def test_a_schema_2_benchmark_carries_both_query_lists(schema_2_dir):
    benchmark = pe.load_benchmark(schema_2_dir)
    assert (benchmark.schema_version, benchmark.query_scenarios) == (2, ("technical", "natural"))
    s03 = benchmark.questions[2]
    assert s03.queries("technical") == ("obblighi del custode del registro",
                                        "conservazione della copia della segnalazione")
    assert s03.queries("natural") == ("doveri del custode", "copia da conservare")


def test_a_schema_1_benchmark_has_the_technical_scenario_only(explorer):
    benchmark = pe.load_benchmark(FIXTURE)
    assert (benchmark.schema_version, benchmark.query_scenarios) == (1, ("technical",))
    with pytest.raises(EvaluationDataError, match="question 's01' has no natural queries"):
        benchmark.questions[0].queries("natural")
    with pytest.raises(EvaluationDataError, match=r"has no 'natural' queries; its scenarios: "
                                                  r"\['technical'\]"):
        pe.evaluate(benchmark, explorer, scenario="natural")
    with pytest.raises(ValueError, match="unknown query scenario 'spoken'"):
        pe.evaluate(benchmark, explorer, scenario="spoken")


@pytest.mark.parametrize(("schema_version", "question", "message"), [
    (2, lambda q: {k: v for k, v in q.items() if k != "search_queries_it_natural"},
     "missing key(s) ['search_queries_it_natural']"),
    (1, lambda q: q, "unknown key(s) ['search_queries_it_natural']"),
    (2, lambda q: {**q, "search_queries_it_natural": []},
     "'search_queries_it_natural' must be a non-empty list of Italian queries"),
    (2, lambda q: {**q, "search_queries_it_natural": ["notification of the breach"]},
     "search query 'notification of the breach' in 'search_queries_it_natural' is English"),
    (2, lambda q: {**q, "search_queries_it_natural": [7]},
     "search query 7 in 'search_queries_it_natural' is not a string"),
])
def test_malformed_natural_queries_are_rejected(tmp_path, schema_version, question, message):
    directory = schema_2(tmp_path, schema_version=schema_version, question=question)
    with pytest.raises(EvaluationDataError) as caught:
        pe.load_benchmark(directory)
    assert "questions.jsonl, line 1: " in str(caught.value) and message in str(caught.value)


def test_each_scenario_searches_with_its_own_queries_only(technical_report, natural_report):
    technical = {q["query_id"]: q["search_queries_it"] for q in records("questions.jsonl")}
    for result, queries in ((technical_report, technical), (natural_report, NATURAL)):
        for e in result["per_query"]:
            assert [s["query"] for s in e["searches"]] == queries[e["query_id"]], e["query_id"]


def test_the_technical_scenario_of_schema_2_gives_the_schema_1_results(technical_report, report):
    for key in ("questions_total", "questions_scored", "questions_skipped", "means",
                "means_by_split", "warnings", "per_query"):
        assert technical_report[key] == report[key], key


def test_natural_metrics_match_hand_computed_values(natural_report, report):
    assert entry(report, "s07")["ranking_length"] == 0  # technical: nothing found
    e = entry(natural_report, "s07")
    # Art. 2, the only relevant article (grade 2), is ranked first.
    assert labels(e)[0] == "2" and e["relevant_articles"] == 1
    assert e["metrics"] == pytest.approx(dict(zip(NAMES, (1.0, 1.0, 1.0, 1.0, 1.0))))


def test_reports_record_the_scenario_and_the_benchmark_schema(report, technical_report,
                                                              natural_report):
    assert pe.REPORT == "provision-retrieval-evaluation/2"
    assert (report["benchmark"]["schema_version"],
            report["benchmark"]["query_scenarios"]) == (1, ["technical"])
    assert (natural_report["benchmark"]["schema_version"],
            natural_report["benchmark"]["query_scenarios"]) == (2, ["technical", "natural"])
    for result, scenario, field in ((report, "technical", "search_queries_it"),
                                    (technical_report, "technical", "search_queries_it"),
                                    (natural_report, "natural", "search_queries_it_natural")):
        assert (result["report"], result["retrieval"]["query_scenario"],
                result["retrieval"]["query_field"]) == (pe.REPORT, scenario, field)
    for section in ("benchmark", "corpus", "code", "metrics"):
        assert technical_report[section] == natural_report[section], section
    assert "query scenario: technical (search_queries_it)" in pe.format_summary(report)
    assert ("query scenario: natural (search_queries_it_natural)"
            in pe.format_summary(natural_report))


def test_a_scenario_run_is_deterministic_and_records_no_time_or_build_path(corpus, schema_2_dir,
                                                                          natural_report, report):
    build_dir, store = corpus
    assert pe.run(schema_2_dir, build_dir, store=store, detect_code=lambda: CLEAN,
                  scenario="natural") == natural_report
    for result in (report, natural_report):
        text = json.dumps(result, ensure_ascii=False)
        assert not re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", text)  # no timestamp
        assert build_dir.resolve().as_posix() not in text and str(build_dir) not in text
    # A benchmark inside the project is recorded by relative paths only.
    assert PROJECT_ROOT.resolve().as_posix() not in json.dumps(report, ensure_ascii=False)


def test_the_cli_runs_the_natural_scenario(cli_store, schema_2_dir, capsys, natural_report):
    args = ["--benchmark", str(schema_2_dir), "--build-dir", str(cli_store), "--scenario", "natural"]
    assert pe.main([*args, "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == natural_report
    assert pe.main(args) == 0
    assert "query scenario: natural (search_queries_it_natural)" in capsys.readouterr().out


def test_the_cli_rejects_an_unknown_scenario(cli_store, capsys):
    with pytest.raises(SystemExit) as caught:
        pe.main(["--benchmark", str(FIXTURE), "--build-dir", str(cli_store), "--scenario", "spoken"])
    assert caught.value.code == 2
    assert "invalid choice: 'spoken'" in capsys.readouterr().err


def test_the_cli_exits_2_for_a_scenario_the_benchmark_lacks(cli_store, capsys):
    assert pe.main(["--benchmark", str(FIXTURE), "--build-dir", str(cli_store),
                    "--scenario", "natural"]) == 2
    assert "has no 'natural' queries" in capsys.readouterr().err


# --- The real benchmark, data/evaluation/legal-v1 (M4 P2, provisional) --------------------------

# An explicit path, not pe.DEFAULT_BENCHMARK, so that a new default cannot retarget these tests.
LEGAL_V1 = PROJECT_ROOT / "data" / "evaluation" / "legal-v1"


def legal_v1_records(name):
    text = (LEGAL_V1 / name).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_legal_v1_is_provisional_and_split_by_its_documented_rule():
    benchmark = pe.load_benchmark(LEGAL_V1)  # validates the schema
    assert (benchmark.benchmark_id, benchmark.version, benchmark.kind) == ("legal", "1", "real")
    ids = [q.query_id for q in benchmark.questions]
    assert len(ids) == len(set(ids)) == 24
    assert all((q.split == "test") == (int(q.query_id[1:]) % 3 == 0) for q in benchmark.questions)
    assert sum(q.split == "test" for q in benchmark.questions) == 8
    records = (*benchmark.questions, *benchmark.judgments)
    assert {x.provenance.review_status for x in records} == {"candidate"}  # nothing reviewed yet
    assert not any(x.provenance.reviewed_by for x in records)


def test_legal_v1_expected_outcomes_agree_with_the_judgments():
    benchmark = pe.load_benchmark(LEGAL_V1)
    best = {}
    for j in benchmark.judgments:
        best[j.query_id] = max(best.get(j.query_id, 0), j.grade)
    for q in benchmark.questions:
        if q.expected_outcome == "answerable":
            assert best.get(q.query_id) == 2, q.query_id
        else:  # out of scope or not in the corpus: nothing relevant, so not scored
            assert best.get(q.query_id, 0) == 0, q.query_id


def test_legal_v1_judges_exactly_its_pool():
    judged = {}
    for j in legal_v1_records("judgments.jsonl"):
        judged.setdefault(j["query_id"], set()).add(f"{j['instrument']}:{j['article']}")
    for row in legal_v1_records("pool.jsonl"):
        pooled = {*row["bm25"], *row["dense"], *row["hybrid"],
                  *(added.split(" point ")[0] for added in row["judge_added"])}
        assert judged[row["query_id"]] == pooled, row["query_id"]


def test_legal_v1_resolves_on_the_recorded_build():
    try:
        explorer = ProvisionExplorer.open(find_recorded_build())
    except ExplorerError as exc:
        pytest.skip(f"recorded build unavailable: {exc}")
    benchmark = pe.load_benchmark(LEGAL_V1)
    grades = pe.resolve_judgments(benchmark.judgments, explorer)
    assert sum(len(articles) for articles in grades.values()) == len(benchmark.judgments)


# --- The recorded build ------------------------------------------------------------------------


def test_real_labels_and_points_resolve_on_the_recorded_build(tmp_path):
    """A test-only benchmark, not the M4 benchmark: it checks that real instrument IDs, labels
    such as '2-bis' and a point of GDPR Art. 4 resolve, and that candidates are flagged."""
    try:
        build = find_recorded_build()
    except ExplorerError as exc:
        pytest.skip(f"recorded build unavailable: {exc}")
    candidate = {"drafted_by": "test", "drafted_on": "2026-11-11", "review_status": "candidate"}
    directory = tmp_path / "real"
    directory.mkdir()
    (directory / "benchmark.json").write_text(json.dumps({
        "schema_version": 1, "benchmark_id": "test-only", "version": "0", "kind": "real",
        "description": "test data"}), encoding="utf-8")
    (directory / "questions.jsonl").write_text(json.dumps({
        "query_id": "t1", "question": "Quando si notifica una violazione?",
        "search_queries_it": ["notifica di una violazione dei dati personali"],
        "category": "procedure", "expected_outcome": "answerable", "split": "dev",
        "provenance": candidate}) + "\n", encoding="utf-8")
    (directory / "judgments.jsonl").write_text("".join(json.dumps(j) + "\n" for j in (
        {"query_id": "t1", "instrument": "eu-reg-2016-679", "article": "33", "grade": 2,
         "rationale": "test", "provenance": candidate},
        {"query_id": "t1", "instrument": "eu-reg-2016-679", "article": "4", "point": "12",
         "grade": 1, "rationale": "test", "provenance": candidate},
        {"query_id": "t1", "instrument": "it-dlgs-2003-196", "article": "2-bis", "grade": 1,
         "rationale": "test", "provenance": candidate},
    )), encoding="utf-8")
    result = pe.run(directory, build, detect_code=lambda: CLEAN)
    assert result["label"] == pe.REAL_LABEL and result["questions_scored"] == 1
    assert entry(result, "t1")["judged_articles"] == 3
    assert any("candidates that no person has reviewed" in w for w in result["warnings"])
