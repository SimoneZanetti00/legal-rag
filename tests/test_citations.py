"""Citation resolution (src/citations.py), on the real provision store.

The store (data/reference) is tracked, so most tests always run. The paragraph and point checks
read article text from the recorded build and skip when it is absent.
"""

import json

import pytest

from src.citations import (
    GDPR,
    INSTRUMENTS,
    PRIVACY_CODE,
    Basis,
    Status,
    extract_references,
    resolve_reference,
    resolve_references,
)
from src.config import PROJECT_ROOT
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.provisions import load_store


@pytest.fixture(scope="module")
def store():
    return load_store()


@pytest.fixture(scope="module")
def article_text(store):
    try:
        explorer = ProvisionExplorer.open(find_recorded_build(), store=store)
    except ExplorerError as exc:
        pytest.skip(f"recorded build unavailable: {exc}")
    return lambda p: "".join(piece["text"] for piece in explorer.provision_view(p)["text"])


def one(text, store, **kwargs):
    [resolution] = resolve_references(text, store, **kwargs)
    return resolution


def target(resolution):
    """(instrument, label) of the resolved provision."""
    pid = resolution.provision_id
    return pid.split("@", 1)[0], pid.rsplit(":", 1)[1]


def test_the_instrument_table_names_registry_instruments():
    registry = json.loads((PROJECT_ROOT / "data" / "reference" / "instruments.json")
                          .read_text(encoding="utf-8"))
    assert {i.instrument_id for i in INSTRUMENTS} == {
        i["instrument_id"] for i in registry["instruments"]}


# --- 1-4: explicit instruments -----------------------------------------------------------------


@pytest.mark.parametrize("text", ["GDPR Article 33", "art. 33 GDPR", "GDPR, art. 33",
                                  "articolo 33 del Regolamento (UE) 2016/679",
                                  "Article 33 of Regulation (EU) 2016/679",
                                  "Cosa prevede l'articolo 33 GDPR?"])
def test_gdpr_article_33_resolves(store, text):
    resolution = one(text, store)
    assert (resolution.status, resolution.reason) == (Status.RESOLVED, "found")
    assert target(resolution) == (GDPR, "33")
    assert resolution.reference.basis == Basis.EXPLICIT


def test_article_34_2_resolves_and_34_9_is_partial(store, article_text):
    resolved = one("Article 34(2) GDPR", store, article_text=article_text)
    assert (resolved.status, target(resolved)) == (Status.RESOLVED, (GDPR, "34"))
    partial = one("Article 34(9) GDPR", store, article_text=article_text)
    assert (partial.status, partial.reason) == (Status.PARTIALLY_RESOLVED, "part_not_found")
    assert target(partial) == (GDPR, "34") and "(9)" in partial.explanation


def test_parts_are_partial_when_no_text_is_available(store):
    resolution = one("Article 34(2) GDPR", store)  # no article_text given
    assert (resolution.status, resolution.reason) == (Status.PARTIALLY_RESOLVED,
                                                      "parts_not_checked")


def test_points_of_a_definitions_article(store, article_text):
    for text in ("art. 4, n. 12, GDPR", "Article 4(12) GDPR", "articolo 4, punto 12, del GDPR"):
        resolution = one(text, store, article_text=article_text)
        assert (resolution.status, target(resolution), resolution.point) == (
            Status.RESOLVED, (GDPR, "4"), "12"), text


@pytest.mark.parametrize("text", [
    "Article 2-bis of the Italian Privacy Code", "articolo 2-bis del Codice privacy",
    "Art. 2 bis d.lgs. 196/2003", "D.Lgs. n. 196/2003, art. 2-bis",
    "Cosa dice l'articolo 2-bis del Codice Privacy?", "art. 2-bis del D.Lgs. 196/2003",
    "art. 2-bis del Codice in materia di protezione dei dati personali",
    "art. 2-bis del codice della protezione dei dati personali",
    "art. 2-bis del codice", "art. 2-bis del codice di cui al d.lgs. 196",
])
def test_code_article_2_bis_resolves(store, text):
    resolution = one(text, store)
    assert (resolution.status, target(resolution)) == (Status.RESOLVED, (PRIVACY_CODE, "2-bis"))


