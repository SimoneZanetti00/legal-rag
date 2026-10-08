"""Tests for the helpers shared by the retrievers and their command-line interfaces."""

import ast

import pytest

from src.config import PROJECT_ROOT
from src.models import LegalChunk, RetrievalMethod, RetrievedPassage, SourceLocation
from src.retrieval_common import Retriever, format_passage, require_positive_int, require_query


def passage(text: str, rank: int = 1, score: float = 1.0, **location) -> RetrievedPassage:
    chunk = LegalChunk(
        chunk_id="doc-a-0001",
        doc_id="doc-a",
        text=text,
        chunk_index=1,
        location=SourceLocation(**location),
    )
    return RetrievedPassage(chunk=chunk, method=RetrievalMethod.BM25, rank=rank, score=score)


# --- format_passage: exact output, recorded before the function was moved here ----------


def test_format_normal_passage():
    result = format_passage(
        passage(
            "Art. 5 (Misure)\n1. Il datore adotta le misure.",
            rank=2,
            score=3.14159,
            source_path="data/raw/law.txt",
            article="5",
            paragraph="1, 2",
            section="Capo II",
        )
    )
    assert result == (
        "#2  score=3.1416  doc-a-0001\n"
        "    data/raw/law.txt | art. 5 | par. 1, 2\n"
        "    Art. 5 (Misure) 1. Il datore adotta le misure."
    )
    assert "Capo II" not in result  # the section heading is not printed


def test_format_single_page():
    expected = "#1  score=1.0000  doc-a-0001\n    data/raw/law.pdf | p. 3\n    Testo."
    assert format_passage(passage("Testo.", source_path="data/raw/law.pdf", page=3)) == expected
    same_page = passage("Testo.", source_path="data/raw/law.pdf", page=3, page_end=3)
    assert format_passage(same_page) == expected


def test_format_page_range():
    result = format_passage(
        passage("Testo.", source_path="data/raw/law.pdf", page=3, page_end=4, article="33")
    )
    assert result == (
        "#1  score=1.0000  doc-a-0001\n    data/raw/law.pdf | p. 3-4 | art. 33\n    Testo."
    )


def test_format_unknown_source():
    assert format_passage(passage("Testo senza provenienza.")) == (
        "#1  score=1.0000  doc-a-0001\n    unknown source\n    Testo senza provenienza."
    )


def test_format_rank_and_score():
    result = format_passage(
        passage("Testo.", rank=12, score=-0.02583957985983383, source_path="a.txt")
    )
    assert result == "#12  score=-0.0258  doc-a-0001\n    a.txt\n    Testo."


def test_format_collapses_whitespace_in_the_excerpt():
    result = format_passage(passage("  Riga uno\n\n   riga\tdue   fine  ", source_path="a.txt"))
    assert result == "#1  score=1.0000  doc-a-0001\n    a.txt\n    Riga uno riga due fine"


def test_format_truncates_long_excerpts():
    words = " ".join(f"parola{i}" for i in range(60))  # 529 characters
    result = format_passage(passage(words, source_path="a.txt"))
    assert result == (
        "#1  score=1.0000  doc-a-0001\n    a.txt\n    "
        "parola0 parola1 parola2 parola3 parola4 parola5 parola6 parola7 parola8 parola9 "
        "parola10 parola11 parola12 parola13 parola14 parola15 parola16 parola17 parola18 "
        "parola19 parola20 parola21 parola22 parola23 parola24 parola25 parola26 parola2 ..."
    )
    excerpt = result.split("\n")[2].strip()
    assert len(excerpt) == 240 + len(" ...")  # the cut is by characters, not by words


def test_format_truncation_boundaries():
    def excerpt_of(text: str) -> str:
        return format_passage(passage(text, source_path="a.txt")).split("\n")[2]

    assert excerpt_of("x" * 240) == "    " + "x" * 240  # exactly at the limit: unchanged
    assert excerpt_of("y" * 241) == "    " + "y" * 240 + " ..."
    # A cut that lands on a space drops it before the marker.
    assert excerpt_of("a" * 239 + " bbbb") == "    " + "a" * 239 + " ..."


