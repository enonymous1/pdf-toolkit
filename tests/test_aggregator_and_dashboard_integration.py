import json
import shutil
from pathlib import Path

from scripts import collect_metadata, dashboard

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def _make_lib_output(lib_name: str, tmp_md: bool = True):
    lib_out = EXAMPLES / lib_name / "outputs"
    lib_out.mkdir(parents=True, exist_ok=True)
    # write a minimal normalized metadata JSON
    payload = {
        "n_pages": 2,
        "metadata": {"Title": f"Test PDF ({lib_name})", "Author": "CI"},
        "raw_metadata": {},
        "details": {"text_length": 123, "image_count": 1, "fonts": ["TestFont"]},
        "attachments": [],
    }
    js_path = lib_out / f"{lib_name}_metadata_test.json"
    js_path.write_text(json.dumps(payload), encoding="utf-8")

    if tmp_md:
        # dashboard expects a markdown file named <json-stem>_metadata.md,
        # e.g. `_int_lib_a_metadata_test_metadata.md` for the JSON we create above.
        md_fname = f"{lib_name}_metadata_test_metadata.md"
        md_path = lib_out / md_fname
        md_path.write_text(f"# Metadata for {lib_name}\n- pages: 2\n", encoding="utf-8")
    return js_path


def test_collect_and_dashboard_end_to_end(tmp_path):
    # create two fake library metadata entries under examples/
    libs = ["_int_lib_a", "_int_lib_b"]
    created = []
    try:
        for lib_name in libs:
            created.append(_make_lib_output(lib_name))

        # collect metadata from the repository examples/ tree
        collected = collect_metadata.collect(ROOT)
        # should contain our two test libs
        assert "_int_lib_a" in collected
        assert "_int_lib_b" in collected

        # write aggregated reports to a temporary directory
        agg_dir = tmp_path / "aggregated"
        json_path, csv_path = collect_metadata.write_reports(collected, agg_dir)
        assert json_path.exists()
        assert csv_path.exists()

        # basic content checks
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert "_int_lib_a" in data and "_int_lib_b" in data
        # CSV should contain header and two rows
        csv_text = csv_path.read_text(encoding="utf-8")
        assert "library" in csv_text
        assert "_int_lib_a" in csv_text

        # build dashboard from the aggregated JSON and verify output
        out_html = tmp_path / "dashboard.html"
        dashboard.build_dashboard(json_path, out_html)
        assert out_html.exists()
        html = out_html.read_text(encoding="utf-8")
        # expected pieces
        assert "PDF Toolkit — Aggregated metadata" in html
        assert "Test PDF (_int_lib_a)" in html
        assert "# Metadata for _int_lib_a" in html
    finally:
        # cleanup the fake libs we created under examples/
        for lib_name in libs:
            d = EXAMPLES / lib_name
            if d.exists():
                shutil.rmtree(d)
