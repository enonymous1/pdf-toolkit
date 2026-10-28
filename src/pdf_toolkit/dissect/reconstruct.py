"""Reconstruct pages as HTML overlays and fillable PDFs.

Ported from ss-documentDissection's ``reconstruct.py``. Two fixes over
the original: fieldmaps are written as JSON (see
:mod:`pdf_toolkit.dissect.fieldmap` — the original wrote ``str()`` and
needed ``eval()`` to read it back), and the HTML overlay escapes field
names and pre-filled values (the original interpolated them raw into
attributes). The interactive JavaScript editor is ported as-is.

Needs OpenCV/NumPy for image work and ReportLab for fillable PDFs
(``pdf-toolkit[dissect]``). The WeasyPrint HTML-to-PDF path from the
original is deliberately not ported: it needs system Cairo/Pango
libraries that are not pip-installable, and filled PDFs are produced
by :mod:`pdf_toolkit.dissect.fill` instead.
"""

from __future__ import annotations

import base64
import html
import io
from pathlib import Path

import fitz

from .detect import require_cv2
from .extract import extract_pages_to_bytes
from .fieldmap import save_fieldmap
from .fields import detect_field_contours, render_page_to_image
from .models import FieldBox

__all__ = [
    "ReconstructionError",
    "create_fillable_pdf_from_image",
    "create_html_overlay",
    "export_html_to_file",
    "reconstruct_pdf_pages",
]


class ReconstructionError(Exception):
    pass


def _encode_png(image) -> bytes:
    """Encode a BGR NumPy image as PNG bytes (OpenCV, falling back to Pillow)."""
    try:
        cv2, _np = require_cv2()
        success, buf = cv2.imencode(".png", image)
        if not success:
            raise ReconstructionError("Failed to encode image")
        return buf.tobytes()
    except Exception:
        # OpenCV unavailable or failed: Pillow understands the same array.
        try:
            from PIL import Image
        except ImportError as exc:
            raise ReconstructionError(
                "Image encoding needs OpenCV or Pillow. "
                'Install them with: pip install "pdf-toolkit[dissect]"'
            ) from exc
        import numpy as np

        rgb = image[:, :, ::-1] if image.ndim == 3 and image.shape[2] == 3 else image
        buf = io.BytesIO()
        Image.fromarray(np.asarray(rgb)).save(buf, format="PNG")
        return buf.getvalue()


_INTERACTIVE_JS = """
<script>
// Draggable inputs, sidebar editor, and save-to-server for fieldmap
(function(){
  function makeDraggable(el){
    el.style.cursor='move';
    let dragging=false, startX, startY, origX, origY;
    el.addEventListener('mousedown',function(e){
      dragging=true; startX=e.clientX; startY=e.clientY;
      origX = parseInt(el.style.left || 0); origY = parseInt(el.style.top || 0);
      e.preventDefault();
    });
    window.addEventListener('mousemove',function(e){
      if(!dragging) return;
      const dx = e.clientX - startX; const dy = e.clientY - startY;
      el.style.left = (origX + dx)+'px'; el.style.top=(origY+dy)+'px';
      updateSidebarPosition(el);
    });
    window.addEventListener('mouseup',function(){dragging=false;});
  }

  function updateSidebarPosition(el){
    const name = el.getAttribute('name');
    const item = document.querySelector(`#fieldlist [data-name="${name}"]`);
    if(item){
      const r = el.getBoundingClientRect(); const p = el.parentElement.getBoundingClientRect();
      item.querySelector('.pos').textContent = `(${Math.round(r.left-p.left)}, ${Math.round(r.top-p.top)})`;
    }
  }

  function buildSidebar(){
    const list = document.getElementById('fieldlist');
    list.innerHTML = '';
    const inputs = document.querySelectorAll('.page input');
    inputs.forEach((inp, idx)=>{
      const li = document.createElement('div'); li.className='field-item'; li.setAttribute('data-name', inp.getAttribute('name'));
      li.innerHTML = `<b>${inp.getAttribute('name')}</b> <input class='rename' value='${inp.getAttribute('name')}' /> <span class='pos'></span>`;
      li.querySelector('.rename').addEventListener('change', function(){ const newName=this.value; const old=inp.getAttribute('name'); inp.setAttribute('name', newName); inp.id=newName; li.setAttribute('data-name', newName); li.querySelector('b').textContent=newName; });
      list.appendChild(li);
      updateSidebarPosition(inp);
    });
  }

  function saveToFile(){
    const inputs = document.querySelectorAll('.page input');
    const fm = [];
    inputs.forEach(inp=>{ const r = inp.getBoundingClientRect(); const p = inp.parentElement.getBoundingClientRect(); fm.push({name: inp.getAttribute('name'), x: Math.round(r.left - p.left), y: Math.round(r.top - p.top), w: Math.round(r.width), h: Math.round(r.height)}); });
    const blob = new Blob([JSON.stringify(fm, null, 2)], {type:'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'fieldmap.json'; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  }

  function postToServer(out_path){
    const inputs = document.querySelectorAll('.page input');
    const fm = [];
    inputs.forEach(inp=>{ const r = inp.getBoundingClientRect(); const p = inp.parentElement.getBoundingClientRect(); fm.push({name: inp.getAttribute('name'), x: Math.round(r.left - p.left), y: Math.round(r.top - p.top), w: Math.round(r.width), h: Math.round(r.height)}); });
    fetch('/save_fieldmap', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({page: null, fieldmap: fm, out_path: out_path})}).then(r=>r.json()).then(console.log).catch(console.error);
  }

  function init(){
    const inputs = document.querySelectorAll('.page input');
    inputs.forEach(inp=>{ makeDraggable(inp); inp.addEventListener('dblclick', ()=>{ inp.select(); }); });
    document.getElementById('saveFieldmap').addEventListener('click', saveToFile);
    document.getElementById('postFieldmap').addEventListener('click', function(){ const out = document.getElementById('outPath').value; postToServer(out); });
    buildSidebar();
  }
  window.addEventListener('load', init);
})();
</script>
"""


