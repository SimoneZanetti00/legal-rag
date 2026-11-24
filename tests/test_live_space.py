"""The live demo's Hugging Face Space folder (deploy/live-space/): the Dockerfile, the Space card,
the notice, the slim requirements and prepare.py, which assembles the upload folder. Offline."""

import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent / "deploy" / "live-space"


def load_prepare():
    path = HERE / "prepare.py"
    spec = importlib.util.spec_from_file_location("prepare_live_space", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_space_files():
    here = HERE
    docker = (here / "Dockerfile").read_text(encoding="utf-8")
    assert 'CMD ["python", "-m", "src.web_demo", "--public", "--port", "7860"]' in docker
    assert "COPY --chown=user src/ src/" in docker and "COPY --chown=user data/ data/" in docker
    card = (here / "README.md").read_text(encoding="utf-8")
    assert "sdk: docker" in card and "app_port: 7860" in card
    requirements = [line.split("==")[0].lower() for line in
                    (here / "requirements.txt").read_text(encoding="utf-8").splitlines()
                    if line and not line.startswith("#")]
    assert requirements == ["python-dotenv", "anthropic", "rank-bm25", "numpy", "pymupdf"]


def test_prepare_writes_the_space_files_the_code_and_exactly_the_live_data(tmp_path):
    prepare = load_prepare()
    root, here = tmp_path / "repo", tmp_path / "here"
    for rel in [*(f"src/{m}.py" for m in ("web_demo", "config")),
                *(f"src/web_static/{n}" for n in prepare.STATIC), *prepare.DATA_FILES,
                "data/raw/source.pdf", "data/evaluation/x.jsonl", ".env", "tests/test_x.py"]:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x", encoding="utf-8")
    here.mkdir()
    for name in prepare.SPACE_FILES:
        (here / name).write_text(name, encoding="utf-8")
    out = tmp_path / "out"
    written = prepare.prepare(out, root, here)
    on_disk = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    assert on_disk == sorted(written)
    assert sorted(r for r in written if r.startswith("data/")) == sorted(prepare.DATA_FILES)
    assert not any(r.endswith(".pdf") or r == ".env" or r.startswith("tests/") for r in written)
    assert len(prepare.DATA_FILES) == 12
    prepare.prepare(out, root, here)  # a previous output is replaced
    (root / prepare.DATA_FILES[0]).unlink()
    with pytest.raises(SystemExit, match="missing, nothing written"):
        prepare.prepare(tmp_path / "out2", root, here)
    (tmp_path / "other").mkdir()
    (root / prepare.DATA_FILES[0]).write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit, match="not a previous output"):
        prepare.prepare(tmp_path / "other", root, here)


def test_the_notice_and_the_card_say_where_the_texts_come_from():
    notice = (HERE / "NOTICE.md").read_text(encoding="utf-8")
    assert "EUR-Lex (https://eur-lex.europa.eu), © European Union" in notice
    assert "CC BY 4.0" in notice
    assert " ".join(notice.split()).count("Text from an unofficial user transcription of the consolidated Privacy Code; not verified against Normattiva or the Gazzetta Ufficiale.") == 1
    assert "Fonte" not in notice and "non autentico" not in notice  # no Normattiva attribution
    assert "PyMuPDF" in notice and "AGPL-3.0" in notice
    card = (HERE / "README.md").read_text(encoding="utf-8")
    assert "[NOTICE.md](NOTICE.md)" in card
    assert "https://github.com/SimoneZanetti00/legal-rag" in card and "AGPL-3.0" in card
