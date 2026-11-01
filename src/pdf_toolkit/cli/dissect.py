"""Dissect subcommands (``pdf-toolkit dissect ...``)."""

from __future__ import annotations

import argparse
from pathlib import Path


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

    from ..dissect import DetectionError, find_template_pages, page_texts

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
            import pymupdf

            outdir = Path(args.save_pages_dir)
            outdir.mkdir(parents=True, exist_ok=True)
            doc = pymupdf.open(str(pdf_path))
            try:
                for page_num in result.matched_pages:
                    page = doc.load_page(page_num - 1)
                    pix = page.get_pixmap(
                        matrix=pymupdf.Matrix(args.dpi / 72, args.dpi / 72), alpha=False
                    )
                    out_path = outdir / f"page_{page_num}.png"
                    pix.save(str(out_path))
                    print(f"Saved page {page_num} as image: {out_path}")
            finally:
                doc.close()
        if args.save_pages_pdf:
            from ..dissect import extract_pages_to_bytes

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

    from ..dissect import (
        DetectionError,
        ReconstructionError,
        find_template_pages,
        reconstruct_pdf_pages,
    )

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        return 2
    prefill: dict | None = {}
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
        from ..dissect import create_html_overlay, export_html_to_file, load_fieldmap
        from ..dissect.detect import require_cv2

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
    from ..dissect import (
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
                from ..dissect import create_html_overlay, export_html_to_file
                from ..dissect.detect import require_cv2

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
    from ..dissect import (
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
            from ..dissect.detect import require_cv2

            cv2, _np = require_cv2()
            img = cv2.imread(str(img_path))
            page_to_docx(img, fields, str(out_docx), dpi=args.dpi)
        except Exception as exc:
            print(f"Error: {exc}")
            failures += 1
            continue
        print(f"Exported DOCX for page {page_num} -> {out_docx}")
        if args.fill and data is not None:
            from ..dissect import fill_docx_template

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
    from ..dissect import run_server

    root = Path(args.root)
    if not root.exists():
        print(f"Error: Root directory not found: {root}")
        return 2
    try:
        run_server(root, host=args.host, port=args.port, allow_remote=args.allow_remote)
    except (RuntimeError, ValueError) as exc:
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
