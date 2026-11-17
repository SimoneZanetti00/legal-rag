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
    reading_form,
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


# --- Reading form ------------------------------------------------------------------------

SHY = chr(0xAD)
# GDPR Art. 6(1) exactly as stored in the recorded build (PDF layout: blank lines between
# lines, a soft hyphen in "precontrattuali", trailing spaces, labels alone on a line).
# tests/test_answer_generation.py checks it against the build when the build is available.
ART6_1 = (
    "Articolo 6\n\nLiceità del trattamento\n\n1.\nIl trattamento è lecito solo se e nella misura "
    "in cui ricorre almeno una delle seguenti condizioni:\n\na)  l'interessato ha espresso il "
    "consenso al trattamento dei propri dati personali per una o più specifiche finalità;\n\nb) "
    "il trattamento è necessario all'esecuzione di un contratto di cui l'interessato è parte o "
    f"all'esecuzione di misure precon{SHY}\n\ntrattuali adottate su richiesta dello stesso;\n\n"
    "c)  il trattamento è necessario per adempiere un obbligo legale al quale è soggetto il "
    "titolare del trattamento;\n\nd)  il trattamento è necessario per la salvaguardia degli "
    "interessi vitali dell'interessato o di un'altra persona fisica;\n\ne)  il trattamento è "
    "necessario per l'esecuzione di un compito di interesse pubblico o connesso all'esercizio di "
    "pubblici\n\npoteri di cui è investito il titolare del trattamento;\n\nf)  il trattamento è "
    "necessario per il perseguimento del legittimo interesse del titolare del trattamento o di "
    "terzi, a\n\ncondizione che non prevalgano gli interessi o i diritti e le libertà "
    "fondamentali dell'interessato che richiedono la \nprotezione dei dati personali, in "
    "particolare se l'interessato è un minore.\n\nLa lettera f) del primo comma non si applica "
    "al trattamento di dati effettuato dalle autorità pubbliche nell'esecuzione dei \nloro "
    "compiti.")

ART6_1_READING = "\n".join([
    "Articolo 6",
    "Liceità del trattamento",
    "1. Il trattamento è lecito solo se e nella misura in cui ricorre almeno una delle seguenti "
    "condizioni:",
    "a)  l'interessato ha espresso il consenso al trattamento dei propri dati personali per una o "
    "più specifiche finalità;",
    "b) il trattamento è necessario all'esecuzione di un contratto di cui l'interessato è parte o "
    "all'esecuzione di misure precontrattuali adottate su richiesta dello stesso;",
    "c)  il trattamento è necessario per adempiere un obbligo legale al quale è soggetto il "
    "titolare del trattamento;",
    "d)  il trattamento è necessario per la salvaguardia degli interessi vitali dell'interessato o "
    "di un'altra persona fisica;",
    "e)  il trattamento è necessario per l'esecuzione di un compito di interesse pubblico o "
    "connesso all'esercizio di pubblici poteri di cui è investito il titolare del trattamento;",
    "f)  il trattamento è necessario per il perseguimento del legittimo interesse del titolare del "
    "trattamento o di terzi, a condizione che non prevalgano gli interessi o i diritti e le "
    "libertà fondamentali dell'interessato che richiedono la protezione dei dati personali, in "
    "particolare se l'interessato è un minore.",
    "La lettera f) del primo comma non si applica al trattamento di dati effettuato dalle autorità "
    "pubbliche nell'esecuzione dei loro compiti.",
])


def test_reading_form_of_gdpr_article_6_paragraph_1():
    assert reading_form(ART6_1) == ART6_1_READING


def test_a_word_split_by_a_soft_hyphen_and_a_line_break_is_joined():
    assert reading_form(f"misure precon{SHY}\n\ntrattuali adottate") == (
        "misure precontrattuali adottate")
    assert reading_form(f"approssi{SHY}\nmativo") == "approssimativo"
    assert reading_form(f"approssi{SHY}mativo") == "approssimativo"
    assert reading_form("dati - personali\n\n- secondo") == "dati - personali - secondo"


@pytest.mark.parametrize("text, expected", [
    ("pubblici\n\npoteri", "pubblici poteri"),  # blank line inside a sentence
    ("richiedono la \nprotezione", "richiedono la protezione"),  # trailing space, line break
    ("di terzi, a\n\ncondizione", "di terzi, a condizione"),  # a lone "a" is not a label
    ("1.\nIl trattamento", "1. Il trattamento"),  # a label alone on its line
    ("((1.\nIl Garante", "((1. Il Garante"),
])
def test_layout_breaks_inside_a_sentence_become_one_space(text, expected):
    assert reading_form(text) == expected


