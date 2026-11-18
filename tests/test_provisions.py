"""Provision store (src/provisions.py): registry, review ledger, provisions, eligibility.

Uses the shipped registry and inventories, and mutated copies of them. No PDF,
parser output or chunk is read. Review records here are synthetic test data
("A. Reviewer"), never written to the shipped ledger.
"""

import copy
import datetime
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from src.provision_anchors import structure_sha256
from src.provisions import (
    LEDGER_PATH,
    OFFICIAL_CHECK_KEYS,
    QUALIFICATIONS,
    REASONS,
    REGISTRY_PATH,
    ProvisionError,
    SourceStatus,
    StructuralStatus,
    Tier,
    build_store,
    eligibility,
    load_ledger,
    load_registry,
    load_store,
    normalise_label,
    official_check_record,
    parse_ledger,
    parse_registry,
)
from src.reference_inventory import entry_id_for, missing_entry_id_for
from src.text_normalization import normalise

ROOT = Path(__file__).resolve().parent.parent
GDPR_V = "eu-reg-2016-679@oj-l119-2016-it"
CODICE_V = "it-dlgs-2003-196@transcription-vigente-2026-11-05"
TODAY = datetime.date(2026, 11, 10)


@pytest.fixture(scope="module")
def registry():
    return load_registry()


@pytest.fixture(scope="module")
def inventories(registry):
    return {
        v.version_id: json.loads((ROOT / v.inventory_path).read_text(encoding="utf-8"))
        for v in registry.versions
    }


@pytest.fixture(scope="module")
def store():
    return load_store()


def copies(inventories):
    return copy.deepcopy(dict(inventories))


def review_entry(inventory, label, by="A. Reviewer", on="2026-11-07"):
    entry = next(e for e in inventory["entries"] if e["label"] == label)
    entry.update(review_status="reviewed", checked_by=by, checked_on=on)
    return entry


def record(inventory, entry, outcome="confirmed", corrections=(), by="A. Reviewer",
           on="2026-11-07"):
    return {
        "inventory_id": inventory["inventory_id"],
        "entry_id": entry["entry_id"],
        "outcome": outcome,
        "checked_by": by,
        "checked_on": on,
        "corrections": list(corrections),
        "note": None,
    }


def build(registry, inventories, ledger=()):
    return build_store(registry, inventories, parse_ledger(list(ledger), today=TODAY))


# --- Shipped registry, ledger and inventories ----------------------------------------------


def test_shipped_files_load_and_the_ledger_is_empty(registry):
    assert load_ledger() == ()
    assert json.loads(LEDGER_PATH.read_text(encoding="utf-8")) == []
    assert [v.version_id for v in registry.versions] == [GDPR_V, CODICE_V]
    assert len(registry.sha256) == 64


def test_the_gdpr_version_is_the_2016_original_publication(registry):
    gdpr = registry.version(GDPR_V)
    assert gdpr.version_kind == "original_publication"
    assert "Official Journal" in gdpr.description and "4 May 2016" in gdpr.description
    assert "not a consolidated text" in gdpr.description
    assert gdpr.publication == {"date": "2016-05-04", "basis": "stated_in_text"}
    assert gdpr.authenticity is None and gdpr.corpus_reference_date is None
    assert gdpr.qualifications == (
        "original_publication_not_consolidated", "authenticity_not_established"
    )


def test_the_privacy_code_version_is_an_unverified_user_transcription(registry):
    codice = registry.version(CODICE_V)
    assert (codice.version_kind, codice.authenticity) == ("transcription", "user_transcription")
    assert codice.corpus_reference_date == {
        "date": "2026-11-05", "basis": "stated_in_text", "verified": False
    }
    assert codice.qualifications == ("unofficial_transcription", "reference_date_unverified")


def test_official_identifiers_are_left_null(registry):
    assert all(i.official_identifiers is None for i in registry.instruments)


def test_article_and_division_counts(store):
    assert len(store.articles(GDPR_V)) == 99 and len(store.articles(CODICE_V)) == 222
    assert len(store.divisions(GDPR_V)) == 26 and len(store.divisions(CODICE_V)) == 75
    assert Counter(p.kind for p in store.divisions(GDPR_V)) == {"chapter": 11, "section": 15}
    assert Counter(p.kind for p in store.divisions(CODICE_V)) == {
        "part": 3, "title": 25, "chapter": 46, "section": 1
    }
    assert store.missing == ()


