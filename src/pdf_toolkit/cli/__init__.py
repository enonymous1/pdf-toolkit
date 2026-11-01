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

The command implementations live in the sibling modules of this
package (one per command family); this module only wires them
together and provides :func:`main`, so existing imports like
``from pdf_toolkit.cli import main`` keep working unchanged.
"""

from __future__ import annotations

import logging

from ..inspector.cli import run_inspect
from .citations import run_check_citations
from .compress import run_compress
from .dissect import run_dissect
from .gui import run_gui
from .office import run_check_format, run_convert
from .parser import create_parser
from .split import run_split

__all__ = [
    "create_parser",
    "main",
    "run_check_citations",
    "run_check_format",
    "run_compress",
    "run_convert",
    "run_dissect",
    "run_gui",
    "run_split",
]


def main(argv: list[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    if getattr(args, "verbose", False):
        logging.basicConfig(level=logging.DEBUG)
    elif getattr(args, "quiet", False):
        logging.basicConfig(level=logging.WARNING)
    else:
        logging.basicConfig(level=logging.INFO)
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
