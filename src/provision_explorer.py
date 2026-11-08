"""Provision explorer (P1.3): article lookup and BM25 question search over a verified build.

This is the reusable core behind `python -m src.provision_cli`; a future chat or web
interface calls the same functions. Every result is a plain JSON-compatible dict
with a fixed set of keys (SCHEMA), so the output format is the interface.

Opening a build checks, before anything is answered:
- the build record and every output file's hash (src.corpus_build.verify_build);
- each segment map's integrity and provenance against its variant, the current
  inventory structure and the current registry (src.provision_anchors);
- each links file against its chunk file, its segment map and the provision store.
Anything missing or stale raises ExplorerError; nothing is answered from it.

Evidence and context are kept apart:
- `evidence`: article text, taken only from `article` segments, with exact offsets;
- `context`: recitals, front matter, division headings, editorial notes, footnotes,
  running headers, closing formulas. Context is shown, never offered as a citation.
Whether a provision may be cited is its eligibility (src.provisions.eligibility). In
the first demonstration only `primary` provisions may be cited; with an empty review
ledger there are none. Nothing here states that a provision is valid or in force.

BM25 scores are uncalibrated relevance signals, not probabilities. Running headers
are still inside the chunk text that BM25 indexes (TECHNICAL_DEBT.md TD-061).
"""

from __future__ import annotations

import json
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.chunk_store import read_chunks
from src.config import PROJECT_ROOT
from src.corpus_build import BUILD_RECORD, BUILDS_ROOT, CorpusBuildError, verify_build
from src.corpus_identity import IngestionVariant, file_sha256
from src.models import LegalChunk
from src.provision_anchors import (
    SEGMENT_KINDS,
    AnchorError,
    SegmentMap,
    links_path,
    load_segment_map,
    segment_map_path,
)
from src.provisions import (
    QUALIFICATIONS,
    REASONS,
    Provision,
    ProvisionError,
    ProvisionStore,
    Tier,
    Version,
    eligibility,
    load_store,
)
from src.retrieval import BM25Retriever

SCHEMA = "lexroom.provision-explorer/1"
SCORE_NOTE = (
    "BM25 scores are uncalibrated relevance signals for ranking, not probabilities or "
    "confidence. Running headers are still inside the indexed chunk text and can affect "
    "the ranking (TECHNICAL_DEBT.md TD-061)."
)
EVIDENCE_NOTE = (
    "Only article text can be evidence for a provision. Everything else is context. A "
    "provision may be cited as primary evidence only if its eligibility tier is 'primary'. "
    "Nothing here establishes that a provision is legally valid or in force."
)


class ExplorerError(RuntimeError):
    """The build, its anchors or its links are missing, damaged or stale."""


def find_recorded_build(root: Path = BUILDS_ROOT) -> Path:
    """The only finished build under `root`; anything else must be named explicitly."""
    builds = sorted(p.parent for p in root.glob(f"*/{BUILD_RECORD}")) if root.is_dir() else []
    if len(builds) != 1:
        found = "none" if not builds else ", ".join(p.name for p in builds)
        raise ExplorerError(
            f"expected exactly one recorded build in {root} (found {found}); pass --build-dir"
        )
    return builds[0]


@dataclass
class _Source:
    variant: IngestionVariant
    version: Version
    segment_map: SegmentMap
    links: dict[str, dict[str, Any]]  # chunk_id -> link record
    links_header: dict[str, Any]


