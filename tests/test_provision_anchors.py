"""Segment maps and passage links (src/provision_anchors.py).

Synthetic text, provisions and chunks only; the end-to-end tests build synthetic
PDFs in tmp_path. Every rule is tested on its failure as well as its success.
"""

import dataclasses
import json
import unicodedata

import pytest

import src.provision_anchors as anchors
from src.corpus_build import parse_spec, run_build
from src.corpus_identity import (
    CodeVersion,
    IngestionVariant,
    current_dependency_versions,
    file_sha256,
)
from src.ingestion import PAGE_SEPARATOR
from src.models import LegalChunk, SourceLocation
from src.provision_anchors import (
    AnchorError,
    SegmentMap,
    build_segment_map,
    check_segment_map,
    expected_chunk_id,
    link_chunks,
    links_path,
    load_segment_map,
    locate_chunks,
    segment_map_path,
    segment_text,
    structure_sha256,
    write_passage_links,
    write_segment_maps,
)
from src.provisions import (
    EditorialNoteRule,
    FootnoteRule,
    Instrument,
    Marker,
    Provision,
    ProvisionStore,
    Registry,
    Review,
    SegmentationRules,
    SourceStatus,
    StructuralStatus,
    Version,
)

V = "x-act@v1"
CLEAN = CodeVersion.clean("e" * 40)


def page_texts(pages):
    return ["\n\n".join(lines) for lines in pages]


def document(pages):
    """Content and page offsets exactly as src.ingestion builds them."""
    texts = page_texts(pages)
    starts, offset = [], 0
    for text in texts:
        starts.append(offset)
        offset += len(text) + len(PAGE_SEPARATOR)
    return PAGE_SEPARATOR.join(texts), tuple(starts)


def prov(label, heading, page, kind="article", parent=None, title="t", review="pending"):
    pid = f"{V}/body/article:{label}" if kind == "article" else f"{V}/body/{label}"
    return Provision(
        provision_id=pid, version_id=V, instrument_id="x-act", kind=kind,
        label_as_printed=label, normalised_label=label, heading_as_printed=heading,
        title=title, status_marker=None, parent_id=parent, path=heading,
        page_start=page, page_end=page,
        structural_status=StructuralStatus.AUTO_UNREVIEWED,
        review=Review("pending_human_review" if review == "pending" else "reviewed"),
        source_status_representation=SourceStatus.NO_STATUS_REPRESENTATION,
        inventory_id="inv", inventory_ref=label, inventory_sha256="0" * 64,
        source_sha256="a" * 64, doc_id="doc-aaaaaaaaaaaaaaaa", notes=(),
    )


# A GDPR-like act: title, preamble, recitals, enacting formula, two chapters,
# a footnote inside Article 1, running headers on both pages, a closing formula.
GDPR_PAGES = [
    ["HDR 1", "REGOLAMENTO DI PROVA", "IL PARLAMENTO E IL CONSIGLIO,", "visto il trattato,",
     "considerando quanto segue:", "(1)", "Primo considerando.",
     "(2) Secondo considerando con un numero all'inizio.",
     "HANNO ADOTTATO IL PRESENTE REGOLAMENTO:", "CAPO I", "Disposizioni generali",
     "Articolo 1", "Oggetto", "1.", "Testo dell'articolo uno che continua"],
    ["HDR 2", "sulla pagina seguente.", "(1) Direttiva di prova (GU L 1 del 1.1.2000,",
     "pag. 3).", "Articolo 2", "Ambito", "Testo due.", "CAPO II", "Disposizioni finali",
     "Articolo 3", "Entrata in vigore", "Testo tre.",
     "Il presente regolamento è obbligatorio in tutti i suoi elementi.", "Fatto a Bruxelles"],
]
GDPR_RULES = SegmentationRules(
    furniture_patterns=(r"HDR \d+",),
    furniture_expected_lines=2,
    markers=(
        Marker("preamble", "IL PARLAMENTO E IL CONSIGLIO,"),
        Marker("recitals", "considerando quanto segue:"),
        Marker("enacting_formula", "HANNO ADOTTATO IL PRESENTE REGOLAMENTO:"),
        Marker("closing_formula", "Il presente regolamento è obbligatorio"),
    ),
    editorial_notes=None,
    footnotes=FootnoteRule(r"\(\d+\) ", r"pag\. \d+\)\.", 200, 1),
)


def gdpr_provisions():
    capo_i = prov("chapter:i", "CAPO I", 1, kind="chapter")
    capo_ii = prov("chapter:ii", "CAPO II", 2, kind="chapter")
    articles = [
        prov("1", "Articolo 1", 1, parent=capo_i.provision_id),
        prov("2", "Articolo 2", 2, parent=capo_i.provision_id),
        prov("3", "Articolo 3", 2, parent=capo_ii.provision_id),
    ]
    return articles, [capo_i, capo_ii]


