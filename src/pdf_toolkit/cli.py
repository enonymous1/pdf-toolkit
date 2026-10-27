"""Top-level ``pdf-toolkit`` CLI.

Subcommands:

- ``inspect`` — the inspector (metadata, TOC, tables, exports, X-Ray).
- ``compress`` — the compressor (structural / pypdf / Ghostscript), for
  one file or a whole directory, interactively or with ``-y``.
- ``gui`` — the PyQt6 drag-and-drop GUI (needs ``pdf-toolkit[gui]``).
- ``convert`` — convert .docx/.xlsx files to PDF (needs
  ``pdf-toolkit[office]``; .xlsx needs Windows with Excel, .docx needs Word).
- ``check-format`` — check a .docx file (or a directory of them) against
  formatting rules, optionally annotating it with Word comments
  (needs ``pdf-toolkit[office]``; annotation needs Windows with Word).

``main()`` accepts an argument list and returns an exit code, so tests
can call it directly; the console-script entry point exits with it.
"""

import argparse
import sys
from pathlib import Path

from .compressor import (
    GHOSTSCRIPT_QUALITIES,
    METHODS,
    compress_pdf,
    estimate_compression,
    find_pdfs,
    format_size,
    quick_inspect,
)
from .inspector.cli import create_parser as create_inspect_parser
from .inspector.cli import run_inspect


def _compress_one(pdf_file: Path, output_dir: Path, method: str, kwargs: dict) -> int:
    target = output_dir / f"{pdf_file.stem}_compressed.pdf"
    result = compress_pdf(pdf_file, target, method, **kwargs)
    if result.success:
        print(f"DONE: {pdf_file.name}")
        print(f"  Result: {format_size(result.initial_size)} -> {format_size(result.final_size)}")
        print(f"  Space Saved: {format_size(result.saved_bytes)} ({result.reduction_pct:.2f}%)\n")
        return 0
    print(f"FAILED: {pdf_file.name} - {result.error}\n")
    return 1


def run_compress(args: argparse.Namespace) -> int:
    """Run a compress operation; mirrors ss-pdf-small, plus method choice."""
    input_path = Path(args.path) if args.path else None
    if input_path is None:
        raw = input("Please enter the path to a PDF file or directory: ").strip().strip("\"'")
        if not raw:
            print("Error: No path provided. Exiting.")
            return 1
        input_path = Path(raw)

    if args.output:
        output_dir = Path(args.output)
    else:
        default_dir = input_path if input_path.is_dir() else input_path.parent
        if args.yes:
            output_dir = default_dir
        else:
            raw = (
                input(f"Enter output directory (leave blank for {default_dir}): ")
                .strip()
                .strip("\"'")
            )
            output_dir = Path(raw) if raw else default_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = find_pdfs(input_path)
    if not pdf_files:
        print(f"Error: No valid PDF files found at {input_path}")
        return 1

    kwargs: dict = {}
    if args.method == "pypdf":
        kwargs["remove_metadata"] = args.remove_metadata
    if args.method == "ghostscript":
        kwargs["quality"] = args.gs_quality

    to_process: list[Path] = []
    yes_to_all = args.yes
    for pdf_file in pdf_files:
        info = quick_inspect(pdf_file)
        if info:
            print(f"--- Found PDF: {info['name']} ---")
            print(f"File Size:       {format_size(info['file_size'])}")
            print(f"Page Count:      {info['page_count']}")
            if info.get("metadata"):
                print(f"Title:           {info['metadata'].get('title', 'N/A')}")
                print(f"Creator:         {info['metadata'].get('creator', 'N/A')}")
            print(f"Images count:    {info['image_count']}")
            print(f"Structural IDs:  {info['object_count']}")
            print(f"Compression Potential: {estimate_compression(info)}\n")
        if yes_to_all:
            to_process.append(pdf_file)
            continue
        choice = input("Compress this PDF? (y/n/all): ").strip().lower()
        if choice == "y":
            to_process.append(pdf_file)
        elif choice == "all":
            idx = pdf_files.index(pdf_file)
            to_process.extend(pdf_files[idx:])
            break
        elif choice == "n":
            print(f"Skipping: {pdf_file.name}\n")
        else:
            print(f"Input '{choice}' not recognized, skipping.\n")

    if not to_process:
        print("No files selected for compression. Done.")
        return 0
    print(f"\nProcessing {len(to_process)} file(s)...\n")
    failures = 0
    for pdf_file in to_process:
        failures += _compress_one(pdf_file, output_dir, args.method, kwargs)
    return 1 if failures else 0


