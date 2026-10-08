"""Dense retrieval tests. No real model is loaded: encoders are deterministic fakes,
and `sentence_transformers` is replaced by a fake module where the real path is
exercised. The only real-model test is opt-in (RUN_REAL_MODEL_TESTS=1) and never
downloads anything."""

import hashlib
import json
import os
import re
import sys
import types
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from src.config import PROJECT_ROOT, Settings
from src.dense_retrieval import (
    DEFAULT_MODEL,
    DenseRetriever,
    SentenceTransformerEncoder,
    input_prefixes,
    main,
)
from src.models import DocumentMetadata, LegalChunk, RetrievalMethod, SourceLocation
from src.retrieval import BM25Retriever
from src.retrieval_eval import main as eval_main
from src.retrieval_eval import run_evaluation

FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "synthetic_retrieval"
FIXTURE_CHUNKS = FIXTURE / "chunks.jsonl"
E5_NAME = "fake/multilingual-e5-test"  # contains an "e5" part, so E5 prefixes apply


def bag_of_words(text: str, dim: int = 512) -> np.ndarray:
    """Deterministic stand-in for an embedding: hashed word counts, prefixes ignored."""
    vector = np.zeros(dim, dtype=np.float32)
    for word in re.findall(r"\w+", text.lower()):
        if word not in {"query", "passage"}:
            vector[int(hashlib.sha256(word.encode()).hexdigest(), 16) % dim] += 1
    return vector


class FakeEncoder:
    def __init__(self, scale: float = 1.0) -> None:
        self.scale = scale
        self.calls: list[list[str]] = []

    def encode(self, texts: list[str]) -> np.ndarray:
        self.calls.append(list(texts))
        return np.stack([bag_of_words(t) for t in texts]) * self.scale


def make_chunk(index: int, text: str, **location) -> LegalChunk:
    return LegalChunk(
        chunk_id=f"doc-a-{index:04d}",
        doc_id="doc-a",
        text=text,
        chunk_index=index,
        location=SourceLocation(source_path="data/raw/doc-a.txt", **location),
    )


CORPUS = [
    make_chunk(0, "La presente legge disciplina la sicurezza sul lavoro.", article="1"),
    make_chunk(1, "Il datore di lavoro valuta i rischi e nomina il responsabile.", article="2"),
    make_chunk(2, "Le sanzioni amministrative sono applicate dall'ispettorato.", article="3"),
    make_chunk(3, "The controller notifies a personal data breach within 72 hours.", article="33"),
    make_chunk(4, "Responsabilità del produttore per prodotti difettosi.", article="4"),
]


def dense(chunks=CORPUS, **kwargs) -> DenseRetriever:
    kwargs.setdefault("encoder", FakeEncoder())
    kwargs.setdefault("model_name", E5_NAME)
    return DenseRetriever(chunks, **kwargs)


def ids(results) -> list[str]:
    return [p.chunk.chunk_id for p in results]


@pytest.fixture
def fake_sentence_transformers(monkeypatch):
    """Replace the sentence_transformers module; returns the fake model class."""

    class FakeSentenceTransformer:
        instances: list["FakeSentenceTransformer"] = []

        def __init__(self, model_name: str, local_files_only: bool = False) -> None:
            self.model_name = model_name
            self.encode_kwargs: list[dict] = []
            FakeSentenceTransformer.instances.append(self)

        def encode(self, texts, **kwargs):
            self.encode_kwargs.append(kwargs)
            vectors = np.stack([bag_of_words(t) for t in texts])
            return vectors / np.linalg.norm(vectors, axis=1, keepdims=True).clip(min=1e-12)

    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    return FakeSentenceTransformer


# --- Ranking and similarity ------------------------------------------------------------


def test_ranks_the_most_similar_chunk_first():
    results = dense().search("rischi del datore di lavoro", top_k=3)
    assert ids(results)[0] == "doc-a-0001"
    scores = [p.score for p in results]
    assert scores == sorted(scores, reverse=True)


