"""Reference inventories (data/reference/, src/reference_inventory.py).

The shipped inventories are validated as they are; the failure cases mutate a
copy of the GDPR inventory. Nothing here reads a PDF or runs the parser.
"""

import copy
import datetime
import json
from collections import Counter
from pathlib import Path

import pytest

from src.reference_inventory import (
    REVIEW_STATUSES,
    STRUCTURAL_STATUSES,
    InventoryError,
    entry_id_for,
    load_inventory,
    missing_entry_id_for,
    serialize_inventory,
    validate_inventory,
)

REFERENCE = Path(__file__).resolve().parent.parent / "data" / "reference"
GDPR = REFERENCE / "gdpr_2016_679_it.inventory.json"
CODICE = REFERENCE / "codice_privacy_dlgs_196_2003.main_body.inventory.json"
# A fixed "today" for the review-date rules, so the tests do not depend on the clock.
TODAY = datetime.date(2026, 11, 10)


@pytest.fixture(scope="module")
def gdpr():
    return load_inventory(GDPR)


@pytest.fixture(scope="module")
def codice():
    return load_inventory(CODICE)


@pytest.fixture
def base(gdpr):
    return copy.deepcopy(gdpr)


def rejected(inventory, message):
    with pytest.raises(InventoryError, match=message):
        validate_inventory(inventory, today=TODAY)


def reviewed(entry, checked_on="2026-11-10", checked_by="A. Reviewer"):
    entry.update(review_status="reviewed", checked_by=checked_by, checked_on=checked_on)


# --- The shipped inventories ---------------------------------------------------------


@pytest.mark.parametrize("path", [GDPR, CODICE], ids=["gdpr", "codice"])
def test_shipped_inventories_are_valid_and_in_canonical_form(path):
    text = path.read_text(encoding="utf-8")
    assert serialize_inventory(json.loads(text)) == text


@pytest.mark.parametrize("path", [GDPR, CODICE], ids=["gdpr", "codice"])
def test_entry_ids_are_unique_and_every_entry_carries_the_document_hash(path):
    inventory = load_inventory(path)
    ids = [entry["entry_id"] for entry in inventory["entries"]]
    assert len(ids) == len(set(ids))
    sha256 = inventory["document"]["sha256"]
    assert {entry["source_sha256"] for entry in inventory["entries"]} == {sha256}
    division_ids = [d["division_id"] for d in inventory["divisions"]]
    assert len(division_ids) == len(set(division_ids))


def test_gdpr_lists_articles_1_to_99_in_order(gdpr):
    assert [e["label"] for e in gdpr["entries"]] == [str(n) for n in range(1, 100)]
    assert all(e["heading_as_printed"] == "Articolo " + e["label"] for e in gdpr["entries"])
    assert gdpr["document"]["sha256"].startswith("8f7504d2")


def test_codice_keeps_the_printed_labels_exactly(codice):
    entries = codice["entries"]
    labels = [e["label"] for e in entries]
    assert len(entries) == 222 and labels[0] == "1" and labels[-1] == "186"
    assert all(e["heading_as_printed"] == "Art. " + e["label"] for e in entries)
    for label in ("2-quaterdecies.1", "2-sex-decies", "2-septies-decies", "32-bis", "132-quater"):
        assert labels.count(label) == 1
    # Two spellings of "fifteenth" are kept as two separate, ambiguous entries.
    pair = [e for e in entries if e["label"] in ("2-quindecies", "2-quinquiesdecies")]
    assert [e["label"] for e in pair] == ["2-quindecies", "2-quinquiesdecies"]
    assert {e["structural_status"] for e in pair} == {"ambiguous"}
    assert codice["document"]["sha256"].startswith("0d264a29")


def test_codice_main_body_stops_before_the_annexes(codice):
    assert codice["scope"]["last_page"] == 53
    assert max(e["page_end"] for e in codice["entries"]) == 53
    assert "ALLEGATO A.1" in codice["scope"]["ends_before"]


