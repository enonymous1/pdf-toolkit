from .adapters.pdfminer import PDFMinerAdapter
from .adapters.pdfplumber import PDFPlumberAdapter
from .adapters.pymupdf import PyMuPDFAdapter
from .adapters.pypdf import PyPDFAdapter
from .analysis.scanning import analyze_document_scanning
from .utils import (
    extract_xmp_from_file,
    metadata_to_markdown,
    normalize_metadata,
    parse_page_range,
    unique_output_path,
)
from .utils import (
    normalize_metadata as normalize_pdf_metadata,
)

__all__ = [
    "unique_output_path",
    "normalize_metadata",
    "normalize_pdf_metadata",
    "parse_page_range",
    "metadata_to_markdown",
    "extract_xmp_from_file",
    "analyze_document_scanning",
    "PyMuPDFAdapter",
    "PyPDFAdapter",
    "PDFMinerAdapter",
    "PDFPlumberAdapter",
]
