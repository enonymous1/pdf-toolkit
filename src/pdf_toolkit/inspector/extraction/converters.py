from typing import Optional

import fitz

from .ocr_utils import get_ocr_text_robust

try:
    import pymupdf4llm
except ImportError:
    pymupdf4llm = None

try:
    from pdf2docx import Converter
except ImportError:
    Converter = None


def convert_to_html(pdf_path: str, output_path: str, pages: Optional[str] = None):
    """Convert PDF to HTML using PyMuPDF."""
    doc = fitz.open(pdf_path)
    # Basic HTML export
    html_content = ""

    # Handle page range
    page_range = []
    if pages == "all" or not pages:
        page_range = range(doc.page_count)
    else:
        try:
            if "-" in pages:
                s, e = pages.split("-")
                page_range = range(int(s) - 1, int(e))
            else:
                page_range = [int(pages) - 1]
        except ValueError:
            page_range = [0]

    for p_idx in page_range:
        if 0 <= p_idx < doc.page_count:
            page = doc.load_page(p_idx)
            html_content += page.get_text("html")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    doc.close()


def convert_to_markdown(
    pdf_path: str,
    output_path: Optional[str] = None,
    use_ocr: bool = False,
    pages: Optional[str] = None,
) -> str:
    """
    Convert PDF to Markdown.
    If use_ocr is True, uses robust OCR pipeline.
    Otherwise uses pymupdf4llm for high-quality digital extraction.
    """
    if use_ocr:
        return convert_to_markdown_ocr(pdf_path, output_path, pages=pages)

    if not pymupdf4llm:
        # Fallback to OCR if pymupdf4llm is missing
        return convert_to_markdown_ocr(pdf_path, output_path, pages=pages)

    # pymupdf4llm is great for digital text
    md_text = pymupdf4llm.to_markdown(pdf_path)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_text)

    return md_text


def convert_to_markdown_ocr(
    pdf_path: str, output_path: Optional[str] = None, pages: Optional[str] = None
) -> str:
    """Robust OCR-based Markdown conversion for scanned documents."""
    doc = fitz.open(pdf_path)
    md_content = []

    # Handle page range
    page_range = []
    if pages == "all" or not pages:
        page_range = range(doc.page_count)
    else:
        try:
            if "-" in pages:
                s, e = pages.split("-")
                page_range = range(int(s) - 1, int(e))
            else:
                page_range = [int(pages) - 1]
        except ValueError:
            page_range = range(doc.page_count)

    total_to_process = len(page_range)
    print(f"Starting OCR conversion for {total_to_process} pages...")

    for count, i in enumerate(page_range):
        if i < 0 or i >= doc.page_count:
            continue

        if count % 5 == 0:
            print(f"Processing page {i + 1}/{doc.page_count} ({count + 1}/{total_to_process})...")

        page = doc.load_page(i)
        text = get_ocr_text_robust(page)

        # Simple Markdown formatting: Page numbers and text
        md_content.append(f"## Page {i + 1}\n\n")
        md_content.append(text)
        md_content.append("\n\n---\n\n")

    full_md = "".join(md_content)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_md)
        print(f"Exported to {output_path}")

    doc.close()
    return full_md


def convert_to_docx(pdf_path: str, output_path: str, pages: Optional[str] = None):
    """Convert PDF to DOCX using pdf2docx."""
    if not Converter:
        raise ImportError("pdf2docx is not installed.")

    cv = Converter(pdf_path)

    start_page = 0
    end_page = None

    if pages:
        if "-" in pages:
            s, e = pages.split("-")
            start_page = int(s) - 1
            end_page = int(e)
        else:
            try:
                start_page = int(pages) - 1
                end_page = start_page + 1
            except ValueError:
                pass  # Use defaults for 'all'

    cv.convert(output_path, start=start_page, end=end_page)
    cv.close()
