"""Identities of ingestion variants and corpus builds (P1.1; TECHNICAL_DEBT.md TD-059).

Three identifiers, with different meanings:

- `doc_id` (src/ingestion.py, unchanged) names the bytes of a source file. Two
  different processings of one file share it, so it is not a variant identity.
- `variant_id` names one processing of one source file: its bytes, the reader
  that extracts its text, its metadata sidecar, the options that change the
  chunks (end boundary, chunk size and overlap), the code version, and the
  versions of the libraries that extract and chunk text.
- `build_id` names one corpus: the variants it combines and the assembly format.

The reader is part of the identity because ingestion chooses it from the file
extension, not from the bytes (`load_document`: ".txt" is read as UTF-8 text,
".pdf" with PyMuPDF). The same bytes under two extensions are therefore two
different processings. A plain-ASCII PDF renamed to ".txt", for example, would
be ingested as its raw PDF syntax.

What a run produced (output path, SHA-256, size, chunk count) is recorded beside
an identity in an `OutputFile` and never feeds into an ID: it describes the
result, not the request. The source path is recorded the same way and is not
part of the identity, because moving a file does not change what is processed.
Chunk records do contain it (`location.source_path`, project-relative, or
absolute for a file outside the project), so two runs of one variant give the
same output hash only if the source is at the same path. A reproduction check
compares the output hash for that case.

Canonical form: the identity inputs form a JSON object serialized with sorted
keys, no whitespace and UTF-8, keeping non-ASCII characters as they are. There
is no Unicode normalization, because the end boundary is matched character by
character. NaN and infinity are rejected. An ID is a prefix plus the first 32
hex characters (128 bits) of the SHA-256 of that form. `IDENTITY_SCHEMA_VERSION`
is part of every payload, so changing these rules changes every ID instead of
silently reusing old ones.

Code version: a variant needs a full Git commit. Uncommitted changes are never
hidden. The state is then "dirty" and carries a fingerprint of the changed
files, so a dirty run has a different ID from the clean commit and from other
dirty states. Without a commit there is no variant.

Nothing here runs ingestion or writes files, and ingestion, retrieval and
evaluation do not use these records yet.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from importlib import metadata as importlib_metadata
from pathlib import Path
from types import MappingProxyType
from typing import Any

from src.chunk_store import read_chunks
from src.ingestion import METADATA_SUFFIX, SUPPORTED_SUFFIXES, display_path

IDENTITY_SCHEMA_VERSION = 1
ID_HEX_CHARS = 32
VARIANT_ID_PREFIX = "var-"
BUILD_ID_PREFIX = "build-"
# Label of the rule that turns variant chunk files into one corpus file. Corpus
# assembly is not implemented yet; whatever implements it must follow this rule
# or use a new label: the chunk files concatenated in the build's variant order.
DEFAULT_ASSEMBLY_FORMAT = "concatenated-jsonl/1"
# Library versions that can change extracted text or chunks.
REQUIRED_DEPENDENCIES = ("pymupdf", "python")
# The reader load_document (src/ingestion.py) selects for each supported
# extension, compared in lower case. A test checks that the keys are exactly
# SUPPORTED_SUFFIXES, so a new extension in ingestion fails here instead of
# being given a reader.
READER_BY_SUFFIX = MappingProxyType({".pdf": "pdf", ".txt": "txt"})
READERS = ("pdf", "txt")

_SHA256 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")


class CodeVersionError(RuntimeError):
    """The code version cannot be established (no Git, no repository, no commit)."""


def canonical_json(value: Any) -> bytes:
    """Deterministic UTF-8 JSON: sorted keys, no whitespace, no NaN or infinity."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _identity_hash(prefix: str, payload: Mapping[str, Any]) -> str:
    return prefix + hashlib.sha256(canonical_json(payload)).hexdigest()[:ID_HEX_CHARS]


