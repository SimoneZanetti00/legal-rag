"""Provision explorer and CLI (src/provision_explorer.py, src/provision_cli.py).

One synthetic act, built from a synthetic PDF in tmp_path, holds a provision of
every kind the explorer must tell apart:
- Art. 1: reviewed (synthetic review, test data only) -> primary;
- Art. 2: not reviewed -> internal_only;
- Art. 3: reviewed but marked repealed by the source -> internal_only;
- Art. 4 / Art. 4-bis: ambiguous -> blocked;
- a title before Art. 1 and running headers -> context only.
"""

import dataclasses
import json

import pytest

import src.provision_cli as cli
from src.corpus_build import parse_spec, run_build
from src.corpus_identity import CodeVersion, current_dependency_versions, file_sha256
from src.provision_anchors import links_path, segment_map_path, write_passage_links, \
    write_segment_maps
from src.provision_explorer import SCHEMA, ExplorerError, ProvisionExplorer, find_recorded_build
from src.provisions import (
    Instrument,
    Provision,
    ProvisionStore,
    Registry,
    Review,
    SegmentationRules,
    SourceStatus,
    StructuralStatus,
    Version,
)

V = "x-act@v1"
CLEAN = CodeVersion.clean("e" * 40)
PAGES = [
    ["HDR 1", "Titolo di prova", "Art. 1", "(Notifica della violazione)",
     "1. Il titolare notifica la violazione al Garante entro settantadue ore."],
    ["HDR 2", "Art. 2", "(Comunicazione all'interessato)",
     "1. Il titolare comunica la violazione all'interessato senza ritardo.",
     "Art. 3", "((ARTICOLO ABROGATO))", "Art. 4", "Art. 4-bis", "((ARTICOLO ABROGATO))"],
]
REVIEW = Review("reviewed", "A. Reviewer", "2026-11-07", "confirmed")


def prov(label, page, *, status=StructuralStatus.AUTO_UNREVIEWED, review=None,
         source=SourceStatus.NO_STATUS_REPRESENTATION, marker=None, title="t"):
    return Provision(
        provision_id=f"{V}/body/article:{label.lower()}", version_id=V, instrument_id="x-act",
        kind="article", label_as_printed=label, normalised_label=label.lower(),
        heading_as_printed=f"Art. {label}", title=title, status_marker=marker, parent_id=None,
        path=f"Art. {label}", page_start=page, page_end=page, structural_status=status,
        review=review or Review("pending_human_review"), source_status_representation=source,
        inventory_id="inv", inventory_ref=f"inv:art:{label}", inventory_sha256="0" * 64,
        source_sha256="a" * 64, doc_id="doc-aaaaaaaaaaaaaaaa", notes=(),
    )


def provisions():
    marker = "((ARTICOLO ABROGATO))"
    return [
        prov("1", 1, status=StructuralStatus.AUTO_VERIFIED, review=REVIEW,
             title="(Notifica della violazione)"),
        prov("2", 2, title="(Comunicazione all'interessato)"),
        prov("3", 2, status=StructuralStatus.AUTO_VERIFIED, review=REVIEW,
             source=SourceStatus.MARKED_REPEALED, marker=marker, title=None),
        prov("4", 2, status=StructuralStatus.AMBIGUOUS, source=None, title=None),
        prov("4-bis", 2, status=StructuralStatus.AMBIGUOUS, source=None, marker=marker,
             title=None),
    ]


def make_store(source_sha, items=None):
    rules = SegmentationRules((r"HDR \d+",), 2, (), None, None)
    version = Version(V, "x-act", "original_publication", "synthetic act", "it", None, None,
                      None, SourceStatus.NO_STATUS_REPRESENTATION, "inv.json", source_sha, rules)
    registry = Registry((Instrument("x-act", "regulation", "EU", ("prova",), None),),
                        (version,), "1" * 64)
    return ProvisionStore(registry, items or provisions(), ())


