import json
from pathlib import Path


def test_metadata_and_markdown_written(tmp_path: Path):
    # generate sample in tmp and run pymupdf extractor in metadata-only mode
    sample = tmp_path / "sample.pdf"
    # reuse the project generator to create a sample in repo then copy
    from scripts.generate_sample_pdf import make_sample_pdf

    make_sample_pdf(str(sample))
    # call the metadata-only CLI for pymupdf
    outdir = tmp_path / "examples" / "pymupdf" / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)

    from examples.pymupdf.metadata import read_metadata

    meta = read_metadata(str(sample))
    json_out = outdir / "sample_metadata.json"
    json_out.write_text(json.dumps(meta), encoding="utf-8")

    # also create markdown using helper
    from pdf_toolkit.inspector import metadata_to_markdown

    md_out = outdir / "sample_metadata.md"
    md_out.write_text(metadata_to_markdown(meta), encoding="utf-8")

    assert json_out.exists()
    assert md_out.exists()
    # basic sanity checks
    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert data.get("n_pages") == 3
    assert "details" in data
    assert md_out.read_text(encoding="utf-8").startswith("# PDF metadata")