def test_score_is_cosine_similarity_of_the_prefixed_texts():
    [result] = dense().search("data breach", top_k=1)
    query = bag_of_words("query: data breach")
    passage = bag_of_words("passage: " + CORPUS[3].text)
    expected = float(query @ passage / (np.linalg.norm(query) * np.linalg.norm(passage)))
    assert result.chunk.chunk_id == "doc-a-0003"
    assert result.score == pytest.approx(expected, abs=1e-6)


def test_vector_length_does_not_change_scores():
    plain = dense(encoder=FakeEncoder(scale=1.0)).search("sanzioni amministrative", top_k=5)
    scaled = dense(encoder=FakeEncoder(scale=37.5)).search("sanzioni amministrative", top_k=5)
    assert ids(plain) == ids(scaled)
    assert [p.score for p in plain] == pytest.approx([p.score for p in scaled], abs=1e-6)
    assert all(-1.0 - 1e-6 <= p.score <= 1.0 + 1e-6 for p in plain)


def test_results_preserve_chunk_fields():
    metadata = DocumentMetadata(jurisdiction="IT", effective_from=date(2024, 1, 1))
    chunk = replace(
        make_chunk(9, "Obbligo di notifica entro 72 ore.", page=3, page_end=4, article="33"),
        metadata=metadata,
    )
    [result, *_] = dense([chunk, CORPUS[0]]).search("notifica 72 ore")
    assert result.chunk is chunk
    assert result.method is RetrievalMethod.DENSE
    assert result.rank == 1
    assert isinstance(result.score, float)
    assert result.chunk.location == SourceLocation("data/raw/doc-a.txt", 3, 4, None, "33", None)
    assert result.chunk.metadata == metadata


def test_top_k_limits_results_and_ranks_are_one_based():
    assert len(dense().search("lavoro", top_k=1)) == 1
    results = dense().search("lavoro", top_k=100)
    assert len(results) == len(CORPUS)  # every chunk has a similarity
    assert [p.rank for p in results] == list(range(1, len(CORPUS) + 1))


def test_ties_keep_corpus_order():
    chunks = [make_chunk(i, "testo identico") for i in range(4)]
    results = dense(chunks).search("testo identico", top_k=4)
    assert len({p.score for p in results}) == 1
    assert ids(results) == ["doc-a-0000", "doc-a-0001", "doc-a-0002", "doc-a-0003"]


def test_query_with_a_zero_embedding_returns_nothing():
    # The fake encoder ignores punctuation, so this query has no usable embedding.
    assert dense().search("?!") == []


def test_search_is_repeatable_and_does_not_mutate():
    retriever = dense()
    first = retriever.search("datore di lavoro")
    assert retriever.search("datore di lavoro") == first
    assert len(retriever) == len(CORPUS)


# --- Validation (same rules as BM25) --------------------------------------------------


@pytest.mark.parametrize(
    ("query", "top_k"),
    [("", 5), ("   ", 5), (None, 5), (7, 5), ("lavoro", 0), ("lavoro", -2),
     ("lavoro", True), ("lavoro", 2.0), ("lavoro", "3")],
)
def test_invalid_arguments_are_rejected_like_bm25(query, top_k):
    with pytest.raises((TypeError, ValueError)) as bm25_error:
        BM25Retriever(CORPUS).search(query, top_k=top_k)
    with pytest.raises((TypeError, ValueError)) as dense_error:
        dense().search(query, top_k=top_k)
    assert type(dense_error.value) is type(bm25_error.value)
    assert str(dense_error.value) == str(bm25_error.value)


def test_empty_corpus_returns_nothing_and_loads_no_model(fake_sentence_transformers):
    retriever = DenseRetriever([], model_name=E5_NAME)
    assert len(retriever) == 0
    assert retriever.search("lavoro") == []
    assert fake_sentence_transformers.instances == []
    with pytest.raises(ValueError):
        retriever.search(" ")  # validation still applies


