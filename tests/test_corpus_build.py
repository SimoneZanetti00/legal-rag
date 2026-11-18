"""Reproducible corpus builds (src/corpus_build.py).

Synthetic PDFs in tmp_path and a code version passed in by the test: nothing
here depends on the real Git state or reads the trial PDFs. The shipped
specification is checked only for its content.
"""

import json
from pathlib import Path

import pytest

import src.corpus_build as corpus_build
from src.corpus_build import (
    BUILD_RECORD,
    BUILDS_ROOT,
    CORPUS_FILE,
    CorpusBuildError,
    check_against_registry,
    load_spec,
    parse_spec,
    plan_build,
    run_build,
    verify_build,
)
from src.corpus_identity import CodeVersion, file_sha256
from src.provisions import load_registry

CLEAN = CodeVersion.clean("e" * 40)
DIRTY = CodeVersion.dirty("e" * 40, "f" * 64)
DEPS = {"pymupdf": "1.28.2", "python": "CPython 3.13.2"}


@pytest.fixture
def sources(tmp_path, write_pdf):
    """Two synthetic PDFs; the second has an annex the build cuts off."""
    a = write_pdf(tmp_path / "src" / "act_a.pdf", [["Art. 1", "Primo testo."], ["Art. 2",
                  "Secondo testo."]])
    b = write_pdf(tmp_path / "src" / "act_b.pdf", [["Art. 1", "Testo B."], ["ALLEGATO A.1",
                  "Allegato."]])
    return a, b


def spec_data(sources, *, reverse=False, end_before="ALLEGATO A.1"):
    a, b = sources
    entries = [
        {"version_id": "x-act-a@v1", "path": "src/act_a.pdf", "sha256": file_sha256(a),
         "end_before": None},
        {"version_id": "x-act-b@v1", "path": "src/act_b.pdf", "sha256": file_sha256(b),
         "end_before": end_before},
    ]
    return {
        "schema_version": 1,
        "name": "synthetic",
        "description": "two synthetic acts",
        "chunk_size": 1200,
        "chunk_overlap": 150,
        "assembly_format": "concatenated-jsonl/1",
        "sources": entries[::-1] if reverse else entries,
    }


def build(tmp_path, sources, root="builds", *, code=CLEAN, allow_dirty=False, data=None,
          detect=None):
    spec = parse_spec(data or spec_data(sources), "synthetic.json")
    return run_build(
        spec,
        detect_code=detect or (lambda: code),
        output_root=tmp_path / root,
        allow_dirty=allow_dirty,
        recorded_root=tmp_path / "builds",
        base_dir=tmp_path,
        dependencies=DEPS,
    )


def snapshot(directory: Path) -> dict[str, bytes]:
    return {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in sorted(directory.rglob("*")) if p.is_file()}


# --- The shipped specification ---------------------------------------------------------


def test_the_shipped_specification_covers_gdpr_and_the_privacy_code():
    spec = load_spec()
    registry = load_registry()
    assert [s.version_id for s in spec.sources] == [v.version_id for v in registry.versions]
    assert {s.version_id: s.sha256 for s in spec.sources} == {
        v.version_id: v.source_sha256 for v in registry.versions
    }
    gdpr, codice = spec.sources
    assert gdpr.end_before is None and codice.end_before == "ALLEGATO A.1"
    assert (spec.chunk_size, spec.chunk_overlap) == (1200, 150)
    assert spec.label == "data/corpus_specs/first_prototype.json"
    check_against_registry(spec, registry)


