"""Official-text extraction and comparison for the M1 review package (read-only).

Reads the archived official HTML files (official_sources.json), checks that each one is
byte-identical to the recorded download, extracts the five demonstration articles, and
compares them with the anchored text of the recorded build.

Run from the repository root to verify the recorded extraction hashes:

    python -m tools.review_package.official_texts [--sources-dir DIR] [--build-dir DIR]

Exit code 0 when every file and every derived hash matches official_sources.json,
1 otherwise. Nothing is written.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

import src.text_normalization as tn
from src.config import PROJECT_ROOT
from src.provisions import ProvisionStore, load_store, official_check_record

ARCHIVE_DIR = PROJECT_ROOT / "data" / "raw" / "trial-2026-10-10" / "official-sources"
PROVENANCE_PATH = ARCHIVE_DIR / "official_sources.json"
DEFAULT_BUILD_DIR = Path("data/processed/builds/build-f76ff6031f2fc82c4852f0a2bde27807")

# (instrument, label, key in the comparison results, name in official_sources.json)
PROVISIONS = (
    ("gdpr", "4", "4", "GDPR Art. 4"),
    ("gdpr", "33", "33", "GDPR Art. 33"),
    ("gdpr", "34", "34", "GDPR Art. 34"),
    ("gdpr", "55", "55", "GDPR Art. 55"),
    ("codice privacy", "2-bis", "2-bis", "Privacy Code Art. 2-bis"),
)


class SourceError(ValueError):
    """An archived source is missing or is not the recorded download."""


def load_provenance(path: Path = PROVENANCE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_archive(sources_dir: Path, provenance: dict[str, Any]) -> dict[str, Path]:
    """Paths of the archived files, after checking their size and SHA-256."""
    paths = {}
    for record in provenance["original_files"]:
        path = sources_dir / record["file"]
        if not path.is_file():
            raise SourceError(f"{path}: missing archived source")
        size, sha = path.stat().st_size, file_sha256(path)
        if (size, sha) != (record["size_bytes"], record["sha256"]):
            raise SourceError(f"{path}: not the recorded download (sha256 {sha}, "
                              f"expected {record['sha256']})")
        paths[record["file"]] = path
    return paths


def page_text(path: Path) -> str:
    """The extraction steps recorded in official_sources.json, 1 to 3."""
    t = path.read_text(encoding="utf-8")
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", t, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", "\n", t))
    return "\n".join(line.strip() for line in t.split("\n") if line.strip())


def eurlex_article(text: str, label: str) -> str:
    start = re.search(rf"(?m)^Articolo {label}$", text)
    rest = text[start.end():]
    end = re.search(r"(?m)^(Articolo \d+|CAPO [IVX]+|Sezione \d+)$", rest)
    return text[start.start(): start.end() + (end.start() if end else len(rest))]


def normattiva_2bis(text: str) -> str:
    i = text.find("Art. 2-bis\n(( (Autorit")
    return text[i: text.find("articolo precedente", i)]


def anchored_text(build_dir: Path, version_id: str, provision_id: str) -> str:
    for path in (build_dir / "anchors").glob("*.segments.json"):
        m = json.loads(path.read_text(encoding="utf-8"))
        if m["version_id"] == version_id:
            return "".join(s["text"] for s in m["segments"]
                           if s["kind"] == "article" and s["provision_id"] == provision_id)
    raise SourceError(f"{build_dir}: no segment map for {version_id}")


_RULES = {"markers": tn._MARKER, "soft_hyphen": tn._SOFT_HYPHEN}


def rules_used(text: str) -> list[str]:
    """Which normalisation transformations change `text`."""
    used = [k for k, r in _RULES.items() if r.search(text)]
    if chr(0x2019) in text:  # typographic apostrophe
        used.append("apostrophe")
    collapsed = tn._WHITESPACE.sub(" ", text).strip()
    if collapsed != text:
        used.append("whitespace")
    if tn._SPACE_BEFORE.search(collapsed) or tn._SPACE_AFTER.search(collapsed):
        used.append("punctuation_spacing")
    return used


def extract_official_texts(sources_dir: Path, provenance: dict[str, Any] | None = None
                           ) -> dict[str, tuple[str, dict[str, Any]]]:
    """The five extracted official texts with their source records, keyed by label.

    Checks the archived files first (verify_archive); needs no build.
    """
    provenance = provenance or load_provenance()
    paths = verify_archive(sources_dir, provenance)
    by_type = {r["source_type"]: r for r in provenance["original_files"]}
    eurlex_record, normattiva_record = by_type["eurlex_consolidated"], by_type["normattiva_vigente"]
    eurlex = page_text(paths[eurlex_record["file"]])
    normattiva = page_text(paths[normattiva_record["file"]])
    texts = {}
    for instrument, label, key, _ in PROVISIONS:
        if instrument == "gdpr":
            texts[key] = (eurlex_article(eurlex, label), eurlex_record)
        else:
            texts[key] = (normattiva_2bis(normattiva), normattiva_record)
    return texts


def compare_all(sources_dir: Path, build_dir: Path, store: ProvisionStore | None = None,
                provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extraction and comparison results for the five provisions, keyed by label."""
    provenance = provenance or load_provenance()
    store = store or load_store()
    texts = extract_official_texts(sources_dir, provenance)
    out: dict[str, Any] = {"files": {r["file"]: file_sha256(sources_dir / r["file"])
                                     for r in provenance["original_files"]}}
    for instrument, label, key, _ in PROVISIONS:
        p = store.lookup(instrument, label)
        mine = anchored_text(build_dir, p.version_id, p.provision_id)
        official, record = texts[key]
        cmp = tn.compare_texts(mine, official)
        candidate = official_check_record(
            mine, official, source_url=record["url"], source_type=record["source_type"],
            consolidation_date=record["consolidation_date"],
            retrieved_on=record["retrieved_at"][:10])
        out[key] = {
            "provision_id": p.provision_id, "ours": mine, "official": official,
            "ours_sha256": hashlib.sha256(mine.encode()).hexdigest(),
            "status": cmp.status, "differences": [[d.ours, d.theirs] for d in cmp.differences],
            "rules_ours": rules_used(mine), "rules_official": rules_used(official),
            "candidate": candidate, "raw_equal": mine == official,
        }
    point = lambda t: re.search(r"(?m)^12\)\s.*?(?=^13\))", t, re.S).group(0)  # noqa: E731
    o12, f12 = point(out["4"]["ours"]), point(out["4"]["official"])
    c12 = tn.compare_texts(o12, f12)
    out["4"]["point12"] = {
        "ours": o12, "official": f12, "status": c12.status,
        "differences": [[d.ours, d.theirs] for d in c12.differences],
        "official_sha256": hashlib.sha256(f12.encode()).hexdigest(),
        "ours_sha256": hashlib.sha256(o12.encode()).hexdigest(),
    }
    return out


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sources-dir", type=Path, default=ARCHIVE_DIR,
                        help=f"archived official sources (default: {ARCHIVE_DIR})")
    parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD_DIR)
    args = parser.parse_args(argv)
    provenance = load_provenance()
    sources_dir = args.sources_dir
    try:
        results = compare_all(sources_dir, args.build_dir, provenance=provenance)
    except SourceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    ok = True
    for f, sha in results["files"].items():
        print(f"file {f}: sha256 {sha} (matches the recorded download)")
    for _, _, key, name in PROVISIONS:
        expected = provenance["derived"]["official_texts"][name]
        r = results[key]
        got = (len(r["official"]), r["candidate"]["official_text_sha256"], r["status"])
        want = (expected["chars"], expected["official_text_sha256"], expected["match_status"])
        ok &= got == want
        print(f"{'OK  ' if got == want else 'DIFF'} {name}: {got[0]} chars, "
              f"official_text_sha256 {got[1]}, {got[2]}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
