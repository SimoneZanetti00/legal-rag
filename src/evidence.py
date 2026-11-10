"""Evidence assembly (MVP task 1): from search queries and exact lookups to E1..En.

Deterministic and independent of any LLM. It reuses the provision explorer for
retrieval (BM25 over the verified build) and for exact article text, and the
provision store for lookups and eligibility. It never retrieves on its own.

An evidence item is article text only, with its exact source anchors (character
offsets and pages in the extracted source text), the chunks it was matched in, and
the provision's eligibility exactly as the store computes it. `citable` is true only
for the `primary` tier. Retrieval rank, similarity or a caller's suggestion never
changes eligibility. Internal-only items stay in the set, marked non-citable.

What goes in:
- articles of up to WHOLE_PROVISION_MAX_CHARS characters: the whole article text;
- longer articles: the matched span from the best-ranked chunk, widened to the
  nearest blank line or line break within SPAN_CONTEXT_CHARS on each side; for a
  lookup of a numbered point ("12)"), exactly that point;
- one hop of explicit references ("articolo 55", "articoli 33 e 34") found in the
  included text of a direct item, attributed by src/citations.py with the item's own
  instrument as context: references that name no act stay in that instrument; with
  `cross_instrument`, references to another corpus instrument are followed too (in the
  Privacy Code, "articolo 51 del regolamento" is GDPR Art. 51, by the Code's own
  definition). References tied to an act outside the corpus, or to no determinable
  act, are never followed, and references are never followed from a reference.

Order and limits: exact lookups first (request order), then search hits interleaved
by rank across queries, then cross-references. Items are taken in that order while
they fit `max_items` and `token_budget`; anything left out is listed in `dropped`
with the reason. Tokens are estimated as ceil(characters / CHARS_PER_TOKEN), a
conservative estimate with no tokenizer dependency.
"""

from __future__ import annotations

import dataclasses
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from src.citations import extract_references
from src.config import Settings, load_settings
from src.provision_explorer import ProvisionExplorer
from src.provisions import Provision, ProvisionError, Tier

WHOLE_PROVISION_MAX_CHARS = 2500
SPAN_CONTEXT_CHARS = 300
CHARS_PER_TOKEN = 3

_POINT_LINE = re.compile(r"(?m)^[ \t]*(\d+)\)\s")


class EvidenceError(ValueError):
    """The evidence request or the limits are invalid."""


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


# --- Request -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class ProvisionRequest:
    """An exact article lookup. `instrument` is an ID or alias known to the provision store."""

    instrument: str
    label: str
    point: str | None = None  # a numbered point "N)" inside the article, e.g. "12"


@dataclass(frozen=True)
class EvidenceRequest:
    """What to retrieve. Built by hand today; later from query_analysis.analyze()."""

    queries: tuple[str, ...] = ()  # Italian search queries, run with BM25 in this order
    provisions: tuple[ProvisionRequest, ...] = ()  # exact lookups, included first
    top_k: int = 5  # BM25 passages per query
    expand_references: bool = True
    cross_instrument: bool = True  # also follow references to another corpus instrument


# --- Result ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceAnchor:
    """A range of the source's extracted text (the segment map's content)."""

    char_start: int
    char_end: int
    page: int
    page_end: int


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str  # "E1", "E2", ... in selection order
    provision_id: str
    version_id: str
    instrument_id: str
    label: str
    heading: str
    title: str | None
    path: str
    text: str  # exact article text: the whole article or a span of it
    whole_provision: bool
    point: str | None  # set when the text is one numbered point
    anchors: tuple[SourceAnchor, ...]  # the source ranges `text` comes from, in order
    chunk_ids: tuple[str, ...]  # chunks the provision was matched in (empty for lookups)
    origins: tuple[str, ...]  # "lookup", "query:<n>" (1-based), "reference:<provision_id>"
    best_rank: int | None  # best BM25 rank over the queries, if matched
    tier: str
    reasons: tuple[str, ...]
    qualifications: tuple[str, ...]
    legal_validity: str
    citable: bool  # tier == "primary"; nothing else decides it
    tokens: int  # estimated

    @property
    def page_start(self) -> int:
        return self.anchors[0].page

    @property
    def page_end(self) -> int:
        return self.anchors[-1].page_end


@dataclass(frozen=True)
class DroppedCandidate:
    provision_id: str
    label: str
    origins: tuple[str, ...]
    reason: str  # "max_items" or "token_budget"
    tokens: int


