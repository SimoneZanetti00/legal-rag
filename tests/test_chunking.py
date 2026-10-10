import re

import pytest

from src.chunking import chunk_document
from src.models import DocumentMetadata, LegalDocument

STRUCTURED_TEXT = """\
Preamble of a synthetic regulation.

Chapter I - General provisions

Article 1 - Scope
1. This regulation applies to synthetic examples.
2. It does not apply to real cases.

Article 2 (Definitions)
For the purposes of this regulation, "example" means a test fixture.

Chapter II

Article 3
The obligations under Article 5 of Directive 2000/1 remain unaffected.
Article 5 of Directive 2000/1 is referenced here only in running text.
"""


def make_doc(content: str, page_starts: tuple[int, ...] = (), **kwargs) -> LegalDocument:
    return LegalDocument(
        doc_id="doc-test", title="t", content=content, page_starts=page_starts, **kwargs
    )


def assert_valid_chunks(doc: LegalDocument, chunks, chunk_size: int) -> None:
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    for chunk in chunks:
        assert chunk.text
        assert chunk.text == chunk.text.strip()
        assert chunk.text in doc.content  # exact substring of the source
        assert len(chunk.text) <= chunk_size
        assert chunk.doc_id == doc.doc_id


def words(text: str) -> list[str]:
    return text.split()


@pytest.mark.parametrize("content", ["", "   ", "\n\n \t\n"])
def test_blank_content_produces_no_chunks(content):
    assert chunk_document(make_doc(content), 100, 10) == []


def test_headings_start_new_chunks_and_carry_structure():
    doc = make_doc(STRUCTURED_TEXT)
    chunks = chunk_document(doc, 1200, 150)
    assert_valid_chunks(doc, chunks, 1200)

    summary = [(c.location.section, c.location.article, c.text.splitlines()[0]) for c in chunks]
    assert summary == [
        (None, None, "Preamble of a synthetic regulation."),
        ("Chapter I - General provisions", "1", "Chapter I - General provisions"),
        ("Chapter I - General provisions", "2", "Article 2 (Definitions)"),
        ("Chapter II", "3", "Chapter II"),
    ]


def test_heading_text_is_kept_in_chunk_text():
    chunks = chunk_document(make_doc(STRUCTURED_TEXT), 1200, 150)
    assert chunks[1].text.startswith("Chapter I - General provisions\n\nArticle 1 - Scope\n1.")


def test_article_reference_in_running_text_is_not_a_heading():
    chunks = chunk_document(make_doc(STRUCTURED_TEXT), 1200, 150)
    last = chunks[-1]
    assert last.location.article == "3"
    assert "Article 5 of Directive 2000/1 is referenced" in last.text


def test_numbered_paragraphs_inside_an_article_are_labelled():
    chunks = chunk_document(make_doc(STRUCTURED_TEXT), 1200, 150)
    assert chunks[1].location.paragraph == "1, 2"
    assert chunks[2].location.paragraph is None


def test_numbered_lines_outside_articles_are_not_labelled():
    chunks = chunk_document(make_doc("1. First item.\n2. Second item."), 1200, 150)
    assert len(chunks) == 1
    assert chunks[0].location.paragraph is None


def test_italian_headings_and_ordinal_suffixes():
    text = "Capo I\n\nArt. 2-bis (Definizioni)\n1. Testo del comma.\n1-bis. Comma aggiunto."
    chunks = chunk_document(make_doc(text), 1200, 150)
    assert len(chunks) == 1
    assert chunks[0].location.section == "Capo I"
    assert chunks[0].location.article == "2-bis"
    assert chunks[0].location.paragraph == "1, 1-bis"


# Ordinal suffixes. The first group was supported before and keeps its joiners
# (hyphen, space or nothing). The second group was added for inserted articles
# such as "2-undecies" and is accepted only after a hyphen. Both groups follow
# Italian drafting practice as generally described; the added forms have not been
# checked against any legal text in this repository.
ORDINAL_SUFFIXES_UP_TO_DECIES = [
    "bis", "ter", "quater", "quinquies", "sexies", "septies", "octies", "novies", "decies",
]
ORDINAL_SUFFIXES_AFTER_DECIES = [
    "undecies", "duodecies", "terdecies", "quaterdecies", "quinquiesdecies", "sexiesdecies",
    "septiesdecies", "octiesdecies", "noviesdecies", "vicies",
    "quindecies", "sedecies", "duodevicies", "undevicies",
]
ORDINAL_SUFFIXES = ORDINAL_SUFFIXES_UP_TO_DECIES + ORDINAL_SUFFIXES_AFTER_DECIES


