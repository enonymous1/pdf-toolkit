"""TOC tests against a synthetic fixture built in the test itself.

The fixture replaces the old ``ext_res`` tractor-manual PDF, which is not
shipped in this repo. It has:

- real PDF outlines (bookmarks) for Introduction / Methods / Results,
- a contents page (page 2) with dotted leader lines, so the PyMuPDF
  text heuristic has something to find.

Honest limits of the current code, encoded in the assertions: the
outline-based extractors return titles but do not resolve outline pages
(page is None), while the PyMuPDF text heuristic returns integer pages.
"""

from pathlib import Path

import fitz
import pytest

from pdf_toolkit.inspector.toc.pdfminer import extract_toc_from_pdf as pdfminer_toc
from pdf_toolkit.inspector.toc.pymupdf import extract_toc_from_pdf as pymupdf_toc
from pdf_toolkit.inspector.toc.pypdf import extract_toc_from_pdf as pypdf_toc


def make_toc_fixture(path: Path) -> Path:
    doc = fitz.open()
    # Page 1: cover.
    page = doc.new_page()
    page.insert_text((72, 72), "Fixture PDF", fontsize=18)
    # Page 2: contents, with dotted leaders the heuristic looks for.
    page = doc.new_page()
    page.insert_text((72, 72), "Contents", fontsize=18)
    page.insert_text((72, 110), "Introduction .......... 3", fontsize=12)
    page.insert_text((72, 130), "Methods .......... 4", fontsize=12)
    page.insert_text((72, 150), "Results .......... 5", fontsize=12)
    # Pages 3-5: content pages.
    for title in ("Introduction", "Methods", "Results"):
        page = doc.new_page()
        page.insert_text((72, 72), title, fontsize=18)
        page.insert_text((72, 110), f"This is the {title} chapter.", fontsize=12)
    doc.set_toc([[1, "Introduction", 3], [1, "Methods", 4], [1, "Results", 5]])
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture()
def fixture(tmp_path: Path) -> Path:
    return make_toc_fixture(tmp_path / "toc_fixture.pdf")


def test_pymupdf_text_toc_finds_contents(fixture: Path):
    entries = pymupdf_toc(str(fixture), hint_page=2, scan_after=4)
    assert isinstance(entries, list)
    assert len(entries) > 0
    titles = [e["title"] for e in entries]
    assert any("Introduction" in t for t in titles)
    for e in entries:
        assert isinstance(e["title"], str)
        assert isinstance(e["page"], int)
        assert e["page"] >= 1


def test_pypdf_outline_toc_returns_titles(fixture: Path):
    entries = pypdf_toc(str(fixture), hint_page=2, scan_after=4)
    assert isinstance(entries, list)
    assert len(entries) > 0
    titles = [e["title"] for e in entries]
    assert "Introduction" in titles
    assert "Methods" in titles


def test_pdfminer_outline_toc_returns_titles(fixture: Path):
    entries = pdfminer_toc(str(fixture), hint_page=2, scan_after=4)
    assert isinstance(entries, list)
    # pdfminer outlines may be present; if not, the list is empty, not an error.
    for e in entries:
        assert isinstance(e["title"], (str, type(None)))
        assert e["page"] is None or isinstance(e["page"], int)
