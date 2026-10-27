"""Table extraction helpers.

``camelot`` and ``tabula`` are optional dependencies (``pdf-toolkit[tables]``).
They are imported lazily inside each function so importing this module, and
running the rest of the toolkit, never requires them. ``tabula-py`` also
needs a Java runtime; its failure is reported as an ImportError with a
plain-language hint instead of a stack trace from deep inside Java.
"""

from pathlib import Path


def extract_tables_camelot(pdf_path: str, pages: str = "1"):
    """Extract tables with Camelot (lattice, falling back to stream)."""
    try:
        import camelot
    except ImportError as exc:
        raise ImportError(
            "Camelot is not installed. Install the tables extra: pip install 'pdf-toolkit[tables]'"
        ) from exc
    try:
        tables = camelot.read_pdf(pdf_path, pages=pages, flavor="lattice")
        if len(tables) == 0:
            tables = camelot.read_pdf(pdf_path, pages=pages, flavor="stream")
        return [t.df for t in tables]
    except Exception as exc:
        print(f"Camelot error: {exc}")
        return []


def extract_tables_tabula(pdf_path: str, pages: str = "all"):
    """Extract tables with tabula-py (requires Java)."""
    try:
        import tabula
    except ImportError as exc:
        raise ImportError(
            "tabula-py is not installed. Install the tables extra: "
            "pip install 'pdf-toolkit[tables]' (tabula-py also needs Java)"
        ) from exc
    try:
        return tabula.read_pdf(pdf_path, pages=pages, multiple_tables=True)
    except Exception as exc:
        print(f"Tabula error: {exc}")
        return []


def extract_tables_smart(pdf_path: str, pages: str = "1", use_ocr: bool = False):
    """Try Camelot first; note the OCR limitation instead of pretending."""
    results = extract_tables_camelot(pdf_path, pages=pages)
    if len(results) == 0 and use_ocr:
        print("Standard table extraction failed. Attempting OCR-based extraction...")
        print(
            "Note: Advanced Table-OCR requires Poppler and Tesseract to "
            "generate searchable PDF layers."
        )
    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m pdf_toolkit.inspector.extraction.tables <pdf> [pages]")
        raise SystemExit(1)
    target = sys.argv[1]
    pages = sys.argv[2] if len(sys.argv) > 2 else "1"
    if Path(target).exists():
        print(f"--- Attempting table extraction on {target} page {pages} ---")
        for i, df in enumerate(extract_tables_tabula(target, pages=pages)):
            print(f"\nTable {i + 1}:")
            print(df.head())
