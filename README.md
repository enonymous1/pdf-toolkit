# pdf-toolkit

Inspect a PDF, compare how four Python PDF libraries see it, shrink it, split it into chapters, dissect its forms, or make one from an office document — from one package, one CLI.

[![CI](https://github.com/enonymous1/pdf-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/enonymous1/pdf-toolkit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## What it does

- **Inspect** — metadata, page count, scanned-vs-digital analysis, and a structural X-Ray explorer, with a unified adapter for pypdf, pdfminer.six, PyMuPDF, and pdfplumber.
- **Compare libraries** — per-library examples in `examples/` that extract text, pages, and metadata the same way, so you can see where the libraries disagree.
- **Find a table of contents** — outline extraction plus a text heuristic for manuals whose TOC is just printed text, with a hint page for where it starts.
- **Split** — one PDF per chapter, by bookmarks, a `title,page` CSV, located headings, or the printed TOC text. Dry-run by default; existing outputs are never silently overwritten.
- **Dissect** — find templated form pages by keyword or image similarity, detect their field boxes, label them with OCR, and rebuild each page as an interactive HTML overlay, a fillable PDF, and a DOCX, with a local preview server for editing fieldmaps. Needs `pdf-toolkit[dissect]`.
- **Export** — convert a PDF to Markdown, HTML, DOCX, or a structured JSON report.
- **Compress** — three methods in one engine:
  - `structural` (default): PyMuPDF garbage collection + stream deflation + clean. Text stays selectable, vectors stay sharp, nothing is rasterized.
  - `pypdf`: rewrite with content-stream compression, optionally dropping metadata.
  - `ghostscript`: Ghostscript `pdfwrite` presets (`screen`, `ebook`, `printer`, `prepress`). Ghostscript is an external binary, not a pip dependency.
- **GUI** — an optional PyQt6 drag-and-drop window with first-page preview, for the compressor.
- **Convert to PDF** — `pdf-toolkit convert` turns a `.docx` or `.xlsx` file into a PDF. The `.docx` path uses docx2pdf (needs Word); the `.xlsx` path drives Excel through COM, so it needs Windows with Excel. Wide sheets go landscape automatically, very wide sheets fit to one page wide.
- **Check .docx formatting** — `pdf-toolkit check-format` checks a Word document against formatting rules (font, body/caption/footnote sizes, line spacing, margins — all overridable on the command line) and reports every issue. With an output path it can also save an annotated copy with Word comments, which needs Windows with Word.
- **Check citations** — `pdf-toolkit check-citations` flags DOCX manuscript text similar to a PDF source, for manual citation review. Needs `pdf-toolkit[citations]` for the DOCX reader. Similarity alone never proves a passage is uncited; matches are reported with the source page, snippet, and context for a human to judge.

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

# Split into chapters (dry-run first: prints the proposed ranges)
pdf-toolkit split document.pdf
pdf-toolkit split document.pdf -o ./chapters/ --yes
# From an explicit chapter list, or by locating headings in the text
pdf-toolkit split document.pdf --csv chapters.csv --yes
pdf-toolkit split document.pdf --headings headings.txt --yes
# No bookmarks? Fall back to the printed TOC (--offset shifts printed
# page numbers to physical pages when there is front matter)
pdf-toolkit split document.pdf --toc-text --hint 2 --offset 4 --yes
# Just dump the resolved chapter list
pdf-toolkit split document.pdf --export-csv chapters.csv

# Dissect form pages (needs pdf-toolkit[dissect])
pdf-toolkit dissect detect document.pdf --keyword "Form Title" --keyword Signature
# Rebuild matched pages: images/, html/ (overlay + fieldmap JSON),
# fillable_pdfs/, extracted_pdfs/ under ./recon/
pdf-toolkit dissect reconstruct document.pdf --keyword "Form Title" --out-dir ./recon/
# Fill from a fieldmap and data JSON (per-page keys, or a "global" mapping)
pdf-toolkit dissect fill document.pdf --fieldmap ./recon/ --data data.json --out-dir ./filled/
# Export pages to DOCX, optionally filled
pdf-toolkit dissect export-docx --fieldmap ./recon/ --out-dir ./docx/ --fill --data data.json
# Preview and edit fieldmaps locally (loopback only, confined to --root)
pdf-toolkit dissect serve --root ./recon/

# Convert to PDF (needs pdf-toolkit[office]; see limitations below)
pdf-toolkit convert document.docx
pdf-toolkit convert spreadsheet.xlsx -o report.pdf
pdf-toolkit convert ./docs/ -o ./pdfs/

# Check .docx formatting (exit 0 = compliant, 1 = issues found)
pdf-toolkit check-format document.docx
pdf-toolkit check-format document.docx --font Calibri --body-size 12 --margin 1.0
pdf-toolkit check-format document.docx -o document-annotated.docx
pdf-toolkit check-format ./docs/ -o ./format-check/ --annotate

# Flag DOCX text similar to a PDF source (needs pdf-toolkit[citations];
# exit 0 = no matches, 1 = matches found, 2 = usage/file error)
pdf-toolkit check-citations manuscript.docx source.pdf --json-out report.json
pdf-toolkit check-citations manuscript.docx source.pdf --threshold 90 --skip-cited
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

from pdf_toolkit.splitter import extract_outline_entries, split_pdf

entries, _warnings = extract_outline_entries("document.pdf")
split_pdf("document.pdf", entries, "./chapters/")

from pdf_toolkit.dissect import find_template_pages, reconstruct_pdf_pages

result = find_template_pages("document.pdf", ["Form Title", "Signature"])
reconstruct_pdf_pages("document.pdf", result.matched_pages, "./recon/")
```

## Install options

| Extra | What it adds |
|---|---|
| *(none)* | Core: PyMuPDF, pypdf, pdfminer.six, pdfplumber, rich |
| `pdf-toolkit[gui]` | PyQt6 GUI |
| `pdf-toolkit[tables]` | Camelot + tabula-py for `--tables` (tabula-py also needs Java) |
| `pdf-toolkit[ocr]` | pytesseract, pdf2image, Pillow, numpy for OCR paths |
| `pdf-toolkit[export]` | pymupdf4llm + pdf2docx for `--export md` / `--export docx` |
| `pdf-toolkit[office]` | python-docx + docx2pdf + openpyxl for `convert` and `check-format` (pywin32 on Windows) |
| `pdf-toolkit[dissect]` | OpenCV + NumPy + Pillow + ReportLab + Flask + python-docx + docxtpl + pytesseract for `dissect` (Tesseract binary still needed separately for OCR labels) |
| `pdf-toolkit[citations]` | python-docx for `check-citations` (RapidFuzz is a core dependency) |
| `pdf-toolkit[dev]` | pytest + ruff |

Optional features fail with a plain "install this extra" message instead of an import error at startup: the CLI imports Camelot, tabula, pytesseract, the export converters, and the office converters lazily, only when that feature is used.

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
│   ├── cli.py                 # pdf-toolkit inspect / compress / split / dissect / gui / convert / check-format / check-citations
│   ├── splitter/              # chapter splitting by bookmarks, CSV, headings, or TOC text
│   ├── dissect/               # form-page detection, field detection, reconstruction, preview server
│   ├── citations/             # DOCX-vs-PDF similarity flagging for citation review
│   ├── to_pdf/                # docx/xlsx to PDF, .docx formatting checker
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

- Split chunks keep the source document's metadata but not its bookmarks; each chunk starts at its chapter's first page. Printed TOC numbers are used as physical pages unless `--offset` is given, so verify the proposed ranges in the dry run before `--yes` — that check is the point of the dry run. Heading location is text-based and needs extractable text; scanned PDFs need an OCR pass first.
- The text-TOC heuristic was tuned on printed manuals; it needs a sensible `--hint` page for documents whose contents page is not near page 6.
- Ghostscript and tabula-py depend on external runtimes (Ghostscript, Java). If they are not installed, those paths report a clear error and the rest of the toolkit still works.
- The GUI is not covered by automated tests (it needs a display); CI covers the CLI, the library, and the examples.
- Office conversion is not covered by automated tests either: `.xlsx` conversion needs Windows with Excel, and `.docx` conversion needs Word. CI covers the dispatch, the Excel page-setup rules, and the formatting checker (which runs anywhere python-docx runs); the actual conversions are verified by hand on a Windows machine. Word-comment annotation likewise needs Windows with Word — the report itself works everywhere.
- The formatting checker's defaults (Calibri, 12pt body / 10pt captions and footnotes, 1.0 spacing, 1-inch margins) come from the original project's style guide; they are defaults, not a standard, so pass your own values if your documents use different rules.
- Table extraction with Camelot works best on bordered tables; unbordered tables may need the stream fallback or pdfplumber's own table finder in the examples.
- Dissect field detection is a contour heuristic: it finds rectangular boxes, so nested boxes and unboxed fields are missed or merged, and OCR labels are one word per field. The preview server has no authentication and is confined to its `--root` directory — keep it on loopback. The original's WeasyPrint HTML-to-PDF path is not ported (it needs system Cairo/Pango libraries); filled PDFs come from `dissect fill` instead.
- Citation checking is a similarity flag, not a plagiarism or citation verdict: it cannot tell a properly quoted or cited passage from an uncited one except for the explicit markers `--skip-cited` recognizes, it uses a lightweight sentence splitter (abbreviations can split early), and it does not read DOCX headers, footers, or footnotes. Scanned PDFs need an OCR pass first, as with the other text paths.

## History

`pdf-toolkit` merges seven earlier projects into one package, with a single CLI and a single dependency story:

- `ss-py-pdf-inspector` — the inspector, its adapters, TOC parsers, dashboard, and examples. Its old tests that required a private, unshipped manual PDF were replaced with tests against a synthetic TOC fixture built in the test, and its generated example outputs were dropped.
- `ss-pdf-small` — the CLI batch compressor. Its PyMuPDF structural pass is now the default `structural` method, and its inspect/estimate step is the compressor's preflight.
- `ss-pdf-tool` — the PyQt6 GUI compressor. Its pypdf and Ghostscript methods are now compressor methods, and the GUI imports the package instead of reaching for a sibling file via `sys.path`.
- `ss-toPDF` (merged in 0.2.0) — DOCX/XLSX to PDF conversion plus the .docx formatting checker. Its converters are now `pdf-toolkit convert`, and its checker is now `pdf-toolkit check-format` with the rules as parameters instead of module constants. Its example documents were real work files and are not shipped; the checker tests build synthetic documents in-test instead. The merge also fixed the original batch script, which imported three checker functions that did not exist, and removed hardcoded local paths from the checker.
- `ss-HESI` (merged in 0.3.0) — scripts for splitting a PDF by bookmarks/TOC text, locating headings, and cleaning split filenames. Its logic is now `pdf-toolkit split` and the `pdf_toolkit.splitter` library, generalized off the one book it was built for: no hardcoded paths, one shared CSV parser and filename sanitizer, heading location in a single pass over the PDF, and the outline page resolution the inspector's TOC extractor was missing (it previously returned titles with no pages). The original's bugs are fixed, not carried over: a duplicated output write, a documented-but-unimplemented `--preview-only` flag, a TOC scan that treated every numbered line on the first ten pages as an entry, and printed page numbers silently used as physical ones. Splitting is verified against a synthetic fixture built in-test; no book content is shipped, and the source PDF is never part of this repo.
- `ss-documentDissection` (merged in 0.4.0) — a pipeline for detecting templated form pages and rebuilding them as fillable HTML, PDF, and DOCX, with a Flask preview server. Its logic is now `pdf-toolkit dissect` and the `pdf_toolkit.dissect` library. The original's bugs are fixed, not carried over: fieldmaps written with `str()` and read back with `eval()` (now JSON throughout), a `--keywords` option that swallowed subcommand names (now repeatable `--keyword`), `--to-html-dir` handling nested inside the wrong subcommand and crashing without `--reconstruct-dir`, a preview server that served and wrote files relative to the working directory with no confinement (now confined to `--root`, with absolute and escaping paths rejected), a `/fill-document` endpoint that passed a filename where bytes were expected (now fills and writes), and PDF filling that only ever filled page 1. The WeasyPrint HTML-to-PDF path is not ported; no sample documents are shipped, and the original's history, which carried a personal email address, was not carried over.
- `ss-missedCitations` (merged in 0.5.0) — a CLI comparing a DOCX manuscript against a PDF source with `thefuzz` `partial_ratio` sliding windows. Its logic is now `pdf-toolkit check-citations` and the `pdf_toolkit.citations` library, generalized off the one RFP/checklist pair it was built for: no sample documents are shipped (the original's test documents were a real RFP and a real proposal checklist), and the original's bugs are fixed, not carried over: raw-text scoring with no normalization or token prefilter, whose shipped reports were all score-100 footnote fragments (`1.`, `P.`) and whose current code finds nothing on its own sample documents; DOCX tables silently ignored; two divergent sentence splitters; an unvalidated threshold; a missing file crashing with a traceback; and tests that only ran with `PYTHONPATH=src`. The thefuzz/Levenshtein stack is replaced with RapidFuzz, and the full-page comparison fallback (which made the "best snippet" a page of unrelated text) is dropped.

Two fixes from the merge are worth knowing about: the old inspector's example metadata scripts imported a `normalize_pdf_metadata` name the package never exported (it is now an alias for `normalize_metadata`), and the old tool's module created a `pdf_compressor.log` file in the working directory on import (logging is now the caller's job, and importing the compressor has no side effects). The old projects' single-commit histories, which carried personal email addresses, were not carried over; this repo starts with a clean history under the `enonymous1` identity.

## License

MIT — see [LICENSE](LICENSE).