def _resolve(path: str, base_dir: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else base_dir / p


class ProvisionExplorer:
    """A verified build, its provision store and a BM25 index over its corpus."""

    def __init__(self, build_dir: Path, record: dict[str, Any], store: ProvisionStore,
                 sources: dict[str, _Source], chunks: list[LegalChunk]) -> None:
        self.build_dir = build_dir
        self.record = record
        self.store = store
        self._sources = sources
        self._by_doc = {s.variant.doc_id: s for s in sources.values()}
        self._retriever = BM25Retriever(chunks)
        self._segments_by_provision: dict[str, list] = {}
        for source in sources.values():
            for segment in source.segment_map.segments:
                if segment.provision_id is not None:
                    self._segments_by_provision.setdefault(segment.provision_id, []).append(
                        (source, segment))

    # --- Opening and checking a build -----------------------------------------------------

    @classmethod
    def open(cls, build_dir: Path, *, store: ProvisionStore | None = None,
             base_dir: Path = PROJECT_ROOT) -> ProvisionExplorer:
        if not build_dir.is_dir():
            raise ExplorerError(f"build directory not found: {build_dir}")
        try:
            build = verify_build(build_dir, base_dir=base_dir)
        except CorpusBuildError as exc:
            raise ExplorerError(f"the build cannot be used: {exc}") from None
        record = json.loads((build_dir / BUILD_RECORD).read_text(encoding="utf-8"))
        store = store if store is not None else load_store()
        registry = store.registry
        versions = {s["variant_id"]: s["version_id"] for s in record["sources"]}
        sources: dict[str, _Source] = {}
        for variant in build.variants:
            version_id = versions.get(variant.variant_id)
            try:
                version = registry.version(version_id)
            except ProvisionError:
                raise ExplorerError(f"{variant.variant_id}: version {version_id!r} is not in the "
                                    "instrument registry") from None
            if version.source_sha256 != variant.source_sha256:
                raise ExplorerError(f"{variant.variant_id}: the registry expects another source")
            if not segment_map_path(build_dir, variant.variant_id).is_file():
                raise ExplorerError(f"{variant.variant_id}: no segment map; run "
                                    f"`build-anchors --build-dir {build_dir}`")
            try:
                segment_map = load_segment_map(build_dir, variant, build_id=build.build_id,
                                               store=store, registry=registry,
                                               version_id=version_id)
            except AnchorError as exc:
                raise ExplorerError(f"{variant.variant_id}: {exc}. Make a new build and its "
                                    "anchors.") from None
            header, links = cls._load_links(build_dir, build.build_id, variant, segment_map,
                                            store, base_dir)
            sources[variant.variant_id] = _Source(variant, version, segment_map, links, header)
        chunks = list(read_chunks(_resolve(build.output.path, base_dir)))
        linked = {cid for s in sources.values() for cid in s.links}
        if {c.chunk_id for c in chunks} != linked or len(chunks) != len(linked):
            raise ExplorerError("the corpus chunks do not match the passage links")
        return cls(build_dir, record, store, sources, chunks)

    @staticmethod
    def _load_links(build_dir, build_id, variant, segment_map, store, base_dir):
        path = links_path(build_dir, variant.variant_id)
        if not path.is_file():
            raise ExplorerError(f"{variant.variant_id}: no passage links; run "
                                f"`link --build-dir {build_dir}`")
        lines = path.read_text(encoding="utf-8").splitlines()
        try:
            header, links = json.loads(lines[0]), [json.loads(x) for x in lines[1:]]
        except (ValueError, IndexError) as exc:
            raise ExplorerError(f"{path}: not a links file: {exc}") from None
        expected = {
            "kind": "passage-links",
            "build_id": build_id,
            "variant_id": variant.variant_id,
            "doc_id": variant.doc_id,
            "chunk_file_sha256": variant.output.sha256,
            "segment_map_sha256": file_sha256(segment_map_path(build_dir, variant.variant_id)),
            "content_sha256": segment_map.content_sha256,
            "chunk_count": variant.output.chunk_count,
        }
        stale = [k for k, v in expected.items() if header.get(k) != v]
        if stale:
            raise ExplorerError(f"{path}: stale or inconsistent links ({', '.join(stale)}); make "
                                "a new build and its anchors")
        chunk_ids = [c.chunk_id for c in read_chunks(_resolve(variant.output.path, base_dir))]
        if [x.get("chunk_id") for x in links] != chunk_ids:
            raise ExplorerError(f"{path}: links do not follow the chunk file")
        for link in links:
            for item in link["provisions"]:
                p = _safe_get(store, item["provision_id"])
                if p is None or not p.is_article:
                    raise ExplorerError(f"{path}: unknown article {item['provision_id']}")
            for item in link["context"]:
                if item["kind"] not in SEGMENT_KINDS or item["kind"] == "article":
                    raise ExplorerError(f"{path}: bad context kind {item['kind']!r}")
                if item["provision_id"] is not None and _safe_get(
                        store, item["provision_id"]) is None:
                    raise ExplorerError(f"{path}: unknown provision {item['provision_id']}")
        return header, {x["chunk_id"]: x for x in links}

    # --- Views -------------------------------------------------------------------------------

    def identity(self) -> dict[str, Any]:
        record = self.record
        build = record["build"]
        return {
            "build_id": build["build_id"],
            "build_kind": record["build_kind"],
            "build_dir": self.build_dir.as_posix(),
            "code": record["code"],
            "spec": record["spec"],
            "corpus_sha256": build["output"]["sha256"],
            "sources": [
                {
                    "version_id": s["version_id"],
                    "variant_id": s["variant_id"],
                    "source_path": s["source_path"],
                    "source_sha256": s["source_sha256"],
                    "end_before": s["end_before"],
                    "content_sha256": self._sources[s["variant_id"]].segment_map.content_sha256,
                }
                for s in record["sources"]
            ],
        }

    def _version_view(self, version: Version) -> dict[str, Any]:
        return {
            "version_id": version.version_id,
            "instrument_id": version.instrument_id,
            "version_kind": version.version_kind,
            "description": version.description,
            "authenticity": version.authenticity,
            "publication": version.publication,
            "corpus_reference_date": version.corpus_reference_date,
        }

    def _eligibility(self, provision: Provision) -> dict[str, Any]:
        anchored = any(seg.kind == "article"
                       for _, seg in self._segments_by_provision.get(provision.provision_id, ()))
        result = eligibility(provision, self.store.registry.version(provision.version_id),
                             anchored=anchored)
        return {
            "tier": result.tier.value,
            "reasons": [{"code": c, "message": REASONS[c]} for c in result.reasons],
            "qualifications": [{"code": c, "message": QUALIFICATIONS[c]}
                               for c in result.qualifications],
        }

    def provision_view(self, provision: Provision) -> dict[str, Any]:
        """A provision with its exact text, status axes, eligibility and provenance."""
        pieces = self._segments_by_provision.get(provision.provision_id, [])
        source = pieces[0][0] if pieces else None
        review = provision.review
        return {
            "provision_id": provision.provision_id,
            "kind": provision.kind,
            "label": provision.label_as_printed,
            "heading": provision.heading_as_printed,
            "title": provision.title,
            "status_marker": provision.status_marker,
            "path": provision.path,
            "page_start": provision.page_start,
            "page_end": provision.page_end,
            "version": self._version_view(self.store.registry.version(provision.version_id)),
            "structural_status": provision.structural_status.value,
            "review": {
                "status": review.status,
                "checked_by": review.checked_by,
                "checked_on": review.checked_on,
                "outcome": review.outcome,
                "corrections": [{"field": c.field, "before": c.before, "after": c.after}
                                for c in review.corrections],
            },
            "source_status_representation": (
                provision.source_status_representation.value
                if provision.source_status_representation else None),
            "legal_validity": provision.legal_validity,
            "eligibility": self._eligibility(provision),
            "text": [_piece(s) for _, s in pieces if s.kind == "article"],
            "context": [dict(_piece(s), kind=s.kind) for _, s in pieces if s.kind != "article"],
            "provenance": {
                "inventory_id": provision.inventory_id,
                "inventory_ref": provision.inventory_ref,
                "inventory_sha256": provision.inventory_sha256,
                "source_sha256": provision.source_sha256,
                "doc_id": provision.doc_id,
                "variant_id": source.variant.variant_id if source else None,
                "content_sha256": source.segment_map.content_sha256 if source else None,
                "extraction": source.segment_map.extraction.to_record() if source else None,
                "segment_map": (segment_map_path(self.build_dir, source.variant.variant_id)
                                .as_posix() if source else None),
            },
        }

    def lookup(self, instrument: str, label: str) -> dict[str, Any]:
        """Exact (or normalised) article lookup; raises ProvisionError if there is none."""
        provision = self.store.lookup(instrument, label)
        return {
            "schema": SCHEMA,
            "command": "lookup",
            "query": {"instrument": instrument, "label": label},
            "build": self.identity(),
            "provision": self.provision_view(provision),
            "notes": [EVIDENCE_NOTE],
        }

    def search(self, question: str, top_k: int = 5) -> dict[str, Any]:
        """BM25 over the build's corpus; each passage mapped to evidence and context."""
        passages = self._retriever.search(question, top_k=top_k)
        results, grouped = [], {}
        for passage in passages:
            chunk = passage.chunk
            source = self._by_doc[chunk.doc_id]
            link = source.links[chunk.chunk_id]
            evidence = []
            for item in link["provisions"]:
                provision = self.store.get(item["provision_id"])
                tier = self._eligibility(provision)
                evidence.append({
                    "provision_id": provision.provision_id,
                    "label": provision.label_as_printed,
                    "heading": provision.heading_as_printed,
                    "title": provision.title,
                    "char_start": item["char_start"],
                    "char_end": item["char_end"],
                    "chars": item["chars"],
                    "pieces": self._article_pieces(source, provision.provision_id,
                                                   link["char_start"], link["char_end"]),
                    "structural_status": provision.structural_status.value,
                    "tier": tier["tier"],
                    "reasons": [r["code"] for r in tier["reasons"]],
                })
                entry = grouped.setdefault(provision.provision_id, {"provision": provision,
                                                                     "ranks": []})
                entry["ranks"].append(passage.rank)
            context = []
            for item in link["context"]:
                pid = item["provision_id"]
                owner = _safe_get(self.store, pid) if pid else None
                context.append({
                    "kind": item["kind"],
                    "provision_id": item["provision_id"],
                    "label": owner.label_as_printed if owner else None,
                    "char_start": item["char_start"],
                    "char_end": item["char_end"],
                    "chars": item["chars"],
                })
            results.append({
                "rank": passage.rank,
                "score": passage.score,
                "chunk_id": chunk.chunk_id,
                "chunk_index": chunk.chunk_index,
                "doc_id": chunk.doc_id,
                "variant_id": source.variant.variant_id,
                "version_id": source.version.version_id,
                "instrument_id": source.version.instrument_id,
                "source_path": source.variant.source_path,
                "page": link["page"],
                "page_end": link["page_end"],
                "char_start": link["char_start"],
                "char_end": link["char_end"],
                "text": chunk.text,
                "role": "article_evidence" if evidence else "context_only",
                "evidence": evidence,
                "context": context,
            })
        provisions = []
        for entry in sorted(grouped.values(), key=lambda e: min(e["ranks"])):
            provision = entry["provision"]
            provisions.append({
                "provision_id": provision.provision_id,
                "version_id": provision.version_id,
                "label": provision.label_as_printed,
                "heading": provision.heading_as_printed,
                "title": provision.title,
                "path": provision.path,
                "best_rank": min(entry["ranks"]),
                "ranks": entry["ranks"],
                "structural_status": provision.structural_status.value,
                "source_status_representation": (
                    provision.source_status_representation.value
                    if provision.source_status_representation else None),
                "legal_validity": provision.legal_validity,
                "eligibility": self._eligibility(provision),
            })
        return {
            "schema": SCHEMA,
            "command": "search",
            "query": {"question": question, "top_k": top_k},
            "retriever": {"method": "bm25", "indexed_chunks": len(self._retriever),
                          "score_note": SCORE_NOTE},
            "build": self.identity(),
            "results": results,
            "provisions": provisions,
            "primary_citations": [p["provision_id"] for p in provisions
                                  if p["eligibility"]["tier"] == Tier.PRIMARY.value],
            "notes": [EVIDENCE_NOTE, SCORE_NOTE],
        }

    def _article_pieces(self, source: _Source, provision_id: str, start: int,
                        end: int) -> list[dict[str, Any]]:
        """The exact article text of `provision_id` inside [start, end), segment by segment."""
        pieces = []
        for seg_source, segment in self._segments_by_provision.get(provision_id, []):
            if seg_source is not source or segment.kind != "article":
                continue
            a, b = max(start, segment.char_start), min(end, segment.char_end)
            if a < b and segment.text[a - segment.char_start: b - segment.char_start].strip():
                starts = source.segment_map.page_starts
                pieces.append({
                    "char_start": a,
                    "char_end": b,
                    "page": bisect_right(starts, a),
                    "page_end": bisect_right(starts, b - 1),
                    "text": segment.text[a - segment.char_start: b - segment.char_start],
                })
        return pieces


def _piece(segment) -> dict[str, Any]:
    return {"char_start": segment.char_start, "char_end": segment.char_end,
            "page": segment.page, "page_end": segment.page_end, "text": segment.text}


def _safe_get(store: ProvisionStore, provision_id: str) -> Provision | None:
    try:
        return store.get(provision_id)
    except ProvisionError:
        return None
