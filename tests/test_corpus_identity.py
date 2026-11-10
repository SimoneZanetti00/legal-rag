"""Ingestion-variant and corpus-build identities (src/corpus_identity.py).

Synthetic inputs only. The Git tests create throwaway repositories under
tmp_path with the user's and the system's Git configuration switched off.
"""

import hashlib
import json
import shutil
import subprocess
import unicodedata
from pathlib import Path

import pytest

from src.chunk_store import write_chunks
from src.corpus_identity import (
    BUILD_ID_PREFIX,
    DEFAULT_ASSEMBLY_FORMAT,
    ID_HEX_CHARS,
    READER_BY_SUFFIX,
    READERS,
    VARIANT_ID_PREFIX,
    CodeState,
    CodeVersion,
    CodeVersionError,
    CorpusBuild,
    IngestionVariant,
    OutputFile,
    canonical_json,
    current_dependency_versions,
    detect_code_version,
    reader_for_path,
    variant_for_file,
)
from src.ingestion import (
    SUPPORTED_SUFFIXES,
    BoundaryError,
    IngestionError,
    ingest,
    load_document,
)
from src.models import DocumentMetadata, LegalChunk

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
COMMIT = "e" * 40
OTHER_COMMIT = "1" * 40
FINGERPRINT = "f" * 64
OTHER_FINGERPRINT = "d" * 64
DEPS = {"pymupdf": "1.28.2", "python": "CPython 3.13.2"}


def make_variant(**overrides) -> IngestionVariant:
    values = {
        "source_sha256": SHA_A,
        "reader": "pdf",
        "metadata_sha256": None,
        "chunk_size": 1200,
        "chunk_overlap": 150,
        "code": CodeVersion.clean(COMMIT),
        "dependencies": DEPS,
    }
    values.update(overrides)
    return IngestionVariant(**values)


def make_output(**overrides) -> OutputFile:
    values = {
        "path": "data/processed/out.jsonl",
        "sha256": SHA_C,
        "size_bytes": 10,
        "chunk_count": 2,
    }
    values.update(overrides)
    return OutputFile(**values)


def is_id(value: str, prefix: str) -> bool:
    hex_part = value.removeprefix(prefix)
    return value.startswith(prefix) and len(hex_part) == ID_HEX_CHARS and int(hex_part, 16) >= 0


# --- Canonical serialization -------------------------------------------------------


def test_canonical_json_ignores_key_insertion_order():
    first = {"b": 1, "a": {"d": [1, 2], "c": None}}
    second = {"a": {"c": None, "d": [1, 2]}, "b": 1}
    assert canonical_json(first) == canonical_json(second) == b'{"a":{"c":null,"d":[1,2]},"b":1}'


def test_canonical_json_keeps_non_ascii_as_utf8_and_rejects_nan():
    assert canonical_json({"x": "Attività"}) == '{"x":"Attività"}'.encode("utf-8")
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})


def test_canonical_form_of_a_variant_is_pinned():
    # Changing this form changes every variant ID: bump IDENTITY_SCHEMA_VERSION.
    variant = make_variant(end_before="ALLEGATO A.1")
    expected = (
        '{"code":{"commit":"' + COMMIT + '","fingerprint":null,"state":"clean"},'
        '"dependencies":{"pymupdf":"1.28.2","python":"CPython 3.13.2"},'
        '"kind":"ingestion-variant","metadata_sha256":null,'
        '"options":{"chunk_overlap":150,"chunk_size":1200,"end_before":"ALLEGATO A.1"},'
        '"reader":"pdf","schema":1,"source_sha256":"' + SHA_A + '"}'
    ).encode("utf-8")
    assert canonical_json(variant.identity()) == expected
    assert variant.variant_id == "var-" + hashlib.sha256(expected).hexdigest()[:32]


# --- Ingestion variant: identity ---------------------------------------------------


def test_variant_id_is_deterministic():
    first, second = make_variant(), make_variant()
    assert first.variant_id == second.variant_id
    assert is_id(first.variant_id, VARIANT_ID_PREFIX)
    assert first.variant_id == make_variant().variant_id  # also on a fresh object


def test_variant_id_ignores_dependency_insertion_order():
    reordered = {"python": "CPython 3.13.2", "pymupdf": "1.28.2"}
    assert make_variant(dependencies=reordered).variant_id == make_variant().variant_id
    assert list(make_variant(dependencies=reordered).dependencies) == ["pymupdf", "python"]