@pytest.fixture
def built(tmp_path, write_pdf, monkeypatch):
    pdf = write_pdf(tmp_path / "src" / "act.pdf", PAGES)
    spec = parse_spec({
        "schema_version": 1, "name": "x", "description": "x", "chunk_size": 1200,
        "chunk_overlap": 150, "assembly_format": "concatenated-jsonl/1",
        "sources": [{"version_id": V, "path": "src/act.pdf", "sha256": file_sha256(pdf),
                     "end_before": None}],
    }, "x.json")
    result = run_build(spec, detect_code=lambda: CLEAN, output_root=tmp_path / "builds",
                       recorded_root=tmp_path / "builds", base_dir=tmp_path,
                       dependencies=current_dependency_versions())
    store = make_store(file_sha256(pdf))
    monkeypatch.setattr(cli, "load_store", lambda: store)
    monkeypatch.setattr(cli, "detect_code_version", lambda root: CLEAN)
    return result.directory, store


@pytest.fixture
def explored(built):
    build_dir, store = built
    write_segment_maps(build_dir, store=store, registry=store.registry,
                       detect_code=lambda: CLEAN)
    write_passage_links(build_dir, store=store, registry=store.registry)
    return build_dir, store


def run(capsys, *args):
    code = cli.main([str(a) for a in args])
    out = capsys.readouterr()
    return code, out.out, out.err


def run_json(capsys, *args):
    code, out, err = run(capsys, *args, "--json")
    assert code == 0, err
    return json.loads(out)


# --- Arguments and commands --------------------------------------------------------------------


@pytest.mark.parametrize("argv", [[], ["lookup"], ["lookup", "gdpr"], ["search"],
                                  ["unknown-command"], ["search", "q", "--top-k", "x"]])
def test_invalid_arguments_exit_with_2(argv):
    with pytest.raises(SystemExit) as error:
        cli.main(argv)
    assert error.value.code == 2


def test_build_delegates_to_the_corpus_build(capsys):
    code, _, err = run(capsys, "build", "--allow-dirty")
    assert code == 2 and "needs an explicit --output-root" in err


def test_anchors_and_links_are_written_by_the_cli_and_never_overwritten(built, capsys):
    build_dir, _ = built
    code, out, err = run(capsys, "build-anchors", "--build-dir", build_dir)
    assert code == 0, err
    assert out.count("wrote") == 1
    code, out, err = run(capsys, "link", "--build-dir", build_dir)
    assert code == 0, err
    assert out.count("wrote") == 1
    (variant,) = [p.name.split(".")[0] for p in build_dir.glob("var-*.jsonl")]
    assert segment_map_path(build_dir, variant).is_file()
    assert links_path(build_dir, variant).is_file()
    for command in ("build-anchors", "link"):
        code, _, err = run(capsys, command, "--build-dir", build_dir)
        assert code == 2 and "never overwritten" in err


def test_anchors_need_the_code_of_the_build(built, capsys, monkeypatch):
    build_dir, _ = built
    monkeypatch.setattr(cli, "detect_code_version", lambda root: CodeVersion.clean("1" * 40))
    code, _, err = run(capsys, "build-anchors", "--build-dir", build_dir)
    assert code == 2 and "current code is" in err


# --- Lookup ------------------------------------------------------------------------------------

LOOKUP_KEYS = {"schema", "command", "query", "build", "provision", "notes"}
PROVISION_KEYS = {
    "provision_id", "kind", "label", "heading", "title", "status_marker", "path", "page_start",
    "page_end", "version", "structural_status", "review", "source_status_representation",
    "legal_validity", "eligibility", "text", "context", "provenance",
}
BUILD_KEYS = {"build_id", "build_kind", "build_dir", "code", "spec", "corpus_sha256", "sources"}


def test_lookup_json_has_a_stable_schema(explored, capsys):
    build_dir, _ = explored
    result = run_json(capsys, "lookup", "prova", "2", "--build-dir", build_dir)
    assert set(result) == LOOKUP_KEYS and result["schema"] == SCHEMA == (
        "legal-rag.provision-explorer/2")
    p = result["provision"]
    assert set(p) == PROVISION_KEYS
    assert set(result["build"]) == BUILD_KEYS
    assert set(p["version"]) == {"version_id", "instrument_id", "version_kind", "description",
                                 "authenticity", "publication", "corpus_reference_date"}
    assert set(p["review"]) == {"status", "checked_by", "checked_on", "outcome", "corrections"}
    assert set(p["eligibility"]) == {"tier", "reasons", "qualifications"}
    assert set(p["provenance"]) == {"inventory_id", "inventory_ref", "inventory_sha256",
                                    "source_sha256", "doc_id", "variant_id", "content_sha256",
                                    "extraction", "segment_map"}
    assert all(set(x) == {"char_start", "char_end", "page", "page_end", "text"} for x in p["text"])