@dataclass(frozen=True)
class EvidenceSet:
    request: EvidenceRequest
    build_id: str
    max_items: int
    token_budget: int
    items: tuple[EvidenceItem, ...]
    dropped: tuple[DroppedCandidate, ...]
    warnings: tuple[str, ...] = field(default=())

    @property
    def citable_items(self) -> tuple[EvidenceItem, ...]:
        return tuple(i for i in self.items if i.citable)

    @property
    def is_empty(self) -> bool:
        return not self.items

    @property
    def has_citable_evidence(self) -> bool:
        return any(i.citable for i in self.items)

    @property
    def total_tokens(self) -> int:
        return sum(i.tokens for i in self.items)

    def get(self, evidence_id: str) -> EvidenceItem:
        for item in self.items:
            if item.evidence_id == evidence_id:
                return item
        raise KeyError(evidence_id)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for item, raw in zip(self.items, data["items"]):
            raw.update(page_start=item.page_start, page_end=item.page_end)
        data.update(total_tokens=self.total_tokens,
                    has_citable_evidence=self.has_citable_evidence)
        return data


# --- Assembly ----------------------------------------------------------------------------------


@dataclass
class _Candidate:
    provision: Provision
    origins: list[str]
    chunk_ids: list[str] = field(default_factory=list)
    best_rank: int | None = None
    span: tuple[int, int] | None = None  # in article-text coordinates; None = not chosen yet
    point: str | None = None


def assemble(request: EvidenceRequest, explorer: ProvisionExplorer, *,
             max_items: int | None = None, token_budget: int | None = None,
             settings: Settings | None = None) -> EvidenceSet:
    """Assemble the evidence set for `request` from the verified build behind `explorer`.

    `max_items` and `token_budget` default to FINAL_EVIDENCE_COUNT and
    CONTEXT_TOKEN_BUDGET from the settings.
    """
    if max_items is None or token_budget is None:
        settings = settings or load_settings()
        max_items = settings.final_evidence_count if max_items is None else max_items
        token_budget = settings.context_token_budget if token_budget is None else token_budget
    _check_request(request, max_items, token_budget)
    warnings: list[str] = []
    articles = _ArticleTexts(explorer)

    direct: dict[str, _Candidate] = {}
    for req in request.provisions:
        _add_lookup(direct, req, explorer, articles, warnings)
    _add_search_hits(direct, request, explorer, articles)

    selected, dropped = _select(list(direct.values()), articles, max_items, token_budget, [])
    if request.expand_references:
        refs = _references(selected, explorer, articles, warnings,
                           cross_instrument=request.cross_instrument)
        selected, more_dropped = _select(refs, articles, max_items, token_budget, selected)
        dropped += more_dropped

    merged: dict[str, DroppedCandidate] = {}  # one entry per provision, first reason kept
    for d in dropped:
        first = merged.get(d.provision_id)
        merged[d.provision_id] = d if first is None else dataclasses.replace(
            first, origins=first.origins + tuple(o for o in d.origins if o not in first.origins))
    dropped = list(merged.values())

    items = tuple(_item(f"E{n}", c, explorer, articles) for n, c in enumerate(selected, 1))
    if not items:
        warnings.append("no_evidence")
    elif not any(i.citable for i in items):
        warnings.append("no_citable_evidence")
    return EvidenceSet(request, explorer.identity()["build_id"], max_items, token_budget,
                       items, tuple(dropped), tuple(warnings))


def _check_request(request: EvidenceRequest, max_items: int, token_budget: int) -> None:
    for name, value in (("max_items", max_items), ("token_budget", token_budget),
                        ("top_k", request.top_k)):
        if type(value) is not int or value < 1:
            raise EvidenceError(f"{name} must be a positive integer, got {value!r}")
    if any(not isinstance(q, str) or not q.strip() for q in request.queries):
        raise EvidenceError("queries must be non-empty strings")


