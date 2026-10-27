import json
from pathlib import Path

from scripts.dashboard import build_dashboard


def test_build_dashboard_creates_html(tmp_path: Path):
    # prepare fake aggregated JSON
    agg_dir = tmp_path / "examples" / "outputs" / "aggregated"
    agg_dir.mkdir(parents=True, exist_ok=True)
    agg = {
        "pypdf": [
            {
                "file": str(agg_dir / "pypdf" / "sample_metadata.json"),
                "data": {"n_pages": 3, "metadata": {"Title": None}},
            }
        ]
    }
    agg_file = agg_dir / "combined_metadata.json"
    agg_file.write_text(json.dumps(agg), encoding="utf-8")

    out = build_dashboard(agg_file, agg_dir / "dashboard.html")
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "PDF Toolkit — Aggregated metadata" in html
    # new UI elements
    assert 'id="export-csv"' in html
    assert 'id="summary-chart"' in html
    assert 'id="download-chart"' in html
    # sample row should include data-fonts attribute when present
    assert "data-fonts" in html or "data-attachments" in html