def test_format_custom_excerpt_length():
    result = format_passage(passage("uno due tre quattro", source_path="a.txt"), excerpt_length=7)
    assert result == "#1  score=1.0000  doc-a-0001\n    a.txt\n    uno due ..."


def test_format_does_not_change_the_passage():
    original = passage("  Testo\ncon   spazi.  ", source_path="a.txt", page=2, page_end=3)
    before = (original.chunk.text, original.chunk.location, original.rank, original.score)
    format_passage(original)
    assert (original.chunk.text, original.chunk.location, original.rank, original.score) == before


# --- Argument checks: one set of types and messages for every retriever --------------------


@pytest.mark.parametrize("query", ["lavoro", " x ", "?!", "articolo 5"])
def test_require_query_accepts_non_blank_strings(query):
    assert require_query(query) is None


@pytest.mark.parametrize("query", ["", "   ", "\n\t "])
def test_require_query_rejects_blank_strings(query):
    with pytest.raises(ValueError) as error:
        require_query(query)
    assert str(error.value) == "query must not be empty or whitespace."


@pytest.mark.parametrize(
    ("query", "type_name"),
    [(None, "NoneType"), (7, "int"), (2.5, "float"), (["lavoro"], "list"), (b"lavoro", "bytes")],
)
def test_require_query_rejects_non_strings(query, type_name):
    with pytest.raises(TypeError) as error:
        require_query(query)
    assert str(error.value) == f"query must be a string (got {type_name})."


@pytest.mark.parametrize("value", [1, 2, 20, 10**9])
def test_require_positive_int_accepts_positive_ints(value):
    assert require_positive_int(value, "top_k") is None


@pytest.mark.parametrize("value", [0, -1, -100])
def test_require_positive_int_rejects_values_below_one(value):
    with pytest.raises(ValueError) as error:
        require_positive_int(value, "top_k")
    assert str(error.value) == f"top_k must be >= 1 (got {value})."


@pytest.mark.parametrize(
    ("value", "type_name"),
    [(True, "bool"), (False, "bool"), (2.0, "float"), ("3", "str"), (None, "NoneType"), ([1], "list")],
)
def test_require_positive_int_rejects_non_ints_including_booleans(value, type_name):
    with pytest.raises(TypeError) as error:
        require_positive_int(value, "top_k")
    assert str(error.value) == f"top_k must be an int (got {type_name})."


def test_require_positive_int_names_the_parameter_in_its_message():
    with pytest.raises(ValueError, match=r"^rrf_k must be >= 1 \(got 0\)\.$"):
        require_positive_int(0, "rrf_k")
    with pytest.raises(TypeError, match=r"^bm25_top_k must be an int \(got str\)\.$"):
        require_positive_int("20", "bm25_top_k")


def test_type_is_checked_before_value():
    # A boolean is rejected as a type error, never treated as the integer 1 or 0.
    with pytest.raises(TypeError):
        require_positive_int(False, "top_k")


# --- One shared interface, and no private names crossing module boundaries -----------------


def test_the_evaluator_and_the_hybrid_retriever_use_the_shared_protocol():
    from src import hybrid_retrieval, retrieval_eval

    assert retrieval_eval.Retriever is Retriever
    assert hybrid_retrieval.Retriever is Retriever


def test_no_source_module_imports_a_private_name_from_another():
    """`from src.x import _name` and `module._name` on an imported src module are not allowed."""
    violations = []
    for path in sorted((PROJECT_ROOT / "src").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "src":
                for alias in node.names:
                    if alias.name.startswith("_") and not alias.name.startswith("__"):
                        violations.append(f"{path.name}:{node.lineno} imports {alias.name}")
                    if node.module == "src":  # `from src import retrieval`
                        imported_modules.add(alias.asname or alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] == "src" and alias.asname:
                        imported_modules.add(alias.asname)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in imported_modules
                and node.attr.startswith("_")
                and not node.attr.startswith("__")
            ):
                violations.append(f"{path.name}:{node.lineno} uses {node.value.id}.{node.attr}")
    assert violations == []
