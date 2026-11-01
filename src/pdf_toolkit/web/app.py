"""Flask frontend: upload a PDF, inspect it, compress it, download it.

Routes (live mode):

- ``GET /`` — upload form (drag-and-drop or browse).
- ``POST /upload`` — store the PDF, redirect to its file page.
- ``GET /file/<id>`` — inspection summary plus a compress form.
- ``POST /file/<id>/compress`` — compress with the chosen method,
  show the result page.
- ``GET /download/<id>`` — download the compressed file.

Demo mode (``create_app(demo=True)`` or ``pdf-toolkit web --demo``)
serves no uploads at all: ``/demo/sample`` and
``/demo/sample/compressed`` render the seeded data from
:mod:`pdf_toolkit.web.demo_data`, labelled as demo data in the UI.
There is deliberately no demo download: a frozen demo must not
promise a file it cannot produce.

Freeze (``freeze_demo``): renders the demo routes with Flask's
test client and writes static HTML. Frozen pages are requested
with ``?frozen=1`` so their forms render disabled with a note that
the frozen Pages demo is view-only, instead of presenting forms
that cannot submit as if they worked. The frozen site is meant to
be served from a site root (the Pages workflow deploys the frozen
directory as the whole site), so templates use ``url_for`` absolute
paths; do not drop the frozen output into a subpath and expect its
links to follow.

Uploaded files live only under the configured upload directory
(a fresh temp directory by default). Download and file routes
resolve their paths and refuse anything that escapes it, the same
confinement pattern as the dissect preview server.
"""

from __future__ import annotations

import io
import tempfile
import uuid
from pathlib import Path
from typing import Any

from .demo_data import DEMO_COMPRESS, DEMO_ESTIMATE, DEMO_INSPECT

__all__ = ["LOOPBACK_HOSTS", "create_app", "freeze_demo", "run_server"]


LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _require_flask():
    from .._optional import require_module

    flask = require_module("flask", extra="web", purpose="The web frontend")
    return (
        flask.Flask,
        flask.abort,
        flask.redirect,
        flask.render_template,
        flask.request,
        flask.send_file,
        flask.url_for,
    )


def _safe_name(name: str) -> str:
    """Reduce an uploaded filename to a safe basename, no directories."""
    base = Path(name).name.strip()
    kept = "".join(ch for ch in base if ch.isalnum() or ch in "._-")
    return kept or "upload.pdf"


def _resolve_within(root: Path, rel: str) -> Path | None:
    candidate = (root / rel).resolve()
    if not candidate.is_relative_to(root):
        return None
    return candidate


def _inspect_summary(path: Path) -> dict[str, Any] | None:
    from ..compressor.inspect import estimate_compression, quick_inspect

    info = quick_inspect(path)
    if not info:
        return None
    info["estimate"] = estimate_compression(info)
    return info


def _demo_pdf_bytes() -> bytes:
    """A tiny one-page PDF for the live demo download, built in memory.

    Only used by the live demo server's download route, which the
    frozen demo deliberately does not link to. Built with PyMuPDF
    (a core dependency), so demo mode needs no fixture file.
    """
    import pymupdf

    doc = pymupdf.open()
    try:
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            "pdf-toolkit demo sample (mock data).\n"
            "This file stands in for a compressed result in demo mode.",
        )
        return doc.tobytes()
    finally:
        doc.close()