class _ArticleTexts:
    """Exact article text of each provision, as joined article pieces, with their anchors."""

    def __init__(self, explorer: ProvisionExplorer) -> None:
        self._explorer = explorer
        self._cache: dict[str, tuple[str, list[tuple[int, dict[str, Any]]], dict]] = {}

    def get(self, provision: Provision):
        pid = provision.provision_id
        if pid not in self._cache:
            view = self._explorer.provision_view(provision)
            offset, pieces = 0, []
            for piece in view["text"]:
                pieces.append((offset, piece))
                offset += len(piece["text"])
            self._cache[pid] = ("".join(p["text"] for _, p in pieces), pieces, view)
        return self._cache[pid]

    def to_article(self, provision: Provision, source_start: int, source_end: int):
        """Article-text coordinates of a source range lying inside the article's pieces."""
        _, pieces, _ = self.get(provision)
        a = b = None
        for offset, piece in pieces:
            lo, hi = piece["char_start"], piece["char_end"]
            if a is None and lo <= source_start < hi:
                a = offset + source_start - lo
            if lo < source_end <= hi:
                b = offset + source_end - lo
        return (a, b) if a is not None and b is not None and a < b else None

    def anchors(self, provision: Provision, start: int, end: int) -> tuple[SourceAnchor, ...]:
        _, pieces, _ = self.get(provision)
        out = []
        for offset, piece in pieces:
            lo, hi = max(start, offset), min(end, offset + len(piece["text"]))
            if lo < hi:
                base = piece["char_start"] - offset
                out.append(SourceAnchor(base + lo, base + hi, piece["page"], piece["page_end"]))
        return tuple(out)


def _add_lookup(direct, req: ProvisionRequest, explorer, articles, warnings) -> None:
    try:
        provision = explorer.store.lookup(req.instrument, req.label)
    except ProvisionError as exc:
        warnings.append(f"lookup_not_found: {req.instrument} {req.label} ({exc})")
        return
    text = articles.get(provision)[0]
    span = None
    if req.point is not None:
        span = _point_span(text, req.point)
        if span is None:
            warnings.append(f"point_not_found: {provision.provision_id} point {req.point}")
            return
    entry = direct.get(provision.provision_id)
    if entry is None:
        direct[provision.provision_id] = _Candidate(provision, ["lookup"], span=span,
                                                    point=req.point)
    elif "lookup" not in entry.origins:
        entry.origins.append("lookup")


def _add_search_hits(direct, request: EvidenceRequest, explorer, articles) -> None:
    per_query = []
    for n, query in enumerate(request.queries, 1):
        result = explorer.search(query, top_k=request.top_k)
        hits = [(r["rank"], e, r["chunk_id"]) for r in result["results"] for e in r["evidence"]]
        per_query.append((n, hits))
    for rank in range(1, request.top_k + 1):  # interleave by rank across queries
        for n, hits in per_query:
            for hit_rank, evidence, chunk_id in hits:
                if hit_rank != rank:
                    continue
                provision = explorer.store.get(evidence["provision_id"])
                entry = direct.get(provision.provision_id)
                if entry is None:
                    entry = direct[provision.provision_id] = _Candidate(provision, [])
                origin = f"query:{n}"
                if origin not in entry.origins:
                    entry.origins.append(origin)
                if chunk_id not in entry.chunk_ids:
                    entry.chunk_ids.append(chunk_id)
                if entry.best_rank is None or rank < entry.best_rank:
                    entry.best_rank = rank
                if entry.span is None and entry.point is None:
                    entry.span = _matched_span(provision, evidence["pieces"], articles)


def _point_span(text: str, point: str) -> tuple[int, int] | None:
    for m in _POINT_LINE.finditer(text):
        if m.group(1) == point:
            nxt = _POINT_LINE.search(text, m.end())
            return _trim(text, m.start(), nxt.start() if nxt else len(text))
    return None


def _matched_span(provision, pieces, articles) -> tuple[int, int] | None:
    ranges = [articles.to_article(provision, p["char_start"], p["char_end"]) for p in pieces]
    ranges = [r for r in ranges if r]
    if not ranges:
        return None
    text = articles.get(provision)[0]
    start, end = min(r[0] for r in ranges), max(r[1] for r in ranges)
    return _trim(text, _widen_back(text, start), _widen_forward(text, end))


def _widen_back(text: str, start: int) -> int:
    lo = max(0, start - SPAN_CONTEXT_CHARS)
    for sep in ("\n\n", "\n"):
        i = text.rfind(sep, lo, start)
        if i != -1:
            return i + len(sep)
    return start


