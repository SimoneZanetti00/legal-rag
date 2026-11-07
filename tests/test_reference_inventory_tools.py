"""Safety rules of the reference-inventory tools (tools/reference_inventory/).

None of these tests needs the source PDFs: every refusal happens before a PDF
is parsed, and nothing is written outside tmp_path.
"""

import ast
import json
import shutil
from pathlib import Path

import pytest

from src.reference_inventory import load_inventory
from tools.reference_inventory import build, crosscheck

REFERENCE = Path(__file__).resolve().parent.parent / "data" / "reference"
SHIPPED = [REFERENCE / cfg["out"] for cfg in build.SOURCES]


@pytest.fixture
def out_dir(tmp_path):
    """An output directory holding copies of the shipped inventories."""
    out = tmp_path / "out"
    out.mkdir()
    for path in SHIPPED:
        shutil.copyfile(path, out / path.name)
    return out


def snapshot(directory):
    return {p.name: p.read_bytes() for p in sorted(directory.iterdir())}


def run_build(args, documents_dir):
    return build.main([str(a) for a in args], documents_dir=documents_dir)


def test_an_output_directory_is_required(tmp_path):
    with pytest.raises(SystemExit) as error:
        run_build([], tmp_path)
    assert error.value.code == 2


def test_existing_inventories_are_not_replaced_without_overwrite(out_dir, tmp_path, capsys):
    before = snapshot(out_dir)
    assert run_build(["--output-dir", out_dir], tmp_path / "no-pdfs") == 2
    assert "exists; pass --overwrite" in capsys.readouterr().err
    assert snapshot(out_dir) == before


def test_a_reviewed_inventory_is_not_replaced_even_with_overwrite(out_dir, tmp_path, capsys):
    target = out_dir / SHIPPED[0].name
    inventory = json.loads(target.read_text(encoding="utf-8"))
    inventory["entries"][0].update(
        review_status="reviewed", checked_by="A. Reviewer", checked_on="2026-11-07"
    )
    target.write_text(json.dumps(inventory), encoding="utf-8")
    before = snapshot(out_dir)
    assert run_build(["--output-dir", out_dir, "--overwrite"], tmp_path / "no-pdfs") == 2
    error = capsys.readouterr().err
    assert "holds 1 entries that are not pending_human_review" in error
    assert "--discard-reviews" in error
    assert snapshot(out_dir) == before


def test_an_unreadable_existing_file_is_treated_as_possibly_reviewed(out_dir, tmp_path, capsys):
    (out_dir / SHIPPED[1].name).write_text("{ not json", encoding="utf-8")
    before = snapshot(out_dir)
    assert run_build(["--output-dir", out_dir, "--overwrite"], tmp_path / "no-pdfs") == 2
    assert "may hold reviews" in capsys.readouterr().err
    assert snapshot(out_dir) == before


def test_overwrite_of_pending_inventories_still_requires_the_exact_sources(
    out_dir, tmp_path, capsys
):
    before = snapshot(out_dir)
    assert run_build(["--output-dir", out_dir, "--overwrite"], tmp_path / "no-pdfs") == 2
    assert "source PDF not found" in capsys.readouterr().err
    assert snapshot(out_dir) == before


def test_a_source_pdf_with_another_hash_is_refused(tmp_path, capsys):
    documents = tmp_path / "documents"
    documents.mkdir()
    for cfg in build.SOURCES:
        (documents / cfg["file"]).write_bytes(b"%PDF-1.7 not the trial file")
    out = tmp_path / "new-output"
    assert run_build(["--output-dir", out], documents) == 2
    assert "not the expected" in capsys.readouterr().err
    assert not out.exists()  # nothing was created


def test_the_builder_expects_the_documents_the_shipped_inventories_describe():
    for cfg, path in zip(build.SOURCES, SHIPPED):
        document = load_inventory(path)["document"]
        assert document["sha256"] == cfg["sha256"]
        assert document["path"] == f"{build.DOCUMENTS_PATH}/{cfg['file']}"


def test_the_builder_reads_no_parser_or_chunk_code():
    tree = ast.parse(Path(build.__file__).read_text(encoding="utf-8"))
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not {"src.ingestion", "src.chunking", "src.chunk_store"} & imported
    assert {"pymupdf", "src.reference_inventory"} <= imported


@pytest.mark.parametrize("value", ["2026-11-7", "07/11/2026", "2026-02-30"])
def test_generated_on_must_be_a_date(tmp_path, value):
    with pytest.raises(SystemExit):
        run_build(["--output-dir", tmp_path, "--generated-on", value], tmp_path)


def test_the_crosscheck_does_not_replace_a_report_without_overwrite(tmp_path, capsys):
    report = tmp_path / "report.md"
    report.write_text("existing\n", encoding="utf-8")
    assert crosscheck.main(["--report", str(report)]) == 2
    assert "pass --overwrite" in capsys.readouterr().err
    assert report.read_text(encoding="utf-8") == "existing\n"


def test_the_crosscheck_requires_a_report_path():
    with pytest.raises(SystemExit):
        crosscheck.main([])


@pytest.mark.parametrize("inventory", [crosscheck.GDPR_INV, crosscheck.CODICE_INV])
def test_the_crosscheck_never_writes_an_inventory_even_with_overwrite(inventory, capsys):
    before = inventory.read_bytes()
    assert crosscheck.main(["--report", str(inventory), "--overwrite"]) == 2
    error = capsys.readouterr().err
    assert "is a reference inventory" in error and "Nothing was written" in error
    assert inventory.read_bytes() == before


def test_an_inventory_path_is_recognised_however_it_is_written():
    name = crosscheck.CODICE_INV.name
    indirect = crosscheck.REPO_ROOT / "data" / "reference" / ".." / "reference" / name
    assert "is a reference inventory" in crosscheck.report_path_problem(indirect)
    assert crosscheck.report_path_problem(crosscheck.REFERENCE / "parser_crosscheck.md") is None


@pytest.mark.parametrize("name", ["report.json", "report.txt", "report", "copy.inventory.json"])
def test_the_report_must_be_markdown(tmp_path, name, capsys):
    target = tmp_path / name
    target.write_text("keep\n", encoding="utf-8")
    assert crosscheck.main(["--report", str(target), "--overwrite"]) == 2
    assert "not a Markdown (.md) file" in capsys.readouterr().err
    assert target.read_text(encoding="utf-8") == "keep\n"
