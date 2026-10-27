from pathlib import Path

from examples.pymupdf.extract_text import extract_text
from examples.pymupdf.render_page import render_page_to_png
from scripts.generate_sample_pdf import make_sample_pdf


def test_pymupdf_text_and_render(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    make_sample_pdf(str(pdf))

    txt = extract_text(str(pdf))
    assert "Sample PDF" in txt

    out = tmp_path / "page0.png"
    render_page_to_png(str(pdf), page_no=0, out_path=str(out))
    assert out.exists() and out.stat().st_size > 0


def test_pymupdf_metadata(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    make_sample_pdf(str(pdf))

    from examples.pymupdf.metadata import read_metadata

    meta = read_metadata(str(pdf))
    assert meta["n_pages"] == 3
    for k in (
        "Title",
        "Author",
        "Subject",
        "Keywords",
        "Creator",
        "Producer",
        "CreationDate",
        "ModDate",
        "Trapped",
        "Format",
        "PDFVersion",
        "IsEncrypted",
        "Permissions",
        "XMP",
        "ObjectCount",
    ):
        assert k in meta["metadata"]
    assert "raw_metadata" in meta
    # details should include page_sizes and text_length
    assert "details" in meta
    assert meta["details"]["page_count"] == 3
    assert meta["details"]["text_length"] > 0
    assert isinstance(meta["details"]["page_sizes"], list)
