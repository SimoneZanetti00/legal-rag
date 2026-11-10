"""Offline demonstration: `python -m src.demo`.

Two demonstrations, run offline with no LLM provider and no API key. Settings come from the
defaults only: LLM_PROVIDER, API keys and any local .env file are ignored.

Part 1, the real corpus. The recorded build of the GDPR and the Italian Privacy Code: its
identity, its corpus preflight, and the evidence that a fixed, hand-written retrieval plan
assembles for the question, each item with its text, source anchors, provenance and
eligibility. Then the real `ask` pipeline (answer_question) runs on the question. No provision
has passed human review yet, so it abstains at the preflight and calls no model. Without a
recorded build, Part 1 is skipped with a warning.

Part 2, synthetic. A fictional act is built in a temporary directory by the project's own
build, anchor and link steps, under its own registry and store; the real corpus is neither read
nor written. answer_question() runs on it. Question references, query analysis, retrieval,
evidence assembly, claim validation, the support check and the renderer of `ask` all execute.
Only the three model replies are scripted (MockLLM). The scripted answer contains claims that
the checks must remove, and the demonstration fails if they do not.

Exit code: 0 when the demonstration ran (an abstention is a result, not a failure); 1 when it
could not run, or a check did not behave as the demonstration says.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from src.answer_generation import TASK as GENERATION_TASK
from src.answer_generation import AnswerResult, Outcome, answer_question, corpus_preflight
from src.config import load_settings
from src.corpus_build import CorpusBuildError, parse_spec, run_build
from src.corpus_identity import (
    CodeVersion,
    canonical_json,
    current_dependency_versions,
    file_sha256,
)
from src.evidence import EvidenceItem, EvidenceRequest, EvidenceSet, ProvisionRequest, assemble
from src.llm import LLMError, MockLLM
from src.models import VerificationStatus
from src.provision_anchors import AnchorError, write_passage_links, write_segment_maps
from src.provision_cli import render_answer
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.provisions import (
    QUALIFICATIONS,
    REASONS,
    Instrument,
    Provision,
    ProvisionError,
    ProvisionStore,
    Registry,
    Review,
    SegmentationRules,
    SourceStatus,
    StructuralStatus,
    Version,
    load_ledger,
)
from src.query_analysis import TASK as ANALYSIS_TASK
from src.support_verification import TASK as VERIFICATION_TASK

Write = Callable[[str], None]

SETTINGS = load_settings({})  # defaults: 5 evidence items, 3,000 tokens, support check on
RULE = "=" * 78

SYNTHETIC = "SYNTHETIC DEMONSTRATION"
FICTIONAL = "FICTIONAL LEGAL INSTRUMENT"
SYNTHETIC_REVIEW = "SYNTHETIC REVIEW — NOT HUMAN LEGAL REVIEW"
SCRIPTED = "SCRIPTED MOCK LLM OUTPUT — NOT A REAL MODEL RESPONSE"
NOT_ADVICE = "NOT LEGAL ADVICE"


class DemoError(RuntimeError):
    """The demonstration could not run, or a check did not behave as it says."""


# --- Part 1: the real corpus -------------------------------------------------------------------

REAL_QUESTION = ("When is a personal data breach required to be notified to the Italian Data "
                 "Protection Authority?")
# The retrieval plan, written by hand: no model turns the English question into Italian queries
# here. One query in the wording of the Italian texts, and the articles the question is about.
REAL_PLAN = EvidenceRequest(
    queries=("notifica di una violazione dei dati personali all'autorità di controllo",),
    provisions=(
        ProvisionRequest("eu-reg-2016-679", "33"),  # notification to the supervisory authority
        ProvisionRequest("eu-reg-2016-679", "4", "12"),  # "personal data breach" defined
        ProvisionRequest("it-dlgs-2003-196", "2-bis"),  # the Garante: Italy's authority
    ),
)


@dataclass(frozen=True)
class RealRun:
    build_id: str
    evidence: EvidenceSet
    result: AnswerResult | None  # None when the preflight passed (not run offline)
    model_calls: int


def real_corpus(write: Write, build_dir: Path | None = None) -> RealRun | None:
    """Part 1. None when no recorded build is available (skipped, with a warning)."""
    _heading(write, "PART 1 of 2 — REAL CORPUS: the recorded build of the GDPR and the Italian "
             "Privacy Code")
    write(f"question: {REAL_QUESTION}")
    try:
        explorer = ProvisionExplorer.open(build_dir or find_recorded_build())
    except (ExplorerError, ProvisionError) as exc:
        write(f"WARNING: no usable recorded build ({exc}).")
        write("Part 1 is skipped. To create the build, see the README section \"Provision "
              "store and corpus explorer\".")
        return None

    write("")
    write("-- the corpus")
    identity = explorer.identity()
    code = identity["code"]
    write(f"recorded build: {identity['build_id']} (code commit {code['commit']}, "
          f"{code['state']}); corpus sha256 {identity['corpus_sha256']}")
    for source in identity["sources"]:
        write(f"  source {source['version_id']}: {source['source_path']}")
        write(f"    file sha256 {source['source_sha256']}; extracted text sha256 "
              f"{source['content_sha256']}")
    preflight = corpus_preflight(explorer)
    tiers = ", ".join(f"{count} {tier}" for tier, count in preflight.article_tiers)
    write(f"review ledger: {len(load_ledger())} human review records")
    write(f"corpus preflight: articles {tiers}; {preflight.citable_articles} citable -> "
          + ("passed" if preflight.passed else "NOT PASSED: no article may be cited"))

    write("")
    write("-- the evidence, from a fixed retrieval plan written by hand (no model is called in "
          "this part)")
    write("  query: " + "; ".join(f"«{q}»" for q in REAL_PLAN.queries))
    write("  lookups: " + ", ".join(f"{p.instrument} art. {p.label}"
                                    + (f" point {p.point}" if p.point else "")
                                    for p in REAL_PLAN.provisions))
    evidence = assemble(REAL_PLAN, explorer, settings=SETTINGS)
    write(f"evidence assembled from build {evidence.build_id}: {len(evidence.items)} items "
          f"({len(evidence.citable_items)} citable), about {evidence.total_tokens} tokens "
          f"(limits: {evidence.max_items} items, {evidence.token_budget} tokens)")
    for item in evidence.items:
        _real_item(write, explorer, item)
    if evidence.dropped:
        write("  left out by the limits: " + ", ".join(
            f"{_name(d.provision_id)} ({d.reason})" for d in evidence.dropped))

    write("")
    if preflight.passed:  # possible only once human reviews are recorded
        write("The corpus now has citable articles. This offline demonstration calls no model; "
              "run `python -m src.cli ask` with a configured provider for an answer.")
        return RealRun(identity["build_id"], evidence, None, 0)
    llm = MockLLM()  # no scripted replies: any model call would raise and fail the demo
    result = answer_question(REAL_QUESTION, llm, explorer, settings=SETTINGS)
    write("-- the `ask` pipeline on the question (answer_question, as `python -m src.cli ask` "
          "runs it)")
    _block(write, render_answer(result))
    write(f"model calls made: {len(llm.calls)}")
    if result.outcome != Outcome.ABSTAIN or llm.calls:
        raise DemoError("the real corpus has no citable article, but the pipeline did not "
                        "abstain without calling a model")
    write("")
    write("RESULT: no legal answer is produced. No provision of the recorded corpus is "
          "currently eligible for citation:")
    write("none has passed human review, so the pipeline abstains at the corpus preflight "
          "before any model is called.")
    return RealRun(identity["build_id"], evidence, result, len(llm.calls))


def _real_item(write: Write, explorer: ProvisionExplorer, item: EvidenceItem) -> None:
    provenance = explorer.provision_view(explorer.store.get(item.provision_id))["provenance"]
    point = f", point {item.point}" if item.point else ""
    write(f"  {item.evidence_id}  {item.instrument_id} {item.heading}{point}  "
          f"(found by: {', '.join(_origin(o) for o in item.origins)})")
    kind = "whole article" if item.whole_provision else "excerpt of the article"
    start = "" if item.whole_provision or item.point else "… "
    write(f"      text ({kind}, shortened here): «{start}{_excerpt(item.text)}»")
    write("      anchors: " + "; ".join(
        f"page {a.page}{'' if a.page_end == a.page else f'-{a.page_end}'}, characters "
        f"{a.char_start}-{a.char_end} of the extracted text" for a in item.anchors))
    write(f"      provenance: {item.provision_id}")
    write(f"        source file sha256 {_known(provenance['source_sha256'])}; extracted text "
          f"sha256 {_known(provenance['content_sha256'])}")
    write(f"        inventory {_known(provenance['inventory_ref'])} (inventory sha256 "
          f"{_known(provenance['inventory_sha256'])})")
    write(f"      eligibility: {item.tier} -> " + ("citable" if item.citable else "NOT CITABLE"))
    for code in item.reasons:
        write(f"        reason {code}: {REASONS.get(code, code)}")
    for code in item.qualifications:
        write(f"        qualification {code}: {QUALIFICATIONS.get(code, code)}")


# --- Part 2: the synthetic demonstration -------------------------------------------------------

INSTRUMENT_ID = "demo-valdoria"
VERSION_ID = f"{INSTRUMENT_ID}@synthetic-v1"
ACT_NAME = "Legge dimostrativa di Valdoria"
# The fixture is rebuilt from the definitions below on every run, so its build records a
# placeholder code identity, not a repository commit.
FIXTURE_CODE = CodeVersion.clean("0" * 40)
# The fictional act, page by page: one line per text block, as the PDF reader extracts it.
PAGES = (
    ("VALDORIA 1", "LEGGE DIMOSTRATIVA DI VALDORIA (ATTO FITTIZIO)",
     "Art. 1", "(Segnalazione degli incidenti informativi)",
     "1. Il custode del registro segnala ogni incidente informativo all'Ufficio",
     "di vigilanza entro quarantotto ore dalla scoperta.",
     "2. La segnalazione non è dovuta se l'incidente riguarda soltanto schede",
     "già pubblicate nel bollettino di Valdoria.",
     "Art. 2", "(Avviso ai titolari delle schede)",
     "1. Se l'incidente espone schede riservate, il custode avvisa anche i",
     "titolari delle schede entro sette giorni."),
    ("VALDORIA 2", "Art. 3", "(Ufficio di vigilanza)",
     "1. L'Ufficio di vigilanza di Valdoria riceve le segnalazioni di cui",
     "all'articolo 1 e ne conserva un elenco per cinque anni.",
     "Art. 4", "Art. 4-bis", "((ARTICOLO ABROGATO))"),
)
# (label, page, title, state, status marker). "reviewed" is the synthetic review.
ARTICLES = (
    ("1", 1, "(Segnalazione degli incidenti informativi)", "reviewed", None),
    ("2", 1, "(Avviso ai titolari delle schede)", "not reviewed", None),
    ("3", 2, "(Ufficio di vigilanza)", "reviewed", None),
    ("4", 2, None, "ambiguous", None),
    ("4-bis", 2, None, "ambiguous", "((ARTICOLO ABROGATO))"),
)

SYNTHETIC_QUESTION = ("Entro quando il custode del registro deve segnalare un incidente "
                      "informativo ai sensi dell'articolo 1, a chi, e chi altro va avvisato?")
ANALYSIS_REPLY = {
    "language": "it", "in_scope": True,
    "scope_reason": "Riguarda la segnalazione degli incidenti informativi nell'atto di Valdoria.",
    "issues": [
        {"question": "Entro quale termine il custode del registro segnala un incidente "
                     "informativo?"},
        {"question": "Quale ufficio riceve le segnalazioni?"},
        {"question": "Quando vanno avvisati i titolari delle schede?"},
    ],
    "search_queries_it": [
        "segnalazione di un incidente informativo all'Ufficio di vigilanza",
        "avviso ai titolari delle schede riservate",
        "Ufficio di vigilanza che riceve le segnalazioni",
    ],
    "suggested_provisions": [], "uncertainty": None, "clarification_question": None,
}


def _claim(issue: str, text: str, *support: tuple[str, str]) -> dict:
    return {"issue_ids": [issue], "kind": "source_statement", "text": text,
            "support": [{"evidence_id": e, "quote": q} for e, q in support]}


# The scripted answer: what a model might return, mistakes included, as (tag, description,
# claim). Tags and descriptions are printed for the reader; the pipeline never sees them.
SCRIPTED_CLAIMS = (
    ("VALID", "quoted from Art. 1",
     _claim("I1", "Il custode del registro segnala ogni incidente informativo all'Ufficio di "
            "vigilanza entro quarantotto ore dalla scoperta.",
            ("E1", "Il custode del registro segnala ogni incidente informativo all'Ufficio di "
                   "vigilanza entro quarantotto ore dalla scoperta"))),
    ("VALID", "quoted from Art. 3; names Art. 1, which Art. 3 itself refers to",
     _claim("I2", "Le segnalazioni previste dall'articolo 1 sono ricevute dall'Ufficio di "
            "vigilanza di Valdoria, che ne conserva un elenco per cinque anni.",
            ("E3", "L'Ufficio di vigilanza di Valdoria riceve le segnalazioni"),
            ("E3", "ne conserva un elenco per cinque anni"))),
    ("FABRICATED QUOTATION", "the quoted words are not in Art. 1",
     _claim("I1", "Il termine di segnalazione può essere prorogato fino a dieci giorni.",
            ("E1", "il termine può essere prorogato fino a dieci giorni"))),
    ("FABRICATED CITATION", "names an article that no cited evidence supports",
     _claim("I1", "La segnalazione segue anche la procedura dell'articolo 9.",
            ("E1", "segnala ogni incidente informativo all'Ufficio di vigilanza"))),
    ("NON-CITABLE EVIDENCE", "cites Art. 2, which is in the evidence but has not been reviewed",
     _claim("I3", "Se l'incidente espone schede riservate, il custode avvisa anche i titolari "
            "delle schede entro sette giorni.",
            ("E2", "il custode avvisa anche i titolari delle schede entro sette giorni"))),
    ("OVERSTATED", "the quotation is real, but Art. 1 does not say this: paragraph 2 makes an "
     "exception",
     _claim("I1", "Ogni incidente informativo va sempre segnalato all'Ufficio di vigilanza, "
            "senza eccezioni.",
            ("E1", "Il custode del registro segnala ogni incidente informativo"))),
)
# The scripted model claims a complete answer; the pipeline decides what is left of it.
GENERATION_REPLY = {"outcome": "answer", "claims": [c for _, _, c in SCRIPTED_CLAIMS],
                    "unanswered_issues": [], "limitations": [], "abstention_reason": None}
# Verdicts on the claims that pass validation, numbered C1, C2, C3 in the model's order.
VERIFICATION_REPLY = {"verdicts": [{"claim_id": "C1", "support": "supported"},
                                   {"claim_id": "C2", "support": "supported"},
                                   {"claim_id": "C3", "support": "unsupported"}]}
SCRIPT = {ANALYSIS_TASK: [ANALYSIS_REPLY], GENERATION_TASK: [GENERATION_REPLY],
          VERIFICATION_TASK: [VERIFICATION_REPLY]}

# What the pipeline must make of the scripted answer (checked on every run).
EXPECTED_EVIDENCE = {"E1": ("1", True), "E2": ("2", False), "E3": ("3", True)}
EXPECTED_KEPT = (0, 1)  # SCRIPTED_CLAIMS indexes
EXPECTED_REMOVED = {2: ("quote_not_found:E1",), 3: ("unsupported_reference:articolo 9",),
                    4: ("not_citable:E2",), 5: ("not_supported_by_evidence",)}


@dataclass(frozen=True)
class SyntheticRun:
    build_id: str
    result: AnswerResult
    llm: MockLLM


def synthetic(write: Write) -> SyntheticRun:
    """Part 2: build the fictional act in a temporary directory and run the pipeline on it."""
    _heading(write, f"PART 2 of 2 — {SYNTHETIC}: the whole pipeline on a {FICTIONAL}")
    write(f"{SYNTHETIC}: everything in this part is invented, to exercise the software.")
    write(f"  - {FICTIONAL}: «{ACT_NAME}». Valdoria does not exist; the act is not law "
          "anywhere.")
    write(f"  - {SYNTHETIC_REVIEW}: Art. 1 and Art. 3 are marked reviewed inside this "
          "temporary fixture only, so that something is citable. No person reviewed them, and "
          "the real review ledger is not used.")
    write(f"  - {SCRIPTED}: the query analysis, the answer and the support verdicts are fixed "
          "replies written for this demonstration (MockLLM, offline).")
    write(f"  - {NOT_ADVICE}.")
    write("Executed, not scripted: the corpus build, segment maps and passage links (in a "
          "temporary directory, deleted afterwards); eligibility and the corpus preflight; "
          "question references; BM25 retrieval and evidence assembly; quotation, citation and "
          "eligibility checks; applying the support verdicts; rendering.")

    with tempfile.TemporaryDirectory(prefix="legal-rag-demo-", ignore_cleanup_errors=True) as tmp:
        explorer = build_synthetic_corpus(Path(tmp))
        build_id = explorer.identity()["build_id"]
        write("")
        write(f"fixture build: {build_id} (code identity: placeholder "
              f"{FIXTURE_CODE.commit[:7]}..., not a repository commit)")
        for label, _, title, state, _ in ARTICLES:
            provision = explorer.store.lookup(INSTRUMENT_ID, label)
            eligibility = explorer.provision_view(provision)["eligibility"]
            reviewed = (f"reviewed by «{provision.review.checked_by}»"
                        if provision.review.status == "reviewed" else state)
            reasons = ", ".join(r["code"] for r in eligibility["reasons"])
            write(f"  Art. {label} {title or ''}".rstrip() + f": {reviewed} -> "
                  f"{eligibility['tier']}" + (f" ({reasons})" if reasons else ""))

        write("")
        write(f"question: {SYNTHETIC_QUESTION}")
        write(f"scripted answer ({SCRIPTED}): {len(SCRIPTED_CLAIMS)} claims")
        for n, (tag, description, _) in enumerate(SCRIPTED_CLAIMS, 1):
            write(f"  claim {n}: {tag}: {description}")
        llm = MockLLM(SCRIPT)
        result = answer_question(SYNTHETIC_QUESTION, llm, explorer, settings=SETTINGS)
        write("")
        write("pipeline result (answer_question, rendered as `ask` prints it):")
        _block(write, render_answer(result))
        write("    (The `lookup` hints refer to the real corpus; the fictional act exists only "
              "during this run.)")
        _check_synthetic(result, llm)
        _guardrails(write, result, llm)
    write("")
    write(f"{SYNTHETIC} — {FICTIONAL} — {SCRIPTED} — {NOT_ADVICE}")
    return SyntheticRun(build_id, result, llm)


def build_synthetic_corpus(root: Path) -> ProvisionExplorer:
    """The fictional act, built under `root` by the project's own build, anchor and link steps."""
    pdf = _write_pdf(root / "sources" / "valdoria.pdf")
    source_sha = file_sha256(pdf)
    definition_sha = hashlib.sha256(canonical_json({"pages": PAGES,
                                                    "articles": ARTICLES})).hexdigest()
    version = Version(
        VERSION_ID, INSTRUMENT_ID, "original_publication",
        f"{ACT_NAME}: {FICTIONAL} ({SYNTHETIC.lower()})", "it", None, None, None,
        SourceStatus.NO_STATUS_REPRESENTATION, "synthetic fixture in src/demo.py", source_sha,
        SegmentationRules((r"VALDORIA \d+",), len(PAGES), (), None, None))
    instrument = Instrument(INSTRUMENT_ID, "law", "fictional", (ACT_NAME.lower(),), None)
    registry = Registry((instrument,), (version,), definition_sha)
    store = ProvisionStore(registry, [_provision(a, source_sha, definition_sha)
                                      for a in ARTICLES], ())
    spec = parse_spec({
        "schema_version": 1, "name": "synthetic-demo", "description": f"{SYNTHETIC}: {ACT_NAME}",
        "chunk_size": 300, "chunk_overlap": 50, "assembly_format": "concatenated-jsonl/1",
        "sources": [{"version_id": VERSION_ID, "path": "sources/valdoria.pdf",
                     "sha256": source_sha, "end_before": None}],
    }, "synthetic-demo.json")
    build = run_build(spec, detect_code=lambda: FIXTURE_CODE, output_root=root / "builds",
                      recorded_root=root / "builds", base_dir=root,
                      dependencies=current_dependency_versions())
    write_segment_maps(build.directory, store=store, registry=registry,
                       detect_code=lambda: FIXTURE_CODE, base_dir=root)
    write_passage_links(build.directory, store=store, registry=registry, base_dir=root)
    return ProvisionExplorer.open(build.directory, store=store, base_dir=root)