@pytest.mark.parametrize("suffix", ORDINAL_SUFFIXES)
def test_article_heading_keeps_its_ordinal_suffix(suffix):
    chunks = chunk_document(make_doc(f"Art. 2-{suffix} (Titolo)\n1. Testo del comma."), 1200, 150)
    assert [c.location.article for c in chunks] == [f"2-{suffix}"]


@pytest.mark.parametrize("suffix", ORDINAL_SUFFIXES)
def test_paragraph_label_keeps_its_ordinal_suffix(suffix):
    text = f"Art. 3 (Titolo)\n1. Primo comma.\n1-{suffix}. Comma inserito.\n2. Secondo comma."
    chunks = chunk_document(make_doc(text), 1200, 150)
    assert [c.location.paragraph for c in chunks] == [f"1, 1-{suffix}, 2"]


@pytest.mark.parametrize(
    ("heading", "article"),
    [
        ("Articolo 2-undecies", "2-undecies"),  # no title
        ("Art. 2-undecies - Limitazioni", "2-undecies"),
        ("Art. 2-undecies: Limitazioni", "2-undecies"),
        ("ART. 2-UNDECIES (LIMITAZIONI)", "2-UNDECIES"),  # the label keeps the source's case
        ("Art. 2-terdecies (Titolo)", "2-terdecies"),  # not cut short to "2-ter"
        ("Art. 2-quaterdecies (Titolo)", "2-quaterdecies"),  # not cut short to "2-quater"
    ],
)
def test_long_ordinal_suffix_in_other_heading_forms(heading, article):
    chunks = chunk_document(make_doc(f"{heading}\n1. Testo del comma."), 1200, 150)
    assert [c.location.article for c in chunks] == [article]


@pytest.mark.parametrize(
    ("heading", "article"),
    [
        ("Art. 5 - Scope", "5"),
        ("Art. 5-Scope", "5"),
        ("Art. 5. Scope", "5"),
        ("Articolo 5: Scope", "5"),
        ("Art. 2-bis (Definizioni)", "2-bis"),
        ("Art. 2 bis (Definizioni)", "2 bis"),
        ("Art. 2-ter", "2-ter"),
    ],
)
def test_ordinary_article_headings_are_unchanged(heading, article):
    chunks = chunk_document(make_doc(f"{heading}\n1. Testo.\n1-bis. Testo inserito."), 1200, 150)
    assert [(c.location.article, c.location.paragraph) for c in chunks] == [(article, "1, 1-bis")]


@pytest.mark.parametrize(
    ("heading", "article"),
    [
        ("Art. 2 bis (Definizioni)", "2 bis"),  # space
        ("Art. 2bis (Definizioni)", "2bis"),  # nothing
        ("Articolo 2 decies", "2 decies"),
    ],
)
def test_original_suffixes_keep_their_joiners(heading, article):
    text = f"{heading}\n1. Testo.\n1 bis. Testo inserito."
    chunks = chunk_document(make_doc(text), 1200, 150)
    assert [(c.location.article, c.location.paragraph) for c in chunks] == [(article, "1, 1 bis")]


@pytest.mark.parametrize(
    "heading",
    [
        "Art. 2 undecies (Limitazioni)",  # space
        "Art. 2undecies (Limitazioni)",  # nothing
        "Articolo 2 quinquiesdecies",
    ],
)
def test_added_suffixes_need_a_hyphen_so_no_new_heading_form_is_accepted(heading):
    # None of these lines was a heading before the added suffixes, and none is now.
    chunks = chunk_document(make_doc(f"Testo precedente.\n\n{heading}\n1. Testo."), 1200, 150)
    assert [c.location.article for c in chunks] == [None]