def test_a_specification_that_disagrees_with_the_registry_is_refused():
    data = json.loads(corpus_build.SPEC_PATH.read_text(encoding="utf-8"))
    data["sources"][0]["sha256"] = "0" * 64
    with pytest.raises(CorpusBuildError, match="the registry"):
        check_against_registry(parse_spec(data, "x"), load_registry())
    data["sources"][0]["version_id"] = "eu-reg-2016-679@other"
    with pytest.raises(CorpusBuildError, match="not in the instrument registry"):
        check_against_registry(parse_spec(data, "x"), load_registry())


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d.pop("description"), "expected keys"),
        (lambda d: d.update(schema_version=2), "schema_version"),
        (lambda d: d.update(chunk_size="1200"), "chunk_size must be an integer"),
        (lambda d: d.update(sources=[]), "sources"),
        (lambda d: d["sources"][0].pop("end_before"), "expected version_id"),
        (lambda d: d["sources"][1].update(version_id="x-act-a@v1"), "listed twice"),
        (lambda d: d["sources"][0].update(end_before=5), "end_before"),
    ],
)
def test_invalid_specifications_are_refused(sources, mutate, message):
    data = spec_data(sources)
    mutate(data)
    with pytest.raises(CorpusBuildError, match=message):
        parse_spec(data, "synthetic.json")


# --- Building ----------------------------------------------------------------------------


def test_a_recorded_build_writes_variants_corpus_and_record(tmp_path, sources):
    result = build(tmp_path, sources)
    record = result.record
    assert result.directory == tmp_path / "builds" / result.build_id
    assert record["build_kind"] == "recorded" and record["code"]["state"] == "clean"
    variants = record["build"]["variants"]
    assert [v["variant_id"] for v in variants] == sorted(v["variant_id"] for v in variants)
    names = {p.name for p in result.directory.iterdir()}
    assert names == {BUILD_RECORD, CORPUS_FILE, *(v["variant_id"] + ".jsonl" for v in variants)}
    # The corpus is the chunk files concatenated in the build's variant order.
    corpus = (result.directory / CORPUS_FILE).read_bytes()
    assert corpus == b"".join(
        (result.directory / f"{v['variant_id']}.jsonl").read_bytes() for v in variants
    )
    # Recorded hashes are those of the files written.
    for v in variants:
        file = result.directory / f"{v['variant_id']}.jsonl"
        assert v["output"]["sha256"] == file_sha256(file)
    assert record["build"]["output"]["sha256"] == file_sha256(result.directory / CORPUS_FILE)
    assert verify_build(result.directory, base_dir=tmp_path).build_id == result.build_id


def test_variants_record_source_identity_and_extraction_inputs(tmp_path, sources):
    record = build(tmp_path, sources).record
    by_version = {s["version_id"]: s for s in record["sources"]}
    a, b = sources
    assert by_version["x-act-a@v1"]["source_sha256"] == file_sha256(a)
    assert by_version["x-act-b@v1"]["end_before"] == "ALLEGATO A.1"
    for variant in record["build"]["variants"]:
        identity = variant["identity"]
        assert identity["reader"] == "pdf" and identity["dependencies"] == DEPS
        assert identity["options"]["chunk_size"] == 1200
        assert identity["code"] == CLEAN.to_record()
    b_chunks = (record["build"]["variants"][0], record["build"]["variants"][1])
    texts = [Path(v["output"]["path"]).read_text(encoding="utf-8") for v in b_chunks]
    assert all("Allegato." not in t for t in texts)  # the boundary was applied


def test_builds_are_reproducible(tmp_path, sources):
    first = build(tmp_path, sources, "verify-1")
    second = build(tmp_path, sources, "verify-2")
    assert first.build_id == second.build_id
    assert first.record["build"]["identity"] == second.record["build"]["identity"]
    assert snapshot(first.directory).keys() == snapshot(second.directory).keys()
    for name, data in snapshot(first.directory).items():
        if name != BUILD_RECORD:  # the record names its own output paths
            assert snapshot(second.directory)[name] == data


def test_the_order_of_sources_in_the_specification_does_not_matter(tmp_path, sources):
    forward = build(tmp_path, sources, "verify-1")
    backward = build(tmp_path, sources, "verify-2", data=spec_data(sources, reverse=True))
    assert forward.build_id == backward.build_id
    assert (forward.directory / CORPUS_FILE).read_bytes() == (
        backward.directory / CORPUS_FILE).read_bytes()