# --- 5: never by number alone ------------------------------------------------------------------


def test_an_article_number_alone_is_ambiguous(store):
    resolution = one("Article 33", store)
    assert (resolution.status, resolution.reason) == (Status.AMBIGUOUS, "instrument_not_stated")
    assert sorted(c.split("@")[0] for c in resolution.candidates) == [GDPR, PRIVACY_CODE]
    assert resolution.provision_id is None
    # Only one corpus article has the label 2-bis: still ambiguous, never resolved.
    single = one("articolo 2-bis", store)
    assert (single.status, len(single.candidates)) == (Status.AMBIGUOUS, 1)
    assert single.provision_id is None


def test_a_part_without_an_act_is_ambiguous(store):
    resolution = one("Quali sono gli obblighi previsti dall'articolo 34, paragrafo 2?", store)
    assert resolution.status == Status.AMBIGUOUS and len(resolution.candidates) == 2


def test_an_unidentified_regulation_is_ambiguous_without_context(store):
    resolution = one("articolo 51 del regolamento", store)
    assert resolution.status == Status.AMBIGUOUS
    assert resolution.reference.basis == Basis.NONE


# --- 6-9: context ------------------------------------------------------------------------------


def test_context_resolves_an_unnamed_reference(store):
    resolution = one("Article 55", store, context_instrument=GDPR)
    assert (resolution.status, target(resolution)) == (Status.RESOLVED, (GDPR, "55"))
    assert resolution.reference.basis == Basis.CONTEXT


@pytest.mark.parametrize("text", ["di cui all'articolo 51 del regolamento è individuata",
                                  "Article 51 of the Regulation"])
def test_the_codes_regolamento_is_the_gdpr(store, text):
    resolution = one(text, store, context_instrument=PRIVACY_CODE)
    assert (resolution.status, target(resolution)) == (Status.RESOLVED, (GDPR, "51"))
    ref = resolution.reference
    assert (ref.source_instrument, ref.target_instrument, ref.basis) == (
        PRIVACY_CODE, GDPR, Basis.CONTEXT)


def test_an_unnamed_reference_in_the_code_stays_in_the_code(store):
    resolution = one("Garante, di cui all'articolo 153.", store, context_instrument=PRIVACY_CODE)
    assert (resolution.status, target(resolution)) == (Status.RESOLVED, (PRIVACY_CODE, "153"))


@pytest.mark.parametrize("text", ["l'articolo 40 sui codici di condotta",
                                  "Article 40 on codes of conduct"])
def test_codes_of_conduct_are_not_the_privacy_code(store, text):
    resolution = one(text, store, context_instrument=GDPR)
    assert target(resolution) == (GDPR, "40")


def test_an_explicit_name_wins_over_the_context(store):
    resolution = one("articolo 33 del Codice privacy", store, context_instrument=GDPR)
    assert target(resolution) == (PRIVACY_CODE, "33")
    assert resolution.reference.basis == Basis.EXPLICIT


# --- Other codes, and "codice" in the GDPR -----------------------------------------------------


@pytest.mark.parametrize("text", [
    "Cosa dice l'art. 98 del codice delle comunicazioni elettroniche?",
    "Cosa prevede l'art. 135 del codice delle assicurazioni private?",
])
def test_other_codes_are_unresolved_not_the_privacy_codes_same_number(store, text):
    resolution = one(text, store)  # the Privacy Code has an Art. 98 and an Art. 135
    assert (resolution.status, resolution.reason) == (Status.UNRESOLVED,
                                                      "instrument_not_in_corpus")
    assert resolution.reference.basis == Basis.EXTERNAL and resolution.provision_id is None


def test_a_bare_codice_in_the_gdprs_own_text_is_a_code_of_conduct(store):
    text = ("consentono all'organismo di cui all'articolo 41, paragrafo 1, di effettuare il "
            "controllo obbligatorio del rispetto delle norme del codice da parte dei titolari")
    resolution = one(text, store, context_instrument=GDPR)  # GDPR Art. 40(4)
    assert target(resolution) == (GDPR, "41")
    assert resolution.reference.basis == Basis.CONTEXT


