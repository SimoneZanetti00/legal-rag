"""Multi-query article retrieval: several phrasings of one question, fused by Reciprocal Rank
Fusion at article level. Opt-in: nothing in `ask` or the evaluator calls it.

Each phrasing (a QueryVariant) is searched with ProvisionExplorer.search, the BM25 search `ask`
uses. Each search ranks articles at their best chunk rank, as provision_eval.rank_articles
does; the rankings are then fused:

    score(article) = sum over the variants that found it of 1 / (rrf_k + best chunk rank)

with rrf_k = hybrid_retrieval.DEFAULT_RRF_K (60). Scores are summed exactly (fractions), and
equal scores keep the order of rank_articles over the same queries, so one variant alone gives
exactly the ranking of rank_articles for that query.

hybrid_retrieval.reciprocal_rank_fusion is not used: it fuses chunks, one list per retrieval
method, while this fuses articles, several lists from the same method.

Every fused article records which variants found it, at which chunk rank, and what each
contributed. The original question is always the first variant (query_variants); a variant
that repeats an earlier one is dropped and recorded, so it cannot count twice.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from src.hybrid_retrieval import DEFAULT_RRF_K
from src.provision_eval import DEFAULT_CHUNK_DEPTH
from src.provision_explorer import ProvisionExplorer
from src.query_understanding import QueryUnderstanding
from src.retrieval_common import require_positive_int

VARIANT_KINDS = ("original", "legal", "semantic")


@dataclass(frozen=True)
class QueryVariant:
    kind: str  # "original", "legal", "semantic"; experiments may use other labels
    text: str


@dataclass(frozen=True)
class Contribution:
    variant: int  # 1-based index into the searched variants
    kind: str
    chunk_rank: int  # the article's best chunk rank in that variant's search
    score: float  # 1 / (rrf_k + chunk_rank)


@dataclass(frozen=True)
class FusedArticle:
    provision_id: str
    instrument_id: str
    label: str
    score: float
    contributions: tuple[Contribution, ...]  # in variant order


@dataclass(frozen=True)
class FusedSearch:
    variants: tuple[QueryVariant, ...]  # searched, in order; the first is the original
    dropped: tuple[QueryVariant, ...]  # repeats of an earlier variant, not searched
    searches: tuple[dict[str, Any], ...]  # ProvisionExplorer.search results, one per variant
    articles: tuple[FusedArticle, ...]  # best first
    chunk_depth: int
    rrf_k: int

    def ranked_ids(self) -> list[str]:
        return [a.provision_id for a in self.articles]

    def summary(self) -> dict[str, Any]:
        return {
            "fusion": "rrf",
            "rrf_k": self.rrf_k,
            "chunk_depth": self.chunk_depth,
            "variants": [{"kind": v.kind, "query": v.text,
                          "chunks": len(s["results"]), "articles": len(s["provisions"])}
                         for v, s in zip(self.variants, self.searches)],
            "dropped_variants": [{"kind": v.kind, "query": v.text,
                                  "reason": "repeats an earlier variant"}
                                 for v in self.dropped],
        }


def query_variants(original: str, understanding: QueryUnderstanding | None = None, *,
                   legal: bool = True, semantic: bool = True) -> tuple[QueryVariant, ...]:
    """The original question, then the legal and semantic restatements that are asked for and
    available. With no understanding, or both switched off, the original alone."""
    if not isinstance(original, str) or not original.strip():
        raise ValueError("the original query is empty")
    variants = [QueryVariant("original", original.strip())]
    if understanding is not None:
        if understanding.original_query != original.strip():
            raise ValueError("the understanding is of another question")
        if legal:
            variants.append(QueryVariant("legal", understanding.legal_query))
        if semantic:
            variants.append(QueryVariant("semantic", understanding.semantic_query))
    return tuple(variants)


def search_variants(explorer: ProvisionExplorer, variants: Sequence[QueryVariant], *,
                    chunk_depth: int = DEFAULT_CHUNK_DEPTH,
                    rrf_k: int = DEFAULT_RRF_K) -> FusedSearch:
    """Search each variant with `explorer` and fuse the article rankings."""
    require_positive_int(chunk_depth, "chunk_depth")
    require_positive_int(rrf_k, "rrf_k")
    kept, dropped = _distinct(variants)
    searches = tuple(explorer.search(v.text, top_k=chunk_depth) for v in kept)
    instruments = {p["provision_id"]: explorer.store.get(p["provision_id"]).instrument_id
                   for s in searches for p in s["provisions"]}
    articles = fuse_rankings([s["provisions"] for s in searches], [v.kind for v in kept],
                             instruments, rrf_k=rrf_k)
    return FusedSearch(tuple(kept), tuple(dropped), searches, tuple(articles), chunk_depth,
                       rrf_k)


def fuse_rankings(rankings: Sequence[Sequence[Mapping[str, Any]]], kinds: Sequence[str],
                  instruments: Mapping[str, str], *,
                  rrf_k: int = DEFAULT_RRF_K) -> list[FusedArticle]:
    """Fuse article rankings, each a ProvisionExplorer.search "provisions" list (entries with
    provision_id, label and best_rank, in rank order)."""
    require_positive_int(rrf_k, "rrf_k")
    if len(rankings) != len(kinds):
        raise ValueError("one kind per ranking is needed")
    scores: dict[str, Fraction] = {}
    found: dict[str, list[Contribution]] = {}
    labels: dict[str, str] = {}
    entries = []  # (best_rank, variant index, position, provision ID)
    for number, (ranking, kind) in enumerate(zip(rankings, kinds), 1):
        for position, p in enumerate(ranking):
            pid, rank = p["provision_id"], p["best_rank"]
            require_positive_int(rank, "best_rank")
            if any(c.variant == number for c in found.get(pid, ())):
                raise ValueError(f"ranking {number} lists {pid} twice")
            share = Fraction(1, rrf_k + rank)
            scores[pid] = scores.get(pid, Fraction(0)) + share
            found.setdefault(pid, []).append(Contribution(number, kind, rank, float(share)))
            labels.setdefault(pid, p["label"])
            entries.append((rank, number, position, pid))
    first_seen: dict[str, int] = {}
    for order, (_, _, _, pid) in enumerate(sorted(entries)):
        first_seen.setdefault(pid, order)
    ordered = sorted(scores, key=lambda pid: (-scores[pid], first_seen[pid]))
    return [FusedArticle(pid, instruments[pid], labels[pid], float(scores[pid]),
                         tuple(found[pid])) for pid in ordered]


def _distinct(variants: Sequence[QueryVariant]) -> tuple[list[QueryVariant], list[QueryVariant]]:
    if not variants:
        raise ValueError("no query variants")
    kept, dropped, seen = [], [], set()
    for v in variants:
        if not isinstance(v.text, str) or not v.text.strip():
            raise ValueError(f"the {v.kind} query is empty")
        key = " ".join(v.text.lower().split())
        if key in seen:
            dropped.append(v)
        else:
            seen.add(key)
            kept.append(v)
    return kept, dropped