def test_every_identity_input_changes_the_variant_id():
    variants = {
        "base": make_variant(),
        "other source": make_variant(source_sha256=SHA_B),
        "other reader": make_variant(reader="txt"),
        "with sidecar": make_variant(metadata_sha256=SHA_B),
        "other sidecar": make_variant(metadata_sha256=SHA_C),
        "end boundary": make_variant(end_before="ALLEGATO A.1"),
        "other boundary": make_variant(end_before="ALLEGATO B"),
        "chunk size": make_variant(chunk_size=1000),
        "chunk overlap": make_variant(chunk_overlap=100),
        "other commit": make_variant(code=CodeVersion.clean(OTHER_COMMIT)),
        "dirty": make_variant(code=CodeVersion.dirty(COMMIT, FINGERPRINT)),
        "other dirty": make_variant(code=CodeVersion.dirty(COMMIT, OTHER_FINGERPRINT)),
        "pymupdf": make_variant(dependencies={**DEPS, "pymupdf": "1.28.3"}),
        "python": make_variant(dependencies={**DEPS, "python": "CPython 3.13.3"}),
        "extra dependency": make_variant(dependencies={**DEPS, "other": "1.0"}),
    }
    ids = {name: variant.variant_id for name, variant in variants.items()}
    assert len(set(ids.values())) == len(ids), ids


def test_end_boundary_is_not_unicode_normalized():
    # Ingestion matches the boundary character by character, so NFC and NFD
    # spellings select different lines and are different variants.
    nfc = unicodedata.normalize("NFC", "ALLEGATO À")
    nfd = unicodedata.normalize("NFD", "ALLEGATO À")
    assert nfc != nfd
    assert make_variant(end_before=nfc).variant_id != make_variant(end_before=nfd).variant_id


def test_output_and_source_path_do_not_change_the_variant_id():
    base = make_variant()
    recorded = [
        make_variant(output=make_output()),
        make_variant(output=make_output(sha256=SHA_B, size_bytes=99, chunk_count=7)),
        make_variant(output=make_output(path="elsewhere/out.jsonl")),
        make_variant(source_path="data/raw/moved.pdf"),
    ]
    assert {variant.variant_id for variant in recorded} == {base.variant_id}
    assert "output" not in base.identity() and "source_path" not in base.identity()


def test_doc_id_is_shared_by_variants_of_one_source_and_is_not_the_variant_id():
    whole, cut = make_variant(), make_variant(end_before="ALLEGATO A.1")
    assert whole.doc_id == cut.doc_id == "doc-" + SHA_A[:16]
    assert whole.variant_id != cut.variant_id
    assert whole.variant_id != whole.doc_id


def test_doc_id_matches_ingestion(tmp_path):
    path = tmp_path / "act.txt"
    path.write_text("Art. 1\nTesto.\n", encoding="utf-8")
    code = CodeVersion.clean(COMMIT)
    variant = variant_for_file(path, chunk_size=1200, chunk_overlap=150, code=code)
    assert variant.doc_id == load_document(path)[0].doc_id
    assert variant.source_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


# --- Ingestion variant: validation -------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    ["", "a" * 63, "a" * 65, "A" * 64, "g" * 64, " " + "a" * 63, None, 123, "doc-aaaaaaaaaaaaaaaa"],
)
def test_source_and_metadata_hashes_must_be_full_lowercase_sha256(bad):
    with pytest.raises(ValueError, match="source_sha256 must be a full SHA-256"):
        make_variant(source_sha256=bad)
    if bad is not None:  # None is valid for the sidecar: it means "no sidecar"
        with pytest.raises(ValueError, match="metadata_sha256 must be a full SHA-256"):
            make_variant(metadata_sha256=bad)


@pytest.mark.parametrize(
    ("size", "overlap", "message"),
    [
        (0, 0, "chunk_size must be an integer >= 1"),
        (-5, 0, "chunk_size must be an integer >= 1"),
        (1200.0, 150, "chunk_size must be an integer"),
        (True, 0, "chunk_size must be an integer"),
        ("1200", 150, "chunk_size must be an integer"),
        (1200, -1, "chunk_overlap must be an integer >= 0"),
        (1200, None, "chunk_overlap must be an integer"),
        (1200, 1200, "must be smaller than chunk_size"),
        (100, 150, "must be smaller than chunk_size"),
    ],
)
def test_invalid_chunk_settings_are_rejected(size, overlap, message):
    with pytest.raises(ValueError, match=message):
        make_variant(chunk_size=size, chunk_overlap=overlap)