# A Privacy-Code-like act: headings marked '((', an editorial note split by a page
# break, a repealed article, a closing formula.
CODICE_PAGES = [
    ["D.Lgs. prova", "Pagina 1", "DECRETO DI PROVA", "PARTE I", "DISPOSIZIONI", "CAPO I",
     "(OGGETTO)", "IL PRESIDENTE DELLA REPUBBLICA", "EMANA il seguente decreto:",
     "Art. 1", "(( (Oggetto). ))", "1. Testo.", "--------------", "AGGIORNAMENTO (1)",
     "Una nota editoriale che"],
    ["D.Lgs. prova", "Pagina 2", "continua.", "(( CAPO II", "(PRINCIPI) ))", "Art. 2",
     "((ARTICOLO ABROGATO))", "Il presente decreto, munito del sigillo dello Stato.",
     "Visto, il Guardasigilli"],
]
CODICE_RULES = SegmentationRules(
    furniture_patterns=(r"D\.Lgs\. prova", r"Pagina \d+"),
    furniture_expected_lines=4,
    markers=(
        Marker("enacting_formula", "IL PRESIDENTE DELLA REPUBBLICA"),
        Marker("closing_formula", "Il presente decreto, munito del sigillo dello Stato"),
    ),
    editorial_notes=EditorialNoteRule(r"-{10,}", r"AGGIORNAMENTO \(\d+\)", 1),
    footnotes=None,
)


def codice_provisions():
    parte = prov("part:i", "PARTE I", 1, kind="part")
    capo_i = prov("part:i/chapter:i", "CAPO I", 1, kind="chapter", parent=parte.provision_id)
    capo_ii = prov("part:i/chapter:ii", "(( CAPO II", 2, kind="chapter",
                   parent=parte.provision_id)
    articles = [prov("1", "Art. 1", 1, parent=capo_i.provision_id),
                prov("2", "Art. 2", 2, parent=capo_ii.provision_id)]
    return articles, [parte, capo_i, capo_ii]


def segments_for(pages, rules, provisions):
    content, starts = document(pages)
    articles, divisions = provisions
    return content, segment_text(content, starts, rules, articles, divisions)


def kinds_text(segments, kind):
    return [s.text for s in segments if s.kind == kind]


# --- Segmentation ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", ["gdpr", "codice"])
def test_segments_cover_the_text_exactly_once(case):
    pages, rules, provs = (GDPR_PAGES, GDPR_RULES, gdpr_provisions()) if case == "gdpr" else (
        CODICE_PAGES, CODICE_RULES, codice_provisions())
    content, segments = segments_for(pages, rules, provs)
    assert segments[0].char_start == 0 and segments[-1].char_end == len(content)
    for a, b in zip(segments, segments[1:]):
        assert a.char_end == b.char_start
    assert "".join(s.text for s in segments) == content
    assert [s.index for s in segments] == list(range(len(segments)))


def test_gdpr_like_regions_are_told_apart():
    content, segments = segments_for(GDPR_PAGES, GDPR_RULES, gdpr_provisions())
    assert kinds_text(segments, "front_matter") == ["REGOLAMENTO DI PROVA\n\n"]
    assert kinds_text(segments, "preamble")[0].startswith("IL PARLAMENTO E IL CONSIGLIO,")
    recitals = "".join(kinds_text(segments, "recitals"))
    assert recitals.startswith("considerando quanto segue:")
    # A recital that starts with "(n) " is not a footnote: footnotes exist only in articles.
    assert "(2) Secondo considerando" in recitals
    assert kinds_text(segments, "enacting_formula") == [
        "HANNO ADOTTATO IL PRESENTE REGOLAMENTO:\n\n"
    ]
    closing = kinds_text(segments, "closing_formula")
    assert len(closing) == 1 and closing[0].endswith("Fatto a Bruxelles")
    assert [s.provision_id for s in segments if s.kind == "division_heading"] == [
        f"{V}/body/chapter:i", f"{V}/body/chapter:ii"
    ]


def test_articles_hold_only_their_own_text():
    content, segments = segments_for(GDPR_PAGES, GDPR_RULES, gdpr_provisions())
    by_article = {}
    for s in segments:
        if s.kind == "article":
            by_article.setdefault(s.provision_id, []).append(s.text)
    one = by_article[f"{V}/body/article:1"]
    # Interrupted by the running header and the footnote: two pieces, neither containing them.
    assert len(one) == 2 and one[0].startswith("Articolo 1\n\nOggetto")
    assert one[1] == "sulla pagina seguente.\n\n"
    text = "".join("".join(t) for t in by_article.values())
    assert "HDR" not in text and "Direttiva di prova" not in text and "CAPO II" not in text
    assert "".join(by_article[f"{V}/body/article:3"]).endswith("Testo tre.\n\n")


