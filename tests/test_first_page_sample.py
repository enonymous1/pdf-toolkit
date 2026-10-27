"""First-page extraction, against the shipped sample PDF.

Replaces the old test that required a private ``ext_res`` PDF. Output
goes to ``tmp_path`` so the repo's example outputs stay clean.
"""

from pathlib import Path

import fitz

from examples.pymupdf.extract_first_page import extract_first_page
from scripts.generate_sample_pdf import make_sample_pdf


def test_extract_first_page_from_sample(tmp_path: Path):
    src = make_sample_pdf(str(tmp_path / "sample.pdf"))
    out = tmp_path / "first_page.pdf"
    out_path = extract_first_page(str(src), str(out))
    assert out_path.exists()
    assert fitz.open(str(out_path)).page_count == 1
    assert fitz.open(str(src)).page_count == 3