def test_a_claim_on_gdpr_evidence_still_reads_codice_as_the_privacy_code():
    [ref] = extract_references("Lo prevede l'articolo 33 del Codice.", context_instrument=GDPR,
                               own_text=False)
    assert (ref.target_instrument, ref.basis) == (PRIVACY_CODE, Basis.EXPLICIT)


def test_in_the_codes_own_text_codice_is_the_code_unless_another_code_is_named():
    refs = extract_references("ai sensi dell'articolo 2-bis del codice e dell'articolo 135 del "
                              "codice delle assicurazioni private", context_instrument=PRIVACY_CODE)
    assert [(r.article, r.target_instrument, r.basis) for r in refs] == [
        ("2-bis", PRIVACY_CODE, Basis.EXPLICIT), ("135", None, Basis.EXTERNAL)]


def test_this_regulation_is_the_texts_own_act(store):
    resolution = one("ai sensi dell'articolo 6 del presente regolamento", store,
                     context_instrument=GDPR)
    assert (target(resolution), resolution.reference.basis) == ((GDPR, "6"), Basis.CONTEXT)


# --- 10-11: unsupported acts and articles -------------------------------------------------------


@pytest.mark.parametrize(("text", "act"), [
    ("articolo 2 del D.Lgs. 101/2018", "D.Lgs. 101/2018"),
    ("articolo 4 della direttiva 95/46/CE", "direttiva 95/46"),
    ("articolo 1218 del codice civile", "codice civile"),
    ("articolo 9 del regolamento (CE) n. 45/2001", "regolamento (CE) n. 45/2001"),
])
def test_acts_outside_the_corpus_are_unresolved(store, text, act):
    resolution = one(text, store, context_instrument=GDPR)
    assert (resolution.status, resolution.reason) == (Status.UNRESOLVED,
                                                      "instrument_not_in_corpus")
    assert resolution.reference.basis == Basis.EXTERNAL
    assert resolution.reference.external_act == act
    assert resolution.provision_id is None and resolution.candidates == ()


@pytest.mark.parametrize("text", ["articolo 100 GDPR", "art. 999 Codice privacy", "articolo 999"])
def test_articles_that_do_not_exist_are_unresolved(store, text):
    resolution = one(text, store)
    assert (resolution.status, resolution.reason) == (Status.UNRESOLVED, "no_such_article")


def test_an_instrument_not_in_the_store_is_unresolved(store):
    [ref] = extract_references("articolo 3", context_instrument="x-unknown-act")
    resolution = resolve_reference(ref, store)
    assert (resolution.status, resolution.reason) == (Status.UNRESOLVED,
                                                      "instrument_not_in_corpus")


# --- 12-13: several references, determinism ----------------------------------------------------


def test_several_references_are_resolved_independently(store):
    question = ("Qual è il rapporto tra l'articolo 2-bis del Codice Privacy e l'articolo 51 del "
                "GDPR?")
    resolutions = resolve_references(question, store)
    assert [(r.status, target(r)) for r in resolutions] == [
        (Status.RESOLVED, (PRIVACY_CODE, "2-bis")), (Status.RESOLVED, (GDPR, "51"))]
    assert [r.reference.instrument_text for r in resolutions] == ["Codice Privacy", "GDPR"]
    listed = resolve_references("articoli 33 e 34 del GDPR", store)
    assert [target(r) for r in listed] == [(GDPR, "33"), (GDPR, "34")]


def test_results_and_offsets_are_deterministic(store):
    text = "Cosa prevede l'articolo 33 GDPR, e l'articolo 2-bis del Codice privacy?"
    first, second = resolve_references(text, store), resolve_references(text, store)
    assert first == second
    for resolution in first:
        ref = resolution.reference
        assert text[ref.start:ref.end] == ref.raw_text
    assert [r.reference.raw_text for r in first] == ["articolo 33", "articolo 2-bis"]


def test_long_numbers_are_never_cut_into_article_labels():
    [ref] = extract_references("articolo 1218 del codice civile")
    assert ref.article == "1218"
    refs = extract_references("articolo 33, 2016/679")
    assert [r.article for r in refs] == ["33"]
