"""Argument parsing for the top-level CLI (no command logic here)."""

from __future__ import annotations

import argparse

from .._defaults import DEFAULT_DPI
from ..compressor.core import GHOSTSCRIPT_QUALITIES, METHODS
from ..inspector.cli import create_parser as create_inspect_parser


def _add_template_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--keyword",
        action="append",
        dest="keywords",
        metavar="KEYWORD",
        help="Keyword identifying the template (repeatable; replaces the "
        "original --keywords, which swallowed subcommand names)",
    )
    group.add_argument("--template-image", help="Path to a template image of the blank form")
    parser.add_argument("--threshold", type=float, default=0.7, help="Image match threshold")
    parser.add_argument("--min-ratio", type=float, default=0.5, help="Keyword match ratio required")
    parser.add_argument("--dpi", type=int, default=150, help="DPI for rendering pages")


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-toolkit",
        description="Inspect, compress, split, dissect, and convert PDFs, check .docx formatting, and flag uncited-looking DOCX text against a PDF source.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_parser = sub.add_parser("inspect", help="Inspect a PDF")
    create_inspect_parser(inspect_parser)

    compress_parser = sub.add_parser("compress", help="Compress a PDF or directory of PDFs")
    compress_parser.add_argument(
        "path", nargs="?", help="PDF file or directory (prompted if omitted)"
    )
    compress_parser.add_argument(
        "-o", "--output", help="Directory to save compressed files (defaults to input directory)"
    )
    compress_parser.add_argument(
        "-y", "--yes", action="store_true", help="Automatically confirm all compression steps"
    )
    compress_parser.add_argument(
        "--method",
        choices=METHODS,
        default="structural",
        help="Compression method (default: structural)",
    )
    compress_parser.add_argument(
        "--gs-quality",
        choices=GHOSTSCRIPT_QUALITIES,
        default="ebook",
        help="Ghostscript PDFSETTINGS preset (ghostscript method only)",
    )
    compress_parser.add_argument(
        "--remove-metadata", action="store_true", help="Drop metadata (pypdf method only)"
    )

    sub.add_parser("gui", help="Open the drag-and-drop GUI (needs pdf-toolkit[gui])")

    web_parser = sub.add_parser("web", help="Serve the browser frontend (needs pdf-toolkit[web])")
    web_parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    web_parser.add_argument("--port", type=int, default=5000, help="Port to bind (default: 5000)")
    web_parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Allow binding to a non-loopback host (the server has no authentication)",
    )
    web_parser.add_argument(
        "--demo",
        action="store_true",
        help="Serve seeded demo data instead of processing uploads",
    )
    web_parser.add_argument(
        "--upload-dir", help="Directory for uploaded files (default: a fresh temp directory)"
    )
    web_parser.add_argument(
        "--freeze-dir",
        help="Write the frozen demo site to this directory and exit (implies --demo)",
    )

    split_parser = sub.add_parser(
        "split", help="Split a PDF into one file per chapter (dry-run by default)"
    )
    split_parser.add_argument("pdf", help="PDF file to split")
    split_parser.add_argument(
        "out_dir", nargs="?", help="Output directory (default: <pdf stem> - split)"
    )
    split_parser.add_argument("--csv", help="CSV file with title,page (1-based) per line")
    split_parser.add_argument(
        "--headings", help="Text file, one heading per line; pages located by text search"
    )
    split_parser.add_argument(
        "--toc-text",
        action="store_true",
        help="Fall back to the printed TOC text when the PDF has no bookmarks",
    )
    split_parser.add_argument(
        "--hint", type=int, default=6, help="1-based page where the printed TOC likely starts"
    )
    split_parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Pages to add to printed TOC numbers to get physical pages (front matter)",
    )
    split_parser.add_argument(
        "--export-csv", help="Write resolved entries as title,page CSV and exit without splitting"
    )
    split_parser.add_argument(
        "--group-csv", help="CSV with title,page (1-based) for grouping outputs into subfolders"
    )
    split_parser.add_argument(
        "--dry-run", "-n", action="store_true", help="Only print proposed ranges (the default)"
    )
    split_parser.add_argument("--yes", "-y", action="store_true", help="Write the chapter PDFs")
    split_parser.add_argument(
        "--no-merge", action="store_true", help="Do not merge entries starting on the same page"
    )
    split_parser.add_argument(
        "--clean-names",
        action="store_true",
        help="Clean messy split titles with the filename heuristics",
    )
    split_parser.add_argument(
        "--overwrite", action="store_true", help="Replace existing output files"
    )
    split_parser.add_argument(
        "--no-metadata", action="store_true", help="Do not copy source metadata onto chunks"
    )
    split_parser.add_argument(
        "--fuzzy",
        action="store_true",
        help="Headings mode: fall back to approximate matching for unfound headings",
    )

    dissect_parser = sub.add_parser(
        "dissect",
        help="Find templated form pages and rebuild them as fillable forms "
        "(needs pdf-toolkit[dissect] for image/OCR/DOCX/server paths)",
    )
    dissect_sub = dissect_parser.add_subparsers(dest="dissect_command", required=True)

    detect_parser = dissect_sub.add_parser("detect", help="Detect templated pages in a PDF")
    detect_parser.add_argument("pdf", help="PDF file to search")
    _add_template_args(detect_parser)
    detect_parser.add_argument(
        "--snippet", type=int, default=120, help="Chars of context around a keyword match"
    )
    detect_parser.add_argument("--save-pages-dir", help="Save matched pages as PNG images")
    detect_parser.add_argument("--save-pages-pdf", help="Save matched pages as single-page PDFs")

    recon_parser = dissect_sub.add_parser(
        "reconstruct", help="Reconstruct matched pages as HTML, fillable PDF, and fieldmaps"
    )
    recon_parser.add_argument("pdf", help="PDF file to reconstruct")
    _add_template_args(recon_parser)
    recon_parser.add_argument(
        "--out-dir", required=True, help="Output directory (images/, html/, ...)"
    )
    recon_parser.add_argument(
        "--to-html-dir", help="Also export HTML overlay pages to this directory"
    )
    recon_parser.add_argument(
        "--interactive-html-dir",
        help="Also export interactive HTML pages (drag/rename/save editor)",
    )
    recon_parser.add_argument("--fill-data", help="JSON file with values to pre-fill exported HTML")

    fill_parser = dissect_sub.add_parser(
        "fill", help="Fill pages using a fieldmap JSON (or directory) and data JSON"
    )
    fill_parser.add_argument("pdf", help="Source PDF (page bytes come from here)")
    fill_parser.add_argument(
        "--fieldmap",
        required=True,
        help="Fieldmap JSON file, or a directory containing *fieldmap.json files",
    )
    fill_parser.add_argument(
        "--data", required=True, help="JSON file mapping field names to values"
    )
    fill_parser.add_argument("--out-dir", required=True, help="Output directory for filled results")
    fill_parser.add_argument(
        "--dpi", type=int, default=DEFAULT_DPI, help="DPI the field boxes were detected at"
    )

    docx_parser = dissect_sub.add_parser(
        "export-docx", help="Export reconstructed pages to DOCX using fieldmaps"
    )
    docx_parser.add_argument(
        "--fieldmap",
        required=True,
        help="Fieldmap JSON file, or a reconstruct output directory (html/ + images/)",
    )
    docx_parser.add_argument("--out-dir", required=True, help="Output directory for DOCX files")
    docx_parser.add_argument(
        "--dpi", type=int, default=DEFAULT_DPI, help="DPI used for image sizes in DOCX"
    )
    docx_parser.add_argument(
        "--fill", action="store_true", help="Fill the DOCX templates using --data"
    )
    docx_parser.add_argument("--data", help="JSON data file when using --fill")

    serve_parser = dissect_sub.add_parser(
        "serve", help="Preview reconstructed pages in a local server (loopback only)"
    )
    serve_parser.add_argument("--root", required=True, help="Reconstruct output directory to serve")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    serve_parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Allow a non-loopback --host. The server has no authentication, "
        "so only use this on a network you trust.",
    )
    serve_parser.add_argument("--port", type=int, default=5000, help="Port to bind")

    convert_parser = sub.add_parser(
        "convert", help="Convert .docx/.xlsx to PDF (needs pdf-toolkit[office])"
    )
    convert_parser.add_argument("path", help="Office file or directory to convert")
    convert_parser.add_argument(
        "-o",
        "--output",
        help="Output PDF file (single file) or output directory (directory input, required)",
    )

    check_parser = sub.add_parser(
        "check-format", help="Check .docx formatting (needs pdf-toolkit[office])"
    )
    check_parser.add_argument("path", help=".docx file or directory of .docx files")
    check_parser.add_argument(
        "-o",
        "--output",
        help="Single file: annotated .docx to write. Directory: output directory (required); "
        "the report goes there as formatting_report.txt",
    )
    check_parser.add_argument(
        "--annotate",
        action="store_true",
        help="Directory mode: also write *_markedup.docx copies (needs Windows with Word)",
    )
    check_parser.add_argument("--report", help="Single file: write the report to this file")
    check_parser.add_argument("--font", default="Calibri", help="Required font (default: Calibri)")
    check_parser.add_argument("--body-size", type=float, default=12.0, help="Body size in pt")
    check_parser.add_argument("--caption-size", type=float, default=10.0, help="Caption size in pt")
    check_parser.add_argument(
        "--footnote-size", type=float, default=10.0, help="Footnote size in pt"
    )
    check_parser.add_argument("--spacing", type=float, default=1.0, help="Line spacing")
    check_parser.add_argument("--margin", type=float, default=1.0, help="Margin in inches")

    citations_parser = sub.add_parser(
        "check-citations",
        help="Flag DOCX text similar to a PDF source (needs pdf-toolkit[citations])",
    )
    citations_parser.add_argument("docx", help="Path to the DOCX manuscript")
    citations_parser.add_argument("pdf", help="Path to the PDF source material")
    citations_parser.add_argument(
        "--threshold", type=int, default=85, help="Similarity threshold (0-100)"
    )
    citations_parser.add_argument("--json-out", help="Write JSON report to this file")
    citations_parser.add_argument(
        "--min-chunk-length",
        type=int,
        default=0,
        help="Minimum characters in a doc chunk to consider",
    )
    citations_parser.add_argument(
        "--context-sentences",
        type=int,
        default=1,
        help="Number of surrounding PDF sentences to include in context",
    )
    citations_parser.add_argument(
        "--max-window-size",
        type=int,
        default=3,
        help="Maximum number of PDF sentences to combine for matching window",
    )
    citations_parser.add_argument(
        "--min-pdf-snippet-length",
        type=int,
        default=10,
        help="Minimum alphanumeric length for a PDF snippet to count as a match",
    )
    citations_parser.add_argument(
        "--min-overlap",
        type=float,
        default=0.5,
        help="Fraction of a chunk's tokens a window must share before scoring (0-1)",
    )
    citations_parser.add_argument(
        "--skip-cited",
        action="store_true",
        help="Skip doc chunks carrying an explicit citation marker",
    )
    return parser
