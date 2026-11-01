"""Office subcommands (``pdf-toolkit convert`` and ``check-format``)."""

from __future__ import annotations

import argparse
from pathlib import Path


def run_convert(args: argparse.Namespace) -> int:
    """Convert a file or directory of office documents to PDF."""
    from ..to_pdf import convert_file, convert_path

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
    from ..to_pdf import FormattingRules

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
    from ..to_pdf import add_comments_to_docx, print_formatting_report

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
