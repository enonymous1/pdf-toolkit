from pypdf import PdfReader


def read_metadata(path: str) -> dict:
    reader = PdfReader(path)
    raw = dict(reader.metadata or {})
    from pdf_toolkit.inspector import normalize_pdf_metadata

    normalized = normalize_pdf_metadata(raw)

    # best-effort details (page sizes, text length, image counts)
    page_sizes = []
    total_text = 0
    total_images = 0
    for p in reader.pages:
        try:
            w = float(p.mediabox.width)
            h = float(p.mediabox.height)
        except Exception:
            w = None
            h = None
        try:
            txt = p.extract_text() or ""
        except Exception:
            txt = ""
        total_text += len(txt)
        # pypdf doesn't expose fonts easily — leave None
        imgs = None
        try:
            if hasattr(p, "images"):
                imgs = len(p.images)
            elif hasattr(p, "get_images"):
                imgs = len(p.get_images())
        except Exception:
            imgs = None
        total_images = (
            (total_images + imgs)
            if isinstance(imgs, int) and isinstance(total_images, int)
            else None
        )
        page_sizes.append(
            {
                "width": w,
                "height": h,
                "rotation": None,
                "text_length": len(txt),
                "image_count": imgs,
            }
        )

    details = {
        "page_count": len(reader.pages),
        "page_sizes": page_sizes or None,
        "text_length": total_text,
        "fonts": None,
        "image_count": total_images,
        "annotations_count": None,
        "form_fields_count": None,
        "has_outlines": None,
        "attachments": None,
    }

    # attempt to extract outlines/toc: try pypdf outlines, then a text-based fallback
    outlines = None
    toc = None
    try:
        # try pypdf outlines first
        if hasattr(reader, "outlines"):
            outlines = reader.outlines
        elif hasattr(reader, "get_outlines"):
            outlines = reader.get_outlines()
    except Exception:
        outlines = None

    if not outlines:
        try:
            from pdf_toolkit.inspector.toc.pypdf import extract_toc_from_pdf

            toc = extract_toc_from_pdf(path, hint_page=6, scan_after=4)
        except Exception:
            toc = None

    # try object count and permission info from pypdf where possible
    try:
        obj_count = reader.trailer.get("/Size") if hasattr(reader, "trailer") else None
    except Exception:
        obj_count = None
    normalized["metadata"]["ObjectCount"] = obj_count
    normalized["metadata"]["Permissions"] = None

    # best-effort XMP extraction
    xmp = None
    try:
        if hasattr(reader, "xmp_metadata") and reader.xmp_metadata:
            xmp = str(reader.xmp_metadata)
    except Exception:
        xmp = None
    if not xmp:
        try:
            from pdf_toolkit.inspector import extract_xmp_from_file

            xmp = extract_xmp_from_file(path)
        except Exception:
            xmp = None
    normalized["metadata"]["XMP"] = xmp

    result = {"n_pages": len(reader.pages), **normalized, "details": details, "raw_metadata": raw}
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
            from pdf_toolkit.inspector import metadata_to_markdown, unique_output_path
        except Exception:
            import sys

            sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
            from pdf_toolkit.inspector import metadata_to_markdown, unique_output_path
        out = unique_output_path(out)
        meta = read_metadata(pdf)
        out.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        # also write a human-friendly markdown summary
        md_out = out.with_name(out.stem + "_metadata.md")
        md_out = unique_output_path(md_out)
        md_out.write_text(metadata_to_markdown(meta), encoding="utf-8")
        print(f"Wrote metadata to: {out} and summary to: {md_out}")
