"""Extract pages from a PDF as bytes, and read page text in one pass.

Ported from ss-documentDissection's ``extract.py`` / ``ingest.py``. The
original opened and re-rendered the document once per operation (and
once per page for image matching); :func:`page_texts` opens it once and
closes it, and every other entry point here opens it exactly once too.
"""

from __future__ import annotations

from pathlib import Path

import fitz

from .models import PageData

__all__ = ["ExtractionError", "extract_pages_to_bytes", "page_texts", "split_pdf_to_pages"]


class ExtractionError(Exception):
    pass


def _open(pdf_path: str | Path) -> fitz.Document:
    try:
        return fitz.open(str(pdf_path))
    except Exception as exc:
        raise ExtractionError(f"Failed to open PDF '{pdf_path}': {exc}") from exc


def page_texts(pdf_path: str | Path) -> list[PageData]:
    """Return one :class:`PageData` per page (1-based numbers), text only."""
    doc = _open(pdf_path)
    try:
        return [
            PageData(page_number=i + 1, text=doc.load_page(i).get_text("text"))
            for i in range(len(doc))
        ]
    finally:
        doc.close()


def extract_pages_to_bytes(pdf_path: str | Path, page_numbers: list[int]) -> bytes:
    """Return a new PDF (bytes) containing only the given 1-based pages."""
    if not page_numbers:
        raise ExtractionError("No page numbers provided")
    src = _open(pdf_path)
    try:
        out = fitz.open()
        for page_number in page_numbers:
            if page_number < 1 or page_number > src.page_count:
                raise ExtractionError(f"Page number out of range: {page_number}")
            out.insert_pdf(src, from_page=page_number - 1, to_page=page_number - 1)
        return out.write()
    finally:
        src.close()


def split_pdf_to_pages(pdf_path: str | Path) -> list[bytes]:
    """Split a PDF into one single-page PDF (bytes) per page."""
    src = _open(pdf_path)
    try:
        pages: list[bytes] = []
        for i in range(src.page_count):
            out = fitz.open()
            out.insert_pdf(src, from_page=i, to_page=i)
            pages.append(out.write())
        return pages
    finally:
        src.close()