def test_lookup_shows_exact_text_status_and_eligibility(explored, capsys):
    build_dir, _ = explored
    result = run_json(capsys, "lookup", "prova", "2", "--build-dir", build_dir)
    p = result["provision"]
    assert p["text"][0]["text"].startswith("Art. 2\n\n(Comunicazione all'interessato)")
    assert "HDR" not in "".join(x["text"] for x in p["text"])
    assert (p["structural_status"], p["legal_validity"]) == ("auto_unreviewed", "not_established")
    assert p["eligibility"]["tier"] == "internal_only"
    assert [r["code"] for r in p["eligibility"]["reasons"]] == ["structure_not_reviewed"]
    assert "legal_validity_not_established" in [q["code"] for q in
                                                p["eligibility"]["qualifications"]]
    assert result["build"]["build_kind"] == "recorded"
    code, out, _ = run(capsys, "lookup", "prova", "2", "--build-dir", build_dir)
    assert code == 0
    for expected in ("tier: internal_only", "not primary because structure_not_reviewed",
                     "legal validity: not_established", "exact source text",
                     "1. Il titolare comunica la violazione"):
        assert expected in out


@pytest.mark.parametrize(
    ("label", "tier", "reasons"),
    [
        ("1", "primary", []),
        ("3", "internal_only", ["source_marks_repealed_excluded_from_first_demo"]),
        ("4", "blocked", ["ambiguous_structure", "structure_not_reviewed"]),
        ("4-bis", "blocked", ["ambiguous_structure", "structure_not_reviewed"]),
    ],
)
def test_lookup_eligibility_of_each_kind(explored, capsys, label, tier, reasons):
    build_dir, _ = explored
    p = run_json(capsys, "lookup", "prova", label, "--build-dir", build_dir)["provision"]
    assert p["eligibility"]["tier"] == tier
    assert [r["code"] for r in p["eligibility"]["reasons"]] == reasons


def test_lookup_accepts_the_normalised_label(explored, capsys):
    build_dir, _ = explored
    p = run_json(capsys, "lookup", "PROVA", "4-BIS", "--build-dir", build_dir)["provision"]
    assert p["label"] == "4-bis"


@pytest.mark.parametrize(
    ("instrument", "label", "message"),
    [("prova", "5", "no article '5'"), ("prova", "art. 1", "no article"),
     ("prova", "4 bis", "no article"), ("altro", "1", "unknown instrument")],
)
def test_lookup_without_a_match_exits_with_1(explored, capsys, instrument, label, message):
    build_dir, _ = explored
    code, out, err = run(capsys, "lookup", instrument, label, "--build-dir", build_dir)
    assert code == 1 and out == "" and message in err


# --- Search -------------------------------------------------------------------------------------

SEARCH_KEYS = {"schema", "command", "query", "retriever", "build", "results", "provisions",
               "primary_citations", "notes"}
RESULT_KEYS = {"rank", "score", "chunk_id", "chunk_index", "doc_id", "variant_id", "version_id",
               "instrument_id", "source_path", "page", "page_end", "char_start", "char_end",
               "text", "role", "evidence", "context"}


def search(capsys, build_dir, question, top_k=10):
    return run_json(capsys, "search", question, "--top-k", top_k, "--build-dir", build_dir)


def test_the_schema_identifier_is_neutral_and_shared_by_every_command(explored, capsys):
    build_dir, _ = explored
    namespace, _, version = SCHEMA.partition(".provision-explorer/")
    assert (namespace, version) == ("legal-rag", "2")
    outputs = [run_json(capsys, "lookup", "prova", "2", "--build-dir", build_dir),
               search(capsys, build_dir, "violazione")]
    assert {r["schema"] for r in outputs} == {"legal-rag.provision-explorer/2"}
    assert all("lexroom" not in json.dumps(r).lower() for r in outputs)


