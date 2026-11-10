"""Evidence assembly (src/evidence.py).

A synthetic act built from a synthetic PDF in tmp_path, with articles chosen to
exercise each rule:
- Art. 1: short, reviewed -> primary; refers to "articolo 2" (followed) and to
  "articolo 51 del regolamento" (another act: not followed);
- Art. 2: short, not reviewed -> internal_only; refers to "articolo 4" (a second hop:
  never followed from a reference);
- Art. 3: long (over 2,500 characters, pages 1-4), reviewed -> primary; numbered
  points "1)".."33)", point 12 being the only one about security;
- Art. 4: short, not reviewed -> internal_only.
Review data here is synthetic test data. The last test runs on the real recorded
build if it is present, and skips otherwise.
"""

import dataclasses

import pytest

from src.config import load_settings
from src.corpus_build import parse_spec, run_build
from src.corpus_identity import current_dependency_versions, file_sha256
from src.evidence import (
    WHOLE_PROVISION_MAX_CHARS,
    EvidenceError,
    EvidenceRequest,
    ProvisionRequest,
    _referenced_targets,
    assemble,
    estimate_tokens,
)
from src.provision_anchors import write_passage_links, write_segment_maps
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.provisions import (
    Instrument,
    ProvisionStore,
    Registry,
    SegmentationRules,
    SourceStatus,
    StructuralStatus,
    Tier,
    Version,
    eligibility,
    load_ledger,
    load_store,
)
from tests.test_provision_cli import CLEAN, REVIEW, V, prov

FILLER = "con parole di riempimento per la prova"
POINTS = [f"{n}) «termine {n}»: definizione del termine numero {n} {FILLER}." for n in range(1, 34)]
POINTS[11] = "12) «violazione dei dati»: la violazione di sicurezza che comporta la perdita dei dati."
PAGES = [
    ["HDR 1", "Titolo di prova", "Art. 1", "(Notifica)",
     "1. Il titolare notifica la violazione al Garante entro settantadue ore.",
     "2. Si applicano l'articolo 2 e l'articolo 51 del regolamento.",
     "Art. 2", "(Comunicazione)",
     "1. Il titolare comunica la violazione all'interessato ai sensi dell'articolo 4.",
     "Art. 3", "(Definizioni)", "Ai fini del presente atto si intende per:"],
    ["HDR 2", *POINTS[0:11]],
    ["HDR 3", *POINTS[11:22]],
    ["HDR 4", *POINTS[22:33]],
    ["HDR 5", "Art. 4", "(Registro)", "1) il titolare tiene un registro dei trattamenti svolti."],
]
ART = {label: f"{V}/body/article:{label}" for label in ("1", "2", "3", "4")}


def act_store(source_sha):
    rules = SegmentationRules((r"HDR \d+",), len(PAGES), (), None, None)
    version = Version(V, "x-act", "original_publication", "synthetic act", "it", None, None,
                      None, SourceStatus.NO_STATUS_REPRESENTATION, "inv.json", source_sha, rules)
    registry = Registry((Instrument("x-act", "regulation", "EU", ("prova",), None),),
                        (version,), "1" * 64)
    items = [
        prov("1", 1, status=StructuralStatus.AUTO_VERIFIED, review=REVIEW, title="(Notifica)"),
        prov("2", 1, title="(Comunicazione)"),
        dataclasses.replace(prov("3", 1, status=StructuralStatus.AUTO_VERIFIED, review=REVIEW,
                                 title="(Definizioni)"), page_end=4),
        prov("4", 5, title="(Registro)"),
    ]
    return ProvisionStore(registry, items, ())


@pytest.fixture
def explorer(tmp_path, write_pdf):
    pdf = write_pdf(tmp_path / "src" / "act.pdf", PAGES)
    spec = parse_spec({
        "schema_version": 1, "name": "x", "description": "x", "chunk_size": 1200,
        "chunk_overlap": 150, "assembly_format": "concatenated-jsonl/1",
        "sources": [{"version_id": V, "path": "src/act.pdf", "sha256": file_sha256(pdf),
                     "end_before": None}],
    }, "x.json")
    result = run_build(spec, detect_code=lambda: CLEAN, output_root=tmp_path / "builds",
                       recorded_root=tmp_path / "builds", base_dir=tmp_path,
                       dependencies=current_dependency_versions())
    store = act_store(file_sha256(pdf))
    write_segment_maps(result.directory, store=store, registry=store.registry,
                       detect_code=lambda: CLEAN)
    write_passage_links(result.directory, store=store, registry=store.registry)
    return ProvisionExplorer.open(result.directory, store=store)


