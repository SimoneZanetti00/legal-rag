"""Reproducible corpus builds (P1.3): ingest each source as a P1.1 ingestion variant.

    python -m src.corpus_build [--spec PATH] [--output-root DIR] [--allow-dirty]

A build reads a tracked specification (data/corpus_specs/*.json): the sources
with their SHA-256 and end boundary, the chunk settings and the assembly format.
For each source it creates an IngestionVariant (src/corpus_identity.py), runs
the existing ingestion pipeline (src.ingestion.ingest, unchanged) into a new
chunk file, and records the output. The chunk files are then concatenated in
the build's variant order into corpus.jsonl, and build.json records everything.

Layout: <output root>/<build_id>/
    <variant_id>.jsonl   one chunk file per source
    corpus.jsonl         the assembled corpus
    build.json           the record, written last: a directory without it is incomplete

Rules:
- the target directory must not exist; nothing is ever overwritten;
- a recorded build needs a clean Git tree and is written under
  data/processed/builds/. --allow-dirty is only for temporary verification
  builds: it is refused for that directory, and the record says
  "build_kind": "verification" with the dirty code state;
- every source must have its expected SHA-256; the code version is checked
  again after ingestion, and must not have changed.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.chunk_store import read_chunks
from src.config import PROJECT_ROOT
from src.corpus_identity import (
    CodeVersion,
    CodeVersionError,
    CorpusBuild,
    IngestionVariant,
    OutputFile,
    canonical_json,
    current_dependency_versions,
    detect_code_version,
    file_sha256,
    variant_for_file,
)
from src.ingestion import BoundaryError, ingest
from src.provisions import ProvisionError, load_registry

SPEC_PATH = PROJECT_ROOT / "data" / "corpus_specs" / "first_prototype.json"
BUILDS_ROOT = PROJECT_ROOT / "data" / "processed" / "builds"
BUILD_RECORD = "build.json"
CORPUS_FILE = "corpus.jsonl"
SPEC_SCHEMA_VERSION = 1
RECORD_SCHEMA_VERSION = 1


class CorpusBuildError(RuntimeError):
    """A build was refused or failed; the message says whether anything was written."""


@dataclass(frozen=True)
class SourceSpec:
    version_id: str
    path: str  # relative to the base directory, or absolute
    sha256: str
    end_before: str | None


@dataclass(frozen=True)
class CorpusSpec:
    name: str
    chunk_size: int
    chunk_overlap: int
    assembly_format: str
    sources: tuple[SourceSpec, ...]
    sha256: str  # of the specification's canonical JSON, independent of line endings
    label: str  # where the specification came from, for the record


def parse_spec(data: Any, label: str) -> CorpusSpec:
    """Validate a parsed specification; `label` names it in the record."""

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise CorpusBuildError(f"specification {label}: {message}")

    keys = {"schema_version", "name", "description", "chunk_size", "chunk_overlap",
            "assembly_format", "sources"}
    require(isinstance(data, Mapping) and set(data) == keys, f"expected keys {sorted(keys)}")
    require(data["schema_version"] == SPEC_SCHEMA_VERSION, "unknown schema_version")
    require(isinstance(data["name"], str) and bool(data["name"].strip()), "name")
    for key in ("chunk_size", "chunk_overlap"):
        require(type(data[key]) is int, f"{key} must be an integer")
    require(isinstance(data["sources"], list) and bool(data["sources"]), "sources")
    sources = []
    for i, raw in enumerate(data["sources"]):
        require(isinstance(raw, Mapping) and set(raw) == {"version_id", "path", "sha256",
                "end_before"}, f"sources[{i}]: expected version_id, path, sha256, end_before")
        require(all(isinstance(raw[k], str) and raw[k].strip() for k in ("version_id", "path",
                "sha256")), f"sources[{i}]: version_id, path and sha256 must be strings")
        require(raw["end_before"] is None or isinstance(raw["end_before"], str),
                f"sources[{i}]: end_before must be a string or null")
        sources.append(SourceSpec(raw["version_id"], raw["path"], raw["sha256"],
                                  raw["end_before"]))
    versions = [s.version_id for s in sources]
    require(len(versions) == len(set(versions)), "a version is listed twice")
    return CorpusSpec(
        name=data["name"],
        chunk_size=data["chunk_size"],
        chunk_overlap=data["chunk_overlap"],
        assembly_format=data["assembly_format"],
        sources=tuple(sources),
        sha256=hashlib.sha256(canonical_json(data)).hexdigest(),
        label=label,
    )


def load_spec(path: Path = SPEC_PATH) -> CorpusSpec:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CorpusBuildError(f"cannot read specification {path}: {exc}") from None
    try:
        label = path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        label = path.resolve().as_posix()
    return parse_spec(data, label)


def check_against_registry(spec: CorpusSpec, registry) -> None:
    """Every source must be a registered version, with the registered source hash."""
    registered = {v.version_id: v for v in registry.versions}
    for source in spec.sources:
        version = registered.get(source.version_id)
        if version is None:
            raise CorpusBuildError(f"{source.version_id} is not in the instrument registry")
        if version.source_sha256 != source.sha256:
            raise CorpusBuildError(
                f"{source.version_id}: the specification expects {source.sha256}, the registry "
                f"{version.source_sha256}"
            )


def _source_path(source: SourceSpec, base_dir: Path) -> Path:
    path = Path(source.path)
    return path if path.is_absolute() else base_dir / path


def plan_build(
    spec: CorpusSpec,
    code: CodeVersion,
    *,
    base_dir: Path = PROJECT_ROOT,
    dependencies: Mapping[str, str] | None = None,
) -> CorpusBuild:
    """The build's variants and ID, before anything is written. Checks every source hash."""
    dependencies = dependencies or current_dependency_versions()
    variants = []
    for source in spec.sources:
        path = _source_path(source, base_dir)
        if not path.is_file():
            raise CorpusBuildError(f"{source.version_id}: source file not found: {path}")
        actual = file_sha256(path)
        if actual != source.sha256:
            raise CorpusBuildError(
                f"{source.version_id}: {path} has SHA-256 {actual}, the specification expects "
                f"{source.sha256}"
            )
        try:
            variants.append(
                variant_for_file(
                    path,
                    chunk_size=spec.chunk_size,
                    chunk_overlap=spec.chunk_overlap,
                    code=code,
                    end_before=source.end_before,
                    dependencies=dependencies,
                )
            )
        except ValueError as exc:
            raise CorpusBuildError(f"{source.version_id}: {exc}") from None
    try:
        return CorpusBuild(tuple(variants), assembly_format=spec.assembly_format)
    except ValueError as exc:
        raise CorpusBuildError(f"invalid build: {exc}") from None


