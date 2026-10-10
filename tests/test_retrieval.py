import math
import subprocess
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from src.chunk_store import read_chunks, write_chunks
from src.chunking import chunk_document
from src.config import PROJECT_ROOT
from src.ingestion import ingest
from src.models import DocumentMetadata, LegalChunk, LegalDocument, RetrievalMethod, SourceLocation
from src.retrieval import BM25Retriever, index_tokens, main, tokenize


def make_chunk(index: int, text: str, doc_id: str = "doc-a", **location) -> LegalChunk:
    return LegalChunk(
        chunk_id=f"{doc_id}-{index:04d}",
        doc_id=doc_id,
        text=text,
        chunk_index=index,
        location=SourceLocation(source_path=f"data/raw/{doc_id}.txt", **location),
    )


CORPUS = [
    make_chunk(0, "Art. 1 (Oggetto) La presente legge disciplina la sicurezza sul lavoro.", article="1"),
    make_chunk(1, "Il datore di lavoro valuta i rischi. Il datore di lavoro nomina il responsabile.", article="2"),
    make_chunk(2, "Le sanzioni si applicano al datore che viola l'articolo 2.", article="3"),
    make_chunk(3, "Personal data breaches shall be notified to the supervisory authority.", doc_id="doc-b"),
    make_chunk(4, "Responsabilità del produttore per danno da prodotti difettosi.", doc_id="doc-b"),
]


@pytest.fixture
def retriever() -> BM25Retriever:
    return BM25Retriever(CORPUS)


def ids(results) -> list[str]:
    return [p.chunk.chunk_id for p in results]


# --- Tokenizer -------------------------------------------------------------------


def test_tokenizer_folds_case_and_strips_punctuation():
    assert tokenize("Il DATORE, di Lavoro!") == ["il", "datore", "di", "lavoro"]


def test_tokenizer_folds_italian_accents_and_apostrophe_accents():
    assert tokenize("Responsabilità") == ["responsabilita"]
    assert tokenize("RESPONSABILITA'") == ["responsabilita"]
    assert tokenize("perché è così") == ["perche", "e", "cosi"]


def test_tokenizer_splits_elisions():
    assert tokenize("dell'articolo l’obbligo") == ["dell", "articolo", "l", "obbligo"]


def test_tokenizer_keeps_legal_identifiers_whole_and_split():
    assert tokenize("Reg. (UE) 2016/679") == ["reg", "ue", "2016/679", "2016", "679"]
    assert tokenize("D.Lgs. 81/2008") == ["d.lgs", "d", "lgs", "81/2008", "81", "2008"]


def test_tokenizer_turns_article_and_paragraph_references_into_structural_tokens():
    assert tokenize("art. 2-bis") == ["art:2-bis", "2-bis", "2", "bis"]
    assert tokenize("Articolo 5, comma 2") == ["art:5", "5", "par:2", "2"]
    assert tokenize("Article 33(1)") == ["art:33", "33", "1"]
    assert tokenize("paragrafo 3") == ["par:3", "3"]
    # Only the first number after the keyword is linked.
    assert tokenize("artt. 5 e 6") == ["art:5", "5", "e", "6"]
    assert tokenize("Art.5") == tokenize("art. 5")  # abbreviation without a space
    assert tokenize("d.lgs") == ["d.lgs", "d", "lgs"]  # other dotted forms unchanged
    # Without a following number the keyword stays an ordinary word.
    assert tokenize("l'articolo non si applica") == ["l", "articolo", "non", "si", "applica"]


def test_tokenizer_keeps_short_words_and_numbers():
    # No stop-word removal: short words can matter in legal text ("lettera a").
    assert tokenize("lettera a) e b), punto 1") == ["lettera", "a", "e", "b", "punto", "1"]


@pytest.mark.parametrize("text", ["", "   ", "— ... ;;"])
def test_tokenizer_returns_nothing_for_text_without_words(text):
    assert tokenize(text) == []


