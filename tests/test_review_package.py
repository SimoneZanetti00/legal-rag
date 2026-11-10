"""Official-source verification for the M1 review package (tools/review_package).

Checks the archived official files (two HTML pages and three Gazzetta Ufficiale issues)
against their recorded SHA-256, and the five official texts extracted from the HTML
pages against their expected official_text_sha256.
The expected values are written here, independently of official_sources.json, so that
changing the provenance record alone cannot make the test pass. The tests skip, saying
so, only when the archived sources are not present. A mismatch fails. The archive
directory must hold exactly the files the provenance record lists, plus the record
itself and NOTICE.md.
"""

import hashlib
import shutil

import pytest

from tools.review_package.official_texts import (
    ARCHIVE_DIR,
    PROVENANCE_PATH,
    PROVISIONS,
    SourceError,
    extract_official_texts,
    file_sha256,
    load_provenance,
)

EXPECTED_FILES = {
    "gdpr_consolidated_it.html": "90d0710134489e08fc26f142c416028d2ee6f3cf049f83c084e772da3ac8d260",
    "normattiva_2bis.html": "f95c865efdc99dedd1993e993b343d1d31dbc902b72ae6992a5f3d4dcd4435ce",
    "gu_sg_2018-09-04_n205_dlgs_101_2018.pdf":
        "baa9b2eeea6f97591a0927a44ee0f2df5265466d56e471cb2f08010ba1213e97",
    "gu_sg_2018-09-12_n212_errata_corrige_18A05889.pdf":
        "1c2757c6e7a80a13156b94cdf040f1af353148fe92bb9f93c05c57f7e4d3adf9",
    "gu_sg_2018-09-27_n225_avviso_rettifica_18A06204.pdf":
        "1a676f49520d06cd4c93f56c648e69ddba78768f74c4237e3888be34ff5e7593",
}
EXPECTED_TEXTS = {  # label: (characters, official_text_sha256)
    "4": (9707, "2053253a4edb5c7693a4dcb39c87ba8018858cb9148745ed625a852f414a394b"),
    "33": (1979, "35ad52b17f064957bddf880c32e094841e7e9142c112dc0a1906e07315a420b2"),
    "34": (1805, "7ca3656e2b8e999733da88d3329f772969f667d722dd77c3a9a8c758555ffc88"),
    "55": (649, "c782e12897b6fe7cde260f76ff478177b32c6792290c5588c6767183d8ab1a54"),
    "2-bis": (225, "73c7c3bd222f87bf114e18e1c8ab1a04f5722ce888104572de4b1c85f8acc988"),
}


def require_archived_sources():
    needed = [ARCHIVE_DIR / f for f in EXPECTED_FILES] + [PROVENANCE_PATH]
    missing = [p.name for p in needed if not p.is_file()]
    if missing:
        pytest.skip(f"archived official sources unavailable: {', '.join(missing)} "
                    f"not found in {ARCHIVE_DIR}")


def test_archived_sources_and_the_five_official_texts_match_their_hashes():
    require_archived_sources()
    assert {f: file_sha256(ARCHIVE_DIR / f) for f in EXPECTED_FILES} == EXPECTED_FILES
    texts = extract_official_texts(ARCHIVE_DIR)
    extracted = {key: (len(text), hashlib.sha256(text.encode("utf-8")).hexdigest())
                 for key, (text, _) in texts.items()}
    assert extracted == EXPECTED_TEXTS
    # The provenance record states the same values.
    provenance = load_provenance()
    assert {r["file"]: r["sha256"] for r in provenance["original_files"]} == EXPECTED_FILES
    recorded = provenance["derived"]["official_texts"]
    assert {key: (recorded[name]["chars"], recorded[name]["official_text_sha256"])
            for _, _, key, name in PROVISIONS} == EXPECTED_TEXTS


def test_the_archive_directory_holds_exactly_the_recorded_files():
    # Skips only when the whole archive is absent; a missing or extra entry fails.
    if not ARCHIVE_DIR.is_dir():
        pytest.skip(f"archived official sources unavailable: {ARCHIVE_DIR} does not exist")
    assert PROVENANCE_PATH.is_file(), f"provenance record missing: {PROVENANCE_PATH}"
    sources = {r["file"] for r in load_provenance()["original_files"]}
    expected = sources | {PROVENANCE_PATH.name, "NOTICE.md"}
    actual = {p.name for p in ARCHIVE_DIR.iterdir()}  # files and directories alike
    assert actual == expected, (f"missing: {sorted(expected - actual)}; "
                                f"unexpected: {sorted(actual - expected)}")
    assert all((ARCHIVE_DIR / name).is_file() for name in expected)


def test_a_changed_archived_source_is_refused(tmp_path):
    require_archived_sources()
    for f in EXPECTED_FILES:
        shutil.copyfile(ARCHIVE_DIR / f, tmp_path / f)
    with (tmp_path / "normattiva_2bis.html").open("ab") as fh:
        fh.write(b" ")
    with pytest.raises(SourceError, match="not the recorded download"):
        extract_official_texts(tmp_path)