def test_provisions_reproduce_the_inventory_exactly(store, inventories):
    for version_id, inventory in inventories.items():
        articles = store.articles(version_id)
        assert [p.inventory_ref for p in articles] == [e["entry_id"] for e in inventory["entries"]]
        for p, e in zip(articles, inventory["entries"]):
            assert (p.label_as_printed, p.heading_as_printed, p.title, p.status_marker) == (
                e["label"], e["heading_as_printed"], e["title"], e["status_marker"]
            )
            assert (p.page_start, p.page_end) == (e["page_start"], e["page_end"])
            assert p.source_sha256 == inventory["document"]["sha256"]
            assert p.doc_id == inventory["document"]["doc_id"]
        divisions = store.divisions(version_id)
        assert [p.inventory_ref for p in divisions] == [
            d["division_id"] for d in inventory["divisions"]
        ]


def test_provision_ids_are_stable_and_unique(store):
    ids = [p.provision_id for p in store]
    assert len(ids) == len(set(ids)) == 422
    assert store.lookup("gdpr", "33").provision_id == f"{GDPR_V}/body/article:33"
    assert store.lookup("codice privacy", "2-quaterdecies.1").provision_id == (
        f"{CODICE_V}/body/article:2-quaterdecies.1"
    )
    capo_iv = store.get(f"{CODICE_V}/body/part:i/title:i/chapter:iv")
    assert capo_iv.label_as_printed == "CAPO IV" and capo_iv.heading_as_printed == "(( CAPO IV"
    assert [p.provision_id for p in load_store()] == ids  # deterministic


def test_paths_and_parents_follow_the_printed_hierarchy(store):
    p = store.lookup("codice privacy", "2-quaterdecies.1")
    assert p.path == "PARTE I > TITOLO I > CAPO IV > Art. 2-quaterdecies.1"
    assert p.parent_id == f"{CODICE_V}/body/part:i/title:i/chapter:iv"
    assert store.lookup("gdpr", "12").path == "CAPO III > Sezione 1 > Articolo 12"
    section = store.get(f"{GDPR_V}/body/chapter:iii/section:1")
    assert section.parent_id == f"{GDPR_V}/body/chapter:iii" and section.title == (
        "Trasparenza e modalità"
    )


def test_statuses_of_the_shipped_inventories(store):
    codice = store.articles(CODICE_V)
    ambiguous = [p.label_as_printed for p in codice if p.structural_status == "ambiguous"]
    assert ambiguous == ["2-quindecies", "2-quinquiesdecies"]
    assert all(p.source_status_representation is None for p in codice if p.label_as_printed
               in ambiguous)
    counts = Counter(p.source_status_representation for p in codice)
    assert counts == {SourceStatus.MARKED_REPEALED: 114, SourceStatus.REPRESENTED_IN_FORCE: 106,
                      None: 2}
    assert {p.source_status_representation for p in store.articles(GDPR_V)} == {
        SourceStatus.NO_STATUS_REPRESENTATION
    }
    assert Counter(p.structural_status for p in store.articles()) == {
        StructuralStatus.AUTO_UNREVIEWED: 319, StructuralStatus.AMBIGUOUS: 2
    }
    assert {p.legal_validity for p in store} == {"not_established"}


def test_nothing_is_primary_while_the_ledger_is_empty(store):
    tiers = Counter(
        eligibility(p, store.registry.version(p.version_id), anchored=True).tier
        for p in store.articles()
    )
    assert tiers == {Tier.INTERNAL_ONLY: 319, Tier.BLOCKED: 2}


def test_repealed_divisions_keep_their_printed_marker(store):
    titolo_ii = store.get(f"{CODICE_V}/body/part:i/title:ii")
    assert titolo_ii.status_marker == "((TITOLO ABROGATO DAL D.LGS. 10 AGOSTO 2018, N. 101))"
    assert titolo_ii.source_status_representation == SourceStatus.MARKED_REPEALED


# --- IDs and labels -----------------------------------------------------------------------


def test_article_ids_do_not_depend_on_the_hierarchy(registry, inventories):
    changed = copies(inventories)
    gdpr = changed[GDPR_V]
    entry = gdpr["entries"][32]  # Article 33, under CAPO IV > Sezione 2
    entry.update(parent_id="gdpr-2016-679-oj-it:capo:IV", parent_path="CAPO IV")
    store = build(registry, changed)
    p = store.lookup("gdpr", "33")
    assert p.provision_id == f"{GDPR_V}/body/article:33" and p.path == "CAPO IV > Articolo 33"