def test_duplicate_chunk_ids_are_rejected():
    with pytest.raises(ValueError, match="duplicate chunk_id"):
        dense([make_chunk(0, "a"), make_chunk(0, "b")])


@pytest.mark.parametrize("batch_size", [0, -1, True, 1.5])
def test_invalid_batch_size_is_rejected(batch_size):
    with pytest.raises(ValueError, match="batch_size"):
        dense(batch_size=batch_size)


@pytest.mark.parametrize(
    ("output", "message"),
    [
        (lambda n: np.ones((n + 1, 4)), "shape"),
        (lambda n: np.ones((n, 0)), "shape"),
        (lambda n: np.ones(n), "shape"),
        (lambda n: np.full((n, 4), np.nan), "non-finite"),
    ],
)
def test_bad_encoder_output_is_rejected(output, message):
    class BadEncoder:
        def encode(self, texts):
            return output(len(texts))

    with pytest.raises(ValueError, match=message):
        dense(encoder=BadEncoder())


def test_embedding_dimension_must_not_change_between_batches():
    class ChangingEncoder:
        def __init__(self):
            self.dim = 3

        def encode(self, texts):
            self.dim += 1
            return np.ones((len(texts), self.dim))

    with pytest.raises(ValueError, match="different dimensions"):
        dense(encoder=ChangingEncoder(), batch_size=2)


# --- Model conventions, batching and loading -------------------------------------------


@pytest.mark.parametrize(
    ("model_name", "expected"),
    [
        ("intfloat/multilingual-e5-small", ("query: ", "passage: ")),
        ("intfloat/e5-base-v2", ("query: ", "passage: ")),
        ("BAAI/bge-m3", ("", "")),
        ("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", ("", "")),
        ("someone/e5x-model", ("", "")),
    ],
)
def test_input_prefixes_follow_the_model(model_name, expected):
    assert input_prefixes(model_name) == expected


def test_default_model_matches_the_configuration_default():
    assert DEFAULT_MODEL == Settings().embedding_model == "intfloat/multilingual-e5-small"


def test_prefixes_can_be_overridden():
    encoder = FakeEncoder()
    retriever = dense(encoder=encoder, query_prefix="Q> ", passage_prefix="")
    retriever.search("lavoro")
    assert encoder.calls[0][0] == CORPUS[0].text
    assert encoder.calls[-1] == ["Q> lavoro"]


def test_chunks_are_encoded_in_batches_with_the_passage_prefix():
    encoder = FakeEncoder()
    retriever = dense(encoder=encoder, batch_size=2)
    assert [len(call) for call in encoder.calls] == [2, 2, 1]
    assert [text for call in encoder.calls for text in call] == [
        "passage: " + c.text for c in CORPUS
    ]
    retriever.search("rischi")
    assert encoder.calls[-1] == ["query: rischi"]


def test_model_is_loaded_once_per_retriever(fake_sentence_transformers):
    retriever = DenseRetriever(CORPUS, model_name=E5_NAME, batch_size=2)
    for query in ("lavoro", "sanzioni", "data breach"):
        retriever.search(query)

    [model] = fake_sentence_transformers.instances
    assert model.model_name == E5_NAME
    assert len(model.encode_kwargs) == 3 + 3  # three chunk batches, three queries
    first = model.encode_kwargs[0]
    assert first["normalize_embeddings"] is True
    assert first["show_progress_bar"] is False
    assert first["batch_size"] == 2


def test_each_retriever_loads_its_own_model(fake_sentence_transformers):
    DenseRetriever(CORPUS, model_name=E5_NAME)
    DenseRetriever(CORPUS, model_name=E5_NAME)
    assert len(fake_sentence_transformers.instances) == 2