@pytest.mark.parametrize(
    "boundary", ["", "   ", " ALLEGATO A.1", "ALLEGATO A.1 ", "ALLEGATO\nA.1", 5]
)
def test_end_boundary_follows_the_ingestion_rule(tmp_path, boundary):
    with pytest.raises(ValueError, match="end_before must be one line"):
        make_variant(end_before=boundary)
    if isinstance(boundary, str):  # ingestion rejects the same strings
        path = tmp_path / "act.txt"
        path.write_text("Art. 1\nTesto.\n\nALLEGATO A.1\nAllegato.\n", encoding="utf-8")
        with pytest.raises(BoundaryError, match="must be one line"):
            load_document(path, end_before=boundary)


@pytest.mark.parametrize(
    ("dependencies", "message"),
    [
        ({"python": "CPython 3.13.2"}, "dependencies must include pymupdf"),
        ({"pymupdf": "1.28.2"}, "dependencies must include python"),
        ({}, "dependencies must include pymupdf, python"),
        ({**DEPS, "pymupdf": ""}, "version of dependency 'pymupdf'"),
        ({**DEPS, "pymupdf": None}, "version of dependency 'pymupdf'"),
        ({**DEPS, "": "1.0"}, "dependency name"),
        ([("pymupdf", "1.28.2"), ("python", "3.13.2")], "dependencies must be a mapping"),
        (None, "dependencies must be a mapping"),
    ],
)
def test_incomplete_or_invalid_dependencies_are_rejected(dependencies, message):
    with pytest.raises(ValueError, match=message):
        make_variant(dependencies=dependencies)


def test_other_invalid_variant_fields_are_rejected():
    with pytest.raises(ValueError, match="code must be a CodeVersion"):
        make_variant(code=COMMIT)
    with pytest.raises(ValueError, match="code must be a CodeVersion"):
        make_variant(code=None)
    with pytest.raises(ValueError, match="source_path must be a non-empty string"):
        make_variant(source_path=" ")
    with pytest.raises(ValueError, match="output must be an OutputFile"):
        make_variant(output={"path": "x"})


def test_dependencies_are_read_only_and_copied():
    given = dict(DEPS)
    variant = make_variant(dependencies=given)
    before = variant.variant_id
    given["pymupdf"] = "9.9.9"  # changing the caller's dict afterwards has no effect
    with pytest.raises(TypeError):
        variant.dependencies["pymupdf"] = "9.9.9"  # type: ignore[index]
    assert variant.variant_id == before
    assert variant.dependencies == DEPS


@pytest.mark.parametrize("omitted", ["metadata_sha256", "reader"])
def test_the_sidecar_hash_and_the_reader_have_no_default(omitted):
    values = {
        "source_sha256": SHA_A,
        "reader": "pdf",
        "metadata_sha256": None,
        "chunk_size": 1200,
        "chunk_overlap": 150,
        "code": CodeVersion.clean(COMMIT),
        "dependencies": DEPS,
    }
    del values[omitted]
    with pytest.raises(TypeError, match=omitted):
        IngestionVariant(**values)


@pytest.mark.parametrize("reader", ["", "PDF", "Pdf", ".pdf", "text", "docx", None, 1, True])
def test_unsupported_reader_values_are_rejected(reader):
    with pytest.raises(ValueError, match="reader must be one of pdf, txt"):
        make_variant(reader=reader)


def test_lone_surrogates_are_rejected_when_the_variant_is_created():
    # A lone surrogate cannot be encoded as UTF-8, so no ID could be computed.
    with pytest.raises(ValueError, match="end_before is not valid Unicode text"):
        make_variant(end_before="ALLEGATO \udc80")
    with pytest.raises(ValueError, match="version of dependency 'pymupdf' is not valid"):
        make_variant(dependencies={**DEPS, "pymupdf": "1.28.2\udc80"})
    with pytest.raises(ValueError, match="dependency name is not valid"):
        make_variant(dependencies={**DEPS, "lib\udc80": "1.0"})
    with pytest.raises(ValueError, match="assembly_format is not valid"):
        CorpusBuild((make_variant(),), assembly_format="concatenated-jsonl/1\udc80")


def test_current_dependency_versions_cover_the_required_ones():
    versions = current_dependency_versions()
    assert set(versions) == {"pymupdf", "python"}
    make_variant(dependencies=versions)  # accepted as is


