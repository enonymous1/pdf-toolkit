# PDF library examples

Each subfolder contains small, focused examples for one PDF library, plus its own tests. All examples run against the generated sample PDF — no private or external document is needed.

```bash
# Generate the sample PDF used by every example and test
python scripts/generate_sample_pdf.py

# Extract text, pages, or metadata with one library
python examples/pypdf/extract_text.py examples/sample_example.pdf
python examples/pypdf/extract_pages.py --start 1 --end 1 examples/sample_example.pdf
python examples/pypdf/metadata.py examples/sample_example.pdf

# The same three operations exist for pdfminer, pdfplumber, and pymupdf.
# Outputs land in examples/<lib>/outputs/ (gitignored; only .gitkeep is tracked).

# Aggregate per-library metadata, then build the dashboard
python scripts/collect_metadata.py
python scripts/dashboard.py

# Run everything
python -m pytest -q
```

The examples import `pdf_toolkit.inspector` (the installed package). If you run an example as a script without installing the package first, it adds the repo's `src/` directory to `sys.path` as a fallback.