def test_labels_that_normalise_to_the_same_id_are_rejected(registry, inventories):
    changed = copies(inventories)
    second = changed[GDPR_V]["entries"][1]
    second.update(label="1.", heading_as_printed="Articolo 1.", entry_id=entry_id_for(
        changed[GDPR_V]["entry_id_prefix"], "1."))
    with pytest.raises(ProvisionError, match="both become .*article:1"):
        build(registry, changed)


def test_normalisation_keeps_spelling_variants_apart():
    assert normalise_label("2-quindecies") != normalise_label("2-quinquiesdecies")
    assert normalise_label("Art. 1.".removeprefix("Art. ")) == "1"
    assert normalise_label("2-Bis") == "2-bis"


# --- Status mapping -----------------------------------------------------------------------


@pytest.mark.parametrize("status", ["uncertain", "ambiguous"])
def test_unsettled_inventory_statuses_become_ambiguous(registry, inventories, status):
    changed = copies(inventories)
    changed[GDPR_V]["entries"][0].update(structural_status=status, notes=["synthetic"])
    p = build(registry, changed).lookup("gdpr", "1")
    assert p.structural_status == StructuralStatus.AMBIGUOUS
    assert p.source_status_representation is None
    assert eligibility(p, registry.version(GDPR_V), anchored=True).tier == Tier.BLOCKED


def test_a_label_printed_twice_stops_the_build(registry, inventories):
    # Two entries with one label would get one provision ID. The build refuses
    # instead of merging them or numbering them; a reviewer must resolve it.
    changed = copies(inventories)
    gdpr = changed[GDPR_V]
    first, second = gdpr["entries"][0], gdpr["entries"][1]
    second.update(label="1", heading_as_printed="Articolo 1",
                  entry_id=entry_id_for(gdpr["entry_id_prefix"], "1", 2))
    for entry in (first, second):
        entry.update(structural_status="duplicate_label", notes=["synthetic"])
    with pytest.raises(ProvisionError, match="both become .*article:1"):
        build(registry, changed)


def test_an_expected_missing_entry_becomes_no_provision(registry, inventories):
    changed = copies(inventories)
    gdpr = changed[GDPR_V]
    gap = {key: None for key in gdpr["entries"][0]}
    gap.update(entry_id=missing_entry_id_for(gdpr["entry_id_prefix"], "100"),
               document_id=gdpr["document"]["doc_id"], ordinal=100, kind="article",
               structural_status="expected_missing", review_status="pending_human_review",
               source_sha256=gdpr["document"]["sha256"], notes=["synthetic gap"])
    gdpr["entries"].append(gap)
    store = build(registry, changed)
    assert store.missing == ((GDPR_V, gap["entry_id"]),)
    assert len(store.articles(GDPR_V)) == 99


# --- Review ledger --------------------------------------------------------------------------


def test_a_confirmed_review_gives_auto_verified_and_primary(registry, inventories):
    changed = copies(inventories)
    gdpr = changed[GDPR_V]
    entry = review_entry(gdpr, "33")
    store = build(registry, changed, [record(gdpr, entry)])
    p = store.lookup("gdpr", "33")
    assert p.structural_status == StructuralStatus.AUTO_VERIFIED
    assert (p.review.outcome, p.review.checked_by, p.review.checked_on) == (
        "confirmed", "A. Reviewer", "2026-11-07"
    )
    result = eligibility(p, registry.version(GDPR_V), anchored=True)
    assert result.tier == Tier.PRIMARY and result.reasons == ()
    assert "legal_validity_not_established" in result.qualifications
    assert p.legal_validity == "not_established"


