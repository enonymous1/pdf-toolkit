"""Convert a Word document to PDF.

From ss-toPDF's ``docx_to_pdf.py``. The conversion itself is done by
``docx2pdf``, which drives Microsoft Word, so this only runs where Word
is available (in practice Windows, or macOS with Word). The import is
lazy so the rest of pdf-toolkit works without the office extra.
"""

import os
from pathlib import Path


def convert_docx_to_pdf(input_path: str | Path, output_path: str | Path) -> Path:
    """Convert ``input_path`` (.docx) to ``output_path`` (.pdf)."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    try:
        from docx2pdf import convert
    except ImportError as exc:
        raise ImportError(
            "docx2pdf is not installed, and converting .docx needs Microsoft Word. "
            "Install it with: pip install 'pdf-toolkit[office]'"
        ) from exc
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # docx2pdf writes into a directory for a single file, so convert into
    # the output directory and rename to the requested name if needed.
    convert(str(input_path), str(output_path.parent))
    produced = output_path.parent / f"{input_path.stem}.pdf"
    if produced.resolve() != output_path.resolve() and produced.is_file():
        os.replace(produced, output_path)
    return output_path