def _write_pdf(path: Path) -> Path:
    """The act as a PDF, byte for byte the same on every run (no dates, no random ID)."""
    pdf = pymupdf.open()
    for lines in PAGES:
        page = pdf.new_page()
        for i, line in enumerate(lines):
            page.insert_text((72, 72 + 60 * i), line)  # far apart: one text block per line
    pdf.set_metadata({})
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, no_new_id=True, garbage=4, deflate=True)
    pdf.close()
    return path


def _provision(article: tuple, source_sha: str, definition_sha: str) -> Provision:
    label, page, title, state, marker = article
    reviewed = state == "reviewed"
    return Provision(
        provision_id=f"{VERSION_ID}/body/article:{label}", version_id=VERSION_ID,
        instrument_id=INSTRUMENT_ID, kind="article", label_as_printed=label,
        normalised_label=label, heading_as_printed=f"Art. {label}", title=title,
        status_marker=marker, parent_id=None, path=f"Art. {label}", page_start=page,
        page_end=page,
        structural_status=(StructuralStatus.AMBIGUOUS if state == "ambiguous"
                           else StructuralStatus.AUTO_VERIFIED if reviewed
                           else StructuralStatus.AUTO_UNREVIEWED),
        review=(Review("reviewed", SYNTHETIC_REVIEW, None, "confirmed") if reviewed
                else Review("pending_human_review")),
        source_status_representation=(None if state == "ambiguous"
                                      else SourceStatus.NO_STATUS_REPRESENTATION),
        inventory_id="synthetic-demo-inventory", inventory_ref=f"synthetic-demo:art:{label}",
        inventory_sha256=definition_sha, source_sha256=source_sha,
        doc_id="doc-" + source_sha[:16], notes=(),
    )