@pytest.mark.parametrize("text, expected", [
    # paragraph numbers, including inserted ones and Normattiva's opening marker
    ("fine del primo.\n\n2. Secondo\n\n2-bis. Inserito\n\n((3. Modificato",
     "fine del primo.\n2. Secondo\n2-bis. Inserito\n((3. Modificato"),
    # point labels: letters, numbers, inserted letters; the break is kept even mid-sentence
    ("deve almeno:\n\na) descrivere\n\nb)  comunicare\n\na-bis) indicare",
     "deve almeno:\na) descrivere\nb)  comunicare\na-bis) indicare"),
    ("si intende per:\n\n11)\n«consenso»: qualsiasi\n\n12) «violazione dei dati personali»",
     "si intende per:\n11) «consenso»: qualsiasi\n12) «violazione dei dati personali»"),
    ("i casi seguenti\n(3) il terzo", "i casi seguenti\n(3) il terzo"),
    # article headings stay on their own line, and so does the line after a sentence end
    ("Art. 2-bis\n(( (Autorità di controllo). ))\n1. Il Garante",
     "Art. 2-bis\n(( (Autorità di controllo). ))\n1. Il Garante"),
    ("prima frase.\n\nLa seconda", "prima frase.\nLa seconda"),
])
def test_paragraph_and_point_breaks_are_kept(text, expected):
    assert reading_form(text) == expected


# Articles without a paragraph number after the title, as stored in the recorded build.
GDPR_4_OPENING = ("Articolo 4\n\nDefinizioni\n\nAi fini del presente regolamento s'intende per:\n\n"
                  "1) «dato personale»: qualsiasi informazione")
CODE_1 = ("Art. 1\n\n(( (Oggetto). ))\n\n((Il trattamento dei dati personali avviene secondo le "
          "norme del regolamento (UE) 2016/679 del Parlamento\neuropeo e del Consiglio, del 27 "
          "aprile 2016, di seguito «Regolamento», e del presente codice, nel rispetto della\n"
          "dignità umana, dei diritti e delle libertà fondamentali della persona.))\n\n")


@pytest.mark.parametrize("text, title, expected", [
    (GDPR_4_OPENING, "Definizioni",
     "Articolo 4\nDefinizioni\nAi fini del presente regolamento s'intende per:\n"
     "1) «dato personale»: qualsiasi informazione"),
    (CODE_1, "(( (Oggetto). ))",
     "Art. 1\n(( (Oggetto). ))\n((Il trattamento dei dati personali avviene secondo le norme del "
     "regolamento (UE) 2016/679 del Parlamento europeo e del Consiglio, del 27 aprile 2016, di "
     "seguito «Regolamento», e del presente codice, nel rispetto della dignità umana, dei diritti "
     "e delle libertà fondamentali della persona.))"),
    # a title printed over two lines is joined, then its line break is kept
    ("Articolo 98\n\nRiesame di altri atti\n\nlegislativi dell'Unione\n\nOve opportuno, la",
     "Riesame di altri atti legislativi dell'Unione",
     "Articolo 98\nRiesame di altri atti legislativi dell'Unione\nOve opportuno, la"),
])
def test_the_line_break_after_the_title_is_kept(text, title, expected):
    assert reading_form(text, title) == expected
    assert normalise(reading_form(text, title)) == normalise(text)


def test_without_a_title_the_title_line_is_joined_to_unnumbered_text():
    assert reading_form(GDPR_4_OPENING).split("\n")[1] == (
        "Definizioni Ai fini del presente regolamento s'intende per:")
    assert reading_form(GDPR_4_OPENING, "Altro titolo") == reading_form(GDPR_4_OPENING)


@pytest.mark.parametrize("text", [
    ART6_1, "", " \n\n ", f"a{SHY}\n b", "Art. 1\n\n1.\n\na)  x\n\n((2. y ))", "x \t\n\xa0y",
])
def test_only_whitespace_and_soft_hyphens_change(text):
    result = reading_form(text)
    assert normalise(result) == normalise(text)
    assert SHY not in result and "\n\n" not in result and result == result.strip()
    assert all(line == line.strip() for line in result.split("\n"))
