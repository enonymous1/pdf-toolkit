"""Convert office documents to PDF, and check .docx formatting.

Merged from ss-toPDF (0.2.0): DOCX conversion via docx2pdf/Word,
XLSX conversion via Excel COM, and a parameterized .docx formatting
checker with optional Word-comment annotation. All Office imports are
lazy, so importing this package never requires the office extra.
"""

from .convert import CONVERTIBLE_SUFFIXES, convert_file, convert_path
from .docx_to_pdf import convert_docx_to_pdf
from .formatting import (
    FormattingRules,
    Issue,
    add_comments_to_docx,
    add_comments_with_word,
    check_docx_formatting,
    print_formatting_report,
)
from .xlsx_to_pdf import convert_xlsx_to_pdf, decide_page_setup

__all__ = [
    "CONVERTIBLE_SUFFIXES",
    "FormattingRules",
    "Issue",
    "add_comments_to_docx",
    "add_comments_with_word",
    "check_docx_formatting",
    "convert_docx_to_pdf",
    "convert_file",
    "convert_path",
    "convert_xlsx_to_pdf",
    "decide_page_setup",
    "print_formatting_report",
]