def test_queries_and_chunks_use_the_same_tokenization():
    chunk = make_chunk(0, "RESPONSABILITÀ del Datore di Lavoro")
    retriever = BM25Retriever([chunk, make_chunk(1, "altro testo")])
    assert ids(retriever.search("responsabilita datore")) == [chunk.chunk_id]
    assert ids(retriever.search("Responsabilità")) == [chunk.chunk_id]


# --- Ranking ----------------------------------------------------------------------


def test_finds_the_passage_containing_the_query_terms(retriever):
    results = retriever.search("supervisory authority breach")
    assert ids(results) == ["doc-b-0003"]


def test_ranks_the_most_relevant_passage_first(retriever):
    results = retriever.search("datore di lavoro")
    # Chunk 1 repeats both terms; chunk 2 only mentions "datore"; chunk 0 only "lavoro".
    assert ids(results)[0] == "doc-a-0001"
    assert set(ids(results)) == {"doc-a-0000", "doc-a-0001", "doc-a-0002"}
    scores = [p.score for p in results]
    assert scores == sorted(scores, reverse=True)


def test_ranks_and_method_are_set(retriever):
    results = retriever.search("datore lavoro", top_k=3)
    assert [p.rank for p in results] == [1, 2, 3]
    assert all(p.method is RetrievalMethod.BM25 for p in results)
    assert all(isinstance(p.score, float) for p in results)


FORMULA_TEXTS = ["alpha beta beta", "gamma", "delta", "epsilon zeta", "eta"]


def expected_bm25(idf: float) -> float:
    """BM25 of query "beta" for chunk 0 of FORMULA_TEXTS, given the IDF of "beta"."""
    k1, b = 1.5, 0.75
    term_freq, doc_len, avg_len = 2, 3, (3 + 1 + 1 + 2 + 1) / 5
    return idf * term_freq * (k1 + 1) / (term_freq + k1 * (1 - b + b * doc_len / avg_len))


def test_default_score_uses_the_positive_idf_formula():
    retriever = BM25Retriever([make_chunk(i, t) for i, t in enumerate(FORMULA_TEXTS)])
    [result] = retriever.search("beta")
    n_docs, doc_freq = 5, 1
    idf = math.log(1 + (n_docs - doc_freq + 0.5) / (doc_freq + 0.5))
    assert result.score == pytest.approx(expected_bm25(idf))


def test_okapi_score_matches_the_bm25_okapi_formula():
    chunks = [make_chunk(i, t) for i, t in enumerate(FORMULA_TEXTS)]
    [result] = BM25Retriever(chunks, positive_idf=False).search("beta")
    n_docs, doc_freq = 5, 1
    idf = math.log((n_docs - doc_freq + 0.5) / (doc_freq + 0.5))
    assert result.score == pytest.approx(expected_bm25(idf))


def test_results_preserve_ids_provenance_and_metadata():
    metadata = DocumentMetadata(jurisdiction="IT", effective_from=date(2024, 1, 1))
    chunk = replace(
        make_chunk(7, "Obbligo di notifica entro 72 ore.", page=3, page_end=4, article="33"),
        metadata=metadata,
    )
    retriever = BM25Retriever([chunk, make_chunk(8, "Altro.")])
    [result] = retriever.search("notifica")
    assert result.chunk == chunk
    assert result.chunk.chunk_id == "doc-a-0007"
    assert result.chunk.doc_id == "doc-a"
    assert result.chunk.location.source_path == "data/raw/doc-a.txt"
    assert (result.chunk.location.page, result.chunk.location.page_end) == (3, 4)
    assert result.chunk.metadata == metadata


# --- top_k ------------------------------------------------------------------------


def test_top_k_limits_results(retriever):
    assert len(retriever.search("datore lavoro", top_k=1)) == 1
    assert ids(retriever.search("datore lavoro", top_k=1)) == ids(retriever.search("datore lavoro"))[:1]


def test_large_top_k_returns_only_matching_chunks(retriever):
    results = retriever.search("sanzioni", top_k=100)
    assert ids(results) == ["doc-a-0002"]