def test_added_suffixes_need_a_hyphen_in_paragraph_numbers_too():
    text = "Art. 3 (Titolo)\n1. Primo comma.\n1 undecies. Testo.\n2. Secondo comma."
    chunks = chunk_document(make_doc(text), 1200, 150)
    assert [c.location.paragraph for c in chunks] == ["1, 2"]


LONG_SENTENCES = "Il titolare adotta misure tecniche e organizzative adeguate. " * 12


@pytest.mark.parametrize("suffix", ORDINAL_SUFFIXES_AFTER_DECIES)
def test_inserted_paragraph_with_an_added_suffix_is_cut_like_1_bis(suffix):
    def article(number: str) -> str:
        return f"Art. 3 (Titolo)\n1. {LONG_SENTENCES}\n{number}. {LONG_SENTENCES}\n2. Fine."

    with_bis = chunk_document(make_doc(article("1-bis")), 1200, 150)
    with_suffix = chunk_document(make_doc(article(f"1-{suffix}")), 1200, 150)
    # Same cut, at the start of the inserted paragraph; only the label differs.
    assert len(with_bis) == len(with_suffix) == 2
    assert with_bis[0].text == with_suffix[0].text
    assert with_suffix[1].text.startswith(f"1-{suffix}. ")
    assert [c.location.paragraph for c in with_bis] == ["1", "1-bis, 2"]
    assert [c.location.paragraph for c in with_suffix] == ["1", f"1-{suffix}, 2"]


@pytest.mark.parametrize("suffix", ORDINAL_SUFFIXES_AFTER_DECIES)
def test_article_with_an_added_suffix_starts_a_unit_like_2_bis(suffix):
    def decree(number: str) -> str:
        return (
            f"Art. 2 (A)\n1. Testo.\n\nArt. {number} (B)\n1. Testo.\n\nArt. 3 (C)\n1. Testo."
        )

    with_bis = chunk_document(make_doc(decree("2-bis")), 1200, 150)
    with_suffix = chunk_document(make_doc(decree(f"2-{suffix}")), 1200, 150)
    assert [c.location.article for c in with_bis] == ["2", "2-bis", "3"]
    assert [c.location.article for c in with_suffix] == ["2", f"2-{suffix}", "3"]
    assert [c.text.replace(f"2-{suffix}", "2-bis") for c in with_suffix] == [c.text for c in with_bis]


@pytest.mark.parametrize(
    "heading",
    [
        "Art. 2-tricies (Titolo)",  # beyond the supported list
        "Art. 2-vicies semel (Titolo)",  # two-word forms are not supported
    ],
)
def test_unsupported_ordinal_suffixes_are_a_known_limitation(heading):
    # Documents current behaviour, not a desired result: the suffix is read as the
    # start of the title, so the article is labelled with its number alone.
    chunks = chunk_document(make_doc(f"{heading}\n1. Testo."), 1200, 150)
    assert [c.location.article for c in chunks] == ["2"]


def test_bare_number_after_article_word_is_not_a_heading():
    # "Article 5." ending a wrapped line is running text, not a heading.
    chunks = chunk_document(make_doc("As required by\nArticle 5.\nThe rest follows."), 1200, 150)
    assert chunks[0].location.article is None


def test_paragraphs_are_packed_and_cut_only_at_paragraph_boundaries():
    paragraphs = [f"Paragraph {i} " + "word " * 12 for i in range(10)]
    doc = make_doc("\n\n".join(p.strip() for p in paragraphs))
    chunks = chunk_document(doc, 200, 50)
    assert_valid_chunks(doc, chunks, 200)
    assert len(chunks) > 1
    for chunk in chunks:
        # Every chunk starts at a paragraph start and ends at a paragraph end.
        assert chunk.text.startswith("Paragraph")
        assert chunk.text.endswith("word")
    # No overlap at clean paragraph boundaries: each paragraph appears once.
    assert sum(c.text.count("Paragraph") for c in chunks) == 10


