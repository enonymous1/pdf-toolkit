from pathlib import Path

import fitz
import pytest

from examples.pdfminer.extract_pages import extract_pages


def test_pdfminer_extract_single_and_range(tmp_path: Path):
    src = Path("examples") / "sample_example.pdf"
    out = tmp_path / "out_single.pdf"
    p = extract_pages(str(src), str(out), 0, 0)
    assert p.exists() and fitz.open(str(p)).page_count == 1

    out2 = tmp_path / "out_range.pdf"
    p2 = extract_pages(str(src), str(out2), 0, 2)
    assert fitz.open(str(p2)).page_count == 3

    total = fitz.open(str(src)).page_count
    with pytest.raises(ValueError):
        extract_pages(str(src), str(tmp_path / "bad.pdf"), total, total + 5)