# --- Code version: dirty states cannot pass as clean ---------------------------------


def test_clean_and_dirty_code_versions_are_distinct():
    clean, dirty = CodeVersion.clean(COMMIT), CodeVersion.dirty(COMMIT, FINGERPRINT)
    assert clean.is_clean and not dirty.is_clean
    assert clean != dirty
    assert dirty.to_record() == {"state": "dirty", "commit": COMMIT, "fingerprint": FINGERPRINT}
    assert "uncommitted changes" in dirty.describe() and "(clean)" in clean.describe()
    assert make_variant(code=clean).variant_id != make_variant(code=dirty).variant_id


def test_a_dirty_state_needs_a_fingerprint_and_a_clean_state_must_not_have_one():
    with pytest.raises(ValueError, match="fingerprint of the uncommitted changes"):
        CodeVersion(CodeState.DIRTY, COMMIT)
    with pytest.raises(ValueError, match="fingerprint of the uncommitted changes"):
        CodeVersion.dirty(COMMIT, "abc")
    with pytest.raises(ValueError, match="a clean code version has no fingerprint"):
        CodeVersion(CodeState.CLEAN, COMMIT, FINGERPRINT)


@pytest.mark.parametrize(
    "commit", [None, "", "eee8c4e", "E" * 40, "e" * 39, "e" * 41, "HEAD", "e" * 64]
)
def test_a_missing_or_abbreviated_commit_is_rejected(commit):
    with pytest.raises(ValueError, match="full 40-character lowercase Git commit"):
        CodeVersion.clean(commit)
    with pytest.raises(ValueError, match="full 40-character lowercase Git commit"):
        CodeVersion.dirty(commit, FINGERPRINT)


@pytest.mark.parametrize("state", ["", "unknown", "CLEAN", None, True])
def test_unknown_code_states_are_rejected(state):
    with pytest.raises(ValueError, match="code state must be 'clean' or 'dirty'"):
        CodeVersion(state, COMMIT)


def test_code_state_can_be_given_as_its_string_value():
    assert CodeVersion("dirty", COMMIT, FINGERPRINT) == CodeVersion.dirty(COMMIT, FINGERPRINT)


@pytest.fixture
def git_repo(tmp_path, monkeypatch):
    """A throwaway repository with one committed file and a committed .gitignore."""
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    empty_config = tmp_path / "empty.gitconfig"
    empty_config.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty_config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> str:
        run = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)
        return run.stdout.decode("utf-8").strip()

    git("init", "-q")
    (repo / "code.py").write_bytes(b"x = 1\n")
    (repo / ".gitignore").write_bytes(b"ignored/\n")
    git("add", "code.py", ".gitignore")
    identity = ("-c", "user.name=Test", "-c", "user.email=test@example.invalid")
    git(*identity, "commit", "-q", "-m", "init")
    return repo, git("rev-parse", "HEAD"), git


def test_detect_clean_repository(git_repo):
    repo, commit, _ = git_repo
    assert detect_code_version(repo) == CodeVersion.clean(commit)


def test_ignored_files_do_not_make_the_state_dirty(git_repo):
    repo, commit, _ = git_repo
    (repo / "ignored").mkdir()
    (repo / "ignored" / "data.jsonl").write_bytes(b"{}\n")
    assert detect_code_version(repo) == CodeVersion.clean(commit)


def test_a_modified_file_makes_the_state_dirty_with_a_content_fingerprint(git_repo):
    repo, commit, git = git_repo
    (repo / "code.py").write_bytes(b"x = 2\n")
    first = detect_code_version(repo)
    assert first.state is CodeState.DIRTY and first.commit == commit
    assert first != CodeVersion.clean(commit)
    assert detect_code_version(repo) == first  # same changes, same fingerprint

    git("add", "code.py")  # staged only: still uncommitted
    assert detect_code_version(repo) == first

    (repo / "code.py").write_bytes(b"x = 3\n")
    other = detect_code_version(repo)
    assert other.state is CodeState.DIRTY and other.fingerprint != first.fingerprint

    git("reset", "-q", "--hard")
    assert detect_code_version(repo) == CodeVersion.clean(commit)