def test_a_corrected_review_gives_manually_curated_with_its_provenance(registry, inventories):
    changed = copies(inventories)
    gdpr = changed[GDPR_V]
    entry = review_entry(gdpr, "34")
    before = entry["title"]
    entry["title"] = before + " (corretto)"
    correction = {"field": "title", "before": before, "after": entry["title"]}
    p = build(registry, changed, [record(gdpr, entry, "corrected", [correction])]).lookup(
        "gdpr", "34")
    assert p.structural_status == StructuralStatus.MANUALLY_CURATED  # never auto_verified
    assert p.review.corrections[0].before == before and p.title == entry["title"]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda inv, e, recs: recs.clear(), "no review ledger record"),
        (lambda inv, e, recs: recs[0].update(checked_by="B. Other"), "reviewer or date differs"),
        (lambda inv, e, recs: recs[0].update(checked_on="2026-11-06"), "reviewer or date differs"),
        (lambda inv, e, recs: recs[0].update(outcome="corrected"), "lists its corrections"),
        (lambda inv, e, recs: recs[0].update(corrections=[
            {"field": "title", "before": "x", "after": "y"}]), "has no corrections"),
        (lambda inv, e, recs: recs[0].update(outcome="corrected", corrections=[
            {"field": "title", "before": e["title"], "after": "Altro titolo"}]), "ledger says"),
        (lambda inv, e, recs: recs[0].update(entry_id="gdpr-2016-679-oj-it:art:999"),
         "no review ledger record"),
        (lambda inv, e, recs: recs.append(dict(recs[0])), "a second record"),
        (lambda inv, e, recs: recs[0].update(checked_on="2026-11-11"), "in the future"),
        (lambda inv, e, recs: recs[0].update(checked_on="7/11/2026"), "not YYYY-MM-DD"),
        (lambda inv, e, recs: recs[0].update(checked_by=" "), "must name the reviewer"),
        (lambda inv, e, recs: recs[0].update(outcome="approved"), "outcome"),
        (lambda inv, e, recs: recs[0].update(corrections=[
            {"field": "notes", "before": [], "after": ["x"]}], outcome="corrected"), "field"),
    ],
)
def test_inconsistent_review_records_are_refused(registry, inventories, mutate, message):
    changed = copies(inventories)
    gdpr = changed[GDPR_V]
    entry = review_entry(gdpr, "33")
    records = [record(gdpr, entry)]
    mutate(gdpr, entry, records)
    with pytest.raises(ProvisionError, match=message):
        build(registry, changed, records)


def test_a_ledger_record_for_a_pending_entry_is_refused(registry, inventories):
    gdpr = inventories[GDPR_V]
    entry = gdpr["entries"][32]
    with pytest.raises(ProvisionError, match="not reviewed"):
        build(registry, copies(inventories), [record(gdpr, entry)])


def test_a_ledger_record_for_an_unknown_inventory_is_refused(registry, inventories):
    changed = copies(inventories)
    entry = review_entry(changed[GDPR_V], "33")
    stray = record(changed[GDPR_V], entry)
    stray["inventory_id"] = "other-inventory"
    with pytest.raises(ProvisionError, match="ledger records for unknown entries"):
        build(registry, changed, [record(changed[GDPR_V], entry), stray])


# --- Eligibility ----------------------------------------------------------------------------


def reviewed_store(registry, inventories, labels_by_version):
    changed = copies(inventories)
    ledger = []
    for version_id, labels in labels_by_version.items():
        for label in labels:
            entry = review_entry(changed[version_id], label)
            ledger.append(record(changed[version_id], entry))
    return build(registry, changed, ledger)


def test_reviewed_repealed_provisions_are_excluded_from_primary_citation(registry, inventories):
    store = reviewed_store(registry, inventories, {CODICE_V: ["3", "2-quindecies"]})
    repealed = store.lookup("codice privacy", "3")
    assert repealed.structural_status == StructuralStatus.AUTO_VERIFIED
    assert repealed.source_status_representation == SourceStatus.MARKED_REPEALED
    result = eligibility(repealed, registry.version(CODICE_V), anchored=True)
    assert result.tier == Tier.INTERNAL_ONLY
    assert result.reasons == ("source_marks_repealed_excluded_from_first_demo",)
    assert "source_marks_repealed" in result.qualifications
    ambiguous = store.lookup("codice privacy", "2-quindecies")  # reviewed but still ambiguous
    assert ambiguous.structural_status == StructuralStatus.AMBIGUOUS
    assert eligibility(ambiguous, registry.version(CODICE_V), anchored=True).tier == Tier.BLOCKED


def test_eligibility_tiers_and_reasons(store, registry):
    gdpr = registry.version(GDPR_V)
    unreviewed = store.lookup("gdpr", "33")
    assert eligibility(unreviewed, gdpr, anchored=True).reasons == ("structure_not_reviewed",)
    unanchored = eligibility(unreviewed, gdpr, anchored=False)
    assert unanchored.tier == Tier.BLOCKED
    assert unanchored.reasons == ("no_anchored_text", "structure_not_reviewed")
    division = eligibility(store.get(f"{GDPR_V}/body/chapter:iv"), gdpr, anchored=True)
    assert (division.tier, division.reasons) == (Tier.CONTEXT_ONLY, ("division_context_only",))
    ambiguous = eligibility(store.lookup("codice privacy", "2-quinquiesdecies"),
                            registry.version(CODICE_V), anchored=True)
    assert ambiguous.reasons == ("ambiguous_structure", "structure_not_reviewed")