def test_sentence_transformer_encoder_returns_normalized_rows(fake_sentence_transformers):
    encoder = SentenceTransformerEncoder("fake/model", local_files_only=True)
    vectors = encoder.encode(["uno due", "tre"])
    assert vectors.shape == (2, 512)
    assert np.linalg.norm(vectors, axis=1) == pytest.approx([1.0, 1.0])


def test_from_jsonl(tmp_path):
    retriever = DenseRetriever.from_jsonl(FIXTURE_CHUNKS, encoder=FakeEncoder(), model_name=E5_NAME)
    assert len(retriever) == 9
    with pytest.raises(FileNotFoundError, match="src.ingestion"):
        DenseRetriever.from_jsonl(tmp_path / "missing.jsonl", encoder=FakeEncoder())


def test_describe_identifies_the_embeddings():
    assert dense().describe() == {
        "model": E5_NAME,
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
        "similarity": "cosine",
    }


# --- Embedding cache ---------------------------------------------------------------------


def cache_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.npy"))


def test_no_cache_by_default(tmp_path):
    retriever = dense()
    assert retriever.cache_status == "disabled"


def test_cache_miss_then_hit_reuses_embeddings(tmp_path):
    first_encoder = FakeEncoder()
    first = dense(encoder=first_encoder, cache_dir=tmp_path)
    assert first.cache_status == "miss"
    assert len(cache_files(tmp_path)) == 1
    assert not list(tmp_path.glob("*.tmp"))

    second_encoder = FakeEncoder()
    second = dense(encoder=second_encoder, cache_dir=tmp_path)
    assert second.cache_status == "hit"
    assert second_encoder.calls == []  # no chunk was re-encoded
    assert second.search("datore di lavoro") == first.search("datore di lavoro")


def test_cache_hit_does_not_load_the_model_until_a_search(tmp_path, fake_sentence_transformers):
    DenseRetriever(CORPUS, model_name=E5_NAME, cache_dir=tmp_path)
    assert len(fake_sentence_transformers.instances) == 1
    retriever = DenseRetriever(CORPUS, model_name=E5_NAME, cache_dir=tmp_path)
    assert retriever.cache_status == "hit"
    assert len(fake_sentence_transformers.instances) == 1
    retriever.search("lavoro")
    assert len(fake_sentence_transformers.instances) == 2


@pytest.mark.parametrize(
    "change",
    [
        {"chunks": [replace(CORPUS[0], text="Testo modificato.")] + CORPUS[1:]},
        {"chunks": CORPUS[:-1]},
        {"model_name": "fake/other-e5-model"},
        {"passage_prefix": "document: "},
    ],
)
def test_cache_is_invalidated_by_chunk_or_model_changes(tmp_path, change):
    dense(cache_dir=tmp_path)
    changed = dense(cache_dir=tmp_path, **change)
    assert changed.cache_status == "miss"
    assert len(cache_files(tmp_path)) == 2


def _object_array(path: Path) -> None:
    np.save(path, np.array([{"a": 1}] * len(CORPUS), dtype=object), allow_pickle=True)


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda path: path.write_bytes(b"not a numpy file"),
        lambda path: np.save(path, np.ones((len(CORPUS) + 1, 512), dtype=np.float32)),
        lambda path: np.save(path, np.ones((len(CORPUS), 512), dtype=np.float32)),  # not unit length
        lambda path: np.save(path, np.zeros((len(CORPUS), 512), dtype=np.float64)),
        lambda path: np.save(path, np.full((len(CORPUS), 512), np.nan, dtype=np.float32)),
        _object_array,  # would need pickle to load
    ],
)
def test_invalid_cache_file_is_recomputed_and_replaced(tmp_path, corrupt):
    reference = dense(cache_dir=tmp_path).search("datore di lavoro")
    [path] = cache_files(tmp_path)
    corrupt(path)

    recovered = dense(cache_dir=tmp_path)
    assert recovered.cache_status == "invalid"
    assert recovered.search("datore di lavoro") == reference
    assert dense(cache_dir=tmp_path).cache_status == "hit"  # the file was repaired


