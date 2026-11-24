"""The offline demonstration (src/demo.py), run with network access blocked.

Part 1 reads the recorded build, and its tests skip when there is none. Part 2 builds its
fictional act in a temporary directory. Neither part may reach a provider or change the real
corpus. A real provider is configured in the environment throughout, to show it is ignored.
"""

import hashlib
import socket

import pytest

import src.answer_generation as answer_generation
import src.demo as demo
import src.llm as llm_module
from src.answer_generation import Outcome
from src.config import PROJECT_ROOT
from src.models import VerificationStatus
from src.provision_explorer import ExplorerError, ProvisionExplorer, find_recorded_build
from src.provisions import load_ledger

LABELS = ("SYNTHETIC DEMONSTRATION", "FICTIONAL LEGAL INSTRUMENT",
          "SYNTHETIC REVIEW — NOT HUMAN LEGAL REVIEW",
          "SCRIPTED MOCK LLM OUTPUT — NOT A REAL MODEL RESPONSE", "NOT LEGAL ADVICE")
CLAIM = {tag: claim["text"] for tag, _, claim in demo.SCRIPTED_CLAIMS if tag != "VALID"}
VALID = [claim["text"] for tag, _, claim in demo.SCRIPTED_CLAIMS if tag == "VALID"]


def _no_network(*args, **kwargs):
    raise AssertionError("the demonstration tried to open a network connection")


def _no_provider(*args, **kwargs):
    raise AssertionError("the demonstration tried to use a real LLM provider")


def go_offline(monkeypatch):
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, _no_network)
    monkeypatch.setattr(socket, "create_connection", _no_network)
    monkeypatch.setattr(socket, "getaddrinfo", _no_network)
    monkeypatch.setattr(llm_module, "make_llm", _no_provider)
    monkeypatch.setattr(llm_module.AnthropicLLM, "_complete", _no_provider)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "claude-opus-5-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")


@pytest.fixture
def offline(monkeypatch):
    go_offline(monkeypatch)


def data_digest():
    """Every file under data/: the corpus, registry, ledger, inventories and builds."""
    digest = hashlib.sha256()
    root = PROJECT_ROOT / "data"
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


@pytest.fixture(scope="module")
def runs():
    """Both parts, run once, offline: (real run or None, synthetic run, output lines, digests)."""
    lines = []
    with pytest.MonkeyPatch.context() as monkeypatch:
        go_offline(monkeypatch)
        before = data_digest()
        real = demo.real_corpus(lines.append)
        synthetic = demo.synthetic(lines.append)
        after = data_digest()
    return real, synthetic, lines, (before, after)


@pytest.fixture(scope="module")
def real(runs):
    if runs[0] is None:
        pytest.skip("recorded build unavailable")
    return runs[0]


@pytest.fixture(scope="module")
def output(runs):
    return "\n".join(runs[2])


@pytest.fixture(scope="module")
def result(runs):
    return runs[1].result


# --- The command -------------------------------------------------------------------------------


def test_the_demo_runs_offline_with_a_real_provider_configured(offline, capsys, output):
    assert demo.main([]) == 0
    out = capsys.readouterr().out
    assert "PART 1 of 2 — REAL CORPUS" in out and "PART 2 of 2 — SYNTHETIC DEMONSTRATION" in out
    assert output in out  # the same output on every run: deterministic
    assert "SUMMARY" in out and "Part 2, synthetic: answer_limited" in out


def test_no_live_provider_is_called(runs):
    real, synthetic, _, _ = runs
    assert real is None or real.model_calls == 0
    assert isinstance(synthetic.llm, llm_module.MockLLM)
    assert [c.task for c in synthetic.llm.calls] == [
        "query_analysis", "answer_generation", "claim_verification"]


def test_the_real_corpus_and_its_records_are_not_changed(runs):
    before, after = runs[3]
    assert before == after


def test_without_a_recorded_build_part_1_is_skipped_with_a_warning(offline, capsys, monkeypatch):
    def missing():
        raise ExplorerError("no recorded build in data/processed/builds")

    monkeypatch.setattr(demo, "find_recorded_build", missing)
    assert demo.main([]) == 0
    out = capsys.readouterr().out
    assert "WARNING: no usable recorded build (no recorded build in data/processed/builds)" in out
    assert "Part 1 is skipped" in out and "Part 1, real corpus: SKIPPED" in out
    assert "PART 2 of 2" in out and "Part 2, synthetic: answer_limited" in out


def test_a_check_that_does_not_hold_fails_the_demonstration(offline, monkeypatch):
    verdicts = {"verdicts": [{"claim_id": c, "support": "supported"} for c in ("C1", "C2", "C3")]}
    monkeypatch.setitem(demo.SCRIPT, demo.VERIFICATION_TASK, [verdicts])
    with pytest.raises(demo.DemoError, match="the kept claims are not the two valid"):
        demo.synthetic(lambda line: None)


# --- Part 1: the real corpus -------------------------------------------------------------------