def test_footnotes_and_running_headers_are_separate_segments():
    content, segments = segments_for(GDPR_PAGES, GDPR_RULES, gdpr_provisions())
    (footnote,) = [s for s in segments if s.kind == "footnote"]
    assert footnote.text.startswith("(1) Direttiva di prova") and "pag. 3)." in footnote.text
    assert footnote.provision_id == f"{V}/body/article:1"  # context of its article
    furniture = [s for s in segments if s.kind == "page_furniture"]
    assert [s.text.strip() for s in furniture] == ["HDR 1", "HDR 2"]
    assert all(s.provision_id is None for s in furniture)
    assert [s.page for s in furniture] == [1, 2]


def test_editorial_notes_division_headings_and_repealed_articles():
    content, segments = segments_for(CODICE_PAGES, CODICE_RULES, codice_provisions())
    notes = [s for s in segments if s.kind == "editorial_note"]
    # One note, interrupted by the running header of page 2.
    assert [s.text for s in notes] == [
        "--------------\n\nAGGIORNAMENTO (1)\n\nUna nota editoriale che\n\n", "continua.\n\n"
    ]
    assert {s.provision_id for s in notes} == {f"{V}/body/article:1"}
    articles = {s.provision_id: s.text for s in segments if s.kind == "article"}
    assert articles[f"{V}/body/article:1"] == "Art. 1\n\n(( (Oggetto). ))\n\n1. Testo.\n\n"
    assert articles[f"{V}/body/article:2"] == "Art. 2\n\n((ARTICOLO ABROGATO))\n\n"
    capo_ii = [s for s in segments if s.provision_id == f"{V}/body/part:i/chapter:ii"]
    assert [s.text for s in capo_ii] == ["(( CAPO II\n\n(PRINCIPI) ))\n\n"]
    assert kinds_text(segments, "enacting_formula")[0].startswith("IL PRESIDENTE")
    division = [s for s in segments if s.kind == "division_heading"]
    assert division[1].text == "CAPO I\n\n(OGGETTO)\n\n"  # ends where the enacting formula starts


def test_a_heading_repeated_on_its_page_is_placed_by_source_order():
    pages = [["HDR 1", "PARTE I", "CAPO I", "Art. 1", "uno", "PARTE II", "CAPO I", "Art. 2",
              "due"]]
    parts = [prov("part:i", "PARTE I", 1, "part"), prov("part:ii", "PARTE II", 1, "part")]
    capi = [prov("part:i/chapter:i", "CAPO I", 1, "chapter", parts[0].provision_id),
            prov("part:ii/chapter:i", "CAPO I", 1, "chapter", parts[1].provision_id)]
    articles = [prov("1", "Art. 1", 1, parent=capi[0].provision_id),
                prov("2", "Art. 2", 1, parent=capi[1].provision_id)]
    rules = dataclasses.replace(CODICE_RULES, furniture_patterns=(r"HDR \d+",),
                                furniture_expected_lines=1, markers=(), editorial_notes=None)
    content, segments = segments_for(pages, rules, (articles, [parts[0], capi[0], parts[1],
                                                              capi[1]]))
    headings = [(s.provision_id.split("/body/")[1], s.text.split("\n")[0])
                for s in segments if s.kind == "division_heading"]
    assert headings == [("part:i", "PARTE I"), ("part:i/chapter:i", "CAPO I"),
                        ("part:ii", "PARTE II"), ("part:ii/chapter:i", "CAPO I")]


def test_a_repeated_heading_that_the_order_does_not_decide_fails():
    # Two "CAPO I" lines, but only one CAPO I division and nothing else to fix its line.
    pages = [["HDR 1", "CAPO I", "Art. 1", "uno", "CAPO I", "Art. 2", "due"]]
    capo = prov("chapter:i", "CAPO I", 1, "chapter")
    articles = [prov("1", "Art. 1", 1), prov("2", "Art. 2", 1)]
    rules = dataclasses.replace(CODICE_RULES, furniture_patterns=(r"HDR \d+",),
                                furniture_expected_lines=1, markers=(), editorial_notes=None)
    with pytest.raises(AnchorError, match="source order does not decide"):
        segments_for(pages, rules, (articles, [capo]))


def mutate_pages(pages, page, index, value):
    copy = [list(p) for p in pages]
    if value is None:
        del copy[page][index]
    else:
        copy[page][index] = value
    return copy


