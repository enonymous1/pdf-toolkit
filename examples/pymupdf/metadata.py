from pathlib import Path

import fitz


def read_metadata(path: str) -> dict:
    doc = fitz.open(path)
    meta = doc.metadata or {}
    n_pages = doc.page_count

    # collect rich details via helper
    try:
        from examples.pymupdf.metadata_details import collect_details

        details = collect_details(doc)
    except Exception:
        details = {}

    # outlines
    try:
        outlines = doc.get_toc()
    except Exception:
        outlines = None

    # attachments
    try:
        attachments = doc.embeddedFileNames()
    except Exception:
        attachments = None

    # try to extract textual TOC (page-based) near a hinted page (1-indexed)
    toc = None
    try:
        from pdf_toolkit.inspector.toc.pymupdf import extract_toc_from_pdf

        toc = extract_toc_from_pdf(path, hint_page=6, scan_after=4)
    except Exception:
        toc = None

    # try to provide object count and permissions if available
    try:
        obj_count = doc.xref_length()
    except Exception:
        obj_count = None
    doc.close()

    from pdf_toolkit.inspector import normalize_pdf_metadata

    normalized = normalize_pdf_metadata(meta)

    normalized["metadata"]["ObjectCount"] = obj_count
    normalized["metadata"]["Permissions"] = None

    # PyMuPDF: attempt XMP via documented API or fallback to scanning the file
    xmp = None
    try:
        xmp = getattr(doc, "xmp_metadata", None)
        if xmp:
            xmp = str(xmp)
    except Exception:
        xmp = None
    if not xmp:
        try:
            from pdf_toolkit.inspector import extract_xmp_from_file

            xmp = extract_xmp_from_file(path)
        except Exception:
            xmp = None
    normalized["metadata"]["XMP"] = xmp

    return {
        "n_pages": n_pages,
        **normalized,
        "details": details,
        "outlines": outlines,
        "toc": toc,
        "attachments": attachments,
        "raw_metadata": meta,
    }


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
        out.write_text(json.dumps(read_metadata(pdf), indent=2), encoding="utf-8")
        print(f"Wrote metadata to: {out}")