def run(explorer, *queries, lookups=(), budget=3000, items=5, expand=True, top_k=5):
    request = EvidenceRequest(queries=tuple(queries), provisions=tuple(lookups), top_k=top_k,
                              expand_references=expand)
    return assemble(request, explorer, max_items=items, token_budget=budget)


def by_provision(evidence):
    return {item.provision_id: item for item in evidence.items}


def article_text(explorer, label):
    return "".join(p["text"] for p in explorer.lookup("prova", label)["provision"]["text"])


def source_slices(explorer, item):
    """The source text the item's anchors point at, read from the provision's pieces."""
    pieces = explorer.provision_view(explorer.store.get(item.provision_id))["text"]
    out = []
    for anchor in item.anchors:
        piece = next(p for p in pieces if p["char_start"] <= anchor.char_start
                     and anchor.char_end <= p["char_end"])
        out.append(piece["text"][anchor.char_start - piece["char_start"]:
                                 anchor.char_end - piece["char_start"]])
    return "".join(out)


# --- Identity, anchors and determinism -----------------------------------------------------


def test_evidence_ids_are_sequential_and_the_output_is_deterministic(explorer):
    first = run(explorer, "notifica violazione Garante", "sicurezza perdita dati",
                lookups=[ProvisionRequest("prova", "4")])
    second = run(explorer, "notifica violazione Garante", "sicurezza perdita dati",
                 lookups=[ProvisionRequest("prova", "4")])
    assert [i.evidence_id for i in first.items] == [f"E{n}" for n in
                                                    range(1, len(first.items) + 1)]
    assert first.to_dict() == second.to_dict()
    assert first.items[0].provision_id == ART["4"]  # exact lookups come first
    assert first.get("E1") is first.items[0]
    with pytest.raises(KeyError):
        first.get("E99")


def test_a_short_provision_is_included_whole_with_exact_anchors(explorer):
    evidence = run(explorer, "settantadue ore", expand=False)
    item = by_provision(evidence)[ART["1"]]
    assert len(article_text(explorer, "1")) <= WHOLE_PROVISION_MAX_CHARS
    assert item.whole_provision and item.point is None
    assert item.text == article_text(explorer, "1").strip()
    assert item.text.startswith("Art. 1") and "settantadue ore" in item.text
    assert source_slices(explorer, item) == item.text  # anchors point at exactly this text
    assert (item.page_start, item.page_end) == (1, 1)
    matched = {r["chunk_id"] for r in explorer.search("settantadue ore")["results"]
               if any(e["provision_id"] == ART["1"] for e in r["evidence"])}
    assert set(item.chunk_ids) == matched and item.chunk_ids
    assert item.origins == ("query:1",) and item.best_rank == 1


# --- Whole provision, matched span, point ---------------------------------------------------


def test_a_long_provision_contributes_its_matched_span(explorer):
    full = article_text(explorer, "3")
    assert len(full) > WHOLE_PROVISION_MAX_CHARS
    item = by_provision(run(explorer, "sicurezza perdita"))[ART["3"]]
    assert not item.whole_provision and item.point is None
    assert "12) «violazione dei dati»: la violazione di sicurezza" in item.text
    assert item.text in full and len(item.text) < len(full)
    start = full.index(item.text)
    assert start == 0 or full[start - 1] == "\n"  # widened to a line boundary
    end = start + len(item.text)
    assert end == len(full.rstrip()) or full[end] == "\n"
    assert source_slices(explorer, item) == item.text
    assert len(item.anchors) >= 1 and item.chunk_ids


def test_a_point_lookup_returns_exactly_that_point(explorer):
    evidence = run(explorer, lookups=[ProvisionRequest("prova", "3", point="12")], expand=False)
    (item,) = evidence.items
    assert item.text == POINTS[11]
    assert item.point == "12" and not item.whole_provision
    assert item.origins == ("lookup",) and item.chunk_ids == () and item.best_rank is None
    assert source_slices(explorer, item) == item.text
    assert (item.page_start, item.page_end) == (3, 3)


def test_a_point_of_a_short_provision_gives_the_whole_provision(explorer):
    evidence = run(explorer, lookups=[ProvisionRequest("prova", "4", point="1")], expand=False)
    (item,) = evidence.items
    assert item.whole_provision and item.point is None
    assert item.text == article_text(explorer, "4").strip()