@pytest.mark.parametrize("path", [GDPR, CODICE], ids=["gdpr", "codice"])
def test_statuses_and_review_fields_use_the_allowed_values(path):
    inventory = load_inventory(path)
    statuses = Counter(e["structural_status"] for e in inventory["entries"])
    reviews = Counter(e["review_status"] for e in inventory["entries"])
    assert set(statuses) <= set(STRUCTURAL_STATUSES)
    assert set(reviews) <= set(REVIEW_STATUSES)
    assert inventory["provenance"]["parser_output_used"] is False


# --- Serialization -------------------------------------------------------------------


def test_serialization_is_deterministic_and_independent_of_key_order(base):
    first = serialize_inventory(base)
    reordered = {key: base[key] for key in reversed(list(base))}
    reordered["entries"] = [
        {key: entry[key] for key in reversed(list(entry))} for entry in base["entries"]
    ]
    assert serialize_inventory(reordered) == first == serialize_inventory(base)
    assert first.endswith("}\n") and "\r" not in first
    assert "Liceità del trattamento" in first  # non-ASCII text is kept, not escaped


def test_serialization_refuses_an_invalid_inventory(base):
    base["entries"][0]["review_status"] = "approved"
    with pytest.raises(InventoryError):
        serialize_inventory(base)


# --- Validation failures --------------------------------------------------------------


def test_duplicate_entry_ids_are_rejected(base):
    base["entries"][1]["entry_id"] = base["entries"][0]["entry_id"]
    rejected(base, "duplicate entry IDs")


def test_an_entry_hash_that_differs_from_the_document_hash_is_rejected(base):
    base["entries"][5]["source_sha256"] = "0" * 64
    rejected(base, "source_sha256 differs")


def test_a_document_id_inconsistent_with_the_hash_is_rejected(base):
    base["document"]["doc_id"] = "doc-0000000000000000"
    rejected(base, "doc_id must be 'doc-'")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("structural_status", "verified", "unknown structural_status"),
        ("structural_status", "Present", "unknown structural_status"),
        ("review_status", "approved", "unknown review_status"),
        ("review_status", None, "unknown review_status"),
        ("ordinal", 7, "ordinal must be 1"),
        ("kind", "paragraph", "kind must be 'article'"),
        ("page_start", 0, "pages must satisfy"),
        ("page_end", 89, "pages must satisfy"),
        ("parent_id", "gdpr-2016-679-oj-it:capo:XII", "is not a division"),
        ("title", " Oggetto", "title must be a non-empty string or null"),
    ],
)
def test_invalid_field_values_are_rejected(base, field, value, message):
    base["entries"][0][field] = value
    rejected(base, message)


def test_missing_and_unknown_fields_are_rejected(base):
    del base["entries"][0]["notes"]
    rejected(base, "must have exactly the keys")
    base = copy.deepcopy(load_inventory(GDPR))
    base["entries"][0]["verified"] = True
    rejected(base, "must have exactly the keys")
    base = copy.deepcopy(load_inventory(GDPR))
    del base["provenance"]
    rejected(base, "top-level keys")


@pytest.mark.parametrize(
    ("checked_by", "checked_on"),
    [("A. Reviewer", None), (None, "2026-11-10"), ("A. Reviewer", "2026-11-10")],
)
def test_a_pending_entry_cannot_carry_review_details(base, checked_by, checked_on):
    entry = base["entries"][0]
    entry["checked_by"], entry["checked_on"] = checked_by, checked_on
    rejected(base, "a pending entry must have checked_by and checked_on null")


@pytest.mark.parametrize(
    ("checked_by", "checked_on", "message"),
    [
        (None, None, "needs checked_by"),
        ("A. Reviewer", None, "needs checked_on"),
        ("A. Reviewer", "10/11/2026", "needs checked_on"),
        (" ", "2026-11-10", "needs checked_by"),
    ],
)
def test_a_reviewed_entry_needs_a_reviewer_and_a_date(base, checked_by, checked_on, message):
    reviewed(base["entries"][0], checked_on=checked_on, checked_by=checked_by)
    rejected(base, message)


@pytest.mark.parametrize("checked_on", ["2026-11-10", "2026-11-09", "2024-02-29"])
def test_a_complete_review_is_accepted(base, checked_on):
    reviewed(base["entries"][0], checked_on=checked_on)
    validate_inventory(base, today=TODAY)