def test_untracked_and_deleted_files_make_the_state_dirty(git_repo):
    repo, commit, _ = git_repo
    (repo / "new_module.py").write_bytes(b"y = 1\n")
    untracked = detect_code_version(repo)
    assert untracked.state is CodeState.DIRTY

    (repo / "new_module.py").unlink()
    (repo / "code.py").unlink()
    deleted = detect_code_version(repo)
    assert deleted.state is CodeState.DIRTY
    assert deleted.fingerprint != untracked.fingerprint


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_files_hidden_from_git_status_still_make_the_state_dirty(git_repo, flag):
    repo, commit, git = git_repo
    git("update-index", flag, "code.py")
    flagged = detect_code_version(repo)  # flagged, not yet changed: counted as changed
    assert flagged.state is CodeState.DIRTY
    (repo / "code.py").write_bytes(b"x = 999\n")  # git status would not show this
    changed = detect_code_version(repo)
    assert changed.state is CodeState.DIRTY and changed.fingerprint != flagged.fingerprint


def test_local_excludes_do_not_hide_untracked_files(git_repo):
    repo, _, _ = git_repo
    (repo / ".git" / "info" / "exclude").write_text("local_*.py\n", encoding="utf-8")
    (repo / "local_patch.py").write_bytes(b"import code\n")
    assert detect_code_version(repo).state is CodeState.DIRTY


def test_what_replaced_a_deleted_file_changes_the_fingerprint(git_repo):
    repo, _, _ = git_repo
    (repo / "code.py").unlink()
    deleted = detect_code_version(repo)
    (repo / "code.py").mkdir()  # an empty directory, which git status does not list
    replaced = detect_code_version(repo)
    assert deleted.state is replaced.state is CodeState.DIRTY
    assert deleted.fingerprint != replaced.fingerprint


def test_a_symlink_is_fingerprinted_by_its_target_not_followed(git_repo, monkeypatch):
    # Creating a real symlink needs a privilege on Windows, so link.py is a regular
    # file with the target's bytes and is reported as a symlink to "code.py".
    repo, _, _ = git_repo
    (repo / "link.py").write_bytes(b"x = 1\n")  # untracked, same bytes as code.py
    as_copy = detect_code_version(repo)
    link = repo / "link.py"
    real_is_symlink = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda self: self == link or real_is_symlink(self))
    monkeypatch.setattr("src.corpus_identity.os.readlink", lambda path: "code.py")
    as_link = detect_code_version(repo)
    assert as_link.state is as_copy.state is CodeState.DIRTY
    assert as_link.fingerprint != as_copy.fingerprint
    monkeypatch.setattr("src.corpus_identity.os.readlink", lambda path: "other.py")
    assert detect_code_version(repo).fingerprint != as_link.fingerprint  # another target


def test_binary_and_non_ascii_files_and_line_endings(git_repo):
    repo, _, _ = git_repo
    (repo / "città_ü.py").write_bytes(b"z = 1\n")
    non_ascii = detect_code_version(repo)
    assert non_ascii.state is CodeState.DIRTY
    assert detect_code_version(repo) == non_ascii
    (repo / "città_ü.py").unlink()
    (repo / "table.bin").write_bytes(bytes(range(256)))
    binary = detect_code_version(repo)
    assert binary.state is CodeState.DIRTY and binary.fingerprint != non_ascii.fingerprint
    (repo / "table.bin").unlink()
    # A documented limit: working-tree bytes are hashed as they are, so the same
    # change saved with LF and with CRLF gives two fingerprints.
    (repo / "code.py").write_bytes(b"x = 2\n")
    lf = detect_code_version(repo)
    (repo / "code.py").write_bytes(b"x = 2\r\n")
    assert detect_code_version(repo).fingerprint != lf.fingerprint


def test_detection_from_a_subdirectory_matches_the_top(git_repo):
    repo, _, git = git_repo
    (repo / "pkg").mkdir()
    (repo / "pkg" / "mod.py").write_bytes(b"a = 1\n")
    git("add", "pkg/mod.py")
    (repo / "pkg" / "mod.py").write_bytes(b"a = 2\n")
    (repo / "notes.txt").write_bytes(b"untracked at the top\n")
    assert detect_code_version(repo / "pkg") == detect_code_version(repo)


def test_no_repository_or_no_commit_is_an_error(tmp_path, git_repo):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(CodeVersionError, match="failed"):
        detect_code_version(plain)
    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "-C", str(empty), "init", "-q"], check=True)
    with pytest.raises(CodeVersionError, match="rev-parse failed"):
        detect_code_version(empty)


def test_missing_git_is_an_error(monkeypatch, tmp_path):
    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr("src.corpus_identity.subprocess.run", no_git)
    with pytest.raises(CodeVersionError, match="git is not installed"):
        detect_code_version(tmp_path)