def test_every_eligibility_carries_the_version_qualifications(store, registry):
    for p in store:
        version = registry.version(p.version_id)
        result = eligibility(p, version, anchored=True)
        assert result.qualifications[: len(version.qualifications)] == version.qualifications
        assert result.qualifications[-1] == "legal_validity_not_established"
        assert set(result.reasons) <= set(REASONS)
        assert set(result.qualifications) <= set(QUALIFICATIONS)


# --- Official-source check in the review ledger ----------------------------------------------

CONSOLIDATED_URL = (
    "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:02016R0679-20160504")
NORMATTIVA_URL = ("https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:"
                  "2003-06-30;196~art2bis")


def official_check(**changes):
    check = {
        "source_url": CONSOLIDATED_URL,
        "source_type": "eurlex_consolidated",
        "consolidation_date": "2016-05-04",
        "retrieved_on": "2026-11-07",
        "official_text_sha256": "a" * 64,
        "normalisation": "ws-markers-softhyphen-v1",
        "match_status": "identical_after_normalisation",
        "differences": [],
    }
    check.update(changes)
    return check


def checked_store(registry, inventories, check, label="33"):
    changed = copies(inventories)
    gdpr = changed[GDPR_V]
    entry = review_entry(gdpr, label)
    rec = record(gdpr, entry)
    rec["official_check"] = check
    return build(registry, changed, [rec]).lookup("gdpr", label)


def parse_one_check(check):
    rec = {"inventory_id": "x", "entry_id": "x:art:1", "outcome": "confirmed",
           "checked_by": "A. Reviewer", "checked_on": "2026-11-07", "corrections": [],
           "note": None, "official_check": check}
    return parse_ledger([rec], today=TODAY)[0].official_check


def test_a_record_without_official_check_still_parses_and_can_be_primary(registry, inventories):
    changed = copies(inventories)
    entry = review_entry(changed[GDPR_V], "33")
    rec = record(changed[GDPR_V], entry)
    assert "official_check" not in rec
    assert parse_ledger([rec], today=TODAY)[0].official_check is None
    p = build(registry, changed, [rec]).lookup("gdpr", "33")
    assert p.review.official_check is None
    assert eligibility(p, registry.version(GDPR_V), anchored=True).tier == Tier.PRIMARY


@pytest.mark.parametrize("status", ["identical", "identical_after_normalisation"])
def test_a_matching_official_check_is_kept_and_allows_primary(registry, inventories, status):
    p = checked_store(registry, inventories, official_check(match_status=status))
    check = p.review.official_check
    assert (check.source_type, check.match_status, check.differences) == (
        "eurlex_consolidated", status, ())
    assert (check.source_url, check.retrieved_on, check.consolidation_date) == (
        CONSOLIDATED_URL, "2026-11-07", "2016-05-04")
    result = eligibility(p, registry.version(GDPR_V), anchored=True)
    assert result.tier == Tier.PRIMARY and result.reasons == ()
    # A match with an official source establishes nothing about legal validity.
    assert p.legal_validity == "not_established"
    assert result.qualifications[-1] == "legal_validity_not_established"
    assert "original_publication_not_consolidated" in result.qualifications


def test_a_differing_official_text_prevents_primary(registry, inventories):
    check = official_check(match_status="differs",
                           differences=[{"ours": "indugio", "official": "ritardo"}])
    p = checked_store(registry, inventories, check, label="56")
    assert p.structural_status == StructuralStatus.AUTO_VERIFIED
    assert p.review.official_check.differences[0].theirs == "ritardo"
    result = eligibility(p, registry.version(GDPR_V), anchored=True)
    assert result.tier == Tier.INTERNAL_ONLY
    assert result.reasons == ("official_text_differs",)
    assert p.legal_validity == "not_established"
    unanchored = eligibility(p, registry.version(GDPR_V), anchored=False)
    assert unanchored.tier == Tier.BLOCKED
    assert unanchored.reasons == ("no_anchored_text", "official_text_differs")


def test_the_official_text_differs_reason_is_documented():
    assert "official_text_differs" in REASONS
    assert "not cited as primary evidence" in REASONS["official_text_differs"]