def test_search_json_has_a_stable_schema(explored, capsys):
    result = search(capsys, explored[0], "violazione titolare Garante")
    assert set(result) == SEARCH_KEYS and result["schema"] == SCHEMA
    assert set(result["retriever"]) == {"method", "indexed_chunks", "score_note"}
    assert all(set(r) == RESULT_KEYS for r in result["results"])
    for r in result["results"]:
        for e in r["evidence"]:
            assert set(e) == {"provision_id", "label", "heading", "title", "char_start",
                              "char_end", "chars", "pieces", "structural_status", "tier",
                              "reasons"}
        for c in r["context"]:
            assert set(c) == {"kind", "provision_id", "label", "char_start", "char_end", "chars"}
    assert all(set(p) == {"provision_id", "version_id", "label", "heading", "title", "path",
                          "best_rank", "ranks", "structural_status",
                          "source_status_representation", "legal_validity", "eligibility"}
               for p in result["provisions"])


def test_search_maps_passages_to_provisions_with_exact_text(explored, capsys):
    build_dir, _ = explored
    result = search(capsys, build_dir, "notifica violazione Garante settantadue")
    first = result["results"][0]
    assert first["role"] == "article_evidence"
    (evidence,) = first["evidence"]
    assert evidence["label"] == "1" and evidence["tier"] == "primary"
    pieces = "".join(p["text"] for p in evidence["pieces"])
    assert pieces.startswith("Art. 1\n\n(Notifica della violazione)")
    assert "HDR" not in pieces  # the running header in the chunk is context
    assert [c["kind"] for c in first["context"]] == ["page_furniture"]
    assert first["text"].endswith("HDR 2")  # the exact chunk, as BM25 retrieved it
    assert result["primary_citations"] == [f"{V}/body/article:1"]


def test_search_groups_provisions_and_keeps_context_apart(explored, capsys):
    build_dir, _ = explored
    result = search(capsys, build_dir, "Titolo violazione articolo abrogato titolare")
    roles = {r["chunk_index"]: r["role"] for r in result["results"]}
    assert roles[0] == "context_only"  # the title before Art. 1
    title = next(r for r in result["results"] if r["chunk_index"] == 0)
    assert title["evidence"] == [] and {c["kind"] for c in title["context"]} == {
        "page_furniture", "front_matter"}
    ids = [p["provision_id"] for p in result["provisions"]]
    assert len(ids) == len(set(ids))
    for p in result["provisions"]:
        assert p["best_rank"] == min(p["ranks"])
    assert [p["best_rank"] for p in result["provisions"]] == sorted(
        p["best_rank"] for p in result["provisions"])


def test_ambiguous_provisions_stay_blocked_together(explored, capsys):
    build_dir, _ = explored
    result = search(capsys, build_dir, "Art. 4-bis ARTICOLO ABROGATO")
    chunk = next(r for r in result["results"]
                 if {e["label"] for e in r["evidence"]} >= {"4", "4-bis"})
    assert {e["tier"] for e in chunk["evidence"]} == {"blocked"}
    assert all("ambiguous_structure" in e["reasons"] for e in chunk["evidence"])
    assert not set(result["primary_citations"]) & {f"{V}/body/article:4",
                                                   f"{V}/body/article:4-bis"}


def test_only_primary_provisions_become_citations(explored, capsys):
    build_dir, _ = explored
    result = search(capsys, build_dir, "titolare violazione abrogato Garante interessato")
    tiers = {p["label"]: p["eligibility"]["tier"] for p in result["provisions"]}
    assert tiers["2"] == "internal_only" and tiers["3"] == "internal_only"
    assert result["primary_citations"] == [p["provision_id"] for p in result["provisions"]
                                           if p["eligibility"]["tier"] == "primary"]
    assert all(cid.endswith("article:1") for cid in result["primary_citations"])


def test_search_text_output_marks_context_and_citations(explored, capsys):
    build_dir, _ = explored
    code, out, _ = run(capsys, "search", "Titolo di prova notifica", "--build-dir", build_dir)
    assert code == 0
    assert "uncalibrated" in out and "CONTEXT ONLY" in out and "primary citations:" in out
    code, out, _ = run(capsys, "search", "zzzz", "--build-dir", build_dir)
    assert code == 0 and "no chunk contains any of the query terms" in out
    assert "primary citations: none" in out


@pytest.mark.parametrize(("args", "message"), [(["--top-k", "0"], "at least 1"),
                                               ([], "")])