def test_a_source_with_another_hash_is_refused_before_anything_is_written(tmp_path, sources):
    data = spec_data(sources)
    data["sources"][1]["sha256"] = "0" * 64
    with pytest.raises(CorpusBuildError, match="the specification expects"):
        build(tmp_path, sources, data=data)
    assert not (tmp_path / "builds").exists()


def test_a_missing_source_is_refused(tmp_path, sources):
    data = spec_data(sources)
    data["sources"][0]["path"] = "src/absent.pdf"
    with pytest.raises(CorpusBuildError, match="source file not found"):
        build(tmp_path, sources, data=data)


@pytest.mark.parametrize(
    ("end_before", "message"),
    [("Art. 2", "at most one variant per source"), (None, "listed more than once")],
)
def test_one_source_file_cannot_enter_a_build_twice(tmp_path, sources, end_before, message):
    data = spec_data(sources)
    data["sources"][1].update(path="src/act_a.pdf", sha256=data["sources"][0]["sha256"],
                              end_before=end_before)
    with pytest.raises(CorpusBuildError, match=message):
        build(tmp_path, sources, data=data)
    assert not (tmp_path / "builds").exists()


# --- Protections --------------------------------------------------------------------------


def test_an_existing_target_is_refused_before_ingestion(tmp_path, sources, monkeypatch):
    planned = plan_build(parse_spec(spec_data(sources), "x"), CLEAN, base_dir=tmp_path,
                         dependencies=DEPS)
    target = tmp_path / "builds" / planned.build_id
    target.mkdir(parents=True)
    (target / "keep.txt").write_text("earlier content", encoding="utf-8")

    def no_ingestion(*args, **kwargs):
        raise AssertionError("ingest must not be called")

    monkeypatch.setattr(corpus_build, "ingest", no_ingestion)
    with pytest.raises(CorpusBuildError, match="already exists; builds are never overwritten"):
        build(tmp_path, sources)
    assert snapshot(target) == {"keep.txt": b"earlier content"}


def test_an_output_root_that_is_a_file_is_refused(tmp_path, sources):
    (tmp_path / "builds").write_text("not a directory", encoding="utf-8")
    with pytest.raises(CorpusBuildError, match="is a file"):
        build(tmp_path, sources)
    assert (tmp_path / "builds").read_text(encoding="utf-8") == "not a directory"


def test_a_dirty_tree_is_refused_by_default(tmp_path, sources):
    with pytest.raises(CorpusBuildError, match="needs a clean tree"):
        build(tmp_path, sources, code=DIRTY)
    assert not (tmp_path / "builds").exists()


def test_allow_dirty_makes_a_temporary_verification_build(tmp_path, sources):
    result = build(tmp_path, sources, "verify", code=DIRTY, allow_dirty=True)
    record = result.record
    assert record["build_kind"] == "verification"
    assert record["code"] == {"state": "dirty", "commit": "e" * 40, "fingerprint": "f" * 64}
    assert all(v["identity"]["code"]["state"] == "dirty" for v in record["build"]["variants"])
    # A dirty build has other variant IDs than the clean build of the same commit.
    clean = build(tmp_path, sources, "verify-clean")
    assert clean.build_id != result.build_id


def test_allow_dirty_is_refused_for_the_recorded_builds_directory(tmp_path, sources):
    with pytest.raises(CorpusBuildError, match="may not be written under"):
        build(tmp_path, sources, "builds", code=DIRTY, allow_dirty=True)
    with pytest.raises(CorpusBuildError, match="may not be written under"):
        build(tmp_path, sources, "builds/sub", code=CLEAN, allow_dirty=True)
    assert not (tmp_path / "builds").exists()


