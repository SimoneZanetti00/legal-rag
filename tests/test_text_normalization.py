"""Tests for the shared comparison normalisation (profile ws-markers-softhyphen-v1)."""

import pytest

from src.text_normalization import (
    DIFFERS,
    IDENTICAL,
    IDENTICAL_AFTER_NORMALISATION,
    MATCH_STATUSES,
    PROFILE,
    PROFILES,
    TextDifference,
    compare_texts,
    normalise,
)


def test_profile_name_and_statuses():
    assert PROFILE == "ws-markers-softhyphen-v1" and PROFILES == (PROFILE,)
    assert MATCH_STATUSES == ("identical", "identical_after_normalisation", "differs")


def test_unknown_profile_is_refused():
    with pytest.raises(ValueError, match="unknown normalisation profile"):
        normalise("testo", "ws-v0")
    with pytest.raises(ValueError, match="unknown normalisation profile"):
        compare_texts("testo", "testo", "ws-v0")


# --- 1. EUR-Lex consolidation markers ---------------------------------------------------


@pytest.mark.parametrize("text", [
    "▼B\nArticolo 33", "▼C2\nArticolo 33", "►M1 Articolo 33 ◄", "▼A1 Articolo 33",
    "▼C12\n\xa0Articolo 33\xa0◄",
])
def test_consolidation_markers_are_removed(text):
    assert normalise(text) == "Articolo 33"


def test_an_inline_corrigendum_marker_leaves_the_corrected_words():
    official = "senza ingiustificato \n►C2\n ritardo.\xa0◄  Entro"
    assert normalise(official) == "senza ingiustificato ritardo. Entro"


@pytest.mark.parametrize("text", [
    "◄ Commissione",  # the closing marker never takes the next word with it
    "▼B Commissione",
])
def test_a_marker_never_swallows_the_next_word(text):
    assert normalise(text) == "Commissione"


@pytest.mark.parametrize("text, without_marker", [
    ("►Commissione", "Commissione"),  # no label: not a marker
    ("►C2Il", "Il"),  # label glued to a word: ambiguous, left alone
    ("▼X1 testo", "testo"),  # unknown label
    ("▼ testo", "testo"),
    ("►C 2 testo", "2 testo"),
])
def test_anything_that_is_not_a_clear_marker_stays(text, without_marker):
    assert normalise(text) == text
    assert compare_texts(text, without_marker).status == DIFFERS


# --- 2. Soft hyphens ---------------------------------------------------------------------


def test_the_article_33_extraction_artifact_is_joined():
    # GDPR Art. 33(4) as extracted from the OJ PDF: soft hyphen across a block break.
    ours = "anche in modo approssi\xad\n\nmativo"
    assert normalise(ours) == "anche in modo approssimativo"
    assert compare_texts(ours, "anche in modo approssimativo").status == (
        IDENTICAL_AFTER_NORMALISATION)


def test_a_soft_hyphen_inside_a_word_is_removed():
    assert normalise("appros\xadsimativo") == "approssimativo"


def test_an_ordinary_hyphen_is_never_joined():
    assert normalise("approssi-\nmativo") == "approssi- mativo"
    assert compare_texts("approssi-\nmativo", "approssimativo").status == DIFFERS
    assert compare_texts("Art. 2-bis", "Art. 2 bis").status == DIFFERS


# --- 3. Typographic apostrophes ------------------------------------------------------------


def test_the_typographic_apostrophe_becomes_ascii():
    assert normalise("dell’articolo 51") == "dell'articolo 51"


@pytest.mark.parametrize("ours, theirs", [
    ("‘dati’", "'dati'"),  # only U+2019 is an apostrophe; U+2018 is a quotation mark
    ("«Garante»", '"Garante"'),
    ("«Garante»", "“Garante”"),
])
def test_quotation_marks_are_not_changed(ours, theirs):
    assert compare_texts(ours, theirs).status == DIFFERS


# --- 4. Whitespace -------------------------------------------------------------------------


def test_every_kind_of_whitespace_becomes_one_space():
    assert normalise("  a\r\n\tb\xa0c\u202fd\n\n\ne  ") == "a b c d e"


