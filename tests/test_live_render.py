"""The live demo on Render: the Blueprint (render.yaml), the Python version file, and the files
the server reads at run time, which must all be tracked (Render builds from the repository).
Offline."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BUILD = "data/processed/builds/build-f76ff6031f2fc82c4852f0a2bde27807"


def test_the_blueprint():
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")
    for line in ("  - type: web", "    runtime: python", "    plan: free",
                 "    buildCommand: pip install -r deploy/live-space/requirements.txt",
                 "    startCommand: python -m src.web_demo --public --port $PORT",
                 "    healthCheckPath: /api/health",
                 "      - key: LLM_PROVIDER\n        value: anthropic",
                 "      - key: LLM_MODEL\n        value: claude-sonnet-5-5",
                 "      - key: ANTHROPIC_API_KEY\n        sync: false",
                 "      - key: LIVE_CLIENT_IP_HEADER\n        value: X-Forwarded-For"):
        assert line in blueprint, line
    assert "sk-ant" not in blueprint  # the key is set in the dashboard, never here
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.13"
    lines = (ROOT / "deploy" / "live-space" / "requirements.txt").read_text(encoding="utf-8")
    packages = {line.split("==")[0].lower() for line in lines.splitlines()
                if line.strip() and not line.startswith("#")}
    assert packages == {"python-dotenv", "anthropic", "rank-bm25", "numpy", "pymupdf"}


def tracked():
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True,
                             text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"git is not available: {exc}")
    return set(filter(None, out.split("\0")))


def test_every_data_file_the_live_path_reads_is_tracked_or_will_be():
    """The 12 data files of deploy/live-space/prepare.py (traced from the live path) are not
    git-ignored, and the recorded build is stored byte for byte."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "prepare_live_space", ROOT / "deploy" / "live-space" / "prepare.py")
    prepare = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prepare)
    ignored = subprocess.run(["git", "-C", str(ROOT), "check-ignore", *prepare.DATA_FILES],
                             capture_output=True, text=True).stdout.split()
    assert ignored == []
    attrs = subprocess.run(["git", "-C", str(ROOT), "check-attr", "text", "--",
                            f"{BUILD}/corpus.jsonl"], capture_output=True, text=True).stdout
    assert attrs.strip().endswith("text: unset")
    other_build = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q",
                                  "data/processed/builds/build-other/build.json"])
    assert other_build.returncode == 0  # no other build is tracked
    assert {f for f in tracked() if f.startswith("data/reference/")} >= {
        f for f in prepare.DATA_FILES if f.startswith("data/reference/")}