def _check_synthetic(result: AnswerResult, llm: MockLLM) -> None:
    """Every statement the demonstration makes about its result, checked."""
    problems = []
    if result.preflight is None or not result.preflight.passed:
        problems.append("the fixture's corpus preflight did not pass")
    items = result.evidence.items if result.evidence else ()
    if {i.evidence_id: (i.label, i.citable) for i in items} != EXPECTED_EVIDENCE:
        problems.append("the assembled evidence is not E1 = Art. 1, E2 = Art. 2, E3 = Art. 3")
    texts = [c["text"] for _, _, c in SCRIPTED_CLAIMS]
    if [c.text for c in result.claims] != [texts[i] for i in EXPECTED_KEPT] or any(
            c.verification != VerificationStatus.SUPPORTED for c in result.claims):
        problems.append("the kept claims are not the two valid, supported ones")
    removed = {r.text: r.reasons for r in result.rejected_claims}
    if removed != {texts[i]: reasons for i, reasons in EXPECTED_REMOVED.items()}:
        problems.append(f"the removed claims and their reasons differ: {removed}")
    if {c.evidence_id for c in result.citations} != {"E1", "E3"} or {
            r.evidence_id for r in result.non_authoritative} != {"E2"}:
        problems.append("citations and non-authoritative references are not kept apart")
    if result.outcome != Outcome.ANSWER_LIMITED:
        problems.append(f"the outcome is {result.outcome.value}, not answer_limited")
    if [c.task for c in llm.calls] != [ANALYSIS_TASK, GENERATION_TASK, VERIFICATION_TASK]:
        problems.append("the model calls are not analysis, generation and support check")
    elif "titolari delle schede entro sette giorni" in llm.calls[1].user:
        problems.append("the non-citable Art. 2 was sent to the model")
    if problems:
        raise DemoError("the synthetic demonstration did not behave as it states: "
                        + "; ".join(problems))


