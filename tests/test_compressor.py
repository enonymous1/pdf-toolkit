"""Compressor tests, run against the shipped sample PDF."""

from pathlib import Path

import pytest

from pdf_toolkit.compressor import (
    compress_ghostscript,
    compress_pdf,
    compress_pypdf,
    compress_structural,
    estimate_compression,
    find_ghostscript,
    find_pdfs,
    format_size,
    quick_inspect,
)
from scripts.generate_sample_pdf import make_sample_pdf


@pytest.fixture()
def sample(tmp_path: Path) -> Path:
    return make_sample_pdf(str(tmp_path / "sample.pdf"))


def test_quick_inspect_and_estimate(sample: Path):
    info = quick_inspect(sample)
    assert info["page_count"] == 3
    assert info["file_size"] > 0
    assert info["image_count"] >= 0
    assert info["object_count"] > 0
    assert estimate_compression(info) in (
        "Estimated High (50% or more)",
        "Estimated Moderate (20-40%)",
        "Estimated Low (5-10%)",
    )
    assert estimate_compression({}) == "Unknown"


def test_format_size_and_find_pdfs(tmp_path: Path, sample: Path):
    assert format_size(500) == "500 B"
    assert format_size(2048) == "2.00 KB"
    assert find_pdfs(sample) == [sample]
    assert find_pdfs(tmp_path / "missing.txt") == []
    other = tmp_path / "note.txt"
    other.write_text("not a pdf", encoding="utf-8")
    assert find_pdfs(other) == []
    # A directory listing excludes its own *_compressed.pdf output.
    compressed = tmp_path / "sample_compressed.pdf"
    compressed.write_bytes(b"%PDF-")
    found = [p.name for p in find_pdfs(tmp_path)]
    assert "sample.pdf" in found
    assert "sample_compressed.pdf" not in found


def test_structural_compression_round_trip(sample: Path, tmp_path: Path):
    out = tmp_path / "out_structural.pdf"
    result = compress_structural(sample, out)
    assert result.success, result.error
    assert out.exists() and out.stat().st_size > 0
    assert result.initial_size == sample.stat().st_size
    assert result.final_size == out.stat().st_size
    assert result.method == "structural"
    # The output is still a valid, readable PDF.
    assert quick_inspect(out)["page_count"] == 3


def test_pypdf_compression_round_trip(sample: Path, tmp_path: Path):
    out = tmp_path / "out_pypdf.pdf"
    result = compress_pypdf(sample, out)
    assert result.success, result.error
    assert out.exists()
    assert quick_inspect(out)["page_count"] == 3
    # Metadata is kept by default.
    import fitz

    assert fitz.open(str(out)).metadata is not None


def test_compress_dispatch_and_unknown_method(sample: Path, tmp_path: Path):
    out = tmp_path / "out_dispatch.pdf"
    result = compress_pdf(sample, out, "pypdf")
    assert result.success and result.method == "pypdf"
    with pytest.raises(ValueError):
        compress_pdf(sample, tmp_path / "x.pdf", "nope")


def test_compress_missing_input(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        compress_structural(tmp_path / "missing.pdf", tmp_path / "out.pdf")
    txt = tmp_path / "x.txt"
    txt.write_text("not a pdf", encoding="utf-8")
    with pytest.raises(ValueError):
        compress_structural(txt, tmp_path / "out.pdf")


def test_ghostscript_reports_missing_binary_or_works(sample: Path, tmp_path: Path):
    out = tmp_path / "out_gs.pdf"
    result = compress_ghostscript(sample, out, quality="ebook")
    if find_ghostscript() is None:
        assert not result.success
        assert "Ghostscript" in (result.error or "")
    else:
        assert result.success, result.error
        assert quick_inspect(out)["page_count"] == 3


def test_ghostscript_rejects_bad_quality(sample: Path, tmp_path: Path):
    with pytest.raises(ValueError):
        compress_ghostscript(sample, tmp_path / "out.pdf", quality="ultra")
