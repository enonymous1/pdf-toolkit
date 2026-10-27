"""Adapter tests against the shipped sample PDF (no external fixture)."""

from pathlib import Path

import pytest

from pdf_toolkit.inspector.adapters.pdfminer import PDFMinerAdapter
from pdf_toolkit.inspector.adapters.pdfplumber import PDFPlumberAdapter
from pdf_toolkit.inspector.adapters.pymupdf import PyMuPDFAdapter
from pdf_toolkit.inspector.adapters.pypdf import PyPDFAdapter
from scripts.generate_sample_pdf import make_sample_pdf

ADAPTERS = [PyMuPDFAdapter, PyPDFAdapter, PDFMinerAdapter, PDFPlumberAdapter]


@pytest.fixture()
def sample(tmp_path: Path) -> Path:
    return make_sample_pdf(str(tmp_path / "sample.pdf"))


@pytest.mark.parametrize("adapter_cls", ADAPTERS)
def test_adapters_report_three_pages_and_text(sample: Path, adapter_cls):
    with adapter_cls(str(sample)) as adapter:
        assert adapter.get_page_count() == 3
        text = adapter.extract_text()
        assert "Sample PDF" in text
        meta = adapter.get_metadata()
        assert isinstance(meta, dict)
        # get_toc must accept the shared signature without raising.
        toc = adapter.get_toc(use_ocr=False, hint_page=1)
        assert isinstance(toc, list)


def test_pymupdf_metadata_includes_scanning(sample: Path):
    with PyMuPDFAdapter(str(sample)) as adapter:
        meta = adapter.get_metadata()
        assert meta["library"] == "PyMuPDF"
        assert "scanned_page_ratio" in meta
        assert "document_type" in meta


def test_missing_file_raises(sample: Path, tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        PyMuPDFAdapter(str(tmp_path / "missing.pdf"))