def _widen_forward(text: str, end: int) -> int:
    hi = min(len(text), end + SPAN_CONTEXT_CHARS)
    for sep in ("\n\n", "\n"):
        i = text.find(sep, end, hi)
        if i != -1:
            return i
    return end


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _span_for(candidate: _Candidate, articles) -> tuple[int, int, bool]:
    """(start, end, whole_provision) in article-text coordinates."""
    text = articles.get(candidate.provision)[0]
    if len(text.strip()) <= WHOLE_PROVISION_MAX_CHARS or candidate.span is None:
        return (*_trim(text, 0, len(text)), True)
    return (*candidate.span, False)


def _select(candidates, articles, max_items, token_budget, already):
    selected, dropped = list(already), []
    used = sum(estimate_tokens(_text(c, articles)) for c in selected)
    for c in candidates:
        tokens = estimate_tokens(_text(c, articles))
        reason = ("max_items" if len(selected) >= max_items
                  else "token_budget" if used + tokens > token_budget else None)
        if reason:
            dropped.append(DroppedCandidate(c.provision.provision_id, c.provision.label_as_printed,
                                            tuple(c.origins), reason, tokens))
        else:
            selected.append(c)
            used += tokens
    return selected, dropped


def _text(candidate: _Candidate, articles) -> str:
    start, end, _ = _span_for(candidate, articles)
    return articles.get(candidate.provision)[0][start:end]


def _references(selected, explorer, articles, warnings, *,
                cross_instrument: bool) -> list[_Candidate]:
    """One hop of explicit references from the direct items' included text.

    The source provision is recorded in each target's origins ("reference:<provision_id>");
    the target keeps its own instrument. Targets are looked up exactly; one already selected
    only gains the origin, and nothing is followed from a reference (no cycles, no 2nd hop).
    """
    by_id = {c.provision.provision_id: c for c in selected}
    found: dict[str, _Candidate] = {}
    for c in list(selected):
        source = c.provision.instrument_id
        for instrument, label in _referenced_targets(_text(c, articles), source,
                                                     cross_instrument=cross_instrument):
            try:
                target = explorer.store.lookup(instrument, label)
            except ProvisionError:
                where = "" if instrument == source else f" {instrument}"
                warnings.append(f"reference_not_found: {c.provision.provision_id} -> "
                                f"articolo {label}{where}")
                continue
            if target.provision_id == c.provision.provision_id:
                continue
            origin = f"reference:{c.provision.provision_id}"
            entry = by_id.get(target.provision_id) or found.get(target.provision_id)
            if entry is None:
                entry = found[target.provision_id] = _Candidate(target, [])
            if origin not in entry.origins:
                entry.origins.append(origin)
    return list(found.values())


def _referenced_targets(text: str, instrument_id: str, *,
                        cross_instrument: bool = True) -> list[tuple[str, str]]:
    """(instrument, label) of the articles `text`, part of `instrument_id`, explicitly refers to.

    A reference that names no act stays in `instrument_id`; one that names another corpus
    instrument (or a term this instrument defines as one) is kept only with
    `cross_instrument`. References to acts outside the corpus, or to no determinable act, are
    left out.
    """
    targets: list[tuple[str, str]] = []
    for ref in extract_references(text, context_instrument=instrument_id):
        if ref.target_instrument is None:
            continue
        if ref.target_instrument != instrument_id and not cross_instrument:
            continue
        key = (ref.target_instrument, ref.article)
        if key not in targets:
            targets.append(key)
    return targets


def _item(evidence_id: str, c: _Candidate, explorer, articles) -> EvidenceItem:
    p = c.provision
    full, _, view = articles.get(p)
    start, end, whole = _span_for(c, articles)
    eligibility = view["eligibility"]
    tier = eligibility["tier"]
    text = full[start:end]
    return EvidenceItem(
        evidence_id=evidence_id,
        provision_id=p.provision_id,
        version_id=p.version_id,
        instrument_id=p.instrument_id,
        label=p.label_as_printed,
        heading=p.heading_as_printed,
        title=p.title,
        path=p.path,
        text=text,
        whole_provision=whole,
        point=None if whole else c.point,
        anchors=articles.anchors(p, start, end),
        chunk_ids=tuple(c.chunk_ids),
        origins=tuple(c.origins),
        best_rank=c.best_rank,
        tier=tier,
        reasons=tuple(r["code"] for r in eligibility["reasons"]),
        qualifications=tuple(q["code"] for q in eligibility["qualifications"]),
        legal_validity=view["legal_validity"],
        citable=tier == Tier.PRIMARY.value,
        tokens=estimate_tokens(text),
    )