# --- Variants from real files and outputs -------------------------------------------


def test_variant_for_file_includes_the_metadata_sidecar(tmp_path):
    path = tmp_path / "act.txt"
    path.write_text("Art. 1\nTesto.\n", encoding="utf-8")
    code = CodeVersion.clean(COMMIT)
    without = variant_for_file(
        path, chunk_size=1200, chunk_overlap=150, code=code, dependencies=DEPS
    )
    assert without.metadata_sha256 is None
    sidecar = tmp_path / "act.txt.meta.json"
    sidecar.write_text('{"language": "it"}', encoding="utf-8")
    with_sidecar = variant_for_file(
        path, chunk_size=1200, chunk_overlap=150, code=code, dependencies=DEPS
    )
    assert with_sidecar.metadata_sha256 == hashlib.sha256(sidecar.read_bytes()).hexdigest()
    assert with_sidecar.variant_id != without.variant_id
    assert with_sidecar.doc_id == without.doc_id


def test_empty_sidecar_and_sidecar_directory_are_told_apart_from_no_sidecar(tmp_path):
    path = tmp_path / "act.txt"
    path.write_text("Art. 1\nTesto.\n", encoding="utf-8")
    sidecar = tmp_path / "act.txt.meta.json"

    def variant():
        code = CodeVersion.clean(COMMIT)
        return variant_for_file(
            path, chunk_size=1200, chunk_overlap=150, code=code, dependencies=DEPS
        )

    absent = variant()
    assert absent.metadata_sha256 is None
    sidecar.write_bytes(b"")  # present but empty: hashed; ingestion fails on it
    empty = variant()
    assert empty.metadata_sha256 == hashlib.sha256(b"").hexdigest()
    with pytest.raises(IngestionError, match="meta.json"):
        load_document(path)
    sidecar.unlink()
    sidecar.mkdir()  # not a file: ingestion ignores it too, so it is "no sidecar"
    assert variant().metadata_sha256 is None
    assert load_document(path)[0].metadata == DocumentMetadata()


def test_the_reader_table_covers_exactly_the_extensions_ingestion_supports():
    assert set(READER_BY_SUFFIX) == set(SUPPORTED_SUFFIXES)
    assert sorted(READER_BY_SUFFIX.values()) == sorted(READERS)
    with pytest.raises(TypeError):
        READER_BY_SUFFIX[".md"] = "txt"  # type: ignore[index]


@pytest.mark.parametrize(
    ("name", "reader"),
    [("act.pdf", "pdf"), ("ACT.PDF", "pdf"), ("act.Pdf", "pdf"), ("act.txt", "txt"),
     ("ACT.TXT", "txt"), ("act.v2.txt", "txt")],
)
def test_reader_follows_the_extension_in_lower_case_like_ingestion(tmp_path, name, reader):
    assert reader_for_path(tmp_path / name) == reader


def test_same_bytes_under_two_extensions_are_two_variants(tmp_path):
    data = "Art. 1\nTesto.\n".encode("utf-8")
    as_text, as_pdf = tmp_path / "act.txt", tmp_path / "act.pdf"
    as_text.write_bytes(data)
    as_pdf.write_bytes(data)
    code = CodeVersion.clean(COMMIT)
    text_variant, pdf_variant = (
        variant_for_file(path, chunk_size=1200, chunk_overlap=150, code=code, dependencies=DEPS)
        for path in (as_text, as_pdf)
    )
    assert (text_variant.reader, pdf_variant.reader) == ("txt", "pdf")
    assert text_variant.source_sha256 == pdf_variant.source_sha256
    assert text_variant.doc_id == pdf_variant.doc_id
    assert text_variant.variant_id != pdf_variant.variant_id
    # The two readers really do treat the same bytes differently.
    assert "Testo." in load_document(as_text)[0].content
    with pytest.raises(IngestionError, match="cannot open PDF"):
        load_document(as_pdf)


@pytest.mark.parametrize(
    "name", ["act.docx", "act.md", "act", "act.json", "act.pdf.bak", "act.TXT~"]
)
def test_unsupported_extensions_fail_like_ingestion(tmp_path, name):
    path = tmp_path / name
    path.write_text("Art. 1\nTesto.\n", encoding="utf-8")
    code = CodeVersion.clean(COMMIT)
    with pytest.raises(ValueError, match="unsupported file type"):
        variant_for_file(path, chunk_size=1200, chunk_overlap=150, code=code, dependencies=DEPS)
    with pytest.raises(IngestionError, match="unsupported file type"):
        load_document(path)