# V1: checked_on is a strict YYYY-MM-DD calendar date, not in the future.
@pytest.mark.parametrize(
    "checked_on",
    [
        "2026-W45-2",  # ISO week date: accepted by date.fromisoformat, not by the format
        "20261110",  # ISO basic format
        "2026-11-7",
        "2026-11-10T09:00",
        " 2026-11-10",
        "2026-02-30",  # not a calendar date
        "2025-02-29",  # not a leap year
        "2026-13-01",
        20261110,
        ["2026-11-10"],
    ],
)
def test_checked_on_must_be_a_strict_calendar_date(base, checked_on):
    reviewed(base["entries"][0], checked_on=checked_on)
    rejected(base, "needs checked_on as a date YYYY-MM-DD")


@pytest.mark.parametrize("checked_on", ["2026-11-11", "2099-01-01"])
def test_checked_on_cannot_be_in_the_future(base, checked_on):
    reviewed(base["entries"][0], checked_on=checked_on)
    rejected(base, f"checked_on {checked_on} is in the future")


def test_the_future_is_judged_against_the_current_date_by_default(base):
    future = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    reviewed(base["entries"][0], checked_on=future)
    with pytest.raises(InventoryError, match="is in the future"):
        validate_inventory(base)


# V2: the structural status and a printed repeal marker must agree.
@pytest.mark.parametrize(
    "marker",
    [
        "((ARTICOLO ABROGATO DAL D.LGS. 10 AGOSTO 2018, N. 101))",
        "(( ARTICOLO NON PIÙ PREVISTO DAL DECRETO 15 MARZO 2019 ))",
        "((articolo abrogato))",
    ],
)
def test_a_present_entry_cannot_carry_a_repeal_marker(base, marker):
    base["entries"][0]["status_marker"] = marker
    rejected(base, "a present entry cannot carry a repeal status_marker")
    base["entries"][0]["structural_status"] = "marked_repealed"
    validate_inventory(base, today=TODAY)


def test_marked_repealed_needs_a_marker_that_says_so(base):
    entry = base["entries"][0]
    entry.update(structural_status="marked_repealed", status_marker="(( TESTO ))")
    rejected(base, "marked_repealed needs the printed repeal status_marker")


def test_the_shipped_repeal_markers_agree_with_the_statuses(codice):
    repealed = [e for e in codice["entries"] if e["structural_status"] == "marked_repealed"]
    assert len(repealed) == 114
    assert all("ABROGAT" in e["status_marker"] for e in repealed)


# V3: parent_path is the printed path of parent_id.
def test_parent_path_must_match_the_division_hierarchy(base):
    entry = base["entries"][11]  # Article 12
    assert (entry["label"], entry["parent_path"]) == ("12", "CAPO III > Sezione 1")
    for wrong in ("CAPO IX", "Sezione 1", "CAPO III", "CAPO III > Sezione 2", "CAPO III>Sezione 1"):
        entry["parent_path"] = wrong
        rejected(base, "parent_path must be 'CAPO III > Sezione 1'")


def test_parent_path_without_parent_id_is_rejected(base):
    base["entries"][0]["parent_id"] = None
    rejected(base, "parent_path must be null when parent_id is null")
    base["entries"][0]["parent_path"] = None
    validate_inventory(base, today=TODAY)


def test_every_shipped_parent_path_is_the_printed_path(codice):
    entry = next(e for e in codice["entries"] if e["label"] == "2-quaterdecies.1")
    assert entry["parent_path"] == "PARTE I > TITOLO I > CAPO IV"
    broken = copy.deepcopy(codice)
    broken["entries"][0]["parent_path"] = "PARTE I > CAPO I"
    rejected(broken, "parent_path must be 'PARTE I > TITOLO I > CAPO I'")


def test_an_altered_label_or_derived_id_is_rejected(base):
    entry = base["entries"][0]
    entry["label"] = "01"  # the heading still prints "Articolo 1"
    rejected(base, "heading_as_printed must end with the label as printed")
    base = copy.deepcopy(load_inventory(GDPR))
    base["entries"][0]["entry_id"] = "gdpr-2016-679-oj-it:art:one"
    rejected(base, "entry_id must be 'gdpr-2016-679-oj-it:art:1'")


