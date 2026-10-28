"""Flask preview server for reconstructed documents, confined to one root.

Ported from ss-documentDissection's ``server.py``. Fixes over the
original, which served and wrote files relative to the process working
directory with no confinement:

- The server is created by :func:`create_app` for an explicit *root*
  directory. Every file path from a request — ``/files``, thumbnails,
  ``group_dir``/``out_path`` in the POST endpoints, and the fieldmap
  ``out_path`` — is resolved and checked to stay inside that root.
  Absolute paths and ``..`` escapes are rejected (400/404).
- ``/save_fieldmap`` only writes ``.json`` files inside the root, and
  validates the payload as field boxes before writing.
- ``/fill-document`` now actually fills: it reads each fillable PDF
  as bytes, fills it with :func:`pdf_toolkit.dissect.fill.fill_pdf_fields`,
  and writes a ``filled_*.pdf`` next to it. The original passed a
  filename string where bytes were expected, so it always errored.
- ``/thumbnail`` validates its ``size`` parameter.

This is a local preview tool. It has no authentication; bind it to
loopback only (the default) and never expose it to a network.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

__all__ = ["create_app", "run_server"]


def _require_flask():
    try:
        from flask import Flask, abort, jsonify, render_template, request, send_file
    except ImportError as exc:
        raise RuntimeError(
            'The preview server needs Flask. Install it with: pip install "pdf-toolkit[dissect]"'
        ) from exc
    return Flask, abort, jsonify, render_template, request, send_file


def _resolve_within(root: Path, rel: str) -> Path | None:
    """Resolve *rel* under *root*; return None if it escapes the root."""
    candidate = (root / rel).resolve()
    if not candidate.is_relative_to(root):
        return None
    return candidate


def _resolve_out_path(root: Path, out_path: str) -> Path | None:
    """Resolve a client-supplied output path: relative, inside *root*."""
    if not out_path or Path(out_path).is_absolute():
        return None
    return _resolve_within(root, out_path)


def create_app(root: str | Path):
    """Create the preview app serving reconstructed output under *root*."""
    Flask, abort, jsonify, render_template, request, send_file = _require_flask()
    root = Path(root).resolve()
    template_dir = Path(__file__).parent / "templates"
    app = Flask(__name__, template_folder=str(template_dir))
    app.config["DISSECT_ROOT"] = root

    @app.route("/")
    def index():
        return (
            "Document Dissection Preview Server - "
            "point your browser to /index to browse reconstructed pages."
        )

    @app.route("/index")
    def index_list():
        candidates = sorted(
            set(root.glob("**/interactive/*.html")) | set(root.glob("**/html/*.html"))
        )
        groups: dict = {}
        for f in candidates:
            cur = f.parent
            group_dir = None
            for _ in range(6):
                if (cur / "images").exists() and (cur / "html").exists():
                    group_dir = cur
                    break
                if cur == root:
                    break
                cur = cur.parent
            if group_dir is None:
                group_dir = f.parent
            key = str(group_dir.relative_to(root)) if group_dir != root else "."
            page_num = None
            try:
                page_num = int("".join(ch for ch in f.name if ch.isdigit()))
            except Exception:
                pass
            img_path = None
            field_count = None
            images_dir = group_dir / "images"
            html_dir = group_dir / "html"
            if images_dir.exists() and page_num is not None:
                candidate_img = images_dir / f"page_{page_num}.png"
                if candidate_img.exists():
                    img_path = str(candidate_img.relative_to(root))
            if page_num is not None:
                fmap = html_dir / f"page_{page_num}_fieldmap.json"
                if fmap.exists():
                    try:
                        field_count = len(json.loads(fmap.read_text(encoding="utf-8")))
                    except Exception:
                        field_count = None
            groups.setdefault(key, []).append(
                {
                    "html_rel": str((html_dir / f.name).relative_to(root)),
                    "page": page_num,
                    "thumb": img_path,
                    "field_count": field_count,
                    "group_dir": key,
                }
            )
        return render_template("index.html", groups=groups)

    @app.route("/files/<path:filename>")
    def files(filename):
        resolved = _resolve_within(root, filename)
        if resolved is None or not resolved.is_file():
            abort(404)
        return send_file(resolved)

    @app.route("/thumbnail")
    def thumbnail():
        pathq = request.args.get("path")
        if not pathq:
            return jsonify({"error": "path required"}), 400
        try:
            size = int(request.args.get("size", 150))
        except ValueError:
            return jsonify({"error": "size must be an integer"}), 400
        if size < 1 or size > 2000:
            return jsonify({"error": "size must be between 1 and 2000"}), 400
        resolved = _resolve_within(root, pathq)
        if resolved is None or not resolved.exists():
            return jsonify({"error": "not found"}), 404
        try:
            from PIL import Image
        except ImportError:
            return jsonify({"error": "Pillow not installed"}), 500
        im = Image.open(str(resolved))
        im.thumbnail((size, size))
        bio = io.BytesIO()
        im.save(bio, format="JPEG")
        bio.seek(0)
        return send_file(bio, mimetype="image/jpeg")

    @app.route("/export-docx", methods=["POST"])
    def export_docx():
        payload = request.get_json() or {}
        group_dir = payload.get("group_dir")
        out_path = payload.get("out_path")
        fill = payload.get("fill")
        if not group_dir or not out_path:
            return jsonify({"error": "group_dir and out_path required"}), 400
        group_abs = _resolve_within(root, group_dir)
        out_abs = _resolve_out_path(root, out_path)
        if group_abs is None or out_abs is None:
            return jsonify({"error": "paths must stay inside the served root"}), 400
        if not group_abs.exists():
            return jsonify({"error": "group_dir not found"}), 404
        try:
            from .to_docx import export_document_to_docx
        except Exception as exc:
            return jsonify({"error": "export helper not available", "exc": str(exc)}), 500
        try:
            export_document_to_docx(str(group_abs), str(out_abs), fill_data=fill)
        except Exception as exc:
            return jsonify({"error": "export failed", "exc": str(exc)}), 500
        return jsonify({"status": "ok", "path": out_path})

    @app.route("/fill-document", methods=["POST"])
    def fill_document():
        payload = request.get_json() or {}
        group_dir = payload.get("group_dir")
        data = payload.get("data")
        if not group_dir or not data:
            return jsonify({"error": "group_dir and data required"}), 400
        group_abs = _resolve_within(root, group_dir)
        if group_abs is None:
            return jsonify({"error": "group_dir must stay inside the served root"}), 400
        if not group_abs.exists():
            return jsonify({"error": "group_dir not found"}), 404
        fillables = (
            list((group_abs / "fillable_pdfs").glob("*.pdf"))
            if (group_abs / "fillable_pdfs").exists()
            else []
        )
        if not fillables:
            return jsonify({"error": "no fillable pdfs found"}), 404
        from .fill import fill_pdf_fields

        results = []
        for p in fillables:
            outp = p.parent / f"filled_{p.name}"
            try:
                filled = fill_pdf_fields(p.read_bytes(), data)
                outp.write_bytes(filled)
                results.append(str(outp.relative_to(root)))
            except Exception as exc:
                results.append({"file": str(p), "error": str(exc)})
        return jsonify({"status": "ok", "filled_files": results})

    @app.route("/save_fieldmap", methods=["POST"])
    def save_fieldmap():
        data = request.get_json()
        if not data:
            return jsonify({"error": "no json provided"}), 400
        out_path = data.get("out_path")
        if not out_path:
            return jsonify({"error": "out_path required"}), 400
        out_abs = _resolve_out_path(root, out_path)
        if out_abs is None or out_abs.suffix.lower() != ".json":
            return jsonify({"error": "out_path must be a .json path inside the served root"}), 400
        from .fieldmap import FieldmapError
        from .fieldmap import save_fieldmap as _save
        from .models import FieldBox

        try:
            fields = [FieldBox.from_dict(item) for item in data.get("fieldmap", [])]
        except (KeyError, TypeError, ValueError) as exc:
            return jsonify({"error": f"invalid fieldmap: {exc}"}), 400
        try:
            _save(fields, out_abs)
        except FieldmapError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"status": "ok", "path": out_path})

    return app


def run_server(root: str | Path, host: str = "127.0.0.1", port: int = 5000) -> None:
    """Serve reconstructed output under *root* on loopback (default)."""
    create_app(root).run(host=host, port=port)
