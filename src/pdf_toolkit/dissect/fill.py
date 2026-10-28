"""Fill PDF form fields, by AcroForm or by text overlay.

Ported from ss-documentDissection's ``fill.py``. Fixes over the
original, which only ever filled the first page and reached into
pypdf's private ``_root_object``:

- Every page is filled, not just page 0: AcroForm values are
  partitioned per page from each page's annotations, and the overlay
  fallback takes a per-page field mapping. The AcroForm path uses
  ``PdfWriter.append`` (which preserves the AcroForm dictionary);
  the original's private ``_root_object`` copy breaks serialization
  on current pypdf.
- The overlay fallback is per page too, and ``fields`` may be a list
  (page 1, as before) or a ``{1-based page: [FieldBox, ...]}`` dict.
- ``pdf_bytes`` must actually be bytes; passing a filename (as the
  original preview server did) raises :class:`FillError` instead of
  producing a confusing downstream error.
- If AcroForm filling writes no values at all, the overlay fallback
  runs instead of returning an apparently-filled PDF.
"""

from __future__ import annotations

import io

from .models import FieldBox

__all__ = ["FillError", "fill_pdf_fields"]


class FillError(Exception):
    pass


def _normalize_fields(fields) -> dict[int, list[FieldBox]]:
    if fields is None:
        return {}
    if isinstance(fields, dict):
        return {int(k): list(v) for k, v in fields.items()}
    return {1: list(fields)}


def _page_field_names(page) -> set[str]:
    """Field names annotated on a pypdf page (empty when there are none)."""
    names: set[str] = set()
    try:
        annots = page.get("/Annots") or []
    except Exception:
        return names
    for annot in annots:
        try:
            obj = annot.get_object()
            name = obj.get("/T")
        except Exception:
            continue
        if name:
            names.add(str(name))
    return names


def _try_acroform_fill(pdf_bytes: bytes, data: dict[str, str]) -> bytes | None:
    """Fill AcroForm fields on every page; return bytes, or None if not applicable.

    Uses ``PdfWriter.append``, which carries the document's AcroForm
    dictionary across intact. The original reached into the writer's
    private ``_root_object`` to copy it, which breaks serialization
    on current pypdf.
    """
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(pdf_bytes))
    try:
        acro = reader.trailer["/Root"].get("/AcroForm")
    except Exception:
        return None
    if acro is None:
        return None
    writer = PdfWriter()
    writer.append(reader)
    for page in writer.pages:
        names = _page_field_names(page)
        page_data = {k: v for k, v in data.items() if not names or k in names}
        if page_data:
            try:
                writer.update_page_form_field_values(page, page_data)
            except Exception:
                return None
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _values_written(pdf_bytes: bytes, data: dict[str, str]) -> bool:
    """True if at least one expected value is readable back via pypdf fields."""
    from pypdf import PdfReader

    try:
        fields = PdfReader(io.BytesIO(pdf_bytes)).get_fields() or {}
    except Exception:
        return False
    for name, value in data.items():
        field = fields.get(name)
        if field is not None and str(field.get("/V", "")) == str(value):
            return True
    return False


def _overlay_fill(
    pdf_bytes: bytes, data: dict[str, str], fields: dict[int, list[FieldBox]], dpi: int
) -> bytes:
    import fitz

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise FillError(f"Failed to open PDF for overlay fill: {exc}") from exc
    try:
        for page_number, boxes in fields.items():
            if page_number < 1 or page_number > doc.page_count:
                continue
            page = doc[page_number - 1]
            for i, f in enumerate(boxes):
                name = f.name or f"field_{i}"
                val = data.get(name) or data.get(f"field_{i}")
                if not val:
                    continue
                x = f.x * 72.0 / dpi
                y = f.y * 72.0 / dpi
                w = f.w * 72.0 / dpi
                h = f.h * 72.0 / dpi
                rect = fitz.Rect(x, y, x + w, y + h)
                # insert_textbox returns negative when the text does not
                # fit at that size and inserts nothing; a fixed 10pt font
                # silently dropped values in short boxes, so shrink to fit.
                for fontsize in (10, 8, 7, 6):
                    if page.insert_textbox(rect, str(val), fontsize=fontsize, fontname="helv") >= 0:
                        break
        return doc.write()
    except Exception as exc:
        raise FillError(f"Failed to overlay PDF fields: {exc}") from exc
    finally:
        doc.close()


def fill_pdf_fields(
    pdf_bytes: bytes,
    data: dict[str, str],
    fields: list[FieldBox] | dict[int, list[FieldBox]] | None = None,
    dpi: int = 150,
) -> bytes:
    """Fill *data* (``field_name -> value``) into *pdf_bytes*.

    AcroForm fields are filled first, on every page. When the PDF has
    no AcroForm (or AcroForm filling writes nothing), text is overlaid
    at the ``FieldBox`` coordinates instead, which requires *fields*.
    """
    if not isinstance(pdf_bytes, (bytes, bytearray)):
        raise FillError("fill_pdf_fields expects PDF bytes, not a file path")
    pdf_bytes = bytes(pdf_bytes)
    normalized = _normalize_fields(fields)
    filled = None
    if data:
        try:
            filled = _try_acroform_fill(pdf_bytes, data)
        except Exception:
            filled = None
        if filled is not None and not _values_written(filled, data):
            filled = None  # AcroForm round-trip wrote nothing; fall through.
    if filled is not None:
        return filled
    if not normalized:
        raise FillError(
            "Failed to fill PDF fields and no field coordinates provided for overlay fallback"
        )
    return _overlay_fill(pdf_bytes, data, normalized, dpi)
