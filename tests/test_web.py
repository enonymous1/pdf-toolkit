"""Tests for the Flask web frontend (``pdf-toolkit web``).

Flask is an optional extra, so the whole module skips without it —
the same pattern as the other extra-gated test modules. Live-mode
tests use the repo's sample PDF; demo tests assert the seeded
fixture data renders, labelled as demo data.
"""

from __future__ import annotations

from pathlib import Path

import pytest

flask = pytest.importorskip("flask")

from pdf_toolkit.web import create_app, freeze_demo  # noqa: E402
from pdf_toolkit.web.demo_data import (  # noqa: E402
    DEMO_COMPRESS,
    DEMO_INSPECT,
)

SAMPLE = Path(__file__).parent.parent / "examples" / "sample_example.pdf"


@pytest.fixture()
def live_client(tmp_path):
    app = create_app(upload_dir=tmp_path)
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture()
def demo_client():
    app = create_app(demo=True)
    app.config["TESTING"] = True
    return app.test_client()


def test_index_renders_upload_form(live_client):
    response = live_client.get("/")
    assert response.status_code == 200
    assert b"Upload and inspect" in response.data
    assert b"Demo data" not in response.data


def test_upload_inspect_compress_download(live_client, tmp_path):
    data = {"pdf": (SAMPLE.open("rb"), SAMPLE.name)}
    response = live_client.post(
        "/upload", data=data, content_type="multipart/form-data", follow_redirects=False
    )
    assert response.status_code == 302
    file_url = response.headers["Location"]
    assert file_url.startswith("/file/")
    page = live_client.get(file_url)
    assert page.status_code == 200
    assert SAMPLE.name.encode() in page.data
    assert b"Pages" in page.data

    file_id = file_url.rsplit("/", 1)[-1]
    result = live_client.post(f"/file/{file_id}/compress", data={"method": "structural"})
    assert result.status_code == 200
    assert b"Compression result" in result.data

    download = live_client.get(f"/download/{file_id}")
    assert download.status_code == 200
    assert download.data[:5] == b"%PDF-"


def test_upload_rejects_non_pdf(live_client):
    import io

    response = live_client.post(
        "/upload",
        data={"pdf": (io.BytesIO(b"not a pdf"), "notes.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert b"Only .pdf files" in response.data


def test_unknown_file_404(live_client):
    assert live_client.get("/file/nope").status_code == 404
    assert live_client.get("/download/nope").status_code == 404


def test_demo_sample_renders_seeded_data(demo_client):
    response = demo_client.get("/demo/sample")
    assert response.status_code == 200
    assert b"Demo data" in response.data
    assert DEMO_INSPECT["name"].encode() in response.data
    assert str(DEMO_INSPECT["page_count"]).encode() in response.data


def test_demo_compress_renders_seeded_result(demo_client):
    response = demo_client.post("/demo/sample/compress", data={"method": "structural"})
    assert response.status_code == 200
    assert b"Demo data" in response.data
    assert str(DEMO_COMPRESS["initial_size"]).encode() in response.data


def test_demo_values_are_real_measurements():
    # The demo fixture must be a real measurement of the sample PDF,
    # not placeholder zeros: if the sample changes, update demo_data
    # from a real quick_inspect run instead of inventing numbers.
    assert DEMO_INSPECT["page_count"] > 0
    assert DEMO_INSPECT["file_size"] > 0
    assert DEMO_COMPRESS["initial_size"] == DEMO_INSPECT["file_size"]
    assert DEMO_COMPRESS["success"] is True


def test_freeze_demo_writes_static_pages(tmp_path):
    written = freeze_demo(tmp_path)
    assert written == [
        "index.html",
        "demo/sample/index.html",
        "demo/sample/compressed/index.html",
        "demo/sample/sample.pdf",
    ]
    frozen_pdf = tmp_path / "demo/sample/sample.pdf"
    assert frozen_pdf.read_bytes()[:5] == b"%PDF-"
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Frozen demo" in index
    assert "Upload and inspect" not in index
    sample = (tmp_path / "demo/sample/index.html").read_text(encoding="utf-8")
    assert "Frozen demo" in sample
    assert DEMO_INSPECT["name"] in sample
    compressed = (tmp_path / "demo/sample/compressed/index.html").read_text(encoding="utf-8")
    assert "Frozen demo" in compressed
    # Project Pages serves the site under /<repo>/, so absolute links
    # ("/demo/sample") resolve off-site and 404. Frozen links must be
    # page-relative: index -> sample, sample -> compressed and home,
    # compressed -> sample and home.
    for page in (index, sample, compressed):
        assert 'href="/' not in page
    assert 'href="demo/sample/"' in index
    assert 'href="compressed/"' in sample
    assert 'href="../../"' in sample
    assert 'href="../"' in compressed
    assert 'href="../../../"' in compressed


def test_pages_are_theme_aware(live_client, demo_client):
    # System-theme media query plus a toggle that remembers the
    # choice in localStorage, on live and demo pages alike.
    for client in (live_client, demo_client):
        page = client.get("/" if client is live_client else "/demo/sample")
        assert b"prefers-color-scheme: dark" in page.data
        assert b"pdf-toolkit-theme" in page.data
        assert b"Toggle dark mode" in page.data


def test_demo_sample_pdf_route(demo_client):
    response = demo_client.get("/demo/sample.pdf")
    assert response.status_code == 200
    assert response.data[:5] == b"%PDF-"
    assert "application/pdf" in response.content_type


def test_demo_sample_page_embeds_source_pdf(demo_client):
    page = demo_client.get("/demo/sample")
    assert b'<embed class="pdf-embed" src="/demo/sample.pdf"' in page.data


def test_frozen_sample_page_embeds_relative_pdf(tmp_path):
    freeze_demo(tmp_path)
    sample = (tmp_path / "demo/sample/index.html").read_text(encoding="utf-8")
    assert '<embed class="pdf-embed" src="sample.pdf"' in sample


def test_run_server_refuses_non_loopback():
    from pdf_toolkit.web import run_server

    with pytest.raises(ValueError, match="Refusing to bind"):
        run_server(host="0.0.0.0")
