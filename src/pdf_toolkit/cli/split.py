"""Split subcommand (``pdf-toolkit split``)."""

from __future__ import annotations

import argparse
from pathlib import Path


def run_split(args: argparse.Namespace) -> int:
    """Split a PDF into chapter PDFs; dry-run unless ``--yes`` is given."""
    from pypdf import PdfReader

    from ..splitter import load_entries_from_csv as _load_groups
    from ..splitter import (
        propose_ranges,
        resolve_entries,
        split_pdf,
        write_entries_csv,
    )

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        return 2
    for label, value in (
        ("--csv", args.csv),
        ("--headings", args.headings),
        ("--group-csv", args.group_csv),
    ):
        if value and not Path(value).exists():
            print(f"Error: {label} file not found: {value}")
            return 2

    entries, source, warnings = resolve_entries(
        pdf_path,
        csv_path=args.csv,
        headings_path=args.headings,
        toc_text=args.toc_text,
        hint_page=args.hint,
        offset=args.offset,
        fuzzy_headings=args.fuzzy,
    )
    for warning in warnings:
        print(f"Warning: {warning}")
    if not entries:
        print(
            "Error: No chapter entries found. Provide --csv or --headings, "
            "or use --toc-text when the PDF has no bookmarks."
        )
        return 2

    total_pages = len(PdfReader(str(pdf_path)).pages)
    ranges, range_warnings = propose_ranges(entries, total_pages, merge_same_page=not args.no_merge)
    for warning in range_warnings:
        print(f"Warning: {warning}")
    if not ranges:
        print("Error: No valid chapter ranges inside this PDF's page range.")
        return 2

    print(f"Source: {source}; total pages: {total_pages}")
    print("Proposed splits:")
    for num, chapter in enumerate(ranges, start=1):
        print(f"{num:02d}: '{chapter.title}' -> pages {chapter.start + 1} - {chapter.end + 1}")

    if args.export_csv:
        write_entries_csv(entries, args.export_csv)
        print(f"\nExported entries to CSV: {args.export_csv}")
        return 0

    if args.dry_run or not args.yes:
        print("\nDry run (no files written). Re-run with --yes to write the chapter PDFs.")
        return 0

    groups = None
    if args.group_csv:
        groups, group_warnings = _load_groups(args.group_csv)
        for warning in group_warnings:
            print(f"Warning: {warning}")
    out_dir = Path(args.out_dir) if args.out_dir else pdf_path.parent / (pdf_path.stem + " - split")
    try:
        written = split_pdf(
            pdf_path,
            entries,
            out_dir,
            groups=groups,
            merge_same_page=not args.no_merge,
            clean_names=args.clean_names,
            overwrite=args.overwrite,
            preserve_metadata=not args.no_metadata,
        )
    except (FileExistsError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1
    for chapter, path in zip(ranges, written):
        print(f"Wrote: {path} ({chapter.start + 1}-{chapter.end + 1})")
    return 0