@pytest.mark.parametrize(("lookup", "warning"), [
    (ProvisionRequest("prova", "3", point="99"), "point_not_found"),
    (ProvisionRequest("prova", "99"), "lookup_not_found"),
    (ProvisionRequest("unknown-act", "1"), "lookup_not_found"),
])
def test_failed_lookups_are_reported_not_guessed(explorer, lookup, warning):
    evidence = run(explorer, lookups=[lookup])
    assert evidence.is_empty
    assert any(w.startswith(warning) for w in evidence.warnings)
    assert "no_evidence" in evidence.warnings


# --- Cross-references ----------------------------------------------------------------------


def test_explicit_references_are_followed_one_hop_within_the_instrument(explorer):
    evidence = run(explorer, "settantadue ore")
    found = by_provision(evidence)
    assert list(found) == [ART["1"], ART["2"]]
    assert found[ART["2"]].origins == (f"reference:{ART['1']}",)
    assert found[ART["2"]].chunk_ids == () and found[ART["2"]].best_rank is None
    assert ART["4"] not in found  # Art. 2 -> Art. 4 would be a second hop
    assert not any("51" in w for w in evidence.warnings)  # "del regolamento": another act


GDPR_ID, CODE_ID = "eu-reg-2016-679", "it-dlgs-2003-196"


@pytest.mark.parametrize(("text", "instrument", "targets"), [
    # In an act with no special rules (the synthetic act): unnamed references stay in it.
    ("competente a norma dell'articolo 55 senza ingiustificato ritardo", "x-act",
     [("x-act", "55")]),
    ("dell'articolo 6, paragrafo 1, lettera c) o e). In tal caso, non si applica l'articolo 56.",
     "x-act", [("x-act", "6"), ("x-act", "56")]),
    ("di cui agli articoli 33 e 34, e all'articolo 2-quater del presente codice", "x-act",
     [("x-act", "33"), ("x-act", "34"), ("x-act", "2-quater")]),
    ("di cui all'articolo 51 del regolamento è individuata", "x-act", []),  # which regulation?
    ("all'articolo 1, paragrafo 1, lettera b), della direttiva (UE) 2015/1535", "x-act", []),
    ("si applicano l'articolo 2 e l'articolo 51 del regolamento", "x-act", [("x-act", "2")]),
    ("nessun riferimento", "x-act", []),
    # In the Privacy Code, «Regolamento» is the GDPR (Code Art. 1): a cross-instrument target.
    ("di cui all'articolo 51 del regolamento è individuata nel Garante, di cui all'articolo "
     "153.", CODE_ID, [(GDPR_ID, "51"), (CODE_ID, "153")]),
    ("ai sensi dell'articolo 2 del decreto legislativo 10 agosto 2018, n. 101", CODE_ID, []),
    ("l'articolo 40 sui codici di condotta", GDPR_ID, [(GDPR_ID, "40")]),  # not the Code
])
def test_reference_targets(text, instrument, targets):
    assert _referenced_targets(text, instrument) == targets


def test_cross_instrument_references_can_be_switched_off():
    text = "di cui all'articolo 51 del regolamento, di cui all'articolo 153."
    assert _referenced_targets(text, CODE_ID, cross_instrument=False) == [(CODE_ID, "153")]


def test_references_can_be_switched_off(explorer):
    assert list(by_provision(run(explorer, "settantadue ore", expand=False))) == [ART["1"]]


def test_a_reference_to_an_item_already_present_only_adds_its_origin(explorer):
    evidence = run(explorer, "settantadue ore", "comunica interessato")
    found = by_provision(evidence)
    assert found[ART["2"]].origins == ("query:2", f"reference:{ART['1']}")
    assert len(evidence.items) == len(set(found))


# --- Limits --------------------------------------------------------------------------------


def test_max_items_is_respected_and_the_rest_is_reported(explorer):
    evidence = run(explorer, "settantadue ore", "sicurezza perdita", items=1)
    assert [i.provision_id for i in evidence.items] == [ART["1"]]
    assert {d.provision_id for d in evidence.dropped} >= {ART["3"], ART["2"]}
    assert {d.reason for d in evidence.dropped} == {"max_items"}


