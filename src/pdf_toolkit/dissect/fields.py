"""Render pages to images and detect rectangular field boxes in them.

Ported from ss-documentDissection's ``ingest.py`` (rendering) and
``reconstruct.py`` (contour detection). The contour heuristic is
unchanged — Canny edges, morphological closing, external contours
approximated to quadrilaterals, sorted top-to-bottom — because it is
the part the original's tests actually pin down. Needs OpenCV and
NumPy (``pdf-toolkit[dissect]``).
"""

from __future__ import annotations

from pathlib import Path

import fitz

from .detect import require_cv2
from .models import FieldBox

__all__ = ["detect_field_contours", "render_page_to_image", "render_pdf_pages"]


def render_page_to_image(page: fitz.Page, dpi: int = 150):
    """Render a PyMuPDF page to an OpenCV-compatible BGR NumPy array."""
    cv2, np = require_cv2()
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    elif pix.n == 1:
        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    return arr


def render_pdf_pages(pdf_path: str | Path, dpi: int = 150) -> dict[int, object]:
    """Render every page of *pdf_path*; returns ``{1-based page: BGR array}``."""
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        raise ValueError(f"Failed to open PDF '{pdf_path}': {exc}") from exc
    try:
        return {i + 1: render_page_to_image(doc.load_page(i), dpi=dpi) for i in range(len(doc))}
    finally:
        doc.close()


def detect_field_contours(
    image, min_area: int = 1000, epsilon_coef: float = 0.02
) -> list[FieldBox]:
    """Detect rectangular contours (fields) in *image*, in pixel coordinates.

    External contours only, so nested boxes inside a larger rectangle
    are not reported separately; that matches the original behaviour
    and is a known limitation for forms with boxed sections.
    """
    cv2, _np = require_cv2()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3))
    closed = cv2.morphologyEx(edged, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[FieldBox] = []
    for cnt in contours:
        if cv2.contourArea(cnt) < min_area:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon_coef * peri, True)
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            boxes.append(FieldBox(name=None, x=int(x), y=int(y), w=int(w), h=int(h)))
    boxes.sort(key=lambda b: (b.y, b.x))
    return boxes