@pytest.mark.parametrize(
    ("pages", "rules", "message"),
    [
        (GDPR_PAGES, dataclasses.replace(GDPR_RULES, furniture_expected_lines=3),
         "expected 3 running-header lines, found 2"),
        (GDPR_PAGES, dataclasses.replace(
            GDPR_RULES, footnotes=FootnoteRule(r"\(\d+\) ", r"pag\. \d+\)\.", 200, 2)),
         "expected 2 footnotes, found 1"),
        (GDPR_PAGES, dataclasses.replace(
            GDPR_RULES, footnotes=FootnoteRule(r"\(\d+\) ", r"pag\. \d+\)\.", 20, 1)),
         "has no end within 20 characters"),
        (mutate_pages(GDPR_PAGES, 0, 4, "considerando:"), GDPR_RULES,
         "recitals: expected exactly one line"),
        (mutate_pages(GDPR_PAGES, 0, 3, "considerando quanto segue: (bis)"), GDPR_RULES,
         "recitals: expected exactly one line .* found 2"),
        (GDPR_PAGES, dataclasses.replace(  # "Testo due." comes before Articolo 3
            GDPR_RULES, markers=GDPR_RULES.markers[:3] + (Marker("closing_formula", "Testo due."),
                                                         )), "not after the last heading"),
        (mutate_pages(GDPR_PAGES, 0, 8, "HANNO ADOTTATO"), GDPR_RULES,
         "enacting_formula: expected exactly one line"),
        (mutate_pages(GDPR_PAGES, 1, 4, "Art. 2"), GDPR_RULES,
         "is not printed as a line on page 2"),
    ],
)
def test_unexpected_gdpr_like_structure_fails(pages, rules, message):
    with pytest.raises(AnchorError, match=message):
        segments_for(pages, rules, gdpr_provisions())


def test_a_marker_in_the_wrong_place_fails():
    rules = dataclasses.replace(GDPR_RULES, markers=(
        Marker("preamble", "IL PARLAMENTO E IL CONSIGLIO,"),
        Marker("recitals", "Testo due."),  # after the first article heading
    ))
    with pytest.raises(AnchorError, match="recitals is not before the first article heading"):
        segments_for(GDPR_PAGES, rules, gdpr_provisions())


def test_a_heading_on_another_page_fails():
    articles, divisions = gdpr_provisions()
    articles[1] = dataclasses.replace(articles[1], page_start=1)
    with pytest.raises(AnchorError, match="not printed as a line on page 1"):
        segments_for(GDPR_PAGES, GDPR_RULES, (articles, divisions))


def test_headings_out_of_order_fail():
    articles, divisions = gdpr_provisions()
    with pytest.raises(AnchorError, match="cannot (follow|precede)"):
        segments_for(GDPR_PAGES, GDPR_RULES, ([articles[0], articles[2], articles[1]],
                                              divisions))


def test_an_article_before_its_parent_division_fails():
    articles, divisions = gdpr_provisions()
    articles[0] = dataclasses.replace(articles[0], parent_id=divisions[1].provision_id)
    with pytest.raises(AnchorError, match="printed before its parent division"):
        segments_for(GDPR_PAGES, GDPR_RULES, (articles, divisions))


@pytest.mark.parametrize(
    ("page", "index", "value", "message"),
    [
        (0, 13, "Nota senza etichetta", "not followed by a note label"),  # label replaced
        (0, 12, "Testo normale", "has no separator line before it"),  # separator replaced
    ],
)
def test_malformed_editorial_notes_fail(page, index, value, message):
    with pytest.raises(AnchorError, match=message):
        segments_for(mutate_pages(CODICE_PAGES, page, index, value), CODICE_RULES,
                     codice_provisions())


def test_an_editorial_note_outside_an_article_fails():
    pages = [list(CODICE_PAGES[0]), list(CODICE_PAGES[1])]
    pages[0][7:7] = ["--------------", "AGGIORNAMENTO (9)"]  # before Art. 1
    rules = dataclasses.replace(CODICE_RULES, editorial_notes=EditorialNoteRule(
        r"-{10,}", r"AGGIORNAMENTO \(\d+\)", 2))
    with pytest.raises(AnchorError, match="is not inside an article"):
        segments_for(pages, rules, codice_provisions())


def test_the_expected_number_of_editorial_notes_is_enforced():
    rules = dataclasses.replace(CODICE_RULES, editorial_notes=EditorialNoteRule(
        r"-{10,}", r"AGGIORNAMENTO \(\d+\)", 2))
    with pytest.raises(AnchorError, match="expected 2 editorial notes, found 1"):
        segments_for(CODICE_PAGES, rules, codice_provisions())


def test_unpaginated_text_is_refused():
    articles, divisions = gdpr_provisions()
    with pytest.raises(AnchorError, match="paginated"):
        segment_text("Articolo 1", (), GDPR_RULES, articles, divisions)


# --- Provenance and staleness ----------------------------------------------------------------


def make_variant(**overrides):
    values = dict(source_sha256="a" * 64, reader="pdf", metadata_sha256=None, chunk_size=1200,
                  chunk_overlap=150, code=CLEAN,
                  dependencies={"pymupdf": "1.28.2", "python": "CPython 3.13.2"})
    values.update(overrides)
    return IngestionVariant(**values)


def make_registry(rules, sha="1" * 64, source_sha="a" * 64):
    version = Version(V, "x-act", "original_publication", "synthetic", "it", None, None, None,
                      SourceStatus.NO_STATUS_REPRESENTATION, "inv.json", source_sha, rules)
    instrument = Instrument("x-act", "regulation", "EU", ("x",), None)
    return Registry((instrument,), (version,), sha)


