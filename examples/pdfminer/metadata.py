from pathlib import Path

from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser


def read_metadata(path: str) -> dict:
    path = Path(path)
    meta = {}
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTChar, LTImage, LTTextContainer

    total_text = 0
    fonts = set()
    total_images = 0
    page_sizes = []

    with open(path, "rb") as fh:
        parser = PDFParser(fh)
        doc = PDFDocument(parser)
        info = doc.info[0] if doc.info else {}
        for k, v in info.items():
            key = k.decode("utf-8", errors="ignore") if isinstance(k, bytes) else str(k)
            val = v.decode("utf-8", errors="ignore") if isinstance(v, bytes) else v
            meta[key] = val
        fh.seek(0)
        n_pages = sum(1 for _ in PDFPage.get_pages(fh))

    # parse layout to get fonts/images/text per page
    try:
        for page_layout in extract_pages(path):
            w = getattr(page_layout, "width", None)
            h = getattr(page_layout, "height", None)
            page_text = ""
            imgs = 0
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    page_text += element.get_text()
                    for ch in element:
                        if isinstance(ch, LTChar):
                            fonts.add(getattr(ch, "fontname", None))
                elif isinstance(element, LTImage):
                    imgs += 1
            total_images += imgs
            total_text += len(page_text)
            page_sizes.append(
                {
                    "width": w,
                    "height": h,
                    "rotation": None,
                    "text_length": len(page_text),
                    "image_count": imgs,
                }
            )
    except Exception:
        # best-effort; leave details partial
        pass

    from pdf_toolkit.inspector import normalize_pdf_metadata

    normalized = normalize_pdf_metadata(meta)
    details = {
        "page_count": n_pages,
        "page_sizes": page_sizes or None,
        "text_length": total_text,
        "fonts": sorted([f for f in fonts if f]) or None,
        "image_count": total_images,
        "annotations_count": None,
        "form_fields_count": None,
        "has_outlines": None,
        "attachments": None,
    }

    # try to extract outlines / TOC via pdfminer low-level API
    outlines = None
    toc = None
    try:
        from pdf_toolkit.inspector.toc.pdfminer import extract_toc_from_pdf

        outlines = extract_toc_from_pdf(path)
        if outlines:
            toc = outlines
    except Exception:
        outlines = None
        toc = None

    # object count / xmp / permissions best-effort placeholders
    normalized["metadata"]["ObjectCount"] = None
    normalized["metadata"]["Permissions"] = None

    # try extracting XMP from the raw file bytes as fallback
    try:
        from pdf_toolkit.inspector import extract_xmp_from_file

        normalized["metadata"]["XMP"] = extract_xmp_from_file(path)
    except Exception:
        normalized["metadata"]["XMP"] = None

    result = {"n_pages": n_pages, **normalized, "details": details, "raw_metadata": meta}
    if outlines:
        result["outlines"] = outlines
    if toc:
        result["toc"] = toc
    return result


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("Usage: python metadata.py <pdf-path> [out-file]")
    else:
        pdf = sys.argv[1]
        out = (
            Path(sys.argv[2])
            if len(sys.argv) > 2
            else Path(__file__).resolve().parent / "outputs" / (Path(pdf).stem + "_metadata.json")
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            from pdf_toolkit.inspector import unique_output_path
        except Exception:
            import sys

            sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
            from pdf_toolkit.inspector import unique_output_path
        out = unique_output_path(out)
        meta = read_metadata(pdf)
        out.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        try:
            from pdf_toolkit.inspector import metadata_to_markdown
        except Exception:
            import sys

            sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
            from pdf_toolkit.inspector import metadata_to_markdown
        md_out = out.with_name(out.stem + "_metadata.md")
        md_out = unique_output_path(md_out)
        md_out.write_text(metadata_to_markdown(meta), encoding="utf-8")
        print(f"Wrote metadata to: {out} and summary to: {md_out}")
