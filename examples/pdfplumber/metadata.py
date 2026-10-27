from pathlib import Path

import pdfplumber


def read_metadata(path: str) -> dict:
    with pdfplumber.open(path) as pdf:
        meta = getattr(pdf, "metadata", {}) or {}
        n_pages = len(pdf.pages)
        page_sizes = []
        total_text = 0
        fonts = set()
        total_images = 0
        for p in pdf.pages:
            w = getattr(p, "width", None)
            h = getattr(p, "height", None)
            txt = p.extract_text() or ""
            total_text += len(txt)
            # collect fonts from chars if available
            try:
                for c in p.chars:
                    fn = c.get("fontname") or c.get("font")
                    if fn:
                        fonts.add(fn)
            except Exception:
                pass
            imgs = 0
            try:
                imgs = len(p.images or [])
            except Exception:
                imgs = 0
            total_images += imgs
            # annotations not well-supported in pdfplumber
            page_sizes.append(
                {
                    "width": w,
                    "height": h,
                    "rotation": None,
                    "text_length": len(txt),
                    "image_count": imgs,
                }
            )

    from pdf_toolkit.inspector import normalize_pdf_metadata

    normalized = normalize_pdf_metadata(meta)
    details = {
        "page_count": n_pages,
        "page_sizes": page_sizes or None,
        "text_length": total_text,
        "fonts": sorted(list(fonts)) if fonts else None,
        "image_count": total_images,
        "annotations_count": None,
        "form_fields_count": None,
        "has_outlines": None,
        "attachments": None,
    }

    # add best-effort object count / xmp / permissions placeholders
    normalized["metadata"]["ObjectCount"] = None
    normalized["metadata"]["Permissions"] = None

    # try to find XMP in file bytes
    try:
        from pdf_toolkit.inspector import extract_xmp_from_file

        normalized["metadata"]["XMP"] = extract_xmp_from_file(path)
    except Exception:
        normalized["metadata"]["XMP"] = None

    return {"n_pages": n_pages, **normalized, "details": details, "raw_metadata": meta}


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
