"""PDF splitting: one PDF per chapter, by bookmarks, CSV, or headings."""

from .core import (
    UNDESIRABLE_SUBSTRINGS,
    Entry,
    ProposedRange,
    clean_filename,
    extract_outline_entries,
    extract_text_toc_entries,
    load_entries_from_csv,
    locate_headings,
    propose_ranges,
    resolve_entries,
    sanitize_filename,
    split_pdf,
    write_entries_csv,
)

__all__ = [
    "UNDESIRABLE_SUBSTRINGS",
    "Entry",
    "ProposedRange",
    "clean_filename",
    "extract_outline_entries",
    "extract_text_toc_entries",
    "load_entries_from_csv",
    "locate_headings",
    "propose_ranges",
    "resolve_entries",
    "sanitize_filename",
    "split_pdf",
    "write_entries_csv",
]