@pytest.mark.parametrize("top_k", [0, -1])
def test_non_positive_top_k_is_rejected(retriever, top_k):
    with pytest.raises(ValueError, match="top_k"):
        retriever.search("lavoro", top_k=top_k)


@pytest.mark.parametrize("top_k", [True, False, 2.0, "3", None])
def test_non_int_top_k_is_rejected(retriever, top_k):
    with pytest.raises(TypeError, match="top_k"):
        retriever.search("lavoro", top_k=top_k)


# --- Queries and edge cases --------------------------------------------------------


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_blank_query_is_rejected(retriever, query):
    with pytest.raises(ValueError, match="query"):
        retriever.search(query)


def test_non_string_query_is_rejected(retriever):
    with pytest.raises(TypeError, match="query"):
        retriever.search(None)  # type: ignore[arg-type]


def test_query_without_word_characters_returns_nothing(retriever):
    assert retriever.search("?!") == []


def test_query_terms_absent_from_corpus_return_nothing(retriever):
    assert retriever.search("blockchain criptovalute", top_k=5) == []


def test_empty_corpus_returns_nothing():
    retriever = BM25Retriever([])
    assert len(retriever) == 0
    assert retriever.search("lavoro") == []
    with pytest.raises(ValueError):
        retriever.search(" ")  # validation still applies


def test_corpus_without_indexable_text_returns_nothing():
    retriever = BM25Retriever([make_chunk(0, "—"), make_chunk(1, "...")])
    assert retriever.search("lavoro") == []


def test_matching_chunks_are_returned_even_when_bm25_scores_them_zero():
    # Okapi IDF is 0 for a term found in exactly half of the chunks.
    chunks = [make_chunk(0, "alpha beta"), make_chunk(1, "gamma delta")]
    [result] = BM25Retriever(chunks, positive_idf=False).search("alpha")
    assert result.chunk.chunk_id == "doc-a-0000"
    assert result.score == 0.0


def test_non_matching_chunks_are_never_returned_even_if_they_score_zero():
    retriever = BM25Retriever([make_chunk(0, "alpha"), make_chunk(1, "beta"), make_chunk(2, "gamma")])
    results = retriever.search("alpha", top_k=3)
    assert ids(results) == ["doc-a-0000"]


def test_ties_keep_corpus_order():
    chunks = [make_chunk(i, "identico testo normativo") for i in range(4)]
    chunks.append(make_chunk(4, "altro"))
    retriever = BM25Retriever(chunks)
    results = retriever.search("normativo", top_k=4)
    assert len({p.score for p in results}) == 1
    assert ids(results) == ["doc-a-0000", "doc-a-0001", "doc-a-0002", "doc-a-0003"]


def test_search_is_repeatable_and_does_not_mutate(retriever):
    before = list(CORPUS)
    first = retriever.search("datore lavoro")
    second = retriever.search("datore lavoro")
    assert first == second
    assert list(CORPUS) == before
    assert len(retriever) == len(CORPUS)


def test_duplicate_chunk_ids_are_rejected():
    with pytest.raises(ValueError, match="duplicate chunk_id"):
        BM25Retriever([make_chunk(0, "a"), make_chunk(0, "b")])


# --- Loading from JSONL -------------------------------------------------------------


def write_jsonl(path: Path, chunks) -> Path:
    with path.open("w", encoding="utf-8", newline="\n") as file:
        write_chunks(file, chunks)
    return path


def test_from_jsonl_round_trip(tmp_path):
    path = write_jsonl(tmp_path / "chunks.jsonl", CORPUS)
    retriever = BM25Retriever.from_jsonl(path)
    assert len(retriever) == len(CORPUS)
    [result] = retriever.search("prodotti difettosi")
    assert result.chunk == CORPUS[4]