@pytest.mark.parametrize("changes", [
    {"source_type": "oj_original", "consolidation_date": None,
     "source_url": "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32016R0679"},
    {"source_type": "oj_corrigendum", "consolidation_date": "2018-05-23",
     "source_url": "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32016R0679R(02)"},
    {"source_type": "normattiva_vigente", "consolidation_date": None,
     "source_url": NORMATTIVA_URL},
    {"source_type": "normattiva_vigente", "consolidation_date": "2026-02-19",
     "source_url": NORMATTIVA_URL},
    {"source_type": "gu_serie_generale", "consolidation_date": None,
     "source_url": "https://www.gazzettaufficiale.it/eli/gu/2018/09/04/205/sg/pdf"},
    {"retrieved_on": "2016-05-04"},  # same day as the consolidation
])
def test_valid_official_checks(changes):
    check = parse_one_check(official_check(**changes))
    assert check.source_type == changes.get("source_type", "eurlex_consolidated")


@pytest.mark.parametrize(("changes", "message"), [
    # exact keys
    ({"extra": 1}, "expected keys"),
    ({"official_text_sha256": None, "normalised_text_sha256": "a" * 64}, "expected keys"),
    # source type and URL
    ({"source_type": "wikipedia"}, "source_type must be one of"),
    ({"source_type": None}, "source_type must be one of"),
    ({"source_url": "http://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32016R0679"},
     "must be https://eur-lex.europa.eu/"),
    ({"source_url": "https://eur-lex.europa.eu.example.com/x"}, "must be https://eur-lex"),
    ({"source_url": "https://example.com/eur-lex.europa.eu"}, "must be https://eur-lex"),
    ({"source_url": "https://eur-lex.europa.eu:8443/x"}, "must be https://eur-lex"),
    ({"source_url": "https://user@eur-lex.europa.eu/x"}, "must be https://eur-lex"),
    ({"source_url": "https://EUR-LEX.europa.eu/x"}, "must be https://eur-lex"),
    ({"source_url": NORMATTIVA_URL}, "must be https://eur-lex.europa.eu/"),
    ({"source_type": "normattiva_vigente"}, "must be https://www.normattiva.it/"),
    ({"source_type": "gu_serie_generale"}, "must be https://www.gazzettaufficiale.it/"),
    ({"source_type": "gu_serie_generale", "source_url": NORMATTIVA_URL},
     "must be https://www.gazzettaufficiale.it/"),
    ({"source_url": "https://eur-lex.europa.eu/x y"}, "source_url"),
    ({"source_url": ""}, "source_url"),
    ({"source_url": 42}, "source_url"),
    # ISO dates and their order
    ({"retrieved_on": "07/11/2026"}, "retrieved_on: not YYYY-MM-DD"),
    ({"retrieved_on": "2026-02-30"}, "not a calendar date"),
    ({"retrieved_on": None}, "retrieved_on: not YYYY-MM-DD"),
    ({"retrieved_on": "2026-11-08"}, "retrieved_on is after checked_on"),
    ({"consolidation_date": "04/05/2016"}, "consolidation_date: not YYYY-MM-DD"),
    ({"consolidation_date": "2026-11-08"}, "consolidation_date is after retrieved_on"),
    ({"consolidation_date": None}, "needs its consolidation_date"),
    # hash of the official text
    ({"official_text_sha256": "A" * 64}, "64 lowercase hex"),
    ({"official_text_sha256": "a" * 63}, "64 lowercase hex"),
    ({"official_text_sha256": None}, "64 lowercase hex"),
    # normalisation profile and match status
    ({"normalisation": "none"}, "normalisation must be one of"),
    ({"match_status": "matches"}, "match_status must be one of"),
    ({"match_status": None}, "match_status must be one of"),
    # differences exactly when the text differs
    ({"match_status": "differs"}, "needs its differences"),
    ({"differences": [{"ours": "indugio", "official": "ritardo"}]},
     "only when the text differs"),
    ({"match_status": "identical", "differences": [{"ours": "a", "official": "b"}]},
     "only when the text differs"),
    ({"match_status": "differs", "differences": "indugio/ritardo"}, "must be a list"),
    ({"match_status": "differs", "differences": [{"ours": "indugio"}]}, "expected keys"),
    ({"match_status": "differs", "differences": [["indugio", "ritardo"]]}, "must be an object"),
    ({"match_status": "differs", "differences": [{"ours": None, "official": "ritardo"}]},
     "must be strings"),
    ({"match_status": "differs", "differences": [{"ours": "ritardo", "official": "ritardo"}]},
     "same text after normalisation"),
    ({"match_status": "differs",
      "differences": [{"ours": "dell’articolo", "official": "dell'articolo"}]},
     "same text after normalisation"),
])
def test_invalid_official_checks_are_refused(changes, message):
    with pytest.raises(ProvisionError, match=message):
        parse_one_check(official_check(**changes))