def _guardrails(write: Write, result: AnswerResult, llm: MockLLM) -> None:
    number = {c["text"]: n for n, (_, _, c) in enumerate(SCRIPTED_CLAIMS, 1)}
    tag = {c["text"]: t for t, _, c in SCRIPTED_CLAIMS}
    write("")
    write("what the checks did (computed by the pipeline; only the model replies are scripted):")
    write("  kept, support assessed as supported: " + ", ".join(
        f"{c.claim_id} (claim {number[c.text]})" for c in result.claims))
    by_validation = [r for r in result.rejected_claims
                     if r.reasons != ("not_supported_by_evidence",)]
    write("  removed by deterministic validation (quotations, citations, eligibility):")
    for r in by_validation:
        write(f"    claim {number[r.text]} ({tag[r.text]}): {', '.join(r.reasons)}")
        write(f"      «{r.text}»")
    write("  removed by the support check (a scripted verdict, applied by the pipeline):")
    for r in result.rejected_claims:
        if r not in by_validation:
            write(f"    claim {number[r.text]} ({tag[r.text]}): {', '.join(r.reasons)}")
            write(f"      «{r.text}»")
    for ref in result.non_authoritative:
        write(f"  non-citable evidence kept apart: {ref.evidence_id} Art. {ref.label} "
              f"({ref.tier}) is listed only as a non-authoritative reference,")
        write("    never as a citation, and its text was not sent to the model.")
    write("  model calls, all to MockLLM (offline): " + ", ".join(c.task for c in llm.calls))


