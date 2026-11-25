"""Assemble the Hugging Face Docker Space of the live demo: python deploy/live-space/prepare.py

Writes dist/live-space/ (git-ignored, replaced on each run), the folder to upload to the Space:
- app.py (the entry point the Gradio SDK runs), README.md (the Space card), NOTICE.md
  (sources, attribution, licences) and requirements.txt, from this folder. The Dockerfile stays
  here for reference: the Space uses the Gradio SDK, not Docker;
- src/: the application code (every module and the page), without caches;
- exactly the data files the live path reads (DATA_FILES): the recorded corpus build with its
  anchors (segment maps and passage links), the instrument registry, the two reference
  inventories and the review ledger.

Nothing else: no source PDF, no evaluation data, no tests, no .env. The build is git-ignored, so
this runs on a machine that has it; a missing file stops the script before anything is written.
Standard library only. Instructions: docs/deploy-live.md.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEFAULT_OUT = ROOT / "dist" / "live-space"
SPACE_FILES = ("app.py", "README.md", "NOTICE.md", "requirements.txt")
BUILD = "data/processed/builds/build-f76ff6031f2fc82c4852f0a2bde27807"
VARIANTS = ("var-30da24d25055784cba1e38b5475791c1", "var-73eec6712eff509c69f66380241cc2b7")
# What ProvisionExplorer.open, corpus_preflight and the evidence status read; nothing else is
# opened on the live path (traced on 2026-11-24 with an audit hook over data/).
DATA_FILES = (
    f"{BUILD}/build.json",
    f"{BUILD}/corpus.jsonl",
    *(f"{BUILD}/{v}.jsonl" for v in VARIANTS),
    *(f"{BUILD}/anchors/{v}.{kind}" for v in VARIANTS for kind in ("segments.json", "links.jsonl")),
    "data/reference/instruments.json",
    "data/reference/review_ledger.json",
    "data/reference/gdpr_2016_679_it.inventory.json",
    "data/reference/codice_privacy_dlgs_196_2003.main_body.inventory.json",
)
STATIC = ("index.html", "app.css", "app.js")


def source_files(root: Path) -> list[str]:
    """The application code to ship: every module of src/ and the page."""
    modules = sorted(p.relative_to(root).as_posix() for p in (root / "src").glob("*.py"))
    return modules + [f"src/web_static/{name}" for name in STATIC]


def prepare(out: Path, root: Path = ROOT, here: Path = HERE) -> list[str]:
    """Write the Space folder to `out`; return the files written, relative to it."""
    files = [(here / name, name) for name in SPACE_FILES]
    files += [(root / rel, rel) for rel in source_files(root) + list(DATA_FILES)]
    missing = [rel for src, rel in files if not src.is_file()]
    if missing:
        raise SystemExit("error: missing, nothing written:\n  " + "\n  ".join(missing)
                         + "\nThe corpus build is created as described in docs/REFERENCE.md "
                           "(\"Provision store and corpus explorer\").")
    if out.exists():
        if not (out / "README.md").is_file() or not (out / "src").is_dir():
            raise SystemExit(f"error: {out} exists and is not a previous output of this script")
        shutil.rmtree(out)
    for src, rel in files:
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
    return [rel for _, rel in files]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python deploy/live-space/prepare.py",
                                     description="Assemble the live demo's Hugging Face Space.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="output folder (default: dist/live-space/; replaced)")
    args = parser.parse_args(argv)
    written = prepare(args.out)
    size = sum((args.out / rel).stat().st_size for rel in written)
    print(f"{len(written)} files, {size / 1e6:.1f} MB -> {args.out}")
    for group, prefix in (("Space", ""), ("code", "src/"), ("data", "data/")):
        names = [r for r in written if (r.startswith(prefix) if prefix else "/" not in r)]
        print(f"  {group}: {len(names)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