# --- Evaluation integration ---------------------------------------------------------------


@pytest.fixture
def dense_settings(monkeypatch, tmp_path, fake_sentence_transformers):
    monkeypatch.setenv("EMBEDDING_MODEL", E5_NAME)
    monkeypatch.setenv("INDEX_DIR", str(tmp_path / "indexes"))
    return tmp_path / "indexes" / "embeddings"


FIXTURE_FILES = (FIXTURE_CHUNKS, FIXTURE / "queries.jsonl", FIXTURE / "qrels.jsonl")


def test_dense_is_available_in_the_evaluator(dense_settings):
    report = run_evaluation("dense", *FIXTURE_FILES, [1, 5])
    assert report["retriever"] == "dense"
    assert report["retriever_details"]["model"] == E5_NAME
    assert report["retriever_details"]["query_prefix"] == "query: "
    assert report["queries_evaluated"] == 4
    assert set(report["metrics"]) == {
        f"{m}@{k}" for m in ("recall", "mrr", "ndcg") for k in (1, 5)
    }
    assert len(cache_files(dense_settings)) == 1  # the cache went to INDEX_DIR, not the repo


def test_dense_evaluation_is_deterministic_across_cache_miss_and_hit(dense_settings):
    first = run_evaluation("dense", *FIXTURE_FILES, [1, 5, 10])
    second = run_evaluation("dense", *FIXTURE_FILES, [1, 5, 10])  # served from the cache
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_bm25_reports_are_unchanged_apart_from_empty_details():
    report = run_evaluation("bm25", *FIXTURE_FILES, [5])
    assert report["retriever_details"] == {}
    assert report["metrics"]["recall@5"] == pytest.approx(0.625)


def test_evaluator_cli_with_dense(dense_settings, capsys, tmp_path):
    output = tmp_path / "report.json"
    args = ["--retriever", "dense", "--chunks", str(FIXTURE_FILES[0]),
            "--queries", str(FIXTURE_FILES[1]), "--qrels", str(FIXTURE_FILES[2]),
            "--output", str(output)]
    assert eval_main(args) == 0
    out = capsys.readouterr().out
    assert "Retriever: dense" in out
    assert f"Model:     {E5_NAME}" in out
    assert json.loads(output.read_text(encoding="utf-8"))["retriever_details"]["model"] == E5_NAME


def test_evaluator_reports_model_load_failure(monkeypatch, tmp_path, capsys):
    class Unloadable:
        def __init__(self, *args, **kwargs):
            raise OSError("We couldn't connect to 'https://huggingface.co'")

    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = Unloadable
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    monkeypatch.setenv("INDEX_DIR", str(tmp_path))
    args = ["--retriever", "dense", "--chunks", str(FIXTURE_FILES[0]),
            "--queries", str(FIXTURE_FILES[1]), "--qrels", str(FIXTURE_FILES[2])]
    assert eval_main(args) == 2
    assert "could not load the retriever" in capsys.readouterr().err


# --- CLI ------------------------------------------------------------------------------------


def test_cli_search_with_cache(dense_settings, capsys):
    args = ["datore di lavoro", "--chunks", str(FIXTURE_CHUNKS), "--top-k", "2"]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert f"Indexed 9 chunk(s) from {FIXTURE_CHUNKS} with {E5_NAME} (embedding cache: miss)" in out
    assert "#1  score=" in out and "#2  score=" in out and "#3" not in out
    assert "synthetic/legge_sintetica.txt" in out

    assert main(args) == 0
    assert "(embedding cache: hit)" in capsys.readouterr().out


