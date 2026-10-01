from collections.abc import Callable
from pathlib import Path

import pymupdf
import pytest

PdfWriter = Callable[[Path, list[list[str] | None]], Path]


@pytest.fixture(autouse=True)
def no_model_downloads(monkeypatch):
    """Keep Hugging Face offline in every test: an accidental real model load
    fails fast instead of downloading. Tests use fake encoders; the opt-in
    real-model test reads the local cache only."""
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")


@pytest.fixture
def write_pdf() -> PdfWriter:
    """Create a synthetic PDF.

    Each entry of `pages` is one page: a list of text lines (placed far apart,
    so PyMuPDF extracts each as its own block), [] for a blank page, or None
    for an image-only page that simulates a scanned page.
    """

    def _write(path: Path, pages: list[list[str] | None]) -> Path:
        pdf = pymupdf.open()
        for lines in pages:
            page = pdf.new_page()
            if lines is None:
                pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 8, 8), False)
                pixmap.clear_with(128)
                page.insert_image(pymupdf.Rect(72, 72, 300, 300), pixmap=pixmap)
                continue
            for i, line in enumerate(lines):
                page.insert_text((72, 72 + 60 * i), line)
        path.parent.mkdir(parents=True, exist_ok=True)
        pdf.save(path)
        pdf.close()
        return path

    return _write
