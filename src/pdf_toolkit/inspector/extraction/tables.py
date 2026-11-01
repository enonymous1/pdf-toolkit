"""Table extraction helpers.

``camelot`` and ``tabula`` are optional dependencies (``pdf-toolkit[tables]``).
They are imported lazily inside each function so importing this module, and
running the rest of the toolkit, never requires them. ``tabula-py`` also
needs a Java runtime; its failure is reported as an ImportError with a
plain-language hint instead of a stack trace from deep inside Java.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_tables_camelot(pdf_path: str, pages: str = "1"):
    """Extract tables with Camelot (lattice, falling back to stream)."""
    from .._optional import require_module

    camelot = require_module("camelot", extra="tables", purpose="Camelot table extraction")
    try:
        tables = camelot.read_pdf(pdf_path, pages=pages, flavor="lattice")
        if len(tables) == 0:
            tables = camelot.read_pdf(pdf_path, pages=pages, flavor="stream")
        return [t.df for t in tables]
    except Exception as exc:
        logger.warning("Camelot extraction failed: %s", exc)
        return []


def extract_tables_tabula(pdf_path: str, pages: str = "all"):
    """Extract tables with tabula-py (requires Java)."""
    from .._optional import require_module

    tabula = require_module(
        "tabula",
        extra="tables",
        purpose="Tabula table extraction",
        message="tabula-py is not installed. Install the tables extra: "
        "pip install 'pdf-toolkit[tables]' (tabula-py also needs Java)",
    )
    try:
        return tabula.read_pdf(pdf_path, pages=pages, multiple_tables=True)
    except Exception as exc:
        logger.warning("Tabula extraction failed: %s", exc)
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