def gdpr_map(variant=None, registry=None, provisions=None):
    content, starts = document(GDPR_PAGES)
    articles, divisions = provisions or gdpr_provisions()
    registry = registry or make_registry(GDPR_RULES)
    store = ProvisionStore(registry, [*divisions, *articles], ())
    return build_segment_map(content, starts, variant=variant or make_variant(),
                             version=registry.versions[0], store=store, registry=registry,
                             build_id="build-1")


def check(segment_map, variant=None, structure=None, registry_sha="1" * 64, build_id="build-1"):
    articles, divisions = gdpr_provisions()
    check_segment_map(segment_map, variant=variant or make_variant(), build_id=build_id,
                      structure=structure or structure_sha256([*articles, *divisions]),
                      registry_sha256=registry_sha)


def test_a_current_map_passes_and_round_trips():
    segment_map = gdpr_map()
    check(segment_map)
    again = SegmentMap.from_record(json.loads(json.dumps(segment_map.to_record())))
    assert again == segment_map and again.content == document(GDPR_PAGES)[0]


@pytest.mark.parametrize(
    ("variant", "message"),
    [
        (make_variant(source_sha256="b" * 64), "extraction source_sha256 differs"),
        (make_variant(code=CodeVersion.clean("1" * 40)), "extraction code differs"),
        (make_variant(code=CodeVersion.dirty("e" * 40, "f" * 64)), "extraction code differs"),
        (make_variant(dependencies={"pymupdf": "1.28.3", "python": "CPython 3.13.2"}),
         "extraction dependencies differs"),
        (make_variant(end_before="ALLEGATO A.1"), "extraction end_before differs"),
        (make_variant(reader="txt"), "extraction reader differs"),
    ],
)
def test_a_changed_extraction_makes_the_map_stale(variant, message):
    with pytest.raises(AnchorError, match=message):
        check(gdpr_map(), variant=variant)


def test_a_changed_extraction_configuration_makes_the_map_stale():
    segment_map = gdpr_map()
    changed = dataclasses.replace(segment_map, extraction=dataclasses.replace(
        segment_map.extraction, page_separator="\n"))
    with pytest.raises(AnchorError, match="extraction page_separator differs"):
        check(changed)


def test_a_changed_document_identity_makes_the_map_stale():
    segment_map = gdpr_map()
    changed = dataclasses.replace(segment_map, extraction=dataclasses.replace(
        segment_map.extraction, doc_id="doc-bbbbbbbbbbbbbbbb"))
    with pytest.raises(AnchorError, match="extraction doc_id differs"):
        check(changed)


def test_changed_content_is_detected():
    record = gdpr_map().to_record()
    record["segments"][3]["text"] = record["segments"][3]["text"].replace("o", "0", 1)
    with pytest.raises(AnchorError, match="text does not match text_sha256"):
        SegmentMap.from_record(record)
    record = gdpr_map().to_record()
    record["content_sha256"] = "0" * 64
    with pytest.raises(AnchorError, match="does not match content_sha256"):
        SegmentMap.from_record(record)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda r: r["segments"].pop(2), "not contiguous"),
        (lambda r: r["segments"][1].update(kind="unknown"), "unknown kind"),
        (lambda r: r["segments"][1].update(page=2), "pages do not match"),
        (lambda r: r.update(content_length=r["content_length"] + 1), "do not cover the whole"),
        (lambda r: r.pop("registry_sha256"), "unexpected or missing keys"),
    ],
)
def test_a_damaged_map_is_refused(mutate, message):
    record = gdpr_map().to_record()
    mutate(record)
    with pytest.raises(AnchorError, match=message):
        SegmentMap.from_record(record)


def test_a_changed_inventory_structure_makes_the_map_stale():
    articles, divisions = gdpr_provisions()
    relabelled = [dataclasses.replace(articles[0], provision_id=f"{V}/body/article:1-bis"),
                  *articles[1:]]
    with pytest.raises(AnchorError, match="inventory structure"):
        check(gdpr_map(), structure=structure_sha256([*relabelled, *divisions]))


def test_a_changed_registry_makes_the_map_stale():
    with pytest.raises(AnchorError, match="instrument registry changed"):
        check(gdpr_map(), registry_sha="2" * 64)


def test_another_build_or_variant_is_refused():
    with pytest.raises(AnchorError, match="build build-1 is not build-2"):
        check(gdpr_map(), build_id="build-2")
    with pytest.raises(AnchorError, match="variant .* is not"):
        check(gdpr_map(), variant=make_variant(chunk_size=1000))


def test_a_review_only_change_keeps_the_map_valid():
    articles, divisions = gdpr_provisions()
    reviewed = [dataclasses.replace(a, review=Review("reviewed", "A. Reviewer", "2026-11-07",
                                                     "confirmed"),
                                    structural_status=StructuralStatus.AUTO_VERIFIED,
                                    title="Titolo corretto") for a in articles]
    assert structure_sha256([*reviewed, *divisions]) == structure_sha256([*articles, *divisions])
    check(gdpr_map(), structure=structure_sha256([*reviewed, *divisions]))


# --- Exact chunk placement ---------------------------------------------------------------------