def test_a_repeated_label_needs_duplicate_label_status_and_a_suffixed_id(base):
    first, second = base["entries"][0], base["entries"][1]
    second.update(
        heading_as_printed="Articolo 1",
        label="1",
        entry_id=entry_id_for(base["entry_id_prefix"], "1", 2),
    )
    rejected(base, "label printed more than once")
    for entry in (first, second):
        entry["structural_status"] = "duplicate_label"
        entry["notes"] = ["The label '1' is printed twice."]
    validate_inventory(base)
    assert second["entry_id"].endswith(":art:1~2")


@pytest.mark.parametrize(
    ("status", "message"),
    [
        ("marked_repealed", "marked_repealed needs the printed repeal status_marker"),
        ("ambiguous", "status ambiguous must be explained in notes"),
        ("uncertain", "status uncertain must be explained in notes"),
        ("duplicate_label", "duplicate_label but the label is printed only once"),
    ],
)
def test_statuses_that_need_evidence_require_it(base, status, message):
    base["entries"][0]["structural_status"] = status
    rejected(base, message)


def with_gap(inventory):
    """Append a valid synthetic expected_missing entry; return it."""
    gap = {
        **{key: None for key in inventory["entries"][0]},
        "entry_id": missing_entry_id_for(inventory["entry_id_prefix"], "100"),
        "document_id": inventory["document"]["doc_id"],
        "ordinal": len(inventory["entries"]) + 1,
        "kind": "article",
        "structural_status": "expected_missing",
        "review_status": "pending_human_review",
        "source_sha256": inventory["document"]["sha256"],
        "notes": ["Synthetic gap for the test."],
    }
    inventory["entries"].append(gap)
    return gap


def test_a_valid_expected_missing_entry_is_accepted(base):
    with_gap(base)
    validate_inventory(base, today=TODAY)


# V4: nothing about an expected_missing entry is printed.
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("page_start", 88),
        ("page_end", 88),
        ("title", "Disposizioni finali"),
        ("status_marker", "((ARTICOLO ABROGATO))"),
        ("parent_id", "gdpr-2016-679-oj-it:capo:XI"),
        ("parent_path", "CAPO XI"),
        ("label", "100"),
        ("heading_as_printed", "Articolo 100"),
    ],
)
def test_an_expected_missing_entry_carries_no_printed_information(base, field, value):
    gap = with_gap(base)
    gap[field] = value
    rejected(base, rf"an expected_missing entry is not printed, so \['{field}'\] must be null")


# V6: values of the wrong type are reported, never raised as TypeError.
@pytest.mark.parametrize(
    ("where", "field", "value"),
    [
        ("entries", "entry_id", ["gdpr-2016-679-oj-it:art:1"]),
        ("entries", "entry_id", 1),
        ("entries", "entry_id", None),
        ("entries", "entry_id", {"id": 1}),
        ("entries", "label", ["1"]),
        ("entries", "parent_id", ["gdpr-2016-679-oj-it:capo:I"]),
        ("entries", "parent_path", {"path": "CAPO I"}),
        ("entries", "structural_status", ["present"]),
        ("entries", "notes", "not a list"),
        ("divisions", "division_id", ["gdpr-2016-679-oj-it:capo:I"]),
        ("divisions", "parent_id", ["x"]),
        ("divisions", "label", 3),
    ],
)
def test_values_of_the_wrong_type_raise_inventory_error(base, where, field, value):
    base[where][0][field] = value
    with pytest.raises(InventoryError):
        validate_inventory(base, today=TODAY)


@pytest.mark.parametrize("bad", [None, [], "inventory", 3])
def test_a_non_object_inventory_raises_inventory_error(bad):
    with pytest.raises(InventoryError):
        validate_inventory(bad)


def test_malformed_nested_values_raise_inventory_error(base):
    base["entries"][0] = ["not", "an", "object"]
    base["divisions"] = {"not": "a list"}
    base["document"]["page_count"] = "88"
    with pytest.raises(InventoryError):
        validate_inventory(base, today=TODAY)
