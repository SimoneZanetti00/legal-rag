"""Sparse lexical retrieval with BM25 over chunks produced by ingestion.

Usage (from the project root, after running `python -m src.ingestion`):

    .\\.venv\\Scripts\\python.exe -m src.retrieval "obblighi del datore di lavoro" --top-k 5

Or from Python:

    retriever = BM25Retriever.from_jsonl(Path("data/processed/chunks.jsonl"))
    for passage in retriever.search("data breach notification", top_k=5):
        print(passage.rank, passage.score, passage.chunk.chunk_id)

The index is held in memory and built from the chunks it is given. Rebuild
it whenever the chunk file changes.

Indexed representation
----------------------
Each chunk is indexed as the tokens of its text plus tokens derived from its
structural metadata (section heading, article, paragraph). A metadata token
is added only if the text does not already contain it, and at most once, so
term frequencies of the text are not inflated. Article and paragraph labels
are indexed only as structural tokens ("art:5", "par:2"), not as bare numbers,
because bare numbers occur everywhere in legal text. Structural tokens come
only from metadata; the tokenizer also produces them for text such as
"articolo 5", but in chunk text those are dropped, so a chunk citing article 5
is not indexed as if it were article 5. Queries keep them ("art. 5" matches
chunks of article 5). The displayed chunk text is never changed. The document
title is not part of `LegalChunk` and is not indexed.

Scoring
-------
BM25 with k1=1.5 and b=0.75, computed by `rank_bm25.BM25Okapi`. By default
(`positive_idf=True`) the IDF is ln(1 + (N - n + 0.5) / (n + 0.5)), the
formula used by Lucene, which is always > 0. With `positive_idf=False` the
library's original Okapi IDF, ln((N - n + 0.5) / (n + 0.5)), is used. It is 0
for a term in exactly half of the chunks and, for a term in more than half,
is replaced by a floor (0.25 x the corpus's average IDF) that is itself 0 or
negative in small or repetitive corpora. A chunk can then score lower by
matching an additional common query term.

- Result policy: a chunk is returned only if it contains at least one query
  token. It is never returned just to fill `top_k`, whatever its score.
- Order: descending BM25 score; ties keep the original corpus order.
- Scores rank chunks for one query. They are not probabilities and are not
  comparable across queries or corpora.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import unicodedata
from collections.abc import Iterable
from pathlib import Path

from rank_bm25 import BM25Okapi

from src.chunk_store import read_chunks
from src.config import ConfigError, load_settings
from src.models import LegalChunk, RetrievalMethod, RetrievedPassage

# A run of letters/digits, optionally joined by "-", "/" or "." to further
# runs: "2-bis", "2016/679", "d.lgs", "6.1". Apostrophes split Italian
# elisions ("dell'articolo" -> "dell", "articolo").
_TOKEN = re.compile(r"[^\W_]+(?:[-/.][^\W_]+)*")
_COMPOUND_SEPARATOR = re.compile(r"[-/.]")

# Words that introduce an article or paragraph number, mapped to the prefix of
# the structural token emitted for that number ("articolo 5" -> "art:5").
_REFERENCE_KEYWORDS = {
    **dict.fromkeys(("art", "artt", "articolo", "articoli", "article", "articles"), "art"),
    **dict.fromkeys(
        ("comma", "commi", "paragrafo", "paragrafi", "paragraph", "paragraphs", "par"), "par"
    ),
}
# "art.5" would otherwise be read as one compound token like "d.lgs".
_ABBREVIATION_BEFORE_NUMBER = re.compile(r"\b(artt?|par)\.(?=\d)")


def tokenize(text: str) -> list[str]:
    """Split text into lowercase, accent-folded tokens (used for chunks and queries).

    - Case is folded and accents are removed, so "Responsabilità",
      "responsabilita" and "RESPONSABILITA'" all become "responsabilita".
    - Punctuation and whitespace separate tokens.
    - A compound identifier is kept whole and also split into its parts:
      "2016/679" -> "2016/679", "2016", "679".
    - An article or paragraph keyword followed by a number becomes a
      structural token in place of the keyword: "Art. 2-bis" -> "art:2-bis",
      "2-bis", "2", "bis"; "comma 3" -> "par:3", "3". Only the first number
      after the keyword is linked ("artt. 5 e 6" -> "art:5", "5", "e", "6").
      A keyword without a number stays an ordinary word.
    - No stop words are removed and no stemming is applied, so "obbligo" and
      "obblighi" are different tokens.
    """
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    folded = _ABBREVIATION_BEFORE_NUMBER.sub(r"\1 ", folded)
    tokens: list[str] = []
    previous = ""
    for match in _TOKEN.finditer(folded):
        token = match.group()
        if previous in _REFERENCE_KEYWORDS and token[0].isdigit():
            # The keyword is always the last token here; the reference replaces it.
            tokens[-1] = f"{_REFERENCE_KEYWORDS[previous]}:{token}"
        tokens.append(token)
        if _COMPOUND_SEPARATOR.search(token):
            tokens.extend(_COMPOUND_SEPARATOR.split(token))
        previous = token
    return tokens


def index_tokens(chunk: LegalChunk) -> list[str]:
    """Tokens indexed for a chunk: its text plus missing structural metadata tokens.

    Structural tokens ("art:5", "par:2") come only from the chunk's metadata,
    i.e. from where the chunker found the article. A reference in running
    text ("ai sensi dell'articolo 5") is indexed as ordinary words, so a
    query for "articolo 5" prefers article 5 itself over chunks citing it.
    """
    tokens = [t for t in tokenize(chunk.text) if ":" not in t]
    location = chunk.location
    extra: list[str] = []
    if location.section:
        extra += [t for t in tokenize(location.section) if ":" not in t]
    if location.article:
        extra += [t for t in tokenize(f"art {location.article}") if t.startswith("art:")]
    if location.paragraph:
        for label in location.paragraph.split(", "):
            extra += [t for t in tokenize(f"par {label}") if t.startswith("par:")]

    present = set(tokens)
    for token in extra:
        if token not in present:
            tokens.append(token)
            present.add(token)
    return tokens


class _PositiveIdfBM25(BM25Okapi):
    """BM25Okapi with the always-positive IDF ln(1 + (N - n + 0.5) / (n + 0.5))."""

    def _calc_idf(self, nd: dict[str, int]) -> None:
        for word, doc_freq in nd.items():
            self.idf[word] = math.log(1 + (self.corpus_size - doc_freq + 0.5) / (doc_freq + 0.5))
        self.average_idf = sum(self.idf.values()) / len(self.idf)


class BM25Retriever:
    """In-memory BM25 index over a fixed collection of chunks.

    `positive_idf=False` selects the library's original Okapi IDF (see the
    module docstring); it is kept for comparison.
    """

    def __init__(self, chunks: Iterable[LegalChunk], *, positive_idf: bool = True) -> None:
        self._chunks = tuple(chunks)
        seen: set[str] = set()
        for chunk in self._chunks:
            if chunk.chunk_id in seen:
                raise ValueError(f"duplicate chunk_id in corpus: {chunk.chunk_id}")
            seen.add(chunk.chunk_id)

        tokenized = [index_tokens(chunk) for chunk in self._chunks]
        self._token_sets = [frozenset(tokens) for tokens in tokenized]
        # BM25Okapi divides by the corpus size and by the average chunk length,
        # so it cannot be built when there is nothing to index.
        bm25_class = _PositiveIdfBM25 if positive_idf else BM25Okapi
        self._bm25 = bm25_class(tokenized) if any(tokenized) else None

    @classmethod
    def from_jsonl(cls, path: Path, *, positive_idf: bool = True) -> BM25Retriever:
        """Build a retriever from a chunk file written by `python -m src.ingestion`."""
        if not path.is_file():
            raise FileNotFoundError(
                f"chunk file not found: {path}. Run `python -m src.ingestion` first."
            )
        return cls(read_chunks(path), positive_idf=positive_idf)

    def __len__(self) -> int:
        return len(self._chunks)

    def search(self, query: str, top_k: int = 5) -> list[RetrievedPassage]:
        """Return up to `top_k` chunks that share a token with `query`, best first.

        Raises TypeError/ValueError for a non-string or blank query and for a
        `top_k` that is not a positive int (booleans are rejected). Returns []
        when the index is empty or no chunk contains a query token.
        """
        if not isinstance(query, str):
            raise TypeError(f"query must be a string (got {type(query).__name__}).")
        if not query.strip():
            raise ValueError("query must not be empty or whitespace.")
        if isinstance(top_k, bool) or not isinstance(top_k, int):
            raise TypeError(f"top_k must be an int (got {type(top_k).__name__}).")
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1 (got {top_k}).")

        query_tokens = tokenize(query)
        if self._bm25 is None or not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)
        query_set = set(query_tokens)
        matches = [
            i for i, tokens in enumerate(self._token_sets) if not query_set.isdisjoint(tokens)
        ]
        matches.sort(key=lambda i: (-scores[i], i))

        return [
            RetrievedPassage(
                chunk=self._chunks[i],
                method=RetrievalMethod.BM25,
                rank=rank,
                score=float(scores[i]),
            )
            for rank, i in enumerate(matches[:top_k], start=1)
        ]


def _format_passage(passage: RetrievedPassage, excerpt_length: int = 240) -> str:
    chunk = passage.chunk
    location = chunk.location
    parts = [location.source_path or "unknown source"]
    if location.page is not None:
        pages = str(location.page)
        if location.page_end not in (None, location.page):
            pages += f"-{location.page_end}"
        parts.append(f"p. {pages}")
    if location.article:
        parts.append(f"art. {location.article}")
    if location.paragraph:
        parts.append(f"par. {location.paragraph}")

    excerpt = " ".join(chunk.text.split())
    if len(excerpt) > excerpt_length:
        excerpt = excerpt[:excerpt_length].rstrip() + " ..."
    return (
        f"#{passage.rank}  score={passage.score:.4f}  {chunk.chunk_id}\n"
        f"    {' | '.join(parts)}\n"
        f"    {excerpt}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.retrieval",
        description="Search ingested chunks with BM25 (lexical matching only).",
    )
    parser.add_argument("query", help="search text")
    parser.add_argument("--top-k", type=int, default=5, help="maximum results (default: 5)")
    parser.add_argument(
        "--chunks",
        type=Path,
        help="JSONL chunk file (default: <DATA_DIR>/processed/chunks.jsonl)",
    )
    args = parser.parse_args(argv)
    # Excerpts may contain characters the console encoding cannot show (e.g.
    # cp1252 on Windows when piped); replace them instead of crashing.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2
    chunks_path = args.chunks or settings.processed_dir / "chunks.jsonl"

    try:
        retriever = BM25Retriever.from_jsonl(chunks_path)
        results = retriever.search(args.query, top_k=args.top_k)
    except (FileNotFoundError, TypeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"Indexed {len(retriever)} chunk(s) from {chunks_path}")
    if not results:
        print("No chunks contain any of the query terms.")
    for passage in results:
        print(_format_passage(passage))
    return 0


if __name__ == "__main__":
    sys.exit(main())
