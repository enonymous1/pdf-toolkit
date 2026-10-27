"""Cross-library page extraction, against the shipped sample PDF."""

import importlib
from pathlib import Path

import pytest
from pypdf import PdfReader

from scripts.generate_sample_pdf import make_sample_pdf

LIBS = ["pypdf", "pymupdf", "pdfminer", "pdfplumber"]


@pytest.fixture()
def sample(tmp_path: Path) -> Path:
    return make_sample_pdf(str(tmp_path / "sample.pdf"))


@pytest.mark.parametrize("libname", LIBS)
def test_extract_first_page_from_sample(libname: str, sample: Path, tmp_path: Path):
    mod = importlib.import_module(f"examples.{libname}.extract_pages")
    out = tmp_path / f"{libname}_page1.pdf"
    mod.extract_pages(str(sample), str(out), 0, 0)
    assert out.exists()
    assert len(PdfReader(str(out)).pages) == 1


@pytest.mark.parametrize("libname", LIBS)
def test_extract_three_pages_from_sample(libname: str, sample: Path, tmp_path: Path):
    mod = importlib.import_module(f"examples.{libname}.extract_pages")
    out = tmp_path / f"{libname}_pages_1-3.pdf"
    mod.extract_pages(str(sample), str(out), 0, 2)
    assert out.exists()
    assert len(PdfReader(str(out)).pages) == 3