DOC = "doc-cccccccccccccccc"


def chunks_for(texts, pages=None, doc_id=DOC):
    pages = pages or [(None, None)] * len(texts)
    return [
        LegalChunk(chunk_id=expected_chunk_id(doc_id, i, t), doc_id=doc_id, text=t,
                   chunk_index=i, location=SourceLocation(page=p, page_end=q))
        for i, (t, (p, q)) in enumerate(zip(texts, pages))
    ]


def single_page(content):
    return content, (0,)


def test_overlapping_chunks_are_placed_exactly():
    content, starts = single_page("alpha beta gamma delta")
    spans = locate_chunks(content, starts, chunks_for(["alpha beta gamma", "gamma delta"]), DOC)
    assert spans == [(0, 16), (11, 22)]


def test_text_repeated_elsewhere_is_placed_in_sequence():
    content, starts = single_page("X ripetuto\n\nY\n\nripetuto")
    spans = locate_chunks(content, starts, chunks_for(["X ripetuto", "Y", "ripetuto"]), DOC)
    assert spans == [(0, 10), (12, 13), (15, 23)]


def test_identical_chunk_texts_get_successive_offsets():
    text = "Art. 3\n\n((ARTICOLO ABROGATO))"
    content, starts = single_page(f"{text}\n\n{text}\n\n{text}")
    spans = locate_chunks(content, starts, chunks_for([text, text, text]), DOC)
    assert [s for s, _ in spans] == [0, len(text) + 2, 2 * (len(text) + 2)]


def test_placement_is_sequential_and_strictly_increasing():
    content, starts = single_page("uno due tre\n\nquattro")
    spans = locate_chunks(content, starts, chunks_for(["uno due", "due tre", "quattro"]), DOC)
    assert [s for s, _ in spans] == sorted({s for s, _ in spans}) == [0, 4, 13]


def test_chunks_on_page_boundaries_carry_their_pages():
    content, starts = document([["prima pagina"], ["seconda pagina"]])
    chunks = chunks_for(["prima pagina", "seconda pagina"], [(1, 1), (2, 2)])
    assert locate_chunks(content, starts, chunks, DOC) == [(0, 12), (14, 28)]
    spanning = chunks_for(["prima pagina\n\nseconda pagina"], [(1, 2)])
    assert locate_chunks(content, starts, spanning, DOC) == [(0, 28)]


def test_a_chunk_with_wrong_pages_fails():
    content, starts = document([["prima pagina"], ["seconda pagina"]])
    with pytest.raises(AnchorError, match="placed on pages 2-2, recorded 1-1"):
        locate_chunks(content, starts, chunks_for(["prima pagina", "seconda pagina"],
                                                  [(1, 1), (1, 1)]), DOC)


@pytest.mark.parametrize(
    "text",
    [
        "Finalità e libertà di espressione",  # accented letters
        "il «diritto all'oblio» — art. 17",  # guillemets, apostrophe, em dash
        "responsabiliz\xadzazione",  # soft hyphen kept as printed
    ],
)
def test_special_characters_are_matched_exactly(text):
    content, starts = single_page(text)
    assert locate_chunks(content, starts, chunks_for([text]), DOC) == [(0, len(text))]


@pytest.mark.parametrize(
    ("content", "chunk"),
    [
        ("responsabiliz\xadzazione", "responsabilizzazione"),  # soft hyphen dropped
        (unicodedata.normalize("NFC", "Attività"), unicodedata.normalize("NFD", "Attività")),
        (unicodedata.normalize("NFD", "Attività"), unicodedata.normalize("NFC", "Attività")),
        ("il «diritto»", 'il "diritto"'),  # different quotation marks
        ("art. 17 — oblio", "art. 17 - oblio"),  # em dash vs hyphen
    ],
)
def test_text_that_differs_only_in_form_is_not_matched(content, chunk):
    with pytest.raises(AnchorError, match="not found"):
        locate_chunks(content, (0,), chunks_for([chunk]), DOC)


def test_more_than_one_possible_placement_fails():
    with pytest.raises(AnchorError, match="found 2 times"):
        locate_chunks("aaaa", (0,), chunks_for(["aa", "aa"]), DOC)


def test_missing_text_fails():
    with pytest.raises(AnchorError, match="not found"):
        locate_chunks("uno\n\ndue", (0,), chunks_for(["uno", "tre"]), DOC)


def test_a_chunk_that_skips_text_fails():
    # "due" exists, but only after text that no chunk covers.
    with pytest.raises(AnchorError, match="not found"):
        locate_chunks("uno\n\nsaltato\n\ndue", (0,), chunks_for(["uno", "due"]), DOC)


def test_text_after_the_last_chunk_must_be_covered():
    with pytest.raises(AnchorError, match="text after 3 is in no chunk"):
        locate_chunks("uno\n\nresto", (0,), chunks_for(["uno"]), DOC)
    assert locate_chunks("uno\n\n  \n", (0,), chunks_for(["uno"]), DOC) == [(0, 3)]