def test_search_input_errors_exit_with_2(explored, capsys, args, message):
    build_dir, _ = explored
    question = "valid" if args else "   "
    code, _, err = run(capsys, "search", question, *args, "--build-dir", build_dir)
    assert code == 2 and message in err


# --- Missing, damaged and stale artifacts ------------------------------------------------------


def test_a_missing_build_exits_with_2(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cli, "load_store", lambda: make_store("a" * 64))
    code, _, err = run(capsys, "lookup", "prova", "1", "--build-dir", tmp_path / "absent")
    assert code == 2 and "build directory not found" in err


def test_the_default_build_must_be_unique(tmp_path):
    with pytest.raises(ExplorerError, match="found none"):
        find_recorded_build(tmp_path)
    for name in ("build-a", "build-b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "build.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ExplorerError, match="build-a, build-b"):
        find_recorded_build(tmp_path)


def test_missing_anchors_or_links_name_the_command_to_run(built, capsys):
    build_dir, store = built
    code, _, err = run(capsys, "lookup", "prova", "1", "--build-dir", build_dir)
    assert code == 2 and "run `build-anchors" in err
    write_segment_maps(build_dir, store=store, registry=store.registry,
                       detect_code=lambda: CLEAN)
    code, _, err = run(capsys, "search", "violazione", "--build-dir", build_dir)
    assert code == 2 and "run `link" in err


def test_a_stale_inventory_structure_is_refused(explored, capsys, monkeypatch):
    build_dir, store = explored
    relabelled = [dataclasses.replace(p, provision_id=f"{V}/body/article:2-ter")
                  if p.label_as_printed == "2" else p for p in provisions()]
    monkeypatch.setattr(cli, "load_store", lambda: make_store(store.registry.versions[0]
                                                             .source_sha256, relabelled))
    code, _, err = run(capsys, "lookup", "prova", "1", "--build-dir", build_dir)
    assert code == 2 and "inventory structure" in err


def test_a_review_recorded_after_the_build_is_used_without_rebuilding(explored, capsys,
                                                                      monkeypatch):
    build_dir, store = explored
    reviewed = [dataclasses.replace(p, structural_status=StructuralStatus.AUTO_VERIFIED,
                                    review=REVIEW) if p.label_as_printed == "2" else p
                for p in provisions()]
    monkeypatch.setattr(cli, "load_store", lambda: make_store(store.registry.versions[0]
                                                             .source_sha256, reviewed))
    p = run_json(capsys, "lookup", "prova", "2", "--build-dir", build_dir)["provision"]
    assert p["eligibility"]["tier"] == "primary" and p["review"]["checked_by"] == "A. Reviewer"


def test_changed_links_are_refused(explored, capsys):
    build_dir, _ = explored
    (path,) = build_dir.glob("anchors/*.links.jsonl")
    lines = path.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    header["chunk_file_sha256"] = "0" * 64
    path.write_text("\n".join([json.dumps(header), *lines[1:]]) + "\n", encoding="utf-8")
    code, _, err = run(capsys, "lookup", "prova", "1", "--build-dir", build_dir)
    assert code == 2 and "stale or inconsistent links (chunk_file_sha256)" in err


def test_links_to_unknown_provisions_are_refused(explored, capsys):
    build_dir, _ = explored
    (path,) = build_dir.glob("anchors/*.links.jsonl")
    text = path.read_text(encoding="utf-8").replace("/body/article:2\"", "/body/article:9\"")
    path.write_text(text, encoding="utf-8")
    code, _, err = run(capsys, "lookup", "prova", "1", "--build-dir", build_dir)
    assert code == 2 and "unknown article" in err


def test_a_changed_chunk_file_is_refused(explored, capsys):
    build_dir, _ = explored
    (chunks,) = build_dir.glob("var-*.jsonl")
    chunks.write_bytes(chunks.read_bytes() + b"\n")
    code, _, err = run(capsys, "search", "violazione", "--build-dir", build_dir)
    assert code == 2 and "the build cannot be used" in err


def test_the_explorer_core_is_usable_without_the_cli(explored):
    build_dir, store = explored
    explorer = ProvisionExplorer.open(build_dir, store=store)
    result = explorer.search("notifica violazione Garante", top_k=3)
    assert result["schema"] == SCHEMA and result["results"]
    assert explorer.lookup("prova", "1")["provision"]["eligibility"]["tier"] == "primary"