@pytest.mark.parametrize(("check", "message"), [
    (None, "rather than null"),
    ("identical", "must be an object"),
    ({}, "expected keys"),
])
def test_an_official_check_must_be_a_complete_object(check, message):
    with pytest.raises(ProvisionError, match=message):
        parse_one_check(check)


def test_official_check_record_hashes_the_official_text_as_given():
    ours = "senza ingiustificato indugio"
    official = "senza ingiustificato \n►C2\n ritardo ◄"
    check = official_check_record(ours, official, source_url=CONSOLIDATED_URL,
                                  source_type="eurlex_consolidated",
                                  consolidation_date="2016-05-04", retrieved_on="2026-11-07")
    assert set(check) == OFFICIAL_CHECK_KEYS
    assert check["official_text_sha256"] == hashlib.sha256(official.encode("utf-8")).hexdigest()
    assert check["official_text_sha256"] != hashlib.sha256(
        normalise(official).encode("utf-8")).hexdigest()
    assert (check["match_status"], check["differences"]) == (
        "differs", [{"ours": "indugio", "official": "ritardo"}])
    assert check["normalisation"] == "ws-markers-softhyphen-v1"
    assert parse_one_check(check).match_status == "differs"  # ready for a ledger record


@pytest.mark.parametrize(("ours", "official", "status"), [
    ("anche in modo approssi\xad\n\nmativo", "▼B\nanche in modo approssimativo",
     "identical_after_normalisation"),
    ("Art. 2-bis", "Art. 2-bis", "identical"),
])
def test_official_check_record_statuses(ours, official, status):
    check = official_check_record(ours, official, source_url=NORMATTIVA_URL,
                                  source_type="normattiva_vigente", consolidation_date=None,
                                  retrieved_on="2026-11-07")
    assert (check["match_status"], check["differences"]) == (status, [])


def test_official_check_record_refuses_an_invalid_source():
    with pytest.raises(ProvisionError, match="must be https://www.normattiva.it/"):
        official_check_record("a", "a", source_url=CONSOLIDATED_URL,
                              source_type="normattiva_vigente", consolidation_date=None,
                              retrieved_on="2026-11-07")


def test_an_official_check_does_not_make_anchors_stale(registry, inventories):
    plain = reviewed_store(registry, inventories, {GDPR_V: ["56"]})
    check = official_check(match_status="differs",
                           differences=[{"ours": "indugio", "official": "ritardo"}])
    checked = checked_store(registry, inventories, check, label="56")
    assert checked.review.official_check is not None
    with_check = [checked if p.provision_id == checked.provision_id else p
                  for p in plain.articles(GDPR_V)]
    assert structure_sha256(with_check) == structure_sha256(plain.articles(GDPR_V))


# --- Lookup ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("instrument", "label", "expected"),
    [
        ("gdpr", "6", f"{GDPR_V}/body/article:6"),
        (" GDPR ", "6", f"{GDPR_V}/body/article:6"),
        ("eu-reg-2016-679", "99", f"{GDPR_V}/body/article:99"),
        ("Codice Privacy", "2-sex-decies", f"{CODICE_V}/body/article:2-sex-decies"),
        ("d.lgs. 196/2003", "2-QUATERDECIES.1", f"{CODICE_V}/body/article:2-quaterdecies.1"),
        ("codice privacy", "2-quindecies", f"{CODICE_V}/body/article:2-quindecies"),
        ("codice privacy", "2-quinquiesdecies", f"{CODICE_V}/body/article:2-quinquiesdecies"),
    ],
)
def test_lookup_by_alias_and_label(store, instrument, label, expected):
    assert store.lookup(instrument, label).provision_id == expected


