"""Top-level ``pdf-toolkit`` CLI.

Subcommands:

- ``inspect`` — the inspector (metadata, TOC, tables, exports, X-Ray).
- ``compress`` — the compressor (structural / pypdf / Ghostscript), for
  one file or a whole directory, interactively or with ``-y``.
- ``split`` — split a PDF into one file per chapter, by bookmarks, a
  ``title,page`` CSV, or located headings. Dry-run by default; ``-y``
  writes the files.
- ``gui`` — the PyQt6 drag-and-drop GUI (needs ``pdf-toolkit[gui]``).
- ``dissect`` — find templated form pages in a PDF and rebuild them
  as fillable forms: ``detect``, ``reconstruct``, ``fill``,
  ``export-docx``, ``serve`` (needs ``pdf-toolkit[dissect]`` for the
  image/OCR/DOCX/server paths; keyword detection needs only core deps).
- ``convert`` — convert .docx/.xlsx files to PDF (needs
  ``pdf-toolkit[office]``; .xlsx needs Windows with Excel, .docx needs Word).
- ``check-format`` — check a .docx file (or a directory of them) against
  formatting rules, optionally annotating it with Word comments
  (needs ``pdf-toolkit[office]``; annotation needs Windows with Word).
- ``check-citations`` — flag DOCX manuscript text similar to a PDF
  source, for manual citation review (needs ``pdf-toolkit[citations]``
  for the DOCX reader). Exit 0 when nothing matches, 1 when matches
  are found, 2 for a usage or file error.

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


def run_split(args: argparse.Namespace) -> int:
    """Split a PDF into chapter PDFs; dry-run unless ``--yes`` is given."""
    from pypdf import PdfReader

    from .splitter import load_entries_from_csv as _load_groups
    from .splitter import (
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


def run_check_citations(args: argparse.Namespace) -> int:
    """Flag DOCX text similar to a PDF source, for citation review."""
    import json

    from .citations import CitationError, compare_documents

    try:
        results = compare_documents(
            args.docx,
            args.pdf,
            threshold=args.threshold,
            min_chunk_length=args.min_chunk_length,
            context_sentences=args.context_sentences,
            max_window=args.max_window_size,
            min_pdf_snippet_length=args.min_pdf_snippet_length,
            min_overlap=args.min_overlap,
            skip_cited=args.skip_cited,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 2
    except (CitationError, ValueError) as exc:
        print(f"Error: {exc}")
        return 2
    except ImportError as exc:
        print(f"Error: {exc}")
        return 1

    if args.json_out:
        payload = [match.to_dict() for match in results]
        with Path(args.json_out).open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print(f"Wrote JSON report to {args.json_out}")
    else:
        if not results:
            print("No matches found.")
        for match in results:
            print("---")
            print(f"Doc chunk id: {match.doc_chunk_id} ({match.doc_source})")
            print(f"Similarity: {match.score}")
            print(f"PDF page: {match.page_number}")
            if match.has_citation_marker:
                print("Note: doc chunk carries a citation marker; review it anyway.")
            print("PDF snippet:")
            print(match.pdf_snippet)
            if match.pdf_context:
                print("PDF context:")
                print(match.pdf_context)
            print("Doc text:")
            print(match.doc_text)

    print(f"Found {len(results)} matches (threshold {args.threshold})")
    return 1 if results else 0


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


def _load_json_file(path: str, label: str) -> dict | None:
    import json

    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error: Cannot read {label} file {path}: {exc}")
        return None
    if not isinstance(data, dict):
        print(f"Error: {label} file {path} must contain a JSON object")
        return None
    return data


def _page_data(data: dict, page_num: int) -> dict:
    """Per-page data, falling back to a ``global`` mapping, then the whole mapping."""
    return data.get(str(page_num), data.get("global", data))


def _template_from_args(args: argparse.Namespace):
    if args.keywords:
        return list(args.keywords)
    return args.template_image


def _run_dissect_detect(args: argparse.Namespace) -> int:
    """Detect templated pages and print the result as JSON."""
    import json

    from .dissect import DetectionError, find_template_pages, page_texts

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        return 2
    try:
        result = find_template_pages(
            pdf_path,
            _template_from_args(args),
            threshold=args.threshold,
            min_ratio=args.min_ratio,
            dpi=args.dpi,
        )
    except DetectionError as exc:
        print(f"Error: {exc}")
        return 1
    print(json.dumps(result.to_dict(), indent=2))
    if result.matched_pages:
        if isinstance(_template_from_args(args), list):
            pages = {p.page_number: p.text for p in page_texts(pdf_path)}
            for page_num in result.matched_pages:
                text = pages.get(page_num, "")
                for keyword in args.keywords:
                    idx = text.lower().find(keyword.lower())
                    if idx >= 0:
                        snippet = text[max(0, idx - args.snippet) : idx + args.snippet]
                        print(f"\n--- Page {page_num} snippet (keyword: '{keyword}') ---")
                        print(snippet.replace("\n", " "))
                        break
        if args.save_pages_dir:
            import fitz

            outdir = Path(args.save_pages_dir)
            outdir.mkdir(parents=True, exist_ok=True)
            doc = fitz.open(str(pdf_path))
            try:
                for page_num in result.matched_pages:
                    page = doc.load_page(page_num - 1)
                    pix = page.get_pixmap(
                        matrix=fitz.Matrix(args.dpi / 72, args.dpi / 72), alpha=False
                    )
                    out_path = outdir / f"page_{page_num}.png"
                    pix.save(str(out_path))
                    print(f"Saved page {page_num} as image: {out_path}")
            finally:
                doc.close()
        if args.save_pages_pdf:
            from .dissect import extract_pages_to_bytes

            outdir = Path(args.save_pages_pdf)
            outdir.mkdir(parents=True, exist_ok=True)
            for page_num in result.matched_pages:
                out_path = outdir / f"page_{page_num}.pdf"
                out_path.write_bytes(extract_pages_to_bytes(pdf_path, [page_num]))
                print(f"Saved page {page_num} as PDF: {out_path}")
    return 0


def _run_dissect_reconstruct(args: argparse.Namespace) -> int:
    """Detect, then reconstruct matched pages (HTML + fillable PDF + fieldmap JSON)."""
    import json

    from .dissect import (
        DetectionError,
        ReconstructionError,
        find_template_pages,
        reconstruct_pdf_pages,
    )

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        return 2
    prefill = {}
    if args.fill_data:
        prefill = _load_json_file(args.fill_data, "fill-data")
        if prefill is None:
            return 2
    try:
        result = find_template_pages(
            pdf_path,
            _template_from_args(args),
            threshold=args.threshold,
            min_ratio=args.min_ratio,
            dpi=args.dpi,
        )
    except DetectionError as exc:
        print(f"Error: {exc}")
        return 1
    print(f"Matched pages: {result.matched_pages}")
    if not result.matched_pages:
        return 0
    out_dir = Path(args.out_dir)
    try:
        results = reconstruct_pdf_pages(pdf_path, result.matched_pages, out_dir, dpi=args.dpi)
    except ReconstructionError as exc:
        print(f"Error: {exc}")
        return 1
    print(json.dumps({str(k): v for k, v in results.items()}, indent=2))
    if args.to_html_dir or args.interactive_html_dir:
        from .dissect import create_html_overlay, export_html_to_file, load_fieldmap
        from .dissect.detect import require_cv2

        try:
            cv2, _np = require_cv2()
        except DetectionError as exc:
            print(f"Error: {exc}")
            return 1
        for page_num, info in results.items():
            page_prefill = _page_data(prefill, page_num) if prefill else {}
            img = cv2.imread(info["image"])
            fields = load_fieldmap(info["fieldmap"])
            if args.to_html_dir:
                tdir = Path(args.to_html_dir)
                tdir.mkdir(parents=True, exist_ok=True)
                html_text = create_html_overlay(img, fields, data=page_prefill)
                out_html = tdir / f"page_{page_num}.html"
                export_html_to_file(html_text, str(out_html))
                print(f"Exported HTML for page {page_num} -> {out_html}")
            if args.interactive_html_dir:
                idir = Path(args.interactive_html_dir)
                idir.mkdir(parents=True, exist_ok=True)
                html_text = create_html_overlay(
                    img,
                    fields,
                    data=page_prefill,
                    interactive=True,
                    interactive_out_path=info["fieldmap"],
                )
                out_int = idir / f"page_{page_num}.html"
                export_html_to_file(html_text, str(out_int))
                print(f"Exported interactive HTML for page {page_num} -> {out_int}")
    return 0


def _run_dissect_fill(args: argparse.Namespace) -> int:
    """Fill pages using fieldmaps (JSON) and a data JSON file."""
    from .dissect import (
        ExtractionError,
        FieldmapError,
        FillError,
        extract_pages_to_bytes,
        fill_pdf_fields,
        find_fieldmaps,
        load_fieldmap,
        page_number_from_name,
    )

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        return 2
    if not Path(args.fieldmap).exists():
        print(f"Error: Fieldmap not found: {args.fieldmap}")
        return 2
    data = _load_json_file(args.data, "data")
    if data is None:
        return 2
    outdir = Path(args.out_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    failures = 0
    for fmap_path in find_fieldmaps(args.fieldmap):
        page_num = page_number_from_name(fmap_path)
        try:
            fields = load_fieldmap(fmap_path)
        except FieldmapError as exc:
            print(f"Error: {exc}")
            failures += 1
            continue
        page_data = _page_data(data, page_num) if page_num else data
        if not isinstance(page_data, dict):
            page_data = {}
        try:
            if page_num:
                pdf_bytes = extract_pages_to_bytes(pdf_path, [page_num])
            else:
                pdf_bytes = pdf_path.read_bytes()
            filled = fill_pdf_fields(pdf_bytes, page_data, fields=fields, dpi=args.dpi)
        except (ExtractionError, FillError) as exc:
            print(f"Error: {exc}")
            failures += 1
            continue
        out_pdf = outdir / f"page_{page_num}_filled.pdf"
        out_pdf.write_bytes(filled)
        print(f"Wrote filled PDF: {out_pdf}")
        img_path = fmap_path.parent.parent / "images" / f"page_{page_num}.png"
        if page_num and img_path.exists():
            try:
                from .dissect import create_html_overlay, export_html_to_file
                from .dissect.detect import require_cv2

                cv2, _np = require_cv2()
                img = cv2.imread(str(img_path))
                html_text = create_html_overlay(img, fields, data=page_data)
                out_html = outdir / f"page_{page_num}_filled.html"
                export_html_to_file(html_text, str(out_html))
                print(f"Wrote filled HTML: {out_html}")
            except Exception as exc:
                print(f"Warning: could not write filled HTML for page {page_num}: {exc}")
    return 1 if failures else 0


def _run_dissect_export_docx(args: argparse.Namespace) -> int:
    """Export reconstructed pages to DOCX, optionally filled with data."""
    from .dissect import (
        DocxError,
        FieldmapError,
        find_fieldmaps,
        load_fieldmap,
        page_number_from_name,
        page_to_docx,
    )

    if args.fill and not args.data:
        print("Error: --fill requires --data")
        return 2
    if not Path(args.fieldmap).exists():
        print(f"Error: Fieldmap not found: {args.fieldmap}")
        return 2
    data = None
    if args.data:
        data = _load_json_file(args.data, "data")
        if data is None:
            return 2
    outdir = Path(args.out_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    failures = 0
    for fmap_path in find_fieldmaps(args.fieldmap):
        page_num = page_number_from_name(fmap_path)
        try:
            fields = load_fieldmap(fmap_path)
        except FieldmapError as exc:
            print(f"Error: {exc}")
            failures += 1
            continue
        img_path = fmap_path.parent.parent / "images" / f"page_{page_num}.png"
        if not img_path.exists():
            print(f"Image not found for page {page_num}, skipping")
            failures += 1
            continue
        out_docx = outdir / f"page_{page_num}.docx"
        try:
            from .dissect.detect import require_cv2

            cv2, _np = require_cv2()
            img = cv2.imread(str(img_path))
            page_to_docx(img, fields, str(out_docx), dpi=args.dpi)
        except Exception as exc:
            print(f"Error: {exc}")
            failures += 1
            continue
        print(f"Exported DOCX for page {page_num} -> {out_docx}")
        if args.fill and data is not None:
            from .dissect import fill_docx_template

            page_data = _page_data(data, page_num) if page_num else data
            out_filled = outdir / f"page_{page_num}_filled.docx"
            try:
                fill_docx_template(str(out_docx), page_data or {}, str(out_filled))
                print(f"Exported filled DOCX for page {page_num} -> {out_filled}")
            except DocxError as exc:
                print(f"Failed to fill DOCX for page {page_num}: {exc}")
                failures += 1
    return 1 if failures else 0


def _run_dissect_serve(args: argparse.Namespace) -> int:
    """Run the confined preview server over a reconstruct output directory."""
    from .dissect import run_server

    root = Path(args.root)
    if not root.exists():
        print(f"Error: Root directory not found: {root}")
        return 2
    try:
        run_server(root, host=args.host, port=args.port)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1
    return 0


def run_dissect(args: argparse.Namespace) -> int:
    if args.dissect_command == "detect":
        return _run_dissect_detect(args)
    if args.dissect_command == "reconstruct":
        return _run_dissect_reconstruct(args)
    if args.dissect_command == "fill":
        return _run_dissect_fill(args)
    if args.dissect_command == "export-docx":
        return _run_dissect_export_docx(args)
    if args.dissect_command == "serve":
        return _run_dissect_serve(args)
    return 2


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
        "--dpi", type=int, default=150, help="DPI the field boxes were detected at"
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
        "--dpi", type=int, default=150, help="DPI used for image sizes in DOCX"
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


def main(argv: list[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    if args.command == "inspect":
        return run_inspect(args)
    if args.command == "compress":
        return run_compress(args)
    if args.command == "split":
        return run_split(args)
    if args.command == "dissect":
        return run_dissect(args)
    if args.command == "gui":
        return run_gui()
    if args.command == "convert":
        return run_convert(args)
    if args.command == "check-format":
        return run_check_format(args)
    if args.command == "check-citations":
        return run_check_citations(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