def test_a_wrong_chunk_id_fails():
    chunks = chunks_for(["uno", "due"])
    chunks[1] = dataclasses.replace(chunks[1], chunk_id=f"{DOC}-0001-00000000")
    with pytest.raises(AnchorError, match="ID does not match"):
        locate_chunks("uno\n\ndue", (0,), chunks, DOC)


def test_a_chunk_of_another_document_fails():
    with pytest.raises(AnchorError, match="belongs to doc-dddddddddddddddd"):
        locate_chunks("uno", (0,), chunks_for(["uno"], doc_id="doc-dddddddddddddddd"), DOC)


def test_chunks_out_of_index_order_fail():
    chunks = chunks_for(["uno", "due"])
    with pytest.raises(AnchorError, match="index 1, expected 0"):
        locate_chunks("uno\n\ndue", (0,), [chunks[1], chunks[0]], DOC)


def test_no_chunks_fails():
    with pytest.raises(AnchorError, match="no chunks"):
        locate_chunks("uno", (0,), [], DOC)


# --- Passage links ---------------------------------------------------------------------------


def test_links_keep_every_overlap():
    segment_map = gdpr_map()
    content = segment_map.content
    head, tail = content.index("CAPO I"), content.index("Testo dell'articolo uno")
    texts = [content[: content.index("HANNO")].strip(),
             content[content.index("HANNO"):head].strip(),
             content[head:tail + 10].strip(),
             content[tail + 3:].strip()]  # overlapping the previous chunk
    links = link_chunks(segment_map, chunks_for(texts, doc_id=segment_map.extraction.doc_id,
                                                pages=[(1, 1), (1, 1), (1, 1), (1, 2)]))
    assert [x["provisions"] for x in links[:2]] == [[], []]
    assert [c["kind"] for c in links[0]["context"]] == ["page_furniture", "front_matter",
                                                        "preamble", "recitals"]
    third = links[2]
    assert [p["provision_id"] for p in third["provisions"]] == [f"{V}/body/article:1"]
    assert [(c["kind"], c["provision_id"]) for c in third["context"]] == [
        ("division_heading", f"{V}/body/chapter:i")
    ]
    last = links[3]
    assert [p["provision_id"].rsplit(":", 1)[1] for p in last["provisions"]] == ["1", "2", "3"]
    kinds = [c["kind"] for c in last["context"]]
    assert kinds == ["page_furniture", "footnote", "division_heading", "closing_formula"]
    # Overlap ranges lie inside the chunk; `chars` counts the non-whitespace characters of
    # that kind only, so a range interrupted by other segments holds more than `chars`.
    for item in last["provisions"] + last["context"]:
        assert last["char_start"] <= item["char_start"] < item["char_end"] <= last["char_end"]
        extent = content[item["char_start"]:item["char_end"]]
        assert 0 < item["chars"] <= sum(1 for ch in extent if not ch.isspace())
    article_two = last["provisions"][1]  # one uninterrupted article segment
    extent = content[article_two["char_start"]:article_two["char_end"]]
    assert extent.startswith("Articolo 2")
    assert article_two["chars"] == sum(1 for ch in extent if not ch.isspace())


# --- Writing and loading, end to end on synthetic PDFs ---------------------------------------


@pytest.fixture
def synthetic_build(tmp_path, write_pdf):
    pdf = write_pdf(tmp_path / "src" / "act.pdf", [
        ["HDR 1", "Art. 1", "(Oggetto)", "1. Testo uno."],
        ["HDR 2", "Art. 2", "(Fine)", "1. Testo due."],
    ])
    spec = parse_spec({
        "schema_version": 1, "name": "x", "description": "x", "chunk_size": 1200,
        "chunk_overlap": 150, "assembly_format": "concatenated-jsonl/1",
        "sources": [{"version_id": V, "path": "src/act.pdf", "sha256": file_sha256(pdf),
                     "end_before": None}],
    }, "x.json")
    result = run_build(spec, detect_code=lambda: CLEAN, output_root=tmp_path / "builds",
                       recorded_root=tmp_path / "builds", base_dir=tmp_path,
                       dependencies=current_dependency_versions())
    rules = SegmentationRules((r"HDR \d+",), 2, (), None, None)
    registry = make_registry(rules, source_sha=file_sha256(pdf))
    articles = [prov("1", "Art. 1", 1), prov("2", "Art. 2", 2)]
    return result.directory, ProvisionStore(registry, articles, ()), registry, tmp_path