def test_from_jsonl_on_real_ingestion_output(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "legge.txt").write_text(
        "Capo I\n\nArt. 1 (Oggetto)\n1. Disciplina la tutela dei dati personali.\n\n"
        "Art. 2 (Sanzioni)\n1. Le sanzioni amministrative sono applicate dal Garante.\n",
        encoding="utf-8",
    )
    (raw / "legge.txt.meta.json").write_text('{"jurisdiction": "IT"}', encoding="utf-8")
    output = tmp_path / "chunks.jsonl"
    ingest(raw, output, chunk_size=1200, chunk_overlap=150)

    [result] = BM25Retriever.from_jsonl(output).search("sanzioni Garante")
    assert result.chunk.location.article == "2"
    assert result.chunk.location.section == "Capo I"
    assert result.chunk.location.source_path.endswith("legge.txt")
    assert result.chunk.metadata.jurisdiction == "IT"


def test_long_ordinal_suffix_is_indexed_as_its_own_article():
    # Regression: "2-undecies" used to be labelled article "2", so it was indexed as
    # "art:2" and competed with article 2 for "articolo 2".
    #
    # The continuation chunk of article 2-undecies repeats neither its heading nor any
    # number, so only its structural token can connect it to a query: the search
    # assertions below depend on the article label, not on words in the text.
    content = (
        "Art. 2 (Definizioni)\n1. Testo sintetico del secondo articolo.\n\n"
        "Art. 2-undecies (Limitazioni)\n1. Le limitazioni sono previste dalla legge.\n\n"
        "Le limitazioni restano soggette a revisione periodica da parte del titolare.\n"
    )
    document = LegalDocument(doc_id="doc-x", title="x", content=content)
    article_2, heading_chunk, continuation = chunk_document(document, 120, 0)
    assert continuation.text.startswith("Le limitazioni restano")  # no heading text
    assert [c.location.article for c in (heading_chunk, continuation)] == ["2-undecies"] * 2

    for chunk in (heading_chunk, continuation):
        tokens = index_tokens(chunk)
        assert "art:2-undecies" in tokens
        assert "art:2" not in tokens

    retriever = BM25Retriever([article_2, heading_chunk, continuation])
    found_by_suffix = [p.chunk for p in retriever.search("art. 2-undecies", top_k=3)]
    found_by_number = [p.chunk for p in retriever.search("articolo 2", top_k=3)]
    assert continuation in found_by_suffix  # reached only through "art:2-undecies"
    assert continuation not in found_by_number  # no longer indexed as article 2
    assert found_by_number[0] is article_2


def test_from_jsonl_empty_file(tmp_path):
    path = tmp_path / "chunks.jsonl"
    path.write_text("", encoding="utf-8")
    assert BM25Retriever.from_jsonl(path).search("lavoro") == []


def test_from_jsonl_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="src.ingestion"):
        BM25Retriever.from_jsonl(tmp_path / "missing.jsonl")


def test_from_jsonl_malformed_file(tmp_path):
    path = write_jsonl(tmp_path / "chunks.jsonl", CORPUS[:1])
    with path.open("a", encoding="utf-8") as file:
        file.write('{"chunk_id": "broken"\n')
    with pytest.raises(ValueError, match="line 2"):
        BM25Retriever.from_jsonl(path)


# --- CLI --------------------------------------------------------------------------


def test_cli_prints_ranked_results(tmp_path, capsys):
    path = write_jsonl(tmp_path / "chunks.jsonl", CORPUS)
    code = main(["datore di lavoro", "--top-k", "2", "--chunks", str(path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "Indexed 5 chunk(s)" in out
    assert "#1  score=" in out and "doc-a-0001" in out
    assert "#2  score=" in out
    assert "#3" not in out


def test_cli_no_matches(tmp_path, capsys):
    path = write_jsonl(tmp_path / "chunks.jsonl", CORPUS)
    assert main(["blockchain", "--chunks", str(path)]) == 0
    assert "No chunks contain any of the query terms." in capsys.readouterr().out


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["lavoro", "--chunks", "MISSING"], "chunk file not found"),
        (["  ", "--chunks", "CHUNKS"], "query must not be empty"),
        (["lavoro", "--top-k", "0", "--chunks", "CHUNKS"], "top_k must be >= 1"),
    ],
)
def test_cli_errors_exit_with_code_2(tmp_path, capsys, args, message):
    chunks = write_jsonl(tmp_path / "chunks.jsonl", CORPUS)
    args = [
        {"MISSING": str(tmp_path / "missing.jsonl"), "CHUNKS": str(chunks)}.get(a, a) for a in args
    ]
    assert main(args) == 2
    assert message in capsys.readouterr().err


