import pymupdf

from .ocr_utils import get_ocr_text_robust

try:
    import pymupdf4llm
except ImportError:
    pymupdf4llm = None

try:
    from pdf2docx import Converter
except ImportError:
    Converter = None


def _page_indices(spec: str | None, total: int) -> range:
    """Parse a page spec into 0-based page indexes.

    ``None`` or ``"all"`` means every page, ``"3"`` means page 3, and
    ``"2-5"`` means pages 2 through 5 (all 1-based, as on the CLI).
    Anything else raises ValueError. This used to be copy-pasted into
    each converter with a different silent fallback on bad input
    (page 1 only, all pages, or defaults), so a typo silently exported
    the wrong pages; now there is one parser and one failure mode.
    """
    if spec is None or spec == "all":
        return range(total)
    try:
        if "-" in spec:
            start, end = spec.split("-", 1)
            start_i, end_i = int(start), int(end)
            if start_i < 1 or end_i < start_i or end_i > total:
                raise ValueError
            return range(start_i - 1, end_i)
        page_i = int(spec)
        if page_i < 1 or page_i > total:
            raise ValueError
        return range(page_i - 1, page_i)
    except ValueError:
        raise ValueError(
            f"Invalid page spec {spec!r} for a {total}-page PDF "
            "(expected 'all', a page number, or 'start-end')"
        ) from None


def convert_to_html(pdf_path: str, output_path: str, pages: str | None = None):
    """Convert PDF to HTML using PyMuPDF."""
    doc = pymupdf.open(pdf_path)
    # Basic HTML export
    html_content = ""

    page_range = _page_indices(pages, doc.page_count)

    for p_idx in page_range:
        if 0 <= p_idx < doc.page_count:
            page = doc.load_page(p_idx)
            html_content += page.get_text("html")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    doc.close()


def convert_to_markdown(
    pdf_path: str,
    output_path: str | None = None,
    use_ocr: bool = False,
    pages: str | None = None,
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
    pdf_path: str, output_path: str | None = None, pages: str | None = None
) -> str:
    """Robust OCR-based Markdown conversion for scanned documents."""
    doc = pymupdf.open(pdf_path)
    md_content = []

    page_range = _page_indices(pages, doc.page_count)

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


def convert_to_docx(pdf_path: str, output_path: str, pages: str | None = None):
    """Convert PDF to DOCX using pdf2docx."""
    if not Converter:
        raise ImportError("pdf2docx is not installed.")

    cv = Converter(pdf_path)
    try:
        # pdf2docx takes start (0-based, inclusive) and end (exclusive);
        # for the whole document both stay at their defaults.
        if pages is None or pages == "all":
            start_page, end_page = 0, None
        else:
            # _page_indices needs a page count it does not have yet, so
            # validate the shape here and let pdf2docx bound-check it.
            indices = _page_indices(pages, 10**9)
            start_page, end_page = indices.start, indices.stop
        cv.convert(output_path, start=start_page, end=end_page)
    finally:
        cv.close()
