from pathlib import Path

import fitz


def extract_pages(src: str, dst: str, start_idx: int, end_idx: int) -> Path:
    doc = fitz.open(src)
    total = doc.page_count
    if start_idx < 0 or end_idx >= total or start_idx > end_idx:
        doc.close()
        raise ValueError("page range out of bounds")

    new = fitz.open()
    new.insert_pdf(doc, from_page=start_idx, to_page=end_idx)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    new.save(str(dst))
    new.close()
    doc.close()
    return Path(dst)


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Extract pages from a PDF using PyMuPDF (fitz)")
    parser.add_argument("pdf", help="source PDF path")
    parser.add_argument("--start", type=int, required=True, help="start page (1-indexed)")
    parser.add_argument("--end", type=int, help="end page (inclusive, 1-indexed)")
    parser.add_argument("--count", type=int, help="number of pages to extract starting at --start")
    parser.add_argument("--out", help="output path (optional)")

    args = parser.parse_args()
    src = Path(args.pdf)
    if not src.exists():
        parser.error(f"source not found: {src}")

    from pdf_toolkit.inspector import parse_page_range, unique_output_path

    total = fitz.open(str(src)).page_count
    try:
        s0, e0 = parse_page_range(total, start=args.start, end=args.end, count=args.count)
    except ValueError as exc:
        parser.error(str(exc))

    default_out = (
        Path(__file__).resolve().parent / "outputs" / f"{src.stem}_pages_{s0 + 1}-{e0 + 1}.pdf"
    )
    out_path = Path(args.out) if args.out else default_out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path = unique_output_path(out_path)

    extract_pages(str(src), str(out_path), s0, e0)
    print(f"Wrote: {out_path}")
