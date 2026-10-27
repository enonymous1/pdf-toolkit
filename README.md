# pdf-toolkit

Inspect a PDF, compare how four Python PDF libraries see it, then shrink it — from one package, one CLI.

[![CI](https://github.com/enonymous1/pdf-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/enonymous1/pdf-toolkit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## What it does

- **Inspect** — metadata, page count, scanned-vs-digital analysis, and a structural X-Ray explorer, with a unified adapter for pypdf, pdfminer.six, PyMuPDF, and pdfplumber.
- **Compare libraries** — per-library examples in `examples/` that extract text, pages, and metadata the same way, so you can see where the libraries disagree.
- **Find a table of contents** — outline extraction plus a text heuristic for manuals whose TOC is just printed text, with a hint page for where it starts.
- **Export** — convert a PDF to Markdown, HTML, DOCX, or a structured JSON report.
- **Compress** — three methods in one engine:
  - `structural` (default): PyMuPDF garbage collection + stream deflation + clean. Text stays selectable, vectors stay sharp, nothing is rasterized.
  - `pypdf`: rewrite with content-stream compression, optionally dropping metadata.
  - `ghostscript`: Ghostscript `pdfwrite` presets (`screen`, `ebook`, `printer`, `prepress`). Ghostscript is an external binary, not a pip dependency.
- **GUI** — an optional PyQt6 drag-and-drop window with first-page preview, for the compressor.

## Quick start

```bash
pip install pdf-toolkit
# or, with the GUI:
pip install "pdf-toolkit[gui]"

# Inspect a PDF
pdf-toolkit inspect document.pdf
pdf-toolkit inspect document.pdf --json
pdf-toolkit inspect document.pdf --toc --hint 6

# Compress it (interactive: inspect, then confirm each file)
pdf-toolkit compress document.pdf
# Batch a directory, no prompts, into ./compressed/
pdf-toolkit compress ./pdfs/ -o ./compressed/ -y --method structural
# pypdf, or Ghostscript at ebook quality
pdf-toolkit compress document.pdf -o ./out/ -y --method pypdf
pdf-toolkit compress document.pdf -o ./out/ -y --method ghostscript --gs-quality ebook

# GUI
pdf-toolkit gui
```

From a checkout, the same commands work after `pip install -e ".[dev]"`, and the library API is importable directly:

```python
from pathlib import Path
from pdf_toolkit.compressor import compress_pdf, quick_inspect
from pdf_toolkit.inspector.adapters.pymupdf import PyMuPDFAdapter

info = quick_inspect(Path("document.pdf"))
print(info["page_count"], info["image_count"])

result = compress_pdf(Path("document.pdf"), Path("document_compressed.pdf"), "structural")
print(result.success, result.reduction_pct)

with PyMuPDFAdapter("document.pdf") as adapter:
    print(adapter.get_metadata()["document_type"])
    print(adapter.get_toc(hint_page=6)[:3])
```

## Install options

| Extra | What it adds |
|---|---|
| *(none)* | Core: PyMuPDF, pypdf, pdfminer.six, pdfplumber, rich |
| `pdf-toolkit[gui]` | PyQt6 GUI |
| `pdf-toolkit[tables]` | Camelot + tabula-py for `--tables` (tabula-py also needs Java) |
| `pdf-toolkit[ocr]` | pytesseract, pdf2image, Pillow, numpy for OCR paths |
| `pdf-toolkit[export]` | pymupdf4llm + pdf2docx for `--export md` / `--export docx` |
| `pdf-toolkit[dev]` | pytest + ruff |

Optional features fail with a plain "install this extra" message instead of an import error at startup: the CLI imports Camelot, tabula, pytesseract, and the export converters lazily, only when that feature is used.

## Examples and scripts

- `examples/` — one folder per library (`pypdf`, `pdfminer`, `pdfplumber`, `pymupdf`), each with text/page/metadata examples and its own tests, all run against the generated `examples/sample_example.pdf`. No generated outputs are shipped; run an example and its outputs land in `examples/<lib>/outputs/`.
- `scripts/generate_sample_pdf.py` — regenerate the sample PDF.
- `scripts/collect_metadata.py` — collect per-library metadata JSON into `examples/outputs/aggregated/combined_metadata.{json,csv}`.
- `scripts/dashboard.py` — build the aggregated HTML dashboard from that JSON.
- `scripts/clean_examples.py` — delete generated example outputs (keeps `.gitkeep`).

```bash
python scripts/generate_sample_pdf.py
python examples/pypdf/extract_text.py examples/sample_example.pdf
python scripts/collect_metadata.py
python scripts/dashboard.py
python -m pytest -q
```

## Project layout

```text
pdf-toolkit/
├── src/pdf_toolkit/
│   ├── cli.py                 # pdf-toolkit inspect / compress / gui
│   ├── inspector/             # adapters, TOC parsers, analysis, extraction
│   │   ├── adapters/          # pypdf, pdfminer, pymupdf, pdfplumber
│   │   ├── toc/               # outline + text-TOC heuristics
│   │   ├── analysis/          # scanned-document detection, X-Ray explorer
│   │   └── extraction/        # tables (optional), converters, OCR (optional)
│   ├── compressor/            # structural / pypdf / ghostscript engines
│   └── gui/                   # PyQt6 GUI (optional)
├── examples/                  # per-library examples + sample PDF
├── scripts/                   # sample generator, aggregator, dashboard, cleaner
└── tests/                     # package tests (examples carry their own too)
```

## Known limitations

- TOC outline extraction returns titles but does not yet resolve outline destinations to page numbers (the PyMuPDF text heuristic does return page numbers). See `tests/test_toc_fixture.py` for exactly what each extractor guarantees.
- The text-TOC heuristic was tuned on printed manuals; it needs a sensible `--hint` page for documents whose contents page is not near page 6.
- Ghostscript and tabula-py depend on external runtimes (Ghostscript, Java). If they are not installed, those paths report a clear error and the rest of the toolkit still works.
- The GUI is not covered by automated tests (it needs a display); CI covers the CLI, the library, and the examples.
- Table extraction with Camelot works best on bordered tables; unbordered tables may need the stream fallback or pdfplumber's own table finder in the examples.

## History

`pdf-toolkit` merges three earlier projects into one package, with a single CLI and a single dependency story:

- `ss-py-pdf-inspector` — the inspector, its adapters, TOC parsers, dashboard, and examples. Its old tests that required a private, unshipped manual PDF were replaced with tests against a synthetic TOC fixture built in the test, and its generated example outputs were dropped.
- `ss-pdf-small` — the CLI batch compressor. Its PyMuPDF structural pass is now the default `structural` method, and its inspect/estimate step is the compressor's preflight.
- `ss-pdf-tool` — the PyQt6 GUI compressor. Its pypdf and Ghostscript methods are now compressor methods, and the GUI imports the package instead of reaching for a sibling file via `sys.path`.

Two fixes from the merge are worth knowing about: the old inspector's example metadata scripts imported a `normalize_pdf_metadata` name the package never exported (it is now an alias for `normalize_metadata`), and the old tool's module created a `pdf_compressor.log` file in the working directory on import (logging is now the caller's job, and importing the compressor has no side effects). The old projects' single-commit histories, which carried personal email addresses, were not carried over; this repo starts with a clean history under the `enonymous1` identity.

## License

MIT — see [LICENSE](LICENSE).
