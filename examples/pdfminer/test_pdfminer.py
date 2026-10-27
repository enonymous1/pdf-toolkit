from pathlib import Path

from examples.pdfminer.extract_text import extract_text
from scripts.generate_sample_pdf import make_sample_pdf


def test_pdfminer_extracts_text(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    make_sample_pdf(str(pdf))

    txt = extract_text(str(pdf))
    assert "Sample PDF" in txt


def test_pdfminer_metadata(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    make_sample_pdf(str(pdf))

    from examples.pdfminer.metadata import read_metadata

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
    assert "details" in meta
    assert meta["details"]["page_count"] == 3
    assert meta["details"]["text_length"] > 0