def create_app(upload_dir: str | Path | None = None, demo: bool = False):
    """Create the web app.

    ``upload_dir`` defaults to a fresh temp directory; pass one
    explicitly in tests so uploaded files can be inspected. ``demo``
    switches the app to seeded fixture data (no uploads processed).
    """
    Flask, abort, redirect, render_template, request, send_file, url_for = _require_flask()
    template_dir = Path(__file__).parent / "templates"
    app = Flask(__name__, template_folder=str(template_dir))
    upload_path = (
        Path(upload_dir) if upload_dir else Path(tempfile.mkdtemp(prefix="pdf-toolkit-web-"))
    )
    upload_path.mkdir(parents=True, exist_ok=True)
    app.config["WEB_UPLOAD_DIR"] = upload_path
    app.config["WEB_DEMO"] = demo
    app.config[
        "WEB_FILES"
    ] = {}  # file_id -> {"path": Path, "name": str, "compressed": Path | None}

    def _frozen() -> bool:
        return request.args.get("frozen") == "1"

    @app.route("/")
    def index():
        return render_template(
            "index.html", demo=demo, frozen=_frozen(), files=app.config["WEB_FILES"]
        )

    @app.route("/upload", methods=["POST"])
    def upload():
        if demo:
            abort(404)
        uploaded = request.files.get("pdf")
        if uploaded is None or not uploaded.filename:
            return render_template(
                "index.html",
                demo=False,
                frozen=False,
                files=app.config["WEB_FILES"],
                error="Choose a PDF file to upload.",
            ), 400
        name = _safe_name(uploaded.filename)
        if not name.lower().endswith(".pdf"):
            return render_template(
                "index.html",
                demo=False,
                frozen=False,
                files=app.config["WEB_FILES"],
                error="Only .pdf files are accepted.",
            ), 400
        file_id = uuid.uuid4().hex[:12]
        stored = upload_path / f"{file_id}_{name}"
        uploaded.save(str(stored))
        app.config["WEB_FILES"][file_id] = {
            "path": stored,
            "name": name,
            "compressed": None,
        }
        return redirect(url_for("file_page", file_id=file_id))

    @app.route("/file/<file_id>")
    def file_page(file_id):
        entry = app.config["WEB_FILES"].get(file_id)
        if entry is None:
            abort(404)
        info = _inspect_summary(entry["path"])
        if info is None:
            return render_template(
                "index.html",
                demo=False,
                frozen=False,
                files=app.config["WEB_FILES"],
                error=f"Could not read {entry['name']} as a PDF.",
            ), 400
        from ..compressor import METHODS

        return render_template(
            "file.html",
            demo=False,
            frozen=_frozen(),
            file_id=file_id,
            name=entry["name"],
            info=info,
            methods=METHODS,
            compressed=entry["compressed"] is not None,
        )

    @app.route("/file/<file_id>/compress", methods=["POST"])
    def compress_file(file_id):
        from ..compressor import METHODS, compress_pdf

        entry = app.config["WEB_FILES"].get(file_id)
        if entry is None:
            abort(404)
        method = request.form.get("method", "structural")
        if method not in METHODS:
            abort(400)
        target = upload_path / f"{file_id}_compressed.pdf"
        result = compress_pdf(entry["path"], target, method)
        if result.success:
            entry["compressed"] = target
        return render_template(
            "compressed.html",
            demo=False,
            frozen=False,
            file_id=file_id,
            name=entry["name"],
            result=result,
        )

    @app.route("/download/<file_id>")
    def download(file_id):
        entry = app.config["WEB_FILES"].get(file_id)
        if entry is None or entry["compressed"] is None:
            abort(404)
        resolved = _resolve_within(upload_path, entry["compressed"].name)
        if resolved is None or not resolved.is_file():
            abort(404)
        return send_file(
            resolved, as_attachment=True, download_name=f"{Path(entry['name']).stem}_compressed.pdf"
        )

    @app.route("/demo/sample")
    def demo_sample():
        from ..compressor import METHODS

        return render_template(
            "file.html",
            demo=True,
            frozen=_frozen(),
            file_id="demo-sample",
            name=DEMO_INSPECT["name"],
            info={**DEMO_INSPECT, "estimate": DEMO_ESTIMATE},
            methods=METHODS,
            compressed=False,
            demo_compress_url="/demo/sample/compress",
        )

    @app.route("/demo/sample/compress", methods=["POST"])
    def demo_compress():
        return render_template(
            "compressed.html",
            demo=True,
            frozen=False,
            file_id="demo-sample",
            name=DEMO_INSPECT["name"],
            result=_DemoResult(DEMO_COMPRESS),
        )

    @app.route("/demo/sample/compressed")
    def demo_compressed():
        # GET twin of the compress result, so the frozen demo can
        # link to a result page without submitting a form.
        return render_template(
            "compressed.html",
            demo=True,
            frozen=_frozen(),
            file_id="demo-sample",
            name=DEMO_INSPECT["name"],
            result=_DemoResult(DEMO_COMPRESS),
        )

    @app.route("/demo/sample/download")
    def demo_download():
        # Live demo server only; the frozen demo never links here.
        return send_file(
            io.BytesIO(_demo_pdf_bytes()),
            as_attachment=True,
            download_name="sample_example_compressed.pdf",
            mimetype="application/pdf",
        )

    return app


class _DemoResult:
    """Duck-typed stand-in for CompressionResult for seeded demo data.

    Templates only read ``success``, ``method``, ``initial_size``,
    ``final_size``, ``saved_bytes``, ``reduction_pct`` and ``error``,
    so the demo does not need to construct a real result object.
    """

    def __init__(self, data: dict[str, Any]):
        self.success = data["success"]
        self.method = data["method"]
        self.initial_size = data["initial_size"]
        self.final_size = data["final_size"]
        self.saved_bytes = data["saved_bytes"]
        self.reduction_pct = data["reduction_pct"]
        self.error = data["error"]


def freeze_demo(out_dir: str | Path) -> list[str]:
    """Render the demo routes to static HTML under *out_dir*.

    Returns the list of written paths, relative to *out_dir*.
    Frozen pages are requested with ``?frozen=1`` (see the module
    docstring) and written without the query string.
    """
    app = create_app(demo=True)
    client = app.test_client()
    routes = [
        ("/?frozen=1", "index.html"),
        ("/demo/sample?frozen=1", "demo/sample/index.html"),
        ("/demo/sample/compressed?frozen=1", "demo/sample/compressed/index.html"),
    ]
    out = Path(out_dir)
    written = []
    for url, rel in routes:
        response = client.get(url)
        if response.status_code != 200:
            raise RuntimeError(f"Freezing {url} failed with status {response.status_code}")
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.data)
        written.append(rel)
    return written


def run_server(
    upload_dir: str | Path | None = None,
    host: str = "127.0.0.1",
    port: int = 5000,
    allow_remote: bool = False,
    demo: bool = False,
) -> None:
    """Serve the web frontend on loopback (default).

    The server has no authentication, so a non-loopback host is
    refused unless ``allow_remote`` is explicitly set. The guard
    runs before Flask is even imported, so it works (and fails
    fast) on a machine without the web extra installed.
    """
    if host not in LOOPBACK_HOSTS and not allow_remote:
        raise ValueError(
            f"Refusing to bind the unauthenticated web server to {host!r}. "
            "Use host 127.0.0.1 (the default), or pass allow_remote=True "
            "if you really mean to expose it."
        )
    create_app(upload_dir=upload_dir, demo=demo).run(host=host, port=port)
