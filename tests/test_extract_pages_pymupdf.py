from pathlib import Path

import fitz
import pytest

from examples.pymupdf.extract_pages import extract_pages


def test_extract_single_page(tmp_path: Path):
    src = Path("examples") / "sample_example.pdf"
    assert src.exists()
    out = tmp_path / "out_single.pdf"
    p = extract_pages(str(src), str(out), 0, 0)
    assert p.exists()
    assert fitz.open(str(p)).page_count == 1


def test_extract_range(tmp_path: Path):
    src = Path("examples") / "sample_example.pdf"
    out = tmp_path / "out_range.pdf"
    p = extract_pages(str(src), str(out), 0, 2)
    assert p.exists()
    assert fitz.open(str(p)).page_count == 3


def test_extract_out_of_bounds_raises(tmp_path: Path):
    src = Path("examples") / "sample_example.pdf"
    out = tmp_path / "bad.pdf"
    total = fitz.open(str(src)).page_count
    with pytest.raises(ValueError):
        extract_pages(str(src), str(out), total, total + 5)