def test_maps_and_links_are_written_once_and_reload(synthetic_build):
    build_dir, store, registry, base = synthetic_build
    (map_path,) = write_segment_maps(build_dir, store=store, registry=registry,
                                     detect_code=lambda: CLEAN, base_dir=base)
    (links_file,) = write_passage_links(build_dir, store=store, registry=registry, base_dir=base)
    variant_id = map_path.name.split(".")[0]
    assert map_path == segment_map_path(build_dir, variant_id)
    assert links_file == links_path(build_dir, variant_id)
    header, *links = [json.loads(x) for x in links_file.read_text(encoding="utf-8").splitlines()]
    # The running header before Art. 1 is a chunk of its own, with no provision.
    assert header["kind"] == "passage-links" and header["chunk_count"] == len(links) == 3
    assert header["segment_map_sha256"] == file_sha256(map_path)
    assert [[p["provision_id"] for p in x["provisions"]] for x in links] == [
        [], [f"{V}/body/article:1"], [f"{V}/body/article:2"]
    ]
    assert [c["kind"] for c in links[0]["context"]] == ["page_furniture"]
    # "HDR 2" ends Article 1's chunk: context of that chunk, not text of Article 1.
    assert [c["kind"] for c in links[1]["context"]] == ["page_furniture"]
    assert links[2]["context"] == []
    before = {p: p.read_bytes() for p in (map_path, links_file)}
    with pytest.raises(AnchorError, match="never overwritten"):
        write_segment_maps(build_dir, store=store, registry=registry, detect_code=lambda: CLEAN,
                           base_dir=base)
    with pytest.raises(AnchorError, match="never overwritten"):
        write_passage_links(build_dir, store=store, registry=registry, base_dir=base)
    assert {p: p.read_bytes() for p in before} == before


def test_maps_are_reproducible(synthetic_build, tmp_path, write_pdf):
    build_dir, store, registry, base = synthetic_build
    (first,) = write_segment_maps(build_dir, store=store, registry=registry,
                                  detect_code=lambda: CLEAN, base_dir=base)
    data = first.read_bytes()
    first.unlink()
    (second,) = write_segment_maps(build_dir, store=store, registry=registry,
                                   detect_code=lambda: CLEAN, base_dir=base)
    assert second.read_bytes() == data


def test_maps_need_the_build_code_and_libraries(synthetic_build, monkeypatch):
    build_dir, store, registry, base = synthetic_build
    with pytest.raises(AnchorError, match="current code is"):
        write_segment_maps(build_dir, store=store, registry=registry,
                           detect_code=lambda: CodeVersion.clean("1" * 40), base_dir=base)
    monkeypatch.setattr(anchors, "current_dependency_versions",
                        lambda: {"pymupdf": "0.0.0", "python": "CPython 0"})
    with pytest.raises(AnchorError, match="installed"):
        write_segment_maps(build_dir, store=store, registry=registry, detect_code=lambda: CLEAN,
                           base_dir=base)
    assert not (build_dir / anchors.ANCHORS_DIR).exists()


def test_maps_need_the_registered_source(synthetic_build):
    build_dir, store, _, base = synthetic_build
    other = make_registry(SegmentationRules((r"HDR \d+",), 2, (), None, None),
                          source_sha="b" * 64)
    with pytest.raises(AnchorError, match="registry expects another source file"):
        write_segment_maps(build_dir, store=store, registry=other, detect_code=lambda: CLEAN,
                           base_dir=base)


def test_links_refuse_a_stale_map(synthetic_build):
    build_dir, store, registry, base = synthetic_build
    write_segment_maps(build_dir, store=store, registry=registry, detect_code=lambda: CLEAN,
                       base_dir=base)
    changed_registry = dataclasses.replace(registry, sha256="2" * 64)
    with pytest.raises(AnchorError, match="instrument registry changed"):
        write_passage_links(build_dir, store=store, registry=changed_registry, base_dir=base)
    relabelled = ProvisionStore(registry, [prov("1", "Art. 1", 1), prov("2-bis", "Art. 2", 2)],
                                ())
    with pytest.raises(AnchorError, match="inventory structure"):
        write_passage_links(build_dir, store=relabelled, registry=registry, base_dir=base)
    assert not any(p.name.endswith(".links.jsonl")
                   for p in (build_dir / anchors.ANCHORS_DIR).iterdir())


def test_links_refuse_a_changed_chunk_file(synthetic_build):
    build_dir, store, registry, base = synthetic_build
    write_segment_maps(build_dir, store=store, registry=registry, detect_code=lambda: CLEAN,
                       base_dir=base)
    chunk_file = next(p for p in build_dir.glob("var-*.jsonl"))
    chunk_file.write_bytes(chunk_file.read_bytes() + b"\n")
    with pytest.raises(Exception, match="does not match its recorded hash"):
        write_passage_links(build_dir, store=store, registry=registry, base_dir=base)


def test_a_loaded_map_must_belong_to_the_requested_version(synthetic_build):
    build_dir, store, registry, base = synthetic_build
    write_segment_maps(build_dir, store=store, registry=registry, detect_code=lambda: CLEAN,
                       base_dir=base)
    from src.corpus_build import verify_build

    build = verify_build(build_dir, base_dir=base)
    with pytest.raises(AnchorError, match="is not other@v1"):
        load_segment_map(build_dir, build.variants[0], build_id=build.build_id, store=store,
                         registry=registry, version_id="other@v1")