def test_cli_module_entry_point_handles_non_console_characters(tmp_path):
    chunk = make_chunk(0, "Obbligo ≥ 72 ore; ﬁne del termine — «notifica».")
    path = write_jsonl(tmp_path / "chunks.jsonl", [chunk])
    run = subprocess.run(
        [sys.executable, "-m", "src.retrieval", "notifica", "--chunks", str(path)],
        cwd=PROJECT_ROOT, capture_output=True, check=False,
    )
    assert run.returncode == 0, run.stderr
    assert b"doc-a-0000" in run.stdout


# --- Structural metadata in the index ----------------------------------------------

GENERAL = "Capo I - Disposizioni generali"
PREVENTION = "Capo II - Prevenzione"
SANCTIONS = "Capo III - Sanzioni"


def make_article(index: int, text: str, article: str, paragraph: str, section: str) -> LegalChunk:
    return make_chunk(index, text, article=article, paragraph=paragraph, section=section)


# A small law in which bare numbers such as "5" are common (as in real legal
# text) while each article has only a few chunks. Chunks 5 and 6 continue
# article 5 without repeating its heading.
STRUCTURED = [
    make_article(0, "Art. 1 (Oggetto)\n1. La domanda è presentata entro 5 giorni.", "1", "1", GENERAL),
    make_article(1, "Art. 2 (Aliquote)\n1. L'aliquota è pari al 5 per cento.", "2", "1", GENERAL),
    make_article(2, "Art. 3 (Durata)\n1. Il registro è conservato per 5 anni.", "3", "1", GENERAL),
    make_article(3, "Art. 4 (Definizioni)\n1. Per datore si intende il titolare.", "4", "1", GENERAL),
    make_article(
        4,
        f"{PREVENTION}\n\nArt. 5 (Misure di prevenzione)\n1. Il datore adotta le misure tecniche.",
        "5", "1", PREVENTION,
    ),
    make_article(5, "adotta inoltre le procedure di emergenza e di evacuazione.", "5", "1", PREVENTION),
    make_article(6, "2. Le misure sono riesaminate periodicamente.", "5", "2", PREVENTION),
    make_article(
        7,
        f"{SANCTIONS}\n\nArt. 9 (Sanzioni)\n1. Chi viola l'articolo 5 è punito con sanzione.",
        "9", "1", SANCTIONS,
    ),
]
ARTICLE_5_IDS = {"doc-a-0004", "doc-a-0005", "doc-a-0006"}


def test_index_tokens_append_missing_metadata_once():
    chunk = STRUCTURED[5]
    text_tokens = tokenize(chunk.text)
    tokens = index_tokens(chunk)
    assert tokens[: len(text_tokens)] == text_tokens  # the text comes first, unchanged
    assert tokens[len(text_tokens) :] == ["capo", "ii", "prevenzione", "art:5", "par:1"]


def test_index_tokens_do_not_duplicate_terms_already_in_the_text():
    chunk = STRUCTURED[4]  # the heading chunk already contains the section heading
    text_tokens = tokenize(chunk.text)
    tokens = index_tokens(chunk)
    for word in ("capo", "ii", "prevenzione"):
        assert tokens.count(word) == text_tokens.count(word)  # metadata adds nothing
    assert tokens.count("art:5") == 1  # the heading's own "art:5" is replaced, not doubled
    assert tokens.count("par:1") == 1