def create_html_overlay(
    image,
    fields: list[FieldBox],
    data: dict | None = None,
    interactive: bool = False,
    interactive_out_path: str | None = None,
) -> str:
    """HTML string: the page image as background, one positioned ``<input>`` per field.

    ``data`` pre-fills inputs by field name (or ``field_<i>``). With
    ``interactive=True`` the page also gets the drag/rename/save editor.
    Field names and values are HTML-escaped.
    """
    b64 = base64.b64encode(_encode_png(image)).decode("ascii")
    h, w = image.shape[:2]
    inputs_html = []
    for i, f in enumerate(fields):
        field_name = f.name or f"field_{i}"
        value = ""
        if data:
            value = data.get(field_name, "")
        style = (
            f"position:absolute;left:{f.x}px;top:{f.y}px;"
            f"width:{f.w}px;height:{f.h}px;box-sizing:border-box;"
        )
        inputs_html.append(
            f'<input id="{html.escape(field_name, quote=True)}" '
            f'data-initial-name="{html.escape(field_name, quote=True)}" '
            f'name="{html.escape(field_name, quote=True)}" '
            f'style="{style}" value="{html.escape(str(value), quote=True)}" />'
        )

    interactive_js = ""
    save_button = ""
    if interactive:
        interactive_js = _INTERACTIVE_JS
        out_val = (
            f' value="{html.escape(interactive_out_path, quote=True)}"'
            if interactive_out_path
            else ""
        )
        save_button = (
            '<button id="saveFieldmap" style="position:fixed;right:10px;bottom:50px;z-index:9999">'
            "Save fieldmap</button>"
            f'<div style="position:fixed;right:10px;bottom:10px;z-index:9999">'
            f'<input id="outPath" placeholder="out path on server" style="width:260px"{out_val}/>'
            '<button id="postFieldmap">Save to server</button></div>'
        )

    sidebar = (
        f'<div id="fieldlist" style="width:280px; max-height:{h}px; overflow:auto; '
        'border-left:1px solid #ddd; padding-left:10px;"></div>'
        if interactive
        else ""
    )
    return f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  .page {{position:relative; width:{w}px; height:{h}px; background-image: url(data:image/png;base64,{b64}); background-size:100% 100%;}}
  input {{border:1px solid rgba(0,0,0,0.3); background: rgba(255,255,255,0.8);}}
</style>
</head>
<body>
  <div style="display:flex; gap:10px; align-items:flex-start">
    <div class="page">
      {"".join(inputs_html)}
    </div>
    {sidebar}
  </div>
  {save_button}
  {interactive_js}