def run_convert(args: argparse.Namespace) -> int:
    """Convert a file or directory of office documents to PDF."""
    from .to_pdf import convert_file, convert_path

    input_path = Path(args.path)
    try:
        if input_path.is_dir():
            outputs = convert_path(input_path, args.output)
        else:
            outputs = [convert_file(input_path, args.output)]
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 2
    except ValueError as exc:
        print(f"Error: {exc}")
        return 2
    except ImportError as exc:
        print(f"Error: {exc}")
        return 1
    for output in outputs:
        print(f"PDF saved to {output}")
    if not outputs:
        print("No convertible files found.")
    return 0


def _check_format_rules(args: argparse.Namespace):
    from .to_pdf import FormattingRules

    return FormattingRules(
        font=args.font,
        body_size=args.body_size,
        caption_size=args.caption_size,
        footnote_size=args.footnote_size,
        spacing=args.spacing,
        margin_inches=args.margin,
    )


def run_check_format(args: argparse.Namespace) -> int:
    """Check .docx formatting for one file or a whole directory."""
    from .to_pdf import add_comments_to_docx, print_formatting_report

    input_path = Path(args.path)
    rules = _check_format_rules(args)
    try:
        if input_path.is_dir():
            if not args.output:
                print("Error: Checking a directory needs an output directory (-o).")
                return 2
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
            report_path = output_dir / "formatting_report.txt"
            any_issues = False
            with report_path.open("w", encoding="utf-8") as report:
                for candidate in sorted(input_path.iterdir()):
                    if candidate.is_file() and candidate.suffix.lower() == ".docx":
                        issues = print_formatting_report(candidate, rules, file=report)
                        any_issues = any_issues or bool(issues)
                        if args.annotate:
                            marked = output_dir / f"{candidate.stem}_markedup.docx"
                            add_comments_to_docx(candidate, marked, issues)
                            print(f"Annotated copy saved to {marked}")
            print(f"Formatting report written to {report_path}")
            return 1 if any_issues else 0

        if args.report:
            with Path(args.report).open("w", encoding="utf-8") as report:
                issues = print_formatting_report(input_path, rules, file=report)
            print(f"Formatting report written to {args.report}")
        else:
            issues = print_formatting_report(input_path, rules)
        if args.output:
            add_comments_to_docx(input_path, Path(args.output), issues)
            print(f"Annotated copy saved to {args.output}")
        return 1 if issues else 0
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 2
    except ImportError as exc:
        print(f"Error: {exc}")
        return 1


def run_gui() -> int:
    """Launch the GUI, with a readable error if PyQt6 is missing."""
    try:
        from .gui.main_gui import main as gui_main
    except ImportError as exc:
        print(
            "The GUI needs PyQt6, which is not installed.\n"
            "Install it with: pip install 'pdf-toolkit[gui]'\n"
            f"(import error: {exc})"
        )
        return 1
    gui_main()
    return 0


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-toolkit",
        description="Inspect, compress, and convert PDFs, and check .docx formatting.",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    if args.command == "inspect":
        return run_inspect(args)
    if args.command == "compress":
        return run_compress(args)
    if args.command == "gui":
        return run_gui()
    if args.command == "convert":
        return run_convert(args)
    if args.command == "check-format":
        return run_check_format(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