@pytest.mark.parametrize(
    ("instrument", "label", "message"),
    [
        ("gdpr", "100", "no article"),
        ("gdpr", "6 ", "no article"),
        ("gdpr", "art. 6", "no article"),
        ("gdpr", "VI", "no article"),
        ("codice privacy", "2-sexdecies", "no article"),
        ("codice privacy", "2 bis", "no article"),
        ("gdpr2016", "6", "unknown instrument"),
        ("codice", "6", "unknown instrument"),  # too generic to be an alias
        ("regolamento", "6", "unknown instrument"),
    ],
)
def test_lookup_never_matches_approximately(store, instrument, label, message):
    with pytest.raises(ProvisionError, match=message):
        store.lookup(instrument, label)


# --- Registry validation --------------------------------------------------------------------


def registry_data():
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d["versions"][0].update(instrument_id="eu-reg-0000-0"), "version_id must be"),
        (lambda d: d["versions"][1].update(version_id=d["versions"][0]["version_id"]),
         "missing or duplicated"),
        (lambda d: d["versions"][0].update(version_kind="consolidated"), "version_kind"),
        (lambda d: d["versions"][0].update(authenticity="authenticated"), "authenticity"),
        (lambda d: d["versions"][0].update(provision_status_representation="marked_repealed"),
         "comes from the printed marker"),
        (lambda d: d["versions"][0].update(provision_status_representation="in_force"),
         "provision_status_representation"),
        (lambda d: d["versions"][0].update(source_sha256="abc"), "source_sha256"),
        (lambda d: d["versions"][1]["corpus_reference_date"].update(date="2026-02-30"),
         "calendar date"),
        (lambda d: d["instruments"][1]["aliases"].append("GDPR"), "already used"),
        (lambda d: d["instruments"][0].update(extra=1), "expected keys"),
        (lambda d: d.update(schema_version=2), "schema_version"),
    ],
)
def test_invalid_registries_are_refused(mutate, message):
    data = registry_data()
    mutate(data)
    with pytest.raises(ProvisionError, match=message):
        parse_registry(data, "0" * 64)


def test_an_inventory_for_another_source_file_is_refused(registry, inventories):
    changed = copies(inventories)
    changed[GDPR_V], changed[CODICE_V] = changed[CODICE_V], changed[GDPR_V]
    with pytest.raises(ProvisionError, match="describes another source file"):
        build(registry, changed)


def test_an_inventory_is_needed_for_each_version(registry, inventories):
    with pytest.raises(ProvisionError, match="exactly each registered version"):
        build(registry, {GDPR_V: inventories[GDPR_V]})


# --- Segmentation rules in the registry -----------------------------------------------------


def test_the_shipped_segmentation_rules(registry):
    gdpr, codice = registry.version(GDPR_V).segmentation, registry.version(CODICE_V).segmentation
    assert gdpr.furniture_expected_lines == 352 and codice.furniture_expected_lines == 106
    assert [m.kind for m in gdpr.markers] == [
        "preamble", "recitals", "enacting_formula", "closing_formula"
    ]
    assert [m.kind for m in codice.markers] == ["enacting_formula", "closing_formula"]
    assert gdpr.footnotes.expected == 3 and gdpr.editorial_notes is None
    assert codice.editorial_notes.expected == 20 and codice.footnotes is None


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda s: s.pop("footnotes"), "expected keys"),
        (lambda s: s["page_furniture"].update(line_patterns=["(unclosed"]),
         "invalid regular expression"),
        (lambda s: s["page_furniture"].update(line_patterns=[]), "line_patterns"),
        (lambda s: s["page_furniture"].update(expected_lines=-1), "integer >= 0"),
        (lambda s: s["markers"].append({"kind": "annex", "line_starts_with": "ALLEGATO"}),
         "kind 'annex'"),
        (lambda s: s["markers"].reverse(), "must follow the order"),
        (lambda s: s["markers"].append(dict(s["markers"][0])), "listed twice"),
        (lambda s: s["markers"][0].update(line_starts_with=" "), "line_starts_with"),
        (lambda s: s["footnotes"].update(expected=0), "integer >= 1"),
        (lambda s: s["footnotes"].update(max_chars="600"), "integer >= 1"),
        (lambda s: s["footnotes"].update(end_text_pattern="pag\. (\d+"),
         "invalid regular expression"),
        (lambda s: s.update(editorial_notes={"separator_pattern": "-+", "label_pattern": "A",
                                             "expected": 0}), "integer >= 1"),
    ],
)
def test_invalid_segmentation_rules_are_refused(mutate, message):
    data = registry_data()
    mutate(data["versions"][0]["segmentation"])
    with pytest.raises(ProvisionError, match=message):
        parse_registry(data, "0" * 64)