def test_oversized_paragraph_is_split_with_overlap():
    sentences = " ".join(f"Sentence number {i} states a rule." for i in range(40))
    doc = make_doc(f"Article 7\n{sentences}")
    chunks = chunk_document(doc, 200, 60)
    assert_valid_chunks(doc, chunks, 200)
    assert len(chunks) > 3
    assert all(c.location.article == "7" for c in chunks)

    for previous, current in zip(chunks, chunks[1:]):
        # Pieces overlap: the next piece starts inside the previous one.
        prev_start = doc.content.index(previous.text)
        cur_start = doc.content.index(current.text, prev_start + 1)
        assert prev_start < cur_start < prev_start + len(previous.text)
        # ...and starts at a word boundary.
        assert doc.content[cur_start - 1].isspace()

    # Nothing is lost: every sentence appears in some chunk.
    for i in range(40):
        assert any(f"Sentence number {i} " in c.text for c in chunks)


def test_oversized_paragraph_prefers_sentence_ends():
    sentences = " ".join(f"Rule {i} applies here." for i in range(30))
    chunks = chunk_document(make_doc(sentences), 150, 0)
    assert all(c.text.endswith(".") for c in chunks)


def test_zero_overlap_splits_without_repetition():
    text = " ".join(f"w{i}" for i in range(300))
    doc = make_doc(text)
    chunks = chunk_document(doc, 100, 0)
    assert_valid_chunks(doc, chunks, 100)
    assert [w for c in chunks for w in words(c.text)] == words(text)


def test_text_without_whitespace_is_hard_cut():
    doc = make_doc("x" * 250)
    chunks = chunk_document(doc, 100, 20)
    assert_valid_chunks(doc, chunks, 100)
    assert len(chunks) >= 3


@pytest.mark.parametrize(("size", "overlap"), [(1, 0), (10, 9), (50, 49), (7, 3)])
def test_extreme_settings_terminate_without_empty_chunks(size, overlap):
    doc = make_doc("Article 1\n" + "Lorem ipsum dolor sit amet, consectetur. " * 20)
    chunks = chunk_document(doc, size, overlap)
    assert_valid_chunks(doc, chunks, size)
    joined = "".join(c.text for c in chunks)
    assert set(re.sub(r"\s", "", doc.content)) <= set(joined)


@pytest.mark.parametrize(("size", "overlap"), [(0, 0), (-5, 0), (100, 100), (100, -1)])
def test_invalid_settings_are_rejected(size, overlap):
    with pytest.raises(ValueError):
        chunk_document(make_doc("text"), size, overlap)


def test_page_range_is_derived_from_offsets():
    page1 = "Article 1\nFirst page text."
    page2 = "continues on the second page."
    page3 = "Article 2\nThird page."
    content = f"{page1}\n\n{page2}\n\n{page3}"
    starts = (0, len(page1) + 2, len(page1) + len(page2) + 4)
    chunks = chunk_document(make_doc(content, starts), 1200, 150)

    assert [(c.location.page, c.location.page_end) for c in chunks] == [(1, 2), (3, 3)]


def test_unpaginated_text_has_no_page():
    chunks = chunk_document(make_doc("Plain text."), 100, 10)
    assert chunks[0].location.page is None
    assert chunks[0].location.page_end is None


def test_provenance_and_metadata_are_inherited():
    metadata = DocumentMetadata(jurisdiction="EU", language="en")
    doc = make_doc(STRUCTURED_TEXT, source_path="data/raw/reg.txt", metadata=metadata)
    for chunk in chunk_document(doc, 300, 50):
        assert chunk.doc_id == "doc-test"
        assert chunk.location.source_path == "data/raw/reg.txt"
        assert chunk.metadata == metadata


def test_chunk_ids_are_deterministic_and_content_sensitive():
    first = chunk_document(make_doc(STRUCTURED_TEXT), 300, 50)
    second = chunk_document(make_doc(STRUCTURED_TEXT), 300, 50)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert len({c.chunk_id for c in first}) == len(first)
    assert all(re.fullmatch(r"doc-test-\d{4}-[0-9a-f]{8}", c.chunk_id) for c in first)

    edited = chunk_document(make_doc(STRUCTURED_TEXT.replace("test fixture", "sample")), 300, 50)
    changed = [a.chunk_id != b.chunk_id for a, b in zip(first, edited)]
    assert changed == [a.text != b.text for a, b in zip(first, edited)]
    assert any(changed)
