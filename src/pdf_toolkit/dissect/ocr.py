"""Assign OCR-derived labels to detected field boxes.

Ported from ss-documentDissection's ``ocr.py``. The heuristic is
unchanged: for each field, the nearest OCR word that does not overlap
the field vertically, within ``max_distance`` pixels, becomes the
field's name (lowercased, non-alphanumerics collapsed to underscores).
One OCR word per field, so multi-word labels like "First Name" keep
only the nearest word — a known limitation, not a regression.

If pytesseract (or the Tesseract binary) is unavailable, fields are
returned unchanged instead of raising: labelling is best-effort, and
``reconstruct_pdf_pages`` treats it that way. Needs OpenCV/NumPy plus
pytesseract (``pdf-toolkit[dissect]``) and a Tesseract install.
"""

from __future__ import annotations

import re

from .detect import require_cv2
from .models import FieldBox

__all__ = ["OCRError", "assign_labels_to_fields"]


class OCRError(Exception):
    pass


def assign_labels_to_fields(
    image, fields: list[FieldBox], max_distance: int = 200
) -> list[FieldBox]:
    """OCR *image* and set ``FieldBox.name`` from nearby text, in place."""
    cv2, _np = require_cv2()
    try:
        import pytesseract
    except ImportError:
        return fields
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    try:
        raw = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
    except Exception:
        # Tesseract binary missing or OCR failed: leave fields unnamed.
        return fields

    texts = []
    for i in range(len(raw.get("text", []))):
        txt = raw["text"][i].strip()
        try:
            conf = int(raw["conf"][i])
        except Exception:
            conf = -1
        if txt:
            texts.append(
                {
                    "text": txt,
                    "conf": conf,
                    "x": int(raw["left"][i]),
                    "y": int(raw["top"][i]),
                    "w": int(raw["width"][i]),
                    "h": int(raw["height"][i]),
                }
            )

    for fd in fields:
        best = None
        fallback = None
        fx_c = fd.x + fd.w / 2
        fy_c = fd.y + fd.h / 2
        for t in texts:
            if len(t["text"].strip()) <= 1 or not any(c.isalpha() for c in t["text"]):
                continue
            if t["y"] < fd.y + fd.h and t["y"] + t["h"] > fd.y:
                continue  # overlaps the field vertically; likely inside it
            tx_c = t["x"] + t["w"] / 2
            ty_c = t["y"] + t["h"] / 2
            dist = ((tx_c - fx_c) ** 2 + (ty_c - fy_c) ** 2) ** 0.5
            if dist <= max_distance:
                score = (1.0 / (1 + dist)) * max(0.01, t["conf"] / 100.0)
                if best is None or score > best["score"]:
                    best = {"text": t["text"], "conf": t["conf"], "dist": dist, "score": score}
                if t["y"] + t["h"] < fd.y + fd.h / 2 and (
                    fallback is None or dist < fallback["dist"]
                ):
                    fallback = {"text": t["text"], "conf": t["conf"], "dist": dist}
        chosen = None
        if best and best["conf"] > 30:
            chosen = best
        elif fallback:
            chosen = fallback
        elif best:
            chosen = best
        if chosen:
            name = re.sub(r"[^a-z0-9_]+", "_", chosen["text"].lower())
            name = re.sub(r"_+", "_", name).strip("_")
            fd.name = name or None
    return fields