def test_variant_for_a_missing_file_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="source file does not exist"):
        variant_for_file(
            tmp_path / "missing.txt",
            chunk_size=1200,
            chunk_overlap=150,
            code=CodeVersion.clean(COMMIT),
        )


def test_output_file_from_a_chunk_file(tmp_path):
    path = tmp_path / "chunks.jsonl"
    chunks = [
        LegalChunk(chunk_id=f"doc-x-{i:04d}", doc_id="doc-x", text="t", chunk_index=i)
        for i in range(3)
    ]
    with path.open("w", encoding="utf-8", newline="\n") as file:
        write_chunks(file, chunks)
    output = OutputFile.from_file(path)
    assert output.chunk_count == 3
    assert output.size_bytes == path.stat().st_size
    assert output.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("path", "", "output path"),
        ("sha256", "abc", "output sha256"),
        ("size_bytes", -1, "output size_bytes"),
        ("chunk_count", 1.5, "output chunk_count"),
    ],
)
def test_invalid_output_files_are_rejected(field, value, message):
    with pytest.raises(ValueError, match=message):
        make_output(**{field: value})


def test_whole_file_and_boundary_runs_share_doc_id_but_not_variant_id(tmp_path):
    # The TD-059 situation, on a synthetic file: same source, same doc_id.
    path = tmp_path / "codice.txt"
    path.write_text(
        "Art. 1 (Oggetto)\n1. Testo.\n\nART. 2 (Fine)\n1. Fine.\n\nALLEGATO A.1\nTesto allegato.\n",
        encoding="utf-8",
    )
    code = CodeVersion.clean(COMMIT)
    variants, outputs = [], []
    for boundary, name in [(None, "whole.jsonl"), ("ALLEGATO A.1", "main.jsonl")]:
        out = tmp_path / name
        ingest(path, out, chunk_size=1200, chunk_overlap=150, end_before=boundary)
        outputs.append(OutputFile.from_file(out))
        variants.append(
            variant_for_file(
                path,
                chunk_size=1200,
                chunk_overlap=150,
                code=code,
                end_before=boundary,
                dependencies=DEPS,
            )
        )
    whole, main_body = variants
    assert whole.doc_id == main_body.doc_id == load_document(path)[0].doc_id
    assert whole.variant_id != main_body.variant_id
    assert outputs[0].sha256 != outputs[1].sha256


# --- Records ----------------------------------------------------------------------------


def test_variant_record_round_trip_and_json():
    variant = make_variant(
        end_before="ALLEGATO A.1",
        metadata_sha256=SHA_B,
        code=CodeVersion.dirty(COMMIT, FINGERPRINT),
        source_path="data/raw/act.pdf",
        output=make_output(),
    )
    record = json.loads(json.dumps(variant.to_record()))
    assert record["variant_id"] == variant.variant_id and record["doc_id"] == variant.doc_id
    restored = IngestionVariant.from_record(record)
    assert restored == variant
    assert restored.code.state is CodeState.DIRTY


@pytest.mark.parametrize(
    "tamper",
    [
        lambda r: r["identity"]["options"].update(chunk_size=1000),
        lambda r: r["identity"]["code"].update(state="clean", fingerprint=None),
        lambda r: r.update(variant_id="var-" + "0" * 32),
        lambda r: r.update(doc_id="doc-0000000000000000"),
        lambda r: r["identity"].update(extra="x"),
        lambda r: r.pop("variant_id"),
        lambda r: r["identity"].update(reader="txt"),
        lambda r: r["identity"].pop("reader"),
    ],
)
def test_variant_records_with_mismatched_ids_are_rejected(tamper):
    record = make_variant(code=CodeVersion.dirty(COMMIT, FINGERPRINT)).to_record()
    tamper(record)
    with pytest.raises(ValueError):
        IngestionVariant.from_record(record)


def test_malformed_variant_records_are_rejected():
    record = make_variant().to_record()
    del record["identity"]["options"]
    with pytest.raises(ValueError, match="malformed ingestion variant record"):
        IngestionVariant.from_record(record)


# --- Corpus build -------------------------------------------------------------------------


def two_sources() -> tuple[IngestionVariant, IngestionVariant]:
    main_body = make_variant(source_sha256=SHA_A, end_before="ALLEGATO A.1")
    return main_body, make_variant(source_sha256=SHA_B)