def test_references_in_running_text_are_not_structural_tokens():
    tokens = index_tokens(STRUCTURED[7])  # "Chi viola l'articolo 5 ..."
    assert "art:5" not in tokens
    assert "art:9" in tokens  # from the chunk's own metadata
    assert "5" in tokens  # the number stays searchable as a word


def test_chunk_without_structure_is_indexed_by_its_text_only():
    chunk = make_chunk(0, "Testo libero senza struttura.")
    assert index_tokens(chunk) == tokenize(chunk.text)


@pytest.mark.parametrize("query", ["articolo 5", "art. 5", "Art.5", "Article 5"])
def test_article_is_retrieved_by_identifier_including_continuation_chunks(query):
    assert "5" not in tokenize(STRUCTURED[5].text)  # no heading, no number in the text
    results = BM25Retriever(STRUCTURED).search(query, top_k=3)
    assert set(ids(results)) == ARTICLE_5_IDS


def test_chunk_citing_an_article_ranks_below_the_article_itself():
    results = BM25Retriever(STRUCTURED).search("articolo 5", top_k=10)
    ranks = {p.chunk.chunk_id: p.rank for p in results}
    assert ranks["doc-a-0007"] > max(ranks[i] for i in ARTICLE_5_IDS)


def test_paragraph_reference_prefers_the_matching_paragraph():
    results = BM25Retriever(STRUCTURED).search("art. 5 comma 2")
    assert ids(results)[0] == "doc-a-0006"


def test_section_heading_finds_continuation_chunks():
    results = BM25Retriever(STRUCTURED).search("prevenzione", top_k=10)
    assert set(ids(results)) == ARTICLE_5_IDS


def test_displayed_text_is_not_changed_by_indexing():
    [result, *_] = BM25Retriever(STRUCTURED).search("procedure di emergenza")
    assert result.chunk is STRUCTURED[5]
    assert result.chunk.text == "adotta inoltre le procedure di emergenza e di evacuazione."


def test_article_lookup_on_real_ingestion_output(tmp_path):
    long_paragraph = " ".join(
        f"Il datore di lavoro adotta la misura di prevenzione numero {i}." for i in range(1, 16)
    )
    articles = "\n\n".join(
        f"Art. {n} (Titolo {n})\n1. Disposizione {n}, con termine di 5 giorni." for n in (1, 2, 3, 4)
    )
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "legge.txt").write_text(
        f"{articles}\n\nArt. 5 (Prevenzione)\n1. {long_paragraph}\n\n"
        "Art. 9 (Sanzioni)\n1. Chi viola l'articolo 5 è punito.\n",
        encoding="utf-8",
    )
    output = tmp_path / "chunks.jsonl"
    ingest(raw, output, chunk_size=300, chunk_overlap=50)

    chunks = list(read_chunks(output))
    article_5 = [c for c in chunks if c.location.article == "5"]
    assert len(article_5) >= 3
    assert any("Art. 5" not in c.text for c in article_5)  # continuation chunks exist

    results = BM25Retriever(chunks).search("articolo 5", top_k=len(article_5))
    assert {p.chunk.chunk_id for p in results} == {c.chunk_id for c in article_5}


# --- Scoring variants ---------------------------------------------------------------

# "common" and "filler" each occur in 4 of 5 chunks, so their Okapi IDF is
# negative and the floor (0.25 x average IDF) is negative too.
INVERSION = [
    make_chunk(0, "rare common"),
    make_chunk(1, "rare filler"),
    make_chunk(2, "common filler"),
    make_chunk(3, "common filler"),
    make_chunk(4, "common filler"),
]


def test_zero_idf_regression():
    chunks = [make_chunk(0, "alpha beta"), make_chunk(1, "gamma delta")]
    [okapi] = BM25Retriever(chunks, positive_idf=False).search("alpha")
    [positive] = BM25Retriever(chunks).search("alpha")
    assert okapi.chunk == positive.chunk == chunks[0]
    assert okapi.score == 0.0
    assert positive.score > 0.0