@dataclass(frozen=True)
class BuildResult:
    directory: Path
    record: dict[str, Any]

    @property
    def build_id(self) -> str:
        return self.record["build"]["build_id"]


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def run_build(
    spec: CorpusSpec,
    *,
    detect_code: Callable[[], CodeVersion],
    output_root: Path,
    allow_dirty: bool = False,
    recorded_root: Path = BUILDS_ROOT,
    base_dir: Path = PROJECT_ROOT,
    dependencies: Mapping[str, str] | None = None,
) -> BuildResult:
    """Run one build; see the module docstring for the rules. Returns where it was written."""
    code = detect_code()
    in_recorded_root = _inside(output_root, recorded_root)
    if not code.is_clean and not allow_dirty:
        raise CorpusBuildError(
            f"the working tree has uncommitted changes ({code.describe()}); a recorded build "
            "needs a clean tree. Use --allow-dirty with an output root outside "
            f"{recorded_root} for a temporary verification build. Nothing was written."
        )
    if allow_dirty and in_recorded_root:
        raise CorpusBuildError(
            f"--allow-dirty builds are temporary verification builds and may not be written "
            f"under {recorded_root}. Nothing was written."
        )
    if output_root.exists() and not output_root.is_dir():
        raise CorpusBuildError(f"output root {output_root} is a file. Nothing was written.")

    dependencies = dependencies or current_dependency_versions()
    planned = plan_build(spec, code, base_dir=base_dir, dependencies=dependencies)
    target = output_root / planned.build_id
    if target.exists():
        raise CorpusBuildError(
            f"{target} already exists; builds are never overwritten. Nothing was written."
        )
    build_kind = "recorded" if code.is_clean and not allow_dirty and in_recorded_root else (
        "verification"
    )
    try:
        target.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise CorpusBuildError(f"cannot create {target}: {exc}. Nothing was written.") from None

    def fail(message: str) -> CorpusBuildError:
        return CorpusBuildError(
            f"{message}. The incomplete build is left in {target} without {BUILD_RECORD}; "
            "remove it before retrying."
        )

    sources = _variant_sources(spec, planned)
    built: list[IngestionVariant] = []
    for variant, source in zip(planned.variants, sources):  # build order: by variant ID
        chunks = target / f"{variant.variant_id}.jsonl"
        try:
            report = ingest(
                _source_path(source, base_dir),
                chunks,
                spec.chunk_size,
                spec.chunk_overlap,
                end_before=source.end_before,
            )
        except (ValueError, BoundaryError) as exc:
            raise fail(f"{source.version_id}: ingestion refused: {exc}") from None
        results = report.results
        if len(results) != 1 or not results[0].ok:
            errors = "; ".join(r.error or "" for r in results) or "no result"
            raise fail(f"{source.version_id}: ingestion failed: {errors}")
        if results[0].doc_id != variant.doc_id or results[0].chunk_count < 1:
            raise fail(f"{source.version_id}: ingestion produced {results[0].doc_id} with "
                       f"{results[0].chunk_count} chunks, expected {variant.doc_id}")
        if {c.doc_id for c in read_chunks(chunks)} != {variant.doc_id}:
            raise fail(f"{source.version_id}: the chunk file holds another document")
        built.append(dataclasses.replace(variant, output=OutputFile.from_file(chunks)))

    if detect_code() != code:
        raise fail("the code version changed during the build")

    corpus = target / CORPUS_FILE
    with corpus.open("wb") as out:
        for variant in built:
            out.write((target / f"{variant.variant_id}.jsonl").read_bytes())
    corpus_output = OutputFile.from_file(corpus)
    if corpus_output.chunk_count != sum(v.output.chunk_count for v in built):
        raise fail("the assembled corpus does not hold every chunk")
    build = CorpusBuild(tuple(built), assembly_format=spec.assembly_format, output=corpus_output)
    if build.build_id != planned.build_id:
        raise fail("the build ID changed between planning and writing")

    record = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "kind": "corpus-build-record",
        "build_kind": build_kind,
        "code": code.to_record(),
        "spec": {"name": spec.name, "path": spec.label, "sha256": spec.sha256},
        "sources": [
            {
                "version_id": source.version_id,
                "variant_id": variant.variant_id,
                "source_path": variant.source_path,
                "source_sha256": variant.source_sha256,
                "end_before": variant.end_before,
            }
            for variant, source in zip(planned.variants, sources)
        ],
        "build": build.to_record(),
    }
    (target / BUILD_RECORD).write_text(_dump(record), encoding="utf-8", newline="\n")
    return BuildResult(target, record)