def test_cli_no_cache_and_model_option(dense_settings, capsys):
    args = ["data breach", "--chunks", str(FIXTURE_CHUNKS), "--no-cache", "--model", "fake/bge-test"]
    assert main(args) == 0
    assert "with fake/bge-test (embedding cache: disabled)" in capsys.readouterr().out
    assert not dense_settings.exists()


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["x", "--chunks", "MISSING"], "chunk file not found"),
        (["x", "--top-k", "0"], "top_k must be >= 1"),
        (["  "], "query must not be empty"),
        (["x", "--batch-size", "0"], "batch_size must be a positive int"),
    ],
)
def test_cli_errors_exit_2(dense_settings, capsys, tmp_path, args, message):
    args = [str(tmp_path / "missing.jsonl") if a == "MISSING" else a for a in args]
    if "--chunks" not in args:
        args += ["--chunks", str(FIXTURE_CHUNKS)]
    assert main(args) == 2
    assert message in capsys.readouterr().err


def test_cli_model_load_failure_exit_2(monkeypatch, tmp_path, capsys):
    class Unloadable:
        def __init__(self, *args, **kwargs):
            raise OSError("model not found")

    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = Unloadable
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    monkeypatch.setenv("INDEX_DIR", str(tmp_path))
    assert main(["lavoro", "--chunks", str(FIXTURE_CHUNKS), "--no-cache"]) == 2
    assert "could not load embedding model" in capsys.readouterr().err


# --- Optional: the real model, only if explicitly requested and already downloaded -------


@pytest.mark.skipif(
    os.environ.get("RUN_REAL_MODEL_TESTS") != "1",
    reason="set RUN_REAL_MODEL_TESTS=1 to run; needs the model already in the Hugging Face cache",
)
def test_real_model_smoke():
    """Checks that the real model integrates correctly. It is not a quality benchmark."""
    # 1. The model loads (from the local cache only; this never downloads).
    encoder = SentenceTransformerEncoder(DEFAULT_MODEL, local_files_only=True)

    # 2. Embeddings have the model's dimension and valid, unit-length values.
    vectors = encoder.encode(["passage: testo di prova", "query: prova"])
    assert vectors.shape == (2, 384)  # multilingual-e5-small
    assert np.isfinite(vectors).all()
    assert np.linalg.norm(vectors, axis=1) == pytest.approx([1.0, 1.0], abs=1e-4)

    chunks = [
        make_chunk(0, "Il datore di lavoro valuta tutti i rischi per la sicurezza dei lavoratori."),
        make_chunk(1, "The controller shall notify a personal data breach within 72 hours."),
        make_chunk(2, "Le sanzioni sono applicate dall'autorità competente."),
    ]
    all_ids = {c.chunk_id for c in chunks}
    retriever = DenseRetriever(chunks, model_name=DEFAULT_MODEL, encoder=encoder)

    def check_valid(results) -> None:
        assert [p.rank for p in results] == [1, 2, 3]
        assert set(ids(results)) == all_ids  # every chunk exactly once
        scores = [p.score for p in results]
        assert all(np.isfinite(s) and -1.0001 <= s <= 1.0001 for s in scores)
        assert scores == sorted(scores, reverse=True)
        assert all(p.method is RetrievalMethod.DENSE for p in results)

    # 3. Retrieval returns valid, repeatable results.
    italian = retriever.search("obblighi del datore di lavoro", top_k=3)
    check_valid(italian)
    assert retriever.search("obblighi del datore di lavoro", top_k=3) == italian

    # 4. Same-language retrieval: the query and its passage share a language.
    assert ids(italian)[0] == "doc-a-0000"
    english = retriever.search("notification of a personal data breach", top_k=3)
    check_valid(english)
    assert ids(english)[0] == "doc-a-0001"

    # 5. Cross-language diagnostic, with no ranking expectation. When this was
    # written, this short Italian query ranked the English breach passage last,
    # behind both Italian passages (see README, dense retrieval limitations).
    check_valid(retriever.search("notifica di una violazione dei dati", top_k=3))
