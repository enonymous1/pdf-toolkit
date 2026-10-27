import json
from pathlib import Path

from scripts.collect_metadata import collect, write_reports


def test_aggregator_creates_reports(tmp_path: Path):
    # create a fake metadata file for one lib
    out = tmp_path / "examples" / "pypdf" / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    # write a small fake metadata JSON into the outputs folder (aggregator reads files)
    fake = {
        "n_pages": 3,
        "metadata": {"Title": None, "Author": None, "PDFVersion": None, "IsEncrypted": None},
        "details": {"page_count": 3, "text_length": 100, "image_count": 0, "fonts": None},
    }
    f = out / "sample_metadata.json"
    f.write_text(json.dumps(fake), encoding="utf-8")

    collected = collect(Path(tmp_path))
    json_path, csv_path = write_reports(collected, tmp_path / "reports")
    assert json_path.exists()
    assert csv_path.exists()