def test_line_breaks_alone_are_not_a_difference():
    ours = ("1. L'Autorità di controllo di cui all'articolo 51 del regolamento è individuata "
            "nel Garante per la protezione dei\ndati personali")
    theirs = ours.replace("\n", " ")
    assert compare_texts(ours, theirs).status == IDENTICAL_AFTER_NORMALISATION


def test_a_missing_space_between_words_is_a_difference():
    assert compare_texts("dati personali", "datipersonali").status == DIFFERS


# --- 5. Spacing before punctuation ------------------------------------------------------------


@pytest.mark.parametrize("text, expected", [
    ("«violazione dei dati personali» :", "«violazione dei dati personali»:"),
    ("trattati ;", "trattati;"),
    ("titolare , il", "titolare, il"),
    ("ore .", "ore."),
    ("perché ?", "perché?"),
    ("lettera f )", "lettera f)"),
    ("( a )", "(a)"),
    ("[ nota ]", "[nota]"),
])
def test_space_before_punctuation_and_inside_brackets_is_removed(text, expected):
    assert normalise(text) == expected


def test_space_after_punctuation_is_kept():
    assert normalise("titolare, il trattamento; e") == "titolare, il trattamento; e"
    assert compare_texts("titolare, il", "titolare,il").status == DIFFERS


def test_normattiva_amendment_markers_are_kept():
    ours = "(( (Autorità di controllo). ))\n\n((\n\n1. L'Autorità"
    assert normalise(ours) == "(((Autorità di controllo).)) ((1. L'Autorità"
    assert compare_texts(ours, "(Autorità di controllo). 1. L'Autorità").status == DIFFERS


# --- Meaningful differences stay detectable ---------------------------------------------------


@pytest.mark.parametrize("ours, theirs, difference", [
    # GDPR Art. 56(3), corrigendum C2: a changed word.
    ("senza ingiustificato indugio", "senza ingiustificato \n►C2\n ritardo ◄",
     TextDifference("indugio", "ritardo")),
    # GDPR Art. 56(1), corrigendum C3: a removed word.
    ("stabilimento unico del titolare e del trattamento",
     "stabilimento unico del titolare del trattamento", TextDifference("e", "")),
    ("entro 72 ore", "entro 96 ore", TextDifference("72", "96")),
    ("Garante per la protezione", "garante per la protezione",
     TextDifference("Garante", "garante")),
    ("il titolare è tenuto", "il titolare e tenuto", TextDifference("è", "e")),
    ("i dati trattati;", "i dati trattati.", TextDifference("trattati;", "trattati.")),
    ("paragrafo 1", "paragrafo 1 e 2", TextDifference("", "e 2")),
])
def test_textual_differences_are_reported_word_by_word(ours, theirs, difference):
    result = compare_texts(ours, theirs)
    assert result.status == DIFFERS and result.differences == (difference,)


def test_no_unicode_normalisation_is_applied():
    precomposed, decomposed = "è", "e\u0300"  # both are è
    assert compare_texts(precomposed, decomposed).status == DIFFERS


def test_word_order_counts():
    assert compare_texts("titolare del trattamento", "trattamento del titolare").status == DIFFERS


# --- Behaviour of the comparison ---------------------------------------------------------------


def test_identical_strings_are_identical_without_normalising():
    text = "▼B\nArticolo 33\n\nNotifica"
    assert compare_texts(text, text).status == IDENTICAL
    assert compare_texts(text, text).differences == ()


def test_normalisation_is_idempotent_and_deterministic():
    text = "▼C2\n Art.\xa033 ( 1 ) approssi\xad\n mativo dell’articolo ;  ◄"
    once = normalise(text)
    assert normalise(once) == once == normalise(text)
    assert once == "Art. 33 (1) approssimativo dell'articolo;"


def test_the_inputs_are_not_changed():
    ours, theirs = "approssi\xad\n\nmativo", "approssimativo"
    compare_texts(ours, theirs)
    assert (ours, theirs) == ("approssi\xad\n\nmativo", "approssimativo")


def test_empty_and_whitespace_only_texts():
    assert compare_texts("", " \n ").status == IDENTICAL_AFTER_NORMALISATION
    result = compare_texts("", "testo")
    assert result.status == DIFFERS and result.differences == (TextDifference("", "testo"),)