# --- Output helpers ----------------------------------------------------------------------------


def _heading(write: Write, title: str) -> None:
    write("")
    write(RULE)
    write(title)
    write(RULE)


def _block(write: Write, text: str) -> None:
    for line in text.splitlines():
        write(f"    {line}" if line else "")


def _excerpt(text: str, limit: int = 240) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:flat.rfind(" ", 0, limit)] + " …"


def _known(value: object) -> str:
    return "not recorded" if value in (None, "") else str(value)


def _name(provision_id: str) -> str:
    """'eu-reg-2016-679@…/body/article:33' -> 'eu-reg-2016-679 art. 33'."""
    return f"{provision_id.split('@', 1)[0]} art. {provision_id.rsplit(':', 1)[-1]}"


def _origin(origin: str) -> str:
    kind, _, rest = origin.partition(":")
    if kind == "reference":
        return f"reference in {_name(rest)}"
    return f"search query {rest}" if kind == "query" else kind


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.demo",
        description="Offline demonstration: the real corpus (evidence, provenance, abstention) "
                    "and a synthetic end-to-end run. No LLM provider or API key is used.")
    parser.add_argument("--build-dir", type=Path,
                        help="recorded build for part 1 (default: the one in "
                             "data/processed/builds/)")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # source text may not fit the console encoding
        sys.stdout.reconfigure(errors="replace")
    try:
        real = real_corpus(print, args.build_dir)
        run = synthetic(print)
    except (DemoError, CorpusBuildError, AnchorError, ExplorerError, ProvisionError,
            LLMError) as exc:
        print(f"DEMO FAILED: {exc}", file=sys.stderr)
        return 1
    result = run.result
    _heading(print, "SUMMARY")
    if real is None:
        print("Part 1, real corpus: SKIPPED (no recorded build).")
    elif real.result is None:
        print("Part 1, real corpus: citable articles exist; no answer is generated offline.")
    else:
        print(f"Part 1, real corpus: {real.result.outcome.value} "
              f"({real.result.abstention_reason}); {len(real.evidence.items)} evidence items "
              f"shown, {len(real.evidence.citable_items)} citable; {real.model_calls} model calls.")
    print(f"Part 2, synthetic: {result.outcome.value}; {len(result.claims)} claims kept, "
          f"{len(result.rejected_claims)} removed; {len(run.llm.calls)} scripted MockLLM replies "
          "used.")
    print(f"{NOT_ADVICE}. Experimental prototype.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