def test_build_id_is_deterministic():
    a, b = two_sources()
    first, second = CorpusBuild((a, b)), CorpusBuild(two_sources())
    assert first.build_id == second.build_id
    assert is_id(first.build_id, BUILD_ID_PREFIX)
    assert first.assembly_format == DEFAULT_ASSEMBLY_FORMAT


def test_build_id_depends_on_membership_not_on_the_order_given():
    a, b = two_sources()
    forward, backward = CorpusBuild((a, b)), CorpusBuild([b, a])
    assert forward.build_id == backward.build_id
    assert forward.variants == backward.variants  # same canonical order
    assert list(forward.variant_ids) == sorted([a.variant_id, b.variant_id])


def test_different_membership_or_format_changes_the_build_id():
    a, b = two_sources()
    other_a = make_variant(source_sha256=SHA_A)  # same source, whole file
    third = make_variant(source_sha256=SHA_C)
    builds = {
        "a+b": CorpusBuild((a, b)),
        "a": CorpusBuild((a,)),
        "b": CorpusBuild((b,)),
        "a+b+c": CorpusBuild((a, b, third)),
        "other variant of a": CorpusBuild((other_a, b)),
        "other format": CorpusBuild((a, b), assembly_format="concatenated-jsonl/2"),
    }
    ids = {name: build.build_id for name, build in builds.items()}
    assert len(set(ids.values())) == len(ids), ids
    # Swapping one variant of a source for another leaves every doc_id unchanged.
    doc_ids = {name: {v.doc_id for v in build.variants} for name, build in builds.items()}
    assert doc_ids["a+b"] == doc_ids["other variant of a"]


def test_output_does_not_change_the_build_id():
    a, b = two_sources()
    plain = CorpusBuild((a, b))
    with_output = CorpusBuild((a, b), output=make_output())
    assert plain.build_id == with_output.build_id
    variant_with_output = make_variant(source_sha256=SHA_B, output=make_output())
    assert CorpusBuild((a, variant_with_output)).build_id == plain.build_id


def test_two_variants_of_one_source_are_rejected():
    whole = make_variant(source_sha256=SHA_A)
    main_body = make_variant(source_sha256=SHA_A, end_before="ALLEGATO A.1")
    with pytest.raises(ValueError, match="at most one variant per source file") as error:
        CorpusBuild((whole, main_body))
    assert "doc-" + SHA_A[:16] in str(error.value)


def test_the_same_variant_twice_is_rejected():
    a, _ = two_sources()
    with pytest.raises(ValueError, match="listed more than once"):
        CorpusBuild((a, make_variant(source_sha256=SHA_A, end_before="ALLEGATO A.1")))


@pytest.mark.parametrize(
    ("variants", "fmt", "message"),
    [
        ((), DEFAULT_ASSEMBLY_FORMAT, "at least one ingestion variant"),
        (["var-x"], DEFAULT_ASSEMBLY_FORMAT, "not an IngestionVariant"),
        ("var-x", DEFAULT_ASSEMBLY_FORMAT, "collection of IngestionVariant"),
        (None, DEFAULT_ASSEMBLY_FORMAT, "collection of IngestionVariant"),
    ],
)
def test_invalid_builds_are_rejected(variants, fmt, message):
    with pytest.raises(ValueError, match=message):
        CorpusBuild(variants, assembly_format=fmt)


def test_blank_assembly_format_is_rejected():
    with pytest.raises(ValueError, match="assembly_format"):
        CorpusBuild(two_sources(), assembly_format=" ")


def test_build_record_round_trip_and_tamper_detection():
    build = CorpusBuild(two_sources(), output=make_output())
    record = json.loads(json.dumps(build.to_record()))
    assert CorpusBuild.from_record(record) == build

    swapped = json.loads(json.dumps(record))
    swapped["identity"]["variant_ids"].reverse()
    with pytest.raises(ValueError, match="does not match"):
        CorpusBuild.from_record(swapped)

    dropped = json.loads(json.dumps(record))
    dropped["variants"].pop()
    with pytest.raises(ValueError, match="does not match"):
        CorpusBuild.from_record(dropped)

    changed = json.loads(json.dumps(record))
    changed["variants"][0]["identity"]["options"]["chunk_size"] = 999
    with pytest.raises(ValueError, match="do not match its identity inputs"):
        CorpusBuild.from_record(changed)
