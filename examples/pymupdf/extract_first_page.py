from pathlib import Path

import fitz


def extract_first_page(src: str, dst: str) -> Path:
    src_p = Path(src)
    dst_p = Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(src_p)
    if doc.page_count < 1:
        doc.close()
        raise ValueError("Source PDF has no pages")

    new_doc = fitz.open()
    new_doc.insert_pdf(doc, from_page=0, to_page=0)
    new_doc.save(str(dst_p))
    new_doc.close()
    doc.close()
    return dst_p


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python extract_first_page.py <source-pdf> <out-pdf>")
        sys.exit(1)
    out = extract_first_page(sys.argv[1], sys.argv[2])
    print(out)
