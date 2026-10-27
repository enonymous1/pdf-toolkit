"""Inspector subcommand logic, shared by the ``pdf-toolkit`` CLI.

This is the original ``ss-py-pdf-inspector`` CLI, with two fixes that
matter for a publishable package:

- Heavy optional imports (tables, converters) are lazy, so ``inspect
  --info`` and ``inspect --toc`` work with only the core dependencies
  installed. ``--tables`` and ``--export docx`` fail with a clear
  "install this extra" message instead of an ImportError at startup.
- ``main()`` accepts an argument list, so the top-level CLI and tests
  can call it without faking ``sys.argv``.
"""

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table as RichTable

from .adapters.pymupdf import PyMuPDFAdapter

console = Console()


def create_parser(parser: argparse.ArgumentParser | None = None) -> argparse.ArgumentParser:
    """Parser for the ``inspect`` subcommand.

    Pass an existing subparser to add the inspect arguments to it, or
    leave ``parser`` out for a standalone parser.
    """
    if parser is None:
        parser = argparse.ArgumentParser(
            description="Inspect a PDF (metadata, TOC, tables, exports)"
        )
    parser.add_argument("path", help="Path to the PDF file")
    mode = parser.add_argument_group("Analysis Modes")
    mode.add_argument("--info", action="store_true", help="Show overview & metadata (default)")
    mode.add_argument("--toc", action="store_true", help="Extract Table of Contents")
    mode.add_argument(
        "--tables", action="store_true", help="Extract tables (needs pdf-toolkit[tables])"
    )
    mode.add_argument("--explore", action="store_true", help="Launch X-Ray structural explorer")
    mode.add_argument(
        "--export",
        choices=["md", "docx", "json", "html"],
        help="Convert and export PDF to specified format",
    )
    mode.add_argument("--xray", action="store_true", help="Show raw XMP metadata (with --explore)")
    config = parser.add_argument_group("Configuration")
    config.add_argument(
        "--page", type=str, default="1", help="Page(s) to process (e.g. '1', '1-5', 'all')"
    )
    config.add_argument("--hint", type=int, default=6, help="Hint page where TOC starts")
    config.add_argument("--output", type=str, help="Output file path for export")
    config.add_argument("--json", action="store_true", help="Output as JSON (for terminal modes)")
    config.add_argument("--ocr", action="store_true", help="Enable OCR for TOC/Text (if supported)")
    return parser


def _page_numbers(page: str, total: int) -> range:
    if page == "all":
        return range(1, total + 1)
    if "-" in page:
        start, end = page.split("-", 1)
        return range(int(start), int(end) + 1)
    return range(int(page), int(page) + 1)


def run_inspect(args: argparse.Namespace) -> int:
    """Run an inspect operation parsed by :func:`create_parser`."""
    path = Path(args.path)
    if not path.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {path}")
        return 1
    try:
        if not (args.toc or args.tables or args.explore or args.export):
            args.info = True

        if args.export:
            from .extraction.converters import (
                convert_to_docx,
                convert_to_html,
                convert_to_markdown,
            )

            out_path = args.output or str(path.with_suffix(f".{args.export}"))
            console.print(f"[bold green]Exporting PDF to {args.export}...[/bold green]")
            if args.export == "md":
                convert_to_markdown(str(path), out_path, use_ocr=args.ocr, pages=args.page)
            elif args.export == "docx":
                convert_to_docx(str(path), out_path, pages=args.page)
            elif args.export == "html":
                convert_to_html(str(path), out_path, pages=args.page)
            elif args.export == "json":
                with PyMuPDFAdapter(str(path)) as adapter:
                    data = adapter.get_metadata()
                    data["toc"] = adapter.get_toc(use_ocr=args.ocr)
                    data["pages"] = [
                        {
                            "page_number": p_num,
                            "elements": [
                                {"type": "NarrativeText", "text": adapter.extract_text(str(p_num))}
                            ],
                        }
                        for p_num in _page_numbers(args.page, adapter.get_page_count())
                    ]
                    with open(out_path, "w", encoding="utf-8") as fh:
                        json.dump(data, fh, indent=2)
            console.print(f"[bold blue]Success:[/bold blue] Exported to {out_path}")
            return 0

        if args.explore:
            from .analysis.explorer import PDFExplorer

            explorer = PDFExplorer(str(path))
            explorer.show_summary()
            if args.xray:
                explorer.show_metadata_xray()
            explorer.explore_structure(int(args.page.split("-")[0]) - 1)
            return 0

        with PyMuPDFAdapter(str(path)) as adapter:
            if args.toc:
                toc = adapter.get_toc(use_ocr=args.ocr, hint_page=args.hint)
                if args.json:
                    print(json.dumps(toc, indent=2))
                else:
                    table = RichTable(title=f"TOC: {path.name}")
                    table.add_column("Title")
                    table.add_column("Page", justify="right")
                    for entry in toc:
                        table.add_row(
                            entry.get("title", "Unknown"), str(entry.get("page", "Unknown"))
                        )
                    console.print(table)
            elif args.tables:
                from .extraction.tables import extract_tables_camelot

                console.print(
                    f"[bold green]Extracting tables from pages {args.page}...[/bold green]"
                )
                dfs = extract_tables_camelot(str(path), pages=args.page)
                if args.json:
                    print(json.dumps([df.to_dict(orient="records") for df in dfs], indent=2))
                else:
                    for i, df in enumerate(dfs):
                        console.print(f"\n[bold]Table {i + 1}:[/bold]")
                        console.print(df)
            elif args.info:
                meta = adapter.get_metadata()
                if args.json:
                    print(json.dumps(meta, indent=2))
                else:
                    console.print(
                        f"[bold cyan]PDF Inspection Report:[/bold cyan] [white]{path.name}[/white]"
                    )
                    table = RichTable(show_header=False, box=None)
                    table.add_row("Type:", f"[bold]{meta.get('document_type')}[/bold]")
                    table.add_row("Pages:", str(adapter.get_page_count()))
                    table.add_row("Scanned:", f"{meta.get('scanned_page_ratio', 0) * 100:.1f}%")
                    table.add_row("Producer:", meta.get("producer", "Unknown"))
                    console.print(table)
        return 0
    except ImportError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        return 1
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        return 1


def main(argv: list[str] | None = None) -> int:
    """Entry point for standalone use (``python -m pdf_toolkit.inspector.cli``)."""
    args = create_parser().parse_args(argv)
    return run_inspect(args)


if __name__ == "__main__":
    sys.exit(main())
