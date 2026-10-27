from typing import List, Optional


def extract_text_via_ocr(pdf_path: str, pages: Optional[List[int]] = None, dpi: int = 300) -> str:
    """
    Perform a high-quality OCR conversion by first rendering pages to images.
    Best for 'Scanned PDFs' that fail simple text extraction.
    """
    # Note: pdf2image needs poppler installed in system PATH to work on Windows.
    # We will wrap this in a try-except to provide helpful advice.
    try:
        import pytesseract
        from pdf2image import convert_from_path

        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            first_page=pages[0] if pages else None,
            last_page=pages[-1] if pages else None,
        )
        full_text = []
        for img in images:
            text = pytesseract.image_to_string(img)
            full_text.append(text)
        return "\n\n".join(full_text)
    except Exception as e:
        if "poppler" in str(e).lower():
            return "ERROR: Poppler not found. Please install Poppler and add /bin to PATH to use pdf2image."
        return f"OCR Error: {str(e)}"


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m pdf_toolkit.inspector.extraction.ocr_engine <pdf>")
        raise SystemExit(1)
    print(extract_text_via_ocr(sys.argv[1])[:1000])