def test_the_real_part_uses_the_recorded_build(real):
    explorer = ProvisionExplorer.open(find_recorded_build())
    assert real.build_id == real.evidence.build_id == explorer.identity()["build_id"]
    assert [(i.instrument_id, i.label, i.point) for i in real.evidence.items[:3]] == [
        ("eu-reg-2016-679", "33", None), ("eu-reg-2016-679", "4", "12"),
        ("it-dlgs-2003-196", "2-bis", None)]  # the plan's lookups, first


def test_the_real_part_abstains_when_nothing_is_citable(real, output):
    if load_ledger():
        pytest.skip("the review ledger has records")
    assert (real.result.outcome, real.result.abstention_reason) == (
        Outcome.ABSTAIN, "no_citable_evidence")
    assert real.model_calls == 0 and real.result.analysis is None
    assert ("corpus preflight: articles 2 blocked, 319 internal_only; 0 citable -> NOT PASSED"
            in output)
    assert "RESULT: no legal answer is produced." in output


def test_the_real_part_shows_actual_provenance_and_eligibility(real, output):
    explorer = ProvisionExplorer.open(find_recorded_build())
    assert real.evidence.items and not real.evidence.citable_items
    for item in real.evidence.items:
        provenance = explorer.provision_view(explorer.store.get(item.provision_id))["provenance"]
        anchor = item.anchors[0]
        for expected in (item.provision_id, provenance["source_sha256"],
                         provenance["content_sha256"], provenance["inventory_ref"],
                         f"characters {anchor.char_start}-{anchor.char_end}"):
            assert expected in output, expected
    assert "eligibility: internal_only -> NOT CITABLE" in output
    assert ("reason structure_not_reviewed: Its structure has not been reviewed by a person"
            in output)
    assert "qualification unofficial_transcription" in output  # the Code is a transcription
    assert "segment_map" not in output and str(PROJECT_ROOT) not in output  # no local paths


# --- Part 2: the synthetic demonstration -------------------------------------------------------


def test_the_synthetic_fixture_passes_its_own_preflight(result, runs):
    assert result.preflight.passed and result.preflight.citable_articles == 2
    assert dict(result.preflight.article_tiers) == {"blocked": 2, "internal_only": 1, "primary": 2}
    assert result.preflight.build_id == runs[1].build_id != (runs[0] and runs[0].build_id)


def test_the_synthetic_part_runs_the_actual_pipeline(result, runs):
    assert demo.answer_question is answer_generation.answer_question
    llm = runs[1].llm
    assert result.evidence.build_id == runs[1].build_id
    assert [(i.evidence_id, i.label, i.tier) for i in result.evidence.items] == [
        ("E1", "1", "primary"), ("E2", "2", "internal_only"), ("E3", "3", "primary")]
    [reference] = result.question_references  # resolved by the real resolver: no act named
    assert (reference.reference.raw_text, reference.status.value) == ("articolo 1", "ambiguous")
    assert "Il custode del registro segnala ogni incidente informativo" in llm.calls[1].user
    assert result.generation.prompt_version and result.verification.prompt_version


def test_valid_synthetic_citations_are_accepted(result):
    assert [c.text for c in result.claims] == VALID
    assert all(c.verification == VerificationStatus.SUPPORTED for c in result.claims)
    assert [(c.evidence_id, c.label) for c in result.citations] == [("E1", "1"), ("E3", "3")]


def test_fabricated_quotations_and_citations_are_rejected(result):
    removed = {r.text: r.reasons for r in result.rejected_claims}
    assert removed[CLAIM["FABRICATED QUOTATION"]] == ("quote_not_found:E1",)
    assert removed[CLAIM["FABRICATED CITATION"]] == ("unsupported_reference:articolo 9",)


def test_an_unsupported_claim_is_not_presented_as_verified(result, output):
    overstated = CLAIM["OVERSTATED"]
    assert {r.text: r.reasons for r in result.rejected_claims}[overstated] == (
        "not_supported_by_evidence",)
    assert overstated not in [c.text for c in result.claims]
    answer = output[output.index("    answer (each claim"):output.index("    citations (")]
    assert overstated not in answer
    assert answer.count("support: supported") == 2 and "support: unsupported" not in output


def test_non_citable_evidence_is_kept_apart(result, runs):
    assert {r.text: r.reasons for r in result.rejected_claims}[
        CLAIM["NON-CITABLE EVIDENCE"]] == ("not_citable:E2",)
    assert [(r.evidence_id, r.citable) for r in result.non_authoritative] == [("E2", False)]
    assert "E2" not in {c.evidence_id for c in result.citations}
    assert "entro sette giorni" not in runs[1].llm.calls[1].user  # never sent to the model


def test_every_disclaimer_is_shown(output):
    synthetic_part = output[output.index("PART 2 of 2"):]
    for label in LABELS:
        assert label in synthetic_part, label
    assert synthetic_part.rstrip().endswith(" — ".join(LABELS[:2] + LABELS[3:]))
    assert "Experimental prototype. Not legal advice." in output
