"""PDF compression: structural (PyMuPDF), pypdf, and Ghostscript."""

from .core import (
    GHOSTSCRIPT_QUALITIES,
    METHODS,
    CompressionResult,
    compress_ghostscript,
    compress_pdf,
    compress_pdf_structural,
    compress_pypdf,
    compress_structural,
    find_ghostscript,
)
from .files import find_pdfs, format_size, get_file_size
from .inspect import estimate_compression, quick_inspect

__all__ = [
    "GHOSTSCRIPT_QUALITIES",
    "METHODS",
    "CompressionResult",
    "compress_ghostscript",
    "compress_pdf",
    "compress_pdf_structural",
    "compress_pypdf",
    "compress_structural",
    "estimate_compression",
    "find_ghostscript",
    "find_pdfs",
    "format_size",
    "get_file_size",
    "quick_inspect",
]
