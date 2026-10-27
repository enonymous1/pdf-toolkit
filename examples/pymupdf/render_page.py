from pathlib import Path

import fitz


def render_page_to_png(pdf_path: str, page_no: int = 0, out_path: str | None = None) -> Path:
    # default output into examples/pymupdf/outputs so artifacts are organized
    if out_path is None:
        out_dir = Path(__file__).resolve().parent / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"page_{page_no}.png"
        try:
            from pdf_toolkit.inspector import unique_output_path
        except Exception:
            import sys

            # add project root to sys.path so `examples` package is importable
            sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
            from pdf_toolkit.inspector import unique_output_path
        out = unique_output_path(out)
    else:
        out = Path(out_path)
        if out.exists():
            try:
                from pdf_toolkit.inspector import unique_output_path
            except Exception:
                import sys

                # add project root to sys.path so `examples` package is importable
                sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
                from pdf_toolkit.inspector import unique_output_path
            out = unique_output_path(out)

    doc = fitz.open(pdf_path)
    page = doc[page_no]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    pix.save(str(out))
    doc.close()
    return out


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python render_page.py <pdf-path> [page_no]")
    else:
        pno = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        print(render_page_to_png(sys.argv[1], pno))
