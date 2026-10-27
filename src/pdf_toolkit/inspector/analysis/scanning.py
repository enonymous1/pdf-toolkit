from typing import Any, Dict

import fitz


def analyze_page_scanning(page: fitz.Page) -> Dict[str, Any]:
    """Analyze a single page to determine if it is likely a scanned image."""
    text = page.get_text("text").strip()
    words = page.get_text("words")
    images = page.get_images()

    # Check block types
    blocks = page.get_text("dict")["blocks"]
    _text_blocks = [b for b in blocks if b["type"] == 0]
    _image_blocks = [b for b in blocks if b["type"] == 1]

    # A page is likely scanned if:
    # 1. It has images but almost no text
    # 2. Or the text length is extremely low but it has 1+ images
    is_scanned = len(images) > 0 and len(text) < 50

    # Heuristic: if there are no fonts or only one font used for spaces
    fonts = page.get_fonts()

    return {
        "text_length": len(text),
        "word_count": len(words),
        "image_count": len(images),
        "font_count": len(fonts),
        "is_scanned": is_scanned,
        "confidence": 0.9 if is_scanned else 0.5,
    }


def analyze_document_scanning(doc: fitz.Document, sample_pages: int = 10) -> Dict[str, Any]:
    """Analyze the whole document for scanning indicators."""
    total_pages = doc.page_count
    check_limit = min(total_pages, sample_pages)

    scanned_count = 0
    results = []

    # We check the first few pages and maybe a few in the middle/end
    pages_to_check = list(range(check_limit))
    if total_pages > sample_pages:
        # Add middle and end
        pages_to_check.extend([total_pages // 2, total_pages - 1])

    pages_to_check = sorted(list(set(pages_to_check)))

    for i in pages_to_check:
        res = analyze_page_scanning(doc.load_page(i))
        results.append(res)
        if res["is_scanned"]:
            scanned_count += 1

    is_mostly_scanned = (scanned_count / len(results)) > 0.5

    return {
        "is_scanned_pdf": is_mostly_scanned,
        "scanned_page_ratio": scanned_count / len(results),
        "sample_size": len(results),
        "document_type": "Scanned Image" if is_mostly_scanned else "Digital Text",
    }