</body>
</html>
"""


def export_html_to_file(html_text: str, out_path: str | Path) -> None:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")


def create_fillable_pdf_from_image(image, boxes: list[FieldBox], dpi: int = 150) -> bytes:
    """PDF bytes: the image as background, one AcroForm text field per box.

    Pixel coordinates (image rendered at *dpi*) are converted to PDF
    points, with the Y axis flipped (PDF origin is bottom-left).
    """
    try:
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise ReconstructionError(
            'Fillable PDFs need ReportLab. Install it with: pip install "pdf-toolkit[dissect]"'
        ) from exc
    cv2, _np = require_cv2()
    h_px, w_px = image.shape[:2]
    w_pt = w_px * 72.0 / dpi
    h_pt = h_px * 72.0 / dpi
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(w_pt, h_pt))
    from PIL import Image as PILImage

    pil_image = PILImage.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    c.drawImage(ImageReader(pil_image), 0, 0, width=w_pt, height=h_pt)
    for i, f in enumerate(boxes):
        x_pt = f.x * 72.0 / dpi
        y_pt = (h_px - (f.y + f.h)) * 72.0 / dpi
        w_f = f.w * 72.0 / dpi
        h_f = f.h * 72.0 / dpi
        c.acroForm.textfield(
            name=f.name or f"field_{i}",
            x=x_pt,
            y=y_pt,
            width=w_f,
            height=h_f,
            borderWidth=1,
            borderStyle="solid",
            fillColor=None,
            textColor=None,
            forceBorder=True,
        )
    c.showPage()
    c.save()
    return buf.getvalue()


def reconstruct_pdf_pages(
    pdf_path: str | Path,
    page_numbers: list[int],
    out_dir: str | Path,
    dpi: int = 150,
) -> dict:
    """Detect fields and generate HTML overlay + fillable PDF per page.

    Writes ``images/``, ``html/`` (overlay + ``page_<n>_fieldmap.json``
    in JSON), ``fillable_pdfs/``, and ``extracted_pdfs/`` under
    *out_dir*. Returns ``{page_number: {image, html, fieldmap,
    fillable_pdf, extracted_pdf, fields_detected}}``. Pages outside
    the document are skipped, as in the original.
    """
    out = Path(out_dir)
    images_dir = out / "images"
    html_dir = out / "html"
    fillable_dir = out / "fillable_pdfs"
    extracted_dir = out / "extracted_pdfs"
    for d in (images_dir, html_dir, fillable_dir, extracted_dir):
        d.mkdir(parents=True, exist_ok=True)

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        raise ReconstructionError(f"Failed to open PDF '{pdf_path}': {exc}") from exc
    results: dict = {}
    try:
        for p in page_numbers:
            if p < 1 or p > doc.page_count:
                continue
            page = doc.load_page(p - 1)
            img = render_page_to_image(page, dpi=dpi)
            img_path = images_dir / f"page_{p}.png"
            cv2, _np = require_cv2()
            cv2.imwrite(str(img_path), img)

            fields = detect_field_contours(img)
            try:
                from .ocr import assign_labels_to_fields

                assign_labels_to_fields(img, fields)
            except Exception:
                pass  # OCR unavailable or failed: fields stay unnamed.

            html_text = create_html_overlay(img, fields)
            html_path = html_dir / f"page_{p}.html"
            export_html_to_file(html_text, str(html_path))

            fmap_path = html_dir / f"page_{p}_fieldmap.json"
            save_fieldmap(fields, fmap_path)

            fillable_bytes = create_fillable_pdf_from_image(img, fields, dpi=dpi)
            fillable_path = fillable_dir / f"page_{p}_fillable.pdf"
            fillable_path.write_bytes(fillable_bytes)

            single_pdf_bytes = extract_pages_to_bytes(pdf_path, [p])
            extracted_path = extracted_dir / f"page_{p}.pdf"
            extracted_path.write_bytes(single_pdf_bytes)

            results[p] = {
                "image": str(img_path),
                "html": str(html_path),
                "fieldmap": str(fmap_path),
                "fillable_pdf": str(fillable_path),
                "extracted_pdf": str(extracted_path),
                "fields_detected": len(fields),
            }
    finally:
        doc.close()
    return results
