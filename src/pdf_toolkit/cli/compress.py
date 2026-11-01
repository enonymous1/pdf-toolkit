"""Compress subcommand (``pdf-toolkit compress``)."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..compressor import compress_pdf
from ..compressor.files import find_pdfs, format_size
from ..compressor.inspect import estimate_compression, quick_inspect


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