def test_the_token_budget_is_respected_and_smaller_items_still_fit(explorer):
    art1 = estimate_tokens(article_text(explorer, "1").strip())
    evidence = run(explorer, "sicurezza perdita", "settantadue ore", budget=art1 + 5,
                   expand=False)
    assert [i.provision_id for i in evidence.items] == [ART["1"]]
    assert [(d.provision_id, d.reason) for d in evidence.dropped] == [(ART["3"], "token_budget")]
    assert evidence.total_tokens <= evidence.token_budget


def test_limits_default_to_the_settings(explorer):
    settings = load_settings({"FINAL_EVIDENCE_COUNT": "2", "CONTEXT_TOKEN_BUDGET": "4000"})
    evidence = assemble(EvidenceRequest(queries=("settantadue ore",)), explorer,
                        settings=settings)
    assert (evidence.max_items, evidence.token_budget) == (2, 4000)


@pytest.mark.parametrize(("kwargs", "message"), [
    ({"max_items": 0}, "max_items"),
    ({"token_budget": 0}, "token_budget"),
    ({"request": EvidenceRequest(queries=("ok",), top_k=0)}, "top_k"),
    ({"request": EvidenceRequest(queries=("  ",))}, "queries"),
])
def test_invalid_requests_are_refused(explorer, kwargs, message):
    args = {"request": EvidenceRequest(queries=("ok",)), "max_items": 5, "token_budget": 100}
    args.update(kwargs)
    with pytest.raises(EvidenceError, match=message):
        assemble(args["request"], explorer, max_items=args["max_items"],
                 token_budget=args["token_budget"])


# --- Eligibility ---------------------------------------------------------------------------


def test_tier_reasons_and_qualifications_come_from_the_provision_store(explorer):
    evidence = run(explorer, "settantadue ore", "sicurezza perdita", "registro trattamenti")
    found = by_provision(evidence)
    assert set(found) == set(ART.values())
    for item in evidence.items:
        provision = explorer.store.get(item.provision_id)
        expected = eligibility(provision, explorer.store.registry.version(provision.version_id),
                               anchored=True)
        assert item.tier == expected.tier.value
        assert item.reasons == expected.reasons
        assert item.qualifications == expected.qualifications
        assert item.citable is (expected.tier == Tier.PRIMARY)
        assert item.legal_validity == "not_established"
    assert {pid for pid, i in found.items() if i.citable} == {ART["1"], ART["3"]}
    assert found[ART["2"]].reasons == ("structure_not_reviewed",)


def test_internal_only_evidence_is_kept_but_never_citable(explorer):
    evidence = run(explorer, "registro trattamenti")
    (item,) = evidence.items
    assert item.provision_id == ART["4"] and item.best_rank == 1  # ranked first ...
    assert item.tier == Tier.INTERNAL_ONLY.value and not item.citable  # ... still not citable
    assert not evidence.has_citable_evidence and evidence.citable_items == ()
    assert "no_citable_evidence" in evidence.warnings


def test_empty_retrieval_gives_an_empty_set(explorer):
    evidence = run(explorer, "blockchain criptovalute")
    assert evidence.is_empty and evidence.items == () and evidence.dropped == ()
    assert evidence.warnings == ("no_evidence",)
    assert not evidence.has_citable_evidence and evidence.total_tokens == 0


def test_the_set_serialises_to_plain_data(explorer):
    data = run(explorer, "settantadue ore").to_dict()
    assert data["items"][0]["evidence_id"] == "E1"
    assert {"page_start", "page_end", "anchors", "citable", "tier"} <= set(data["items"][0])
    assert data["has_citable_evidence"] is True


# --- The demonstration question on the real recorded build ------------------------------------

DEMO = EvidenceRequest(
    queries=(
        "notifica di una violazione dei dati personali all'autorità di controllo",
        "comunicazione di una violazione dei dati personali all'interessato",
        "autorità di controllo competente",
        "Garante per la protezione dei dati personali autorità di controllo",
    ),
    provisions=(ProvisionRequest("gdpr", "4", point="12"),),
)
GDPR = "eu-reg-2016-679@oj-l119-2016-it/body/article:"
CODICE = "it-dlgs-2003-196@transcription-vigente-2026-11-05/body/article:"


@pytest.fixture(scope="module")
def real_explorer():
    try:
        return ProvisionExplorer.open(find_recorded_build())
    except ExplorerError as exc:
        pytest.skip(f"recorded build unavailable: {exc}")


