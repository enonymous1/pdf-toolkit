import json
from pathlib import Path

from pdf_toolkit.inspector.adapters.pymupdf import PyMuPDFAdapter


def main():
    # Use the shipped sample PDF (examples/sample_example.pdf).
    pdf_path = Path(__file__).resolve().parents[1] / "sample_example.pdf"
    if not pdf_path.exists():
        print(f"Sample PDF not found at {pdf_path}")
        return

    print(f"--- Inspecting {pdf_path.name} with PyMuPDFAdapter ---")

    with PyMuPDFAdapter(str(pdf_path)) as adapter:
        # Get standardized metadata which now includes scanning analysis
        metadata = adapter.get_metadata()

        print(f"Document Type: {metadata.get('document_type')}")
        print(f"Scanned Ratio: {metadata.get('scanned_page_ratio'):.1%}")
        print(f"Page Count:    {adapter.get_page_count()}")
        print(f"Is Scanned:    {metadata.get('is_scanned_pdf')}")

        print("\nFull Metadata (JSON):")
        print(json.dumps(metadata, indent=2))

        # Accessing TOC (heuristic based)
        toc = adapter.get_toc()
        if toc:
            print(f"\nExtracted TOC ({len(toc)} entries):")
            for entry in toc[:5]:
                print(f" - {entry['title']} (Page {entry['page']})")
        else:
            print("\nNo TOC found (Document is scanned and OCR is not active).")


if __name__ == "__main__":
    main()
