from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from src.models import (
    Citation,
    Claim,
    DocumentMetadata,
    LegalAnswer,
    LegalChunk,
    LegalDocument,
    RetrievalMethod,
    RetrievedPassage,
    SourceLocation,
    VerificationStatus,
)


def make_chunk(**overrides) -> LegalChunk:
    values = {
        "chunk_id": "doc1-0",
        "doc_id": "doc1",
        "text": "Article 1. Example provision.",
        "chunk_index": 0,
    }
    values.update(overrides)
    return LegalChunk(**values)


def test_missing_metadata_stays_unknown():
    doc = LegalDocument(doc_id="doc1", title="Example", content="text")
    metadata = doc.metadata
    assert metadata.jurisdiction is None
    assert metadata.language is None
    assert metadata.publication_date is None
    assert metadata.effective_from is None
    assert metadata.effective_to is None
    assert doc.source_path is None


def test_publication_and_effective_dates_are_distinct():
    metadata = DocumentMetadata(
        publication_date=date(2023, 12, 1),
        effective_from=date(2024, 1, 1),
    )
    assert metadata.publication_date != metadata.effective_from
    assert metadata.effective_to is None


def test_effective_range_must_be_ordered():
    with pytest.raises(ValueError, match="effective_to"):
        DocumentMetadata(effective_from=date(2024, 1, 1), effective_to=date(2023, 1, 1))


def test_source_models_are_immutable():
    chunk = make_chunk()
    with pytest.raises(FrozenInstanceError):
        chunk.text = "changed"  # type: ignore[misc]


def test_chunk_keeps_location_and_inherited_metadata():
    location = SourceLocation(source_path="data/raw/law.pdf", page=3, article="5")
    metadata = DocumentMetadata(jurisdiction="IT", language="it")
    chunk = make_chunk(location=location, metadata=metadata)
    assert chunk.doc_id == "doc1"
    assert chunk.location.page == 3
    assert chunk.location.article == "5"
    assert chunk.metadata.jurisdiction == "IT"


@pytest.mark.parametrize(
    "overrides",
    [{"chunk_id": ""}, {"doc_id": "  "}, {"chunk_index": -1}],
)
def test_invalid_chunks_are_rejected(overrides):
    with pytest.raises(ValueError):
        make_chunk(**overrides)


def test_empty_document_id_is_rejected():
    with pytest.raises(ValueError, match="doc_id"):
        LegalDocument(doc_id="", title="t", content="c")


def test_invalid_page_is_rejected():
    with pytest.raises(ValueError, match="page"):
        SourceLocation(page=0)


def test_page_range():
    assert SourceLocation(page=2, page_end=3).page_end == 3
    with pytest.raises(ValueError, match="page_end"):
        SourceLocation(page=3, page_end=2)
    with pytest.raises(ValueError, match="page_end"):
        SourceLocation(page_end=2)


def test_page_starts_map_offsets_to_pages():
    doc = LegalDocument(doc_id="d", title="t", content="aa\n\nbb", page_starts=(0, 4))
    assert doc.page_at(0) == 1
    assert doc.page_at(4) == 2
    assert LegalDocument(doc_id="d", title="t", content="aa").page_at(0) is None


@pytest.mark.parametrize("starts", [(1,), (0, 5, 3), (0, 99)])
def test_invalid_page_starts_are_rejected(starts):
    with pytest.raises(ValueError, match="page_starts"):
        LegalDocument(doc_id="d", title="t", content="aa\n\nbb", page_starts=starts)


def test_retrieved_passage_rank_is_one_based():
    chunk = make_chunk()
    passage = RetrievedPassage(
        chunk=chunk,
        method=RetrievalMethod.HYBRID,
        rank=1,
        score=0.03,
        method_ranks={RetrievalMethod.BM25: 2, RetrievalMethod.DENSE: 1},
    )
    assert passage.method_ranks[RetrievalMethod.DENSE] == 1
    with pytest.raises(ValueError, match="rank"):
        RetrievedPassage(chunk=chunk, method=RetrievalMethod.BM25, rank=0, score=1.0)


@pytest.mark.parametrize("source_id", ["S1", "S12"])
def test_valid_source_ids(source_id):
    citation = Citation(source_id=source_id, chunk_id="doc1-0", doc_id="doc1", text="x")
    assert citation.source_id == source_id


@pytest.mark.parametrize("source_id", ["", "S0", "s1", "S01", "1", "S1a", "[S1]", "S1\n"])
def test_malformed_source_ids_are_rejected(source_id):
    with pytest.raises(ValueError, match="source_id"):
        Citation(source_id=source_id, chunk_id="doc1-0", doc_id="doc1", text="x")


def test_claims_start_unverified_even_with_citations():
    claim = Claim(text="The provision applies.", source_ids=["S1"])
    assert claim.status is VerificationStatus.NOT_VERIFIED


def test_verification_statuses_match_spec():
    assert {s.value for s in VerificationStatus} == {
        "NOT_VERIFIED",
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "UNSUPPORTED",
        "CONTRADICTED",
        "UNCERTAIN",  # M2 support verification: insufficient or contradictory evidence
    }


def test_abstention_requires_reason():
    answer = LegalAnswer.abstain("No relevant evidence was retrieved.")
    assert answer.abstained is True
    assert answer.claims == []
    assert answer.citations == []

    with pytest.raises(ValueError, match="reason"):
        LegalAnswer(answer_text="", abstained=True)


def test_mutable_defaults_are_not_shared():
    first = LegalAnswer(answer_text="a")
    second = LegalAnswer(answer_text="b")
    first.warnings.append("w")
    assert second.warnings == []