def test_code_2_bis_expands_across_instruments_to_gdpr_51(real_explorer):
    request = EvidenceRequest(provisions=(ProvisionRequest("codice privacy", "2-bis"),))
    evidence = assemble(request, real_explorer, max_items=5, token_budget=3000)
    found = by_provision(evidence)
    assert list(found)[0] == CODICE + "2-bis"  # the requested provision comes first
    gdpr51 = found[GDPR + "51"]
    assert gdpr51.instrument_id == "eu-reg-2016-679"  # the target keeps its instrument...
    assert gdpr51.origins == (f"reference:{CODICE}2-bis",)  # ...and records its source
    assert CODICE + "153" in found  # the unnamed reference stays in the Code
    without = assemble(dataclasses.replace(request, cross_instrument=False), real_explorer,
                       max_items=5, token_budget=3000)
    assert GDPR + "51" not in by_provision(without) and CODICE + "153" in by_provision(without)


def test_cross_instrument_expansion_is_bounded_and_displaces_nothing(real_explorer):
    requested = (ProvisionRequest("codice privacy", "2-bis"), ProvisionRequest("gdpr", "33"))
    evidence = assemble(EvidenceRequest(provisions=requested), real_explorer, max_items=2,
                        token_budget=3000)
    assert [i.provision_id for i in evidence.items] == [CODICE + "2-bis", GDPR + "33"]
    dropped = {d.provision_id: d.reason for d in evidence.dropped}
    assert dropped[GDPR + "51"] == dropped[GDPR + "55"] == "max_items"
    assert len(evidence.dropped) == len(dropped)  # one entry per provision, no duplicates
    # The token budget bounds references the same way.
    tight = assemble(EvidenceRequest(provisions=requested[:1]), real_explorer, max_items=5,
                     token_budget=100)
    assert [i.provision_id for i in tight.items] == [CODICE + "2-bis"]
    assert {d.provision_id: d.reason for d in tight.dropped}[GDPR + "51"] == "token_budget"


def expanded(explorer, instrument, label):
    """Every provision the lookup brings in, selected or dropped (room for all of them)."""
    evidence = assemble(EvidenceRequest(provisions=(ProvisionRequest(instrument, label),)),
                        explorer, max_items=30, token_budget=50000)
    return {i.provision_id for i in evidence.items} | {d.provision_id for d in evidence.dropped}


def test_gdpr_40_does_not_expand_to_the_privacy_code(real_explorer):
    # "l'organismo di cui all'articolo 41 ... le norme del codice": a code of conduct.
    found = expanded(real_explorer, "gdpr", "40")
    assert CODICE + "41" not in found and GDPR + "41" in found
    assert not any(pid.startswith("it-dlgs-2003-196@") for pid in found)


def test_code_120_does_not_expand_to_its_own_article_135(real_explorer):
    # "l'articolo 135 del codice delle assicurazioni private": another code.
    assert expanded(real_explorer, "codice privacy", "120") == {CODICE + "120"}


def test_the_demonstration_evidence_on_the_recorded_build(real_explorer):
    evidence = assemble(DEMO, real_explorer, max_items=5, token_budget=3000)
    found = by_provision(evidence)
    assert set(found) == {GDPR + "4", GDPR + "33", GDPR + "34", GDPR + "55", CODICE + "2-bis"}
    art4 = found[GDPR + "4"]
    assert art4.point == "12" and not art4.whole_provision
    assert art4.text.startswith("12) «violazione dei dati personali»")
    for label in ("33", "34", "55"):
        assert found[GDPR + label].whole_provision
    dropped_ids = [d.provision_id for d in evidence.dropped]
    assert len(dropped_ids) == len(set(dropped_ids))  # one entry per provision
    assert not set(dropped_ids) & set(found)
    store = load_store()
    for item in evidence.items:  # tiers as the store computes them today, whatever they are
        provision = store.get(item.provision_id)
        tier = eligibility(provision, store.registry.version(provision.version_id),
                           anchored=True).tier
        assert item.tier == tier.value and item.citable is (tier == Tier.PRIMARY)
    art2bis = found[CODICE + "2-bis"]
    assert not art2bis.citable and art2bis.tier != Tier.PRIMARY.value
    assert {"unofficial_transcription", "legal_validity_not_established"} <= set(
        art2bis.qualifications)
    if not load_ledger():  # nothing reviewed yet: nothing in the set may be citable
        assert not evidence.has_citable_evidence
        assert "no_citable_evidence" in evidence.warnings
    assert assemble(DEMO, real_explorer, max_items=5, token_budget=3000).to_dict() == \
        evidence.to_dict()
