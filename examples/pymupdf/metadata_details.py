# helper utilities for extracting detailed information using PyMuPDF
from typing import Any

import fitz


def collect_details(doc: fitz.Document) -> dict[str, Any]:
    pages = []
    total_text_len = 0
    fonts = set()
    total_images = 0
    annotations = 0

    for page in doc:
        rect = page.rect
        page_text = page.get_text()
        total_text_len += len(page_text or "")
        # fonts: page.get_fonts() -> list of tuples where second item is fontname
        try:
            for f in page.get_fonts():
                fonts.add(f[1])
        except Exception:
            pass
        imgs = 0
        try:
            imgs = len(page.get_images(full=True))
        except Exception:
            imgs = 0
        total_images += imgs
        annots = 0
        try:
            ann_iter = page.annots()
            if ann_iter:
                annots = sum(1 for _ in ann_iter)
        except Exception:
            annots = 0
        annotations += annots

        pages.append(
            {
                "width": rect.width,
                "height": rect.height,
                "rotation": page.rotation,
                "text_length": len(page_text or ""),
                "image_count": imgs,
            }
        )

    details = {
        "page_count": len(pages),
        "page_sizes": pages,
        "text_length": total_text_len,
        "fonts": sorted(list(fonts)) if fonts else None,
        "image_count": total_images,
        "annotations_count": annotations,
        "form_fields_count": None,
        "has_outlines": bool(doc.get_toc()),
        "attachments": None,
    }
    # try attachments
    try:
        names = doc.embeddedFileNames()
        details["attachments"] = names if names else None
        details["has_attachments"] = bool(names)
    except Exception:
        details["attachments"] = None
        details["has_attachments"] = None

    return details