def _variant_sources(spec: CorpusSpec, build: CorpusBuild) -> list[SourceSpec]:
    """The specification source of each variant, in the build's variant order."""
    by_sha = {s.sha256: s for s in spec.sources}
    return [by_sha[v.source_sha256] for v in build.variants]


def _dump(record: Mapping[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def verify_build(directory: Path, *, base_dir: Path = PROJECT_ROOT) -> CorpusBuild:
    """Check a finished build: its record, its IDs and every output file's hash and size."""
    path = directory / BUILD_RECORD
    if not path.is_file():
        raise CorpusBuildError(f"{directory} has no {BUILD_RECORD}: not a finished build")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        build = CorpusBuild.from_record(record["build"])
    except (ValueError, KeyError, TypeError) as exc:
        raise CorpusBuildError(f"{path}: invalid build record: {exc}") from None
    if record.get("kind") != "corpus-build-record" or directory.name != build.build_id:
        raise CorpusBuildError(f"{path}: the directory name is not the build ID {build.build_id}")
    outputs = [v.output for v in build.variants] + [build.output]
    if any(o is None for o in outputs):
        raise CorpusBuildError(f"{path}: an output file is not recorded")
    for output in outputs:
        file = Path(output.path)
        file = file if file.is_absolute() else base_dir / file
        if not file.is_file():
            raise CorpusBuildError(f"{path}: missing output {file}")
        if file.stat().st_size != output.size_bytes or file_sha256(file) != output.sha256:
            raise CorpusBuildError(f"{path}: {file} does not match its recorded hash or size")
    return build


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.corpus_build",
        description="Build the corpus from a tracked specification (see the module docstring).",
    )
    parser.add_argument("--spec", type=Path, default=SPEC_PATH, help="corpus specification")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help=f"where <build_id>/ is created (default: {BUILDS_ROOT}, for recorded builds)",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="temporary verification build from a dirty tree; needs an --output-root outside "
        "the recorded builds directory",
    )
    args = parser.parse_args(argv)
    if args.allow_dirty and args.output_root is None:
        print("error: --allow-dirty needs an explicit --output-root for the temporary "
              "verification build. Nothing was written.", file=sys.stderr)
        return 2
    try:
        spec = load_spec(args.spec)
        try:
            check_against_registry(spec, load_registry())
        except ProvisionError as exc:
            raise CorpusBuildError(f"instrument registry: {exc}") from None
        result = run_build(
            spec,
            detect_code=lambda: detect_code_version(PROJECT_ROOT),
            output_root=args.output_root or BUILDS_ROOT,
            allow_dirty=args.allow_dirty,
        )
    except (CorpusBuildError, CodeVersionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    record = result.record
    print(f"{record['build_kind']} build {result.build_id} written to {result.directory}")
    for source in record["sources"]:
        print(f"  {source['version_id']}: {source['variant_id']}")
    print(f"  code: {record['code']['state']} {record['code']['commit']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