def file_sha256(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def _require_sha256(value: Any, name: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(
            f"{name} must be a full SHA-256, 64 lowercase hex characters (got {value!r})."
        )


def _require_int(value: Any, name: str, minimum: int) -> None:
    if type(value) is not int or value < minimum:  # bool is not accepted as an int
        raise ValueError(f"{name} must be an integer >= {minimum} (got {value!r}).")


def _require_text(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string (got {value!r}).")


def _require_utf8(value: str, name: str) -> None:
    """Strings in an identity must encode as UTF-8, or the ID could not be computed."""
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError(
            f"{name} is not valid Unicode text: it contains a lone surrogate ({value!r})."
        ) from None


def reader_for_path(path: Path) -> str:
    """The reader ingestion uses for `path`, chosen from its extension like load_document."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES or suffix not in READER_BY_SUFFIX:
        raise ValueError(
            f"unsupported file type {suffix or '(no extension)'!r}; supported: "
            + ", ".join(SUPPORTED_SUFFIXES)
        )
    return READER_BY_SUFFIX[suffix]


def _from_record(build, record: Any, what: str):
    try:
        return build(record)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"malformed {what} record: {exc!r}") from exc


# --- Code version ----------------------------------------------------------------


class CodeState(StrEnum):
    CLEAN = "clean"  # the commit, with no uncommitted change in the repository
    DIRTY = "dirty"  # the commit plus uncommitted changes, identified by a fingerprint


@dataclass(frozen=True)
class CodeVersion:
    """The code a run used. There is no default state: clean must be stated explicitly."""

    state: CodeState
    commit: str
    fingerprint: str | None = None  # SHA-256 of the uncommitted changes; DIRTY only

    def __post_init__(self) -> None:
        try:
            state = CodeState(self.state)
        except ValueError:
            raise ValueError(
                f"code state must be 'clean' or 'dirty' (got {self.state!r})."
            ) from None
        object.__setattr__(self, "state", state)
        if not isinstance(self.commit, str) or not _COMMIT.fullmatch(self.commit):
            raise ValueError(
                "commit must be a full 40-character lowercase Git commit hash; a missing or "
                f"abbreviated commit is not accepted (got {self.commit!r})."
            )
        if state is CodeState.CLEAN and self.fingerprint is not None:
            raise ValueError(
                "a clean code version has no fingerprint; uncommitted changes need state 'dirty'."
            )
        if state is CodeState.DIRTY:
            _require_sha256(self.fingerprint, "the fingerprint of the uncommitted changes")

    @classmethod
    def clean(cls, commit: str) -> CodeVersion:
        return cls(CodeState.CLEAN, commit)

    @classmethod
    def dirty(cls, commit: str, fingerprint: str) -> CodeVersion:
        return cls(CodeState.DIRTY, commit, fingerprint)

    @property
    def is_clean(self) -> bool:
        return self.state is CodeState.CLEAN

    def describe(self) -> str:
        if self.is_clean:
            return f"{self.commit} (clean)"
        return f"{self.commit} plus uncommitted changes (fingerprint {self.fingerprint})"

    def to_record(self) -> dict[str, Any]:
        return {"state": self.state.value, "commit": self.commit, "fingerprint": self.fingerprint}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> CodeVersion:
        return _from_record(
            lambda r: cls(r["state"], r["commit"], r["fingerprint"]), record, "code version"
        )


def detect_code_version(repo_root: Path) -> CodeVersion:
    """Read the commit and working-tree state of the Git repository containing `repo_root`.

    The state is dirty if any of these exists (paths relative to the top of
    the repository):
    - a tracked file that differs from HEAD, staged or not, including deleted
      and renamed files;
    - a tracked file marked assume-unchanged or skip-worktree. Git does not
      compare such files, so they count as changed even when they are not;
    - an untracked file not ignored by the repository's own `.gitignore`
      files. Local excludes (`.git/info/exclude`, `core.excludesFile`) are not
      applied, because another checkout of the commit would not have the file.

    The fingerprint is the SHA-256 over the sorted changed paths, each with
    what is there now: the SHA-256 of a regular file's bytes, a symlink's
    target, "directory" or "absent". Limits: working-tree bytes are hashed as
    they are, so the same change saved with LF and with CRLF line endings gives
    two fingerprints, and fingerprints are not meant to be compared across
    machines. A changed submodule counts as "directory" whatever its content.
    Raises CodeVersionError if there is no Git, no repository or no commit.
    """

    def git(cwd: Path, *args: str) -> bytes:
        command = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(cwd)]
        try:
            run = subprocess.run([*command, *args], capture_output=True, check=True)
        except FileNotFoundError as exc:
            raise CodeVersionError("git is not installed or not on PATH") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.decode("utf-8", "replace").strip()
            raise CodeVersionError(f"git {args[0]} failed in {cwd}: {message}") from exc
        return run.stdout

    commit = git(repo_root, "rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip()
    top = Path(git(repo_root, "rev-parse", "--show-toplevel").decode("utf-8").strip())
    changed = _status_paths(git(top, "status", "--porcelain=v1", "-z", "--untracked-files=no"))
    changed |= _flagged_paths(git(top, "ls-files", "-v", "-z"))
    untracked = git(top, "ls-files", "--others", "-z", "--exclude-per-directory=.gitignore")
    changed |= {_decode(path) for path in untracked.split(b"\0") if path}
    if not changed:
        return CodeVersion.clean(commit)

    digest = hashlib.sha256()
    for rel in sorted(changed):
        digest.update(rel.encode("utf-8", "surrogateescape") + b"\0")
        digest.update(_current_content(top / rel) + b"\0")
    return CodeVersion.dirty(commit, digest.hexdigest())


def _decode(path: bytes) -> str:
    return path.decode("utf-8", "surrogateescape")


def _status_paths(status: bytes) -> set[str]:
    """Paths in `git status --porcelain=v1 -z` output, including both sides of a rename."""
    fields = status.split(b"\0")
    paths: set[str] = set()
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        if not entry:
            continue
        code, path = entry[:2], entry[3:]
        paths.add(_decode(path))
        if b"R" in code or b"C" in code:  # renamed or copied: the original path follows
            paths.add(_decode(fields[index]))
            index += 1
    return paths


def _flagged_paths(listing: bytes) -> set[str]:
    """Files in `git ls-files -v -z` output marked assume-unchanged (lowercase tag) or
    skip-worktree (tag "S")."""
    entries = (entry for entry in listing.split(b"\0") if entry)
    return {
        _decode(entry[2:])
        for entry in entries
        if entry[:1].decode("ascii").islower() or entry[:1] == b"S"
    }


def _current_content(path: Path) -> bytes:
    """What is at `path` now, for the fingerprint; symlinks are not followed."""
    if path.is_symlink():
        return b"symlink:" + os.fsencode(os.readlink(path))
    if path.is_file():
        return b"file:" + file_sha256(path).encode("ascii")
    if path.is_dir():
        return b"directory"
    return b"absent" if not path.exists() else b"other"


def current_dependency_versions() -> dict[str, str]:
    """Versions of the libraries that can change extracted text or chunks, as installed now."""
    return {
        "pymupdf": importlib_metadata.version("PyMuPDF"),
        "python": f"{platform.python_implementation()} {platform.python_version()}",
    }


# --- Output files ----------------------------------------------------------------


@dataclass(frozen=True)
class OutputFile:
    """A chunk file a run produced. Recorded beside an identity, never part of it."""

    path: str
    sha256: str
    size_bytes: int
    chunk_count: int

    def __post_init__(self) -> None:
        _require_text(self.path, "output path")
        _require_sha256(self.sha256, "output sha256")
        _require_int(self.size_bytes, "output size_bytes", 0)
        _require_int(self.chunk_count, "output chunk_count", 0)

    @classmethod
    def from_file(cls, path: Path) -> OutputFile:
        """Describe an existing chunk file; its chunks are read, so a malformed file fails."""
        chunk_count = sum(1 for _ in read_chunks(path))
        return cls(display_path(path), file_sha256(path), path.stat().st_size, chunk_count)

    def to_record(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "chunk_count": self.chunk_count,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> OutputFile:
        return _from_record(
            lambda r: cls(r["path"], r["sha256"], r["size_bytes"], r["chunk_count"]),
            record,
            "output file",
        )


# --- Ingestion variant ------------------------------------------------------------


@dataclass(frozen=True)
class IngestionVariant:
    """One processing of one source file.

    Identity inputs: `source_sha256`, `reader`, `metadata_sha256`,
    `end_before`, `chunk_size`, `chunk_overlap`, `code` and `dependencies`.
    `source_path` and `output` are recorded only. `dependencies` is stored
    read-only, so the identity of a variant cannot change after it is created.

    `reader` ("pdf" or "txt") has no default. `variant_for_file` sets it from
    the extension, as ingestion chooses it (`reader_for_path`).

    `metadata_sha256` has no default, so the sidecar must be stated:
    - a SHA-256: the "<file>.meta.json" sidecar exists, hashed as it is, even
      if it is empty or invalid (ingestion then fails on it);
    - None: it was checked and there is no such file, so ingestion uses empty
      metadata. A sidecar that exists but cannot be read stops
      `variant_for_file` with an OSError, so no variant is created.
    """

    source_sha256: str
    reader: str
    metadata_sha256: str | None
    chunk_size: int
    chunk_overlap: int
    code: CodeVersion
    dependencies: Mapping[str, str]
    end_before: str | None = None  # None = the whole file
    source_path: str | None = None
    output: OutputFile | None = None

    def __post_init__(self) -> None:
        _require_sha256(self.source_sha256, "source_sha256")
        if not isinstance(self.reader, str) or self.reader not in READERS:
            raise ValueError(
                f"reader must be one of {', '.join(READERS)} (got {self.reader!r})."
            )
        if self.metadata_sha256 is not None:
            _require_sha256(self.metadata_sha256, "metadata_sha256")
        _require_int(self.chunk_size, "chunk_size", 1)
        _require_int(self.chunk_overlap, "chunk_overlap", 0)
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be smaller than "
                f"chunk_size ({self.chunk_size})."
            )
        boundary = self.end_before
        # The same rule as the ingestion option --end-before (src/ingestion.py).
        if boundary is not None and (
            not isinstance(boundary, str)
            or not boundary.strip()
            or boundary != boundary.strip()
            or "\n" in boundary
        ):
            raise ValueError(
                f"end_before must be one line without surrounding whitespace (got {boundary!r})."
            )
        if boundary is not None:
            _require_utf8(boundary, "end_before")
        if not isinstance(self.code, CodeVersion):
            raise ValueError(f"code must be a CodeVersion (got {self.code!r}).")
        if not isinstance(self.dependencies, Mapping):
            raise ValueError(f"dependencies must be a mapping (got {self.dependencies!r}).")
        dependencies = dict(self.dependencies)
        for name, version in dependencies.items():
            _require_text(name, "dependency name")
            _require_text(version, f"version of dependency {name!r}")
            _require_utf8(name, "dependency name")
            _require_utf8(version, f"version of dependency {name!r}")
        missing = [name for name in REQUIRED_DEPENDENCIES if name not in dependencies]
        if missing:
            raise ValueError(f"dependencies must include {', '.join(missing)}.")
        object.__setattr__(
            self, "dependencies", MappingProxyType(dict(sorted(dependencies.items())))
        )
        if self.source_path is not None:
            _require_text(self.source_path, "source_path")
        if self.output is not None and not isinstance(self.output, OutputFile):
            raise ValueError(f"output must be an OutputFile or None (got {self.output!r}).")

    @property
    def doc_id(self) -> str:
        """The existing source-file ID: shared by every variant of the same file."""
        return "doc-" + self.source_sha256[:16]

    def identity(self) -> dict[str, Any]:
        """Everything the variant ID is computed from, and nothing else."""
        return {
            "kind": "ingestion-variant",
            "schema": IDENTITY_SCHEMA_VERSION,
            "source_sha256": self.source_sha256,
            "reader": self.reader,
            "metadata_sha256": self.metadata_sha256,
            "options": {
                "end_before": self.end_before,
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap,
            },
            "code": self.code.to_record(),
            "dependencies": dict(self.dependencies),
        }

    @property
    def variant_id(self) -> str:
        return _identity_hash(VARIANT_ID_PREFIX, self.identity())

    def to_record(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "doc_id": self.doc_id,
            "identity": self.identity(),
            "source_path": self.source_path,
            "output": self.output.to_record() if self.output else None,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> IngestionVariant:
        """Rebuild a variant; raises ValueError if its stored IDs do not match its inputs."""

        def build(r: Mapping[str, Any]) -> IngestionVariant:
            identity, options = r["identity"], r["identity"]["options"]
            return cls(
                source_sha256=identity["source_sha256"],
                reader=identity["reader"],
                metadata_sha256=identity["metadata_sha256"],
                end_before=options["end_before"],
                chunk_size=options["chunk_size"],
                chunk_overlap=options["chunk_overlap"],
                code=CodeVersion.from_record(identity["code"]),
                dependencies=identity["dependencies"],
                source_path=r["source_path"],
                output=OutputFile.from_record(r["output"]) if r["output"] is not None else None,
            )

        variant = _from_record(build, record, "ingestion variant")
        if variant.identity() != record["identity"]:
            raise ValueError("ingestion variant record: identity has unexpected or missing fields.")
        stored = (record.get("variant_id"), record.get("doc_id"))
        if stored != (variant.variant_id, variant.doc_id):
            raise ValueError(
                f"ingestion variant record: stored IDs {stored} "
                f"do not match its identity inputs ({variant.variant_id}, {variant.doc_id})."
            )
        return variant


def variant_for_file(
    source: Path,
    *,
    chunk_size: int,
    chunk_overlap: int,
    code: CodeVersion,
    end_before: str | None = None,
    dependencies: Mapping[str, str] | None = None,
) -> IngestionVariant:
    """The variant for ingesting `source` with these options. Reads files; ingests nothing.

    The reader and the sidecar ("<file>.meta.json") are found the same way
    ingestion finds them; an unsupported extension raises ValueError.
    `dependencies` defaults to the installed versions.
    """
    reader = reader_for_path(source)
    if not source.is_file():
        raise ValueError(f"source file does not exist: {source}")
    sidecar = source.with_name(source.name + METADATA_SUFFIX)
    return IngestionVariant(
        source_sha256=file_sha256(source),
        reader=reader,
        metadata_sha256=file_sha256(sidecar) if sidecar.is_file() else None,
        end_before=end_before,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        code=code,
        dependencies=current_dependency_versions() if dependencies is None else dependencies,
        source_path=display_path(source),
    )


# --- Corpus build -----------------------------------------------------------------


@dataclass(frozen=True)
class CorpusBuild:
    """One corpus assembled from ingestion variants, at most one per source file.

    The variants are kept in a canonical order (by variant ID), so membership,
    not the order in which they were passed, determines the build ID. That order
    is also the order of assembly.
    """

    variants: tuple[IngestionVariant, ...]
    assembly_format: str = DEFAULT_ASSEMBLY_FORMAT
    output: OutputFile | None = None

    def __post_init__(self) -> None:
        if isinstance(self.variants, (str, bytes)) or not isinstance(self.variants, Iterable):
            raise ValueError(
                f"variants must be a collection of IngestionVariant (got {self.variants!r})."
            )
        variants = tuple(self.variants)
        if not variants:
            raise ValueError("a corpus build needs at least one ingestion variant.")
        by_id: dict[str, IngestionVariant] = {}
        by_source: dict[str, IngestionVariant] = {}
        for variant in variants:
            if not isinstance(variant, IngestionVariant):
                raise ValueError(f"corpus build member is not an IngestionVariant: {variant!r}")
            variant_id = variant.variant_id
            if variant_id in by_id:
                raise ValueError(f"variant {variant_id} is listed more than once.")
            other = by_source.get(variant.source_sha256)
            if other is not None:
                raise ValueError(
                    f"source file {variant.doc_id} (sha256 {variant.source_sha256}) is represented "
                    f"by two ingestion variants ({other.variant_id}, {variant_id}); a corpus build "
                    "allows at most one variant per source file."
                )
            by_id[variant_id] = by_source[variant.source_sha256] = variant
        _require_text(self.assembly_format, "assembly_format")
        _require_utf8(self.assembly_format, "assembly_format")
        if self.output is not None and not isinstance(self.output, OutputFile):
            raise ValueError(f"output must be an OutputFile or None (got {self.output!r}).")
        object.__setattr__(self, "variants", tuple(by_id[key] for key in sorted(by_id)))

    @property
    def variant_ids(self) -> tuple[str, ...]:
        return tuple(variant.variant_id for variant in self.variants)

    def identity(self) -> dict[str, Any]:
        return {
            "kind": "corpus-build",
            "schema": IDENTITY_SCHEMA_VERSION,
            "assembly_format": self.assembly_format,
            "variant_ids": list(self.variant_ids),
        }

    @property
    def build_id(self) -> str:
        return _identity_hash(BUILD_ID_PREFIX, self.identity())

    def to_record(self) -> dict[str, Any]:
        return {
            "build_id": self.build_id,
            "identity": self.identity(),
            "variants": [variant.to_record() for variant in self.variants],
            "output": self.output.to_record() if self.output else None,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> CorpusBuild:
        """Rebuild a build and its variants; raises ValueError on any ID mismatch."""

        def build(r: Mapping[str, Any]) -> CorpusBuild:
            return cls(
                variants=tuple(IngestionVariant.from_record(v) for v in r["variants"]),
                assembly_format=r["identity"]["assembly_format"],
                output=OutputFile.from_record(r["output"]) if r["output"] is not None else None,
            )

        corpus = _from_record(build, record, "corpus build")
        if corpus.identity() != record["identity"] or record.get("build_id") != corpus.build_id:
            raise ValueError(
                f"corpus build record: stored build ({record.get('build_id')}) does not match "
                f"its variants and assembly format ({corpus.build_id})."
            )
        return corpus
