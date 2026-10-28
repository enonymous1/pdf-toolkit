"""Template detection: keyword matching and image similarity (SSIM).

Ported from ss-documentDissection's ``detect.py``. Fixes over the
original: the document is opened once per call and closed; the image
path reuses the already-extracted page text instead of re-reading the
PDF a second time; and the ``method`` argument the original accepted
and ignored is gone — the template's type decides the method, which is
what the code always did.

Image matching needs OpenCV and NumPy (``pdf-toolkit[dissect]``); the
keyword path needs only PyMuPDF, which is a core dependency.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union

import fitz

from .extract import page_texts
from .models import DetectionResult, PageData

__all__ = [
    "DetectionError",
    "find_template_pages",
    "image_template_match",
    "keyword_match",
    "require_cv2",
]


class DetectionError(Exception):
    pass


def require_cv2():
    """Import cv2/numpy, or raise a readable error naming the extra."""
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise DetectionError(
            "Image template matching needs OpenCV and NumPy. "
            'Install them with: pip install "pdf-toolkit[dissect]"'
        ) from exc
    return cv2, np


def keyword_match(
    pages: list[PageData], keywords: list[str], min_ratio: float = 0.5
) -> DetectionResult:
    """Match pages containing at least *min_ratio* of *keywords* (substring, case-insensitive)."""
    if not keywords:
        raise DetectionError("Empty keywords list provided")
    lower_kw = [k.lower() for k in keywords]
    matches: list[int] = []
    scores: dict[int, float] = {}
    for page in pages:
        text = page.text.lower()
        found = sum(1 for k in lower_kw if k in text)
        score = found / len(lower_kw)
        if score >= min_ratio:
            matches.append(page.page_number)
        scores[page.page_number] = score
    return DetectionResult(template_name="keyword_template", matched_pages=matches, scores=scores)


def _ssim_gray(img1, img2) -> float:
    """Global SSIM between two same-size grayscale images (OpenCV implementation)."""
    import cv2

    if img1.shape != img2.shape:
        raise ValueError("Images must be the same size for SSIM")
    img1 = img1.astype("float64")
    img2 = img2.astype("float64")
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    mu1 = cv2.GaussianBlur(img1, (11, 11), 1.5)
    mu2 = cv2.GaussianBlur(img2, (11, 11), 1.5)
    mu1_sq = mu1 * mu1
    mu2_sq = mu2 * mu2
    mu1_mu2 = mu1 * mu2
    sigma1_sq = cv2.GaussianBlur(img1 * img1, (11, 11), 1.5) - mu1_sq
    sigma2_sq = cv2.GaussianBlur(img2 * img2, (11, 11), 1.5) - mu2_sq
    sigma12 = cv2.GaussianBlur(img1 * img2, (11, 11), 1.5) - mu1_mu2
    ssim_map = ((2 * mu1_mu2 + c1) * (2 * sigma12 + c2)) / (
        (mu1_sq + mu2_sq + c1) * (sigma1_sq + sigma2_sq + c2)
    )
    return float(ssim_map.mean())


def _page_to_bgr(page: fitz.Page, dpi: int, cv2, np):
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    elif pix.n == 1:
        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    return arr


def image_template_match(
    pdf_path: str | Path,
    template_path: str | Path,
    threshold: float = 0.7,
    dpi: int = 150,
) -> DetectionResult:
    """Match pages whose rendered image is SSIM-similar to *template_path*.

    The template is resized to each page's rendered size before
    comparison, as in the original; pages of a different aspect ratio
    than the template therefore score lower, which callers should keep
    in mind when choosing a threshold.
    """
    cv2, np = require_cv2()
    if not os.path.exists(template_path):
        raise DetectionError(f"Template image not found: {template_path}")
    tpl = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
    if tpl is None:
        raise DetectionError(f"Failed to read template image: {template_path}")

    matched_pages: list[int] = []
    scores: dict[int, float] = {}
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        raise DetectionError(f"Failed to open PDF '{pdf_path}': {exc}") from exc
    try:
        for page in doc:
            page_img = _page_to_bgr(page, dpi, cv2, np)
            tpl_resized = cv2.resize(
                tpl, (page_img.shape[1], page_img.shape[0]), interpolation=cv2.INTER_AREA
            )
            gray_page = cv2.cvtColor(page_img, cv2.COLOR_BGR2GRAY)
            gray_tpl = cv2.cvtColor(tpl_resized, cv2.COLOR_BGR2GRAY)
            try:
                score = _ssim_gray(gray_page, gray_tpl)
            except Exception:
                score = 0.0
            scores[page.number + 1] = score
            if score >= threshold:
                matched_pages.append(page.number + 1)
    finally:
        doc.close()
    return DetectionResult(
        template_name=os.path.basename(str(template_path)),
        matched_pages=matched_pages,
        scores=scores,
    )


def find_template_pages(
    pdf_path: str | Path,
    template: Union[list[str], str],
    **kwargs,
) -> DetectionResult:
    """Detect template pages: a keyword list uses :func:`keyword_match`,
    a path uses :func:`image_template_match`.

    Keyword options: ``min_ratio`` (default 0.5). Image options:
    ``threshold`` (default 0.7), ``dpi`` (default 150).
    """
    if isinstance(template, list):
        from .extract import ExtractionError

        try:
            pages = page_texts(pdf_path)
        except ExtractionError as exc:
            raise DetectionError(str(exc)) from exc
        return keyword_match(pages, template, min_ratio=kwargs.get("min_ratio", 0.5))
    if isinstance(template, str):
        return image_template_match(
            pdf_path,
            template,
            threshold=kwargs.get("threshold", 0.7),
            dpi=kwargs.get("dpi", 150),
        )
    raise DetectionError("Unsupported template type")