def test_a_clean_build_outside_the_recorded_directory_is_only_a_verification(tmp_path, sources):
    assert build(tmp_path, sources, "elsewhere").record["build_kind"] == "verification"


def test_earlier_builds_and_other_files_are_left_untouched(tmp_path, sources):
    root = tmp_path / "builds"
    (root / "build-earlier").mkdir(parents=True)
    (root / "build-earlier" / "corpus.jsonl").write_bytes(b'{"old": true}\n')
    (root / "notes.txt").write_text("keep me", encoding="utf-8")
    before = snapshot(root)
    result = build(tmp_path, sources)
    after = snapshot(root)
    assert {k: v for k, v in after.items() if not k.startswith(result.build_id)} == before


def test_a_code_change_during_the_build_fails_without_a_record(tmp_path, sources):
    versions = iter([CLEAN, CodeVersion.clean("1" * 40)])
    with pytest.raises(CorpusBuildError, match="code version changed"):
        build(tmp_path, sources, detect=lambda: next(versions))
    (target,) = (tmp_path / "builds").iterdir()
    assert not (target / BUILD_RECORD).exists()
    with pytest.raises(CorpusBuildError, match="not a finished build"):
        verify_build(target, base_dir=tmp_path)


def test_a_failed_ingestion_leaves_no_record(tmp_path, sources):
    data = spec_data(sources, end_before="ALLEGATO Z")  # not in the file
    with pytest.raises(CorpusBuildError, match="ingestion refused"):
        build(tmp_path, sources, data=data)
    (target,) = (tmp_path / "builds").iterdir()
    assert not (target / BUILD_RECORD).exists()


def test_verify_build_detects_changed_outputs(tmp_path, sources):
    result = build(tmp_path, sources)
    variant = result.record["build"]["variants"][0]["variant_id"]
    chunks = result.directory / f"{variant}.jsonl"
    chunks.write_bytes(chunks.read_bytes() + b"\n")
    with pytest.raises(CorpusBuildError, match="does not match its recorded hash"):
        verify_build(result.directory, base_dir=tmp_path)
    renamed = result.directory.with_name("build-renamed")
    result.directory.rename(renamed)
    with pytest.raises(CorpusBuildError, match="not the build ID"):
        verify_build(renamed, base_dir=tmp_path)


# --- Command line ---------------------------------------------------------------------------


def test_allow_dirty_needs_an_explicit_output_root(capsys):
    assert corpus_build.main(["--allow-dirty"]) == 2
    assert "needs an explicit --output-root" in capsys.readouterr().err


def test_the_command_line_refuses_allow_dirty_into_the_recorded_directory(monkeypatch, capsys):
    monkeypatch.setattr(corpus_build, "detect_code_version", lambda root: DIRTY)
    assert corpus_build.main(["--allow-dirty", "--output-root", str(BUILDS_ROOT)]) == 2
    assert "may not be written under" in capsys.readouterr().err


def test_the_command_line_refuses_a_dirty_tree(monkeypatch, capsys):
    monkeypatch.setattr(corpus_build, "detect_code_version", lambda root: DIRTY)
    assert corpus_build.main([]) == 2
    assert "needs a clean tree" in capsys.readouterr().err


def test_the_command_line_runs_a_verification_build(tmp_path, sources, monkeypatch, capsys):
    data = spec_data(sources)
    for entry in data["sources"]:
        entry["path"] = str(tmp_path / entry["path"])
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(corpus_build, "detect_code_version", lambda root: DIRTY)
    monkeypatch.setattr(corpus_build, "check_against_registry", lambda spec, registry: None)
    out = tmp_path / "verify"
    assert corpus_build.main(["--spec", str(spec), "--output-root", str(out),
                              "--allow-dirty"]) == 0
    assert "verification build" in capsys.readouterr().out
    (target,) = out.iterdir()
    assert verify_build(target).build_id == target.name