def test_negative_idf_regression_okapi_inverts_the_ranking():
    okapi = BM25Retriever(INVERSION, positive_idf=False).search("rare common")
    # Chunk 0 matches both query terms, yet ranks below chunk 1, which matches one.
    assert ids(okapi)[:2] == ["doc-a-0001", "doc-a-0000"]
    assert any(p.score < 0 for p in okapi)


def test_negative_idf_regression_positive_idf_ranks_the_fuller_match_first():
    positive = BM25Retriever(INVERSION).search("rare common")
    assert ids(positive)[:2] == ["doc-a-0000", "doc-a-0001"]
    assert all(p.score > 0 for p in positive)


@pytest.mark.parametrize("positive_idf", [True, False])
def test_both_variants_return_only_and_all_matching_chunks(positive_idf):
    cases = [(INVERSION, "rare common"), (STRUCTURED, "datore misure"), (CORPUS, "lavoro")]
    for corpus, query in cases:
        results = BM25Retriever(corpus, positive_idf=positive_idf).search(query, top_k=100)
        query_tokens = set(tokenize(query))
        expected = [c.chunk_id for c in corpus if query_tokens & set(index_tokens(c))]
        assert sorted(ids(results)) == sorted(expected)


def test_positive_idf_scores_every_match_above_zero():
    cases = [(INVERSION, "common"), (STRUCTURED, "il datore 5"), (CORPUS, "di lavoro")]
    for corpus, query in cases:
        results = BM25Retriever(corpus).search(query, top_k=100)
        assert results
        assert all(p.score > 0 for p in results)


@pytest.mark.parametrize("positive_idf", [True, False])
def test_ties_are_deterministic_for_both_variants(positive_idf):
    results = BM25Retriever(INVERSION, positive_idf=positive_idf).search("filler", top_k=5)
    assert ids(results) == ["doc-a-0001", "doc-a-0002", "doc-a-0003", "doc-a-0004"]


def test_from_jsonl_accepts_the_scoring_variant(tmp_path):
    path = write_jsonl(tmp_path / "chunks.jsonl", INVERSION)
    assert ids(BM25Retriever.from_jsonl(path).search("rare common"))[0] == "doc-a-0000"
    okapi = BM25Retriever.from_jsonl(path, positive_idf=False)
    assert ids(okapi.search("rare common"))[0] == "doc-a-0001"


# --- Italian legal queries: what lexical matching does and does not cover -----------


@pytest.mark.parametrize(
    ("query", "text"),
    [
        ("responsabilità del datore", "RESPONSABILITA' DEL DATORE DI LAVORO"),
        ("dell'obbligo di sicurezza", "L'obbligo di sicurezza grava sul datore."),
        ("D.Lgs. 81/2008", "ai sensi del d.lgs. n. 81/2008"),
        ("decreto 81/2008", "ai sensi del d.lgs. n. 81/2008"),
        ("Regolamento UE 2016/679", "il regolamento (UE) 2016/679 si applica"),
    ],
)
def test_italian_query_variants_that_match(query, text):
    chunk = make_chunk(0, text)
    results = BM25Retriever([chunk, make_chunk(1, "testo non pertinente")]).search(query)
    assert ids(results) == [chunk.chunk_id]


@pytest.mark.parametrize(
    ("query", "text"),
    [
        # Inflection: no stemming, so singular and plural forms differ.
        ("obblighi", "L'obbligo del datore di lavoro."),
        ("obbligo", "Gli obblighi del datore di lavoro."),
        ("lavoratori", "Il lavoratore riceve la formazione."),
        ("sanzioni", "Si applica una sanzione pecuniaria."),
        # Abbreviations and synonyms are not expanded.
        ("decreto legislativo", "ai sensi del d.lgs. n. 81/2008"),
        ("licenziamento", "Il recesso del datore deve essere motivato."),
    ],
)
def test_limitation_inflections_abbreviations_and_synonyms_do_not_match(query, text):
    chunk = make_chunk(0, text)
    assert BM25Retriever([chunk, make_chunk(1, "testo non pertinente")]).search(query) == []
