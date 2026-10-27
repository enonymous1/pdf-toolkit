"""Dispatch office-document conversion by file extension.

From ss-toPDF's ``main.py`` and ``example.py``: a single file converts
to the same stem with a .pdf suffix, and a directory converts every
.docx/.xlsx file in it. Directory mode needs an explicit output
directory so converted files never land somewhere surprising.
"""

from pathlib import Path

from .docx_to_pdf import convert_docx_to_pdf
from .xlsx_to_pdf import convert_xlsx_to_pdf

CONVERTIBLE_SUFFIXES = {".docx": convert_docx_to_pdf, ".xlsx": convert_xlsx_to_pdf}


def convert_file(input_path: str | Path, output_path: str | Path | None = None) -> Path:
    """Convert one .docx or .xlsx file to PDF; return the output path."""
    input_path = Path(input_path)
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    converter = CONVERTIBLE_SUFFIXES.get(input_path.suffix.lower())
    if converter is None:
        raise ValueError(
            f"Unsupported file type: {input_path.suffix} "
            f"(supported: {', '.join(sorted(CONVERTIBLE_SUFFIXES))})"
        )
    if output_path is None:
        output_path = input_path.with_suffix(".pdf")
    return converter(input_path, Path(output_path))


def convert_path(input_path: str | Path, output_dir: str | Path | None = None) -> list[Path]:
    """Convert a file or every convertible file in a directory to PDF."""
    input_path = Path(input_path)
    if input_path.is_file():
        return [convert_file(input_path)]
    if not input_path.is_dir():
        raise FileNotFoundError(f"Input path not found: {input_path}")
    if output_dir is None:
        raise ValueError("Converting a directory needs an output directory (-o).")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for candidate in sorted(input_path.iterdir()):
        if candidate.is_file() and candidate.suffix.lower() in CONVERTIBLE_SUFFIXES:
            outputs.append(convert_file(candidate, output_dir / f"{candidate.stem}.pdf"))
    return outputs
