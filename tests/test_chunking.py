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
