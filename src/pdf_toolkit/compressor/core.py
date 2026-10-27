"""Compression engines, unified from ss-pdf-small and ss-pdf-tool.

Three methods, one result shape:

- ``structural`` — PyMuPDF garbage collection + stream deflation + clean.
  Keeps text selectable and vectors sharp; never rasterizes images.
- ``pypdf`` — pypdf rewrite with content-stream compression, optionally
  dropping metadata.
- ``ghostscript`` — Ghostscript ``pdfwrite`` with a quality preset.
  Ghostscript is an external binary, not a pip dependency; if it is not
  on PATH the result reports that instead of raising.

Importing this module has no side effects: unlike the original
``pdf_utils.py`` it does not create a log file in the working directory.
Callers (the CLI, the GUI) own logging.
"""

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

METHODS = ("structural", "pypdf", "ghostscript")
GHOSTSCRIPT_QUALITIES = ("screen", "ebook", "printer", "prepress")


@dataclass
class CompressionResult:
    """Outcome of one compression attempt."""

    success: bool
    input_path: Path
    output_path: Path
    method: str
    initial_size: int = 0
    final_size: int = 0
    error: str | None = None

    @property
    def saved_bytes(self) -> int:
        return self.initial_size - self.final_size

    @property
    def reduction_pct(self) -> float:
        if self.initial_size > 0:
            return (self.initial_size - self.final_size) / self.initial_size * 100
        return 0.0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "input_path": str(self.input_path),
            "output_path": str(self.output_path),
            "method": self.method,
            "initial_size": self.initial_size,
            "final_size": self.final_size,
            "saved_bytes": self.saved_bytes,
            "reduction_pct": self.reduction_pct,
            "error": self.error,
        }


def _check_input(input_path: Path) -> None:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if input_path.suffix.lower() != ".pdf":
        raise ValueError(f"Input file must be a PDF: {input_path}")


def _finish(result: CompressionResult) -> CompressionResult:
    if result.success and result.output_path.exists():
        result.final_size = result.output_path.stat().st_size
    return result


def compress_structural(input_path: Path, output_path: Path) -> CompressionResult:
    """Compress with PyMuPDF: garbage=4, deflate, clean."""
    import fitz

    input_path, output_path = Path(input_path), Path(output_path)
    _check_input(input_path)
    initial = input_path.stat().st_size
    try:
        doc = fitz.open(str(input_path))
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            doc.save(str(output_path), garbage=4, deflate=True, clean=True)
        finally:
            doc.close()
    except Exception as exc:
        logger.error("Structural compression failed for %s: %s", input_path, exc)
        return CompressionResult(
            False,
            input_path,
            output_path,
            "structural",
            initial_size=initial,
            error=str(exc),
        )
    return _finish(
        CompressionResult(
            True,
            input_path,
            output_path,
            "structural",
            initial_size=initial,
        )
    )


def compress_pypdf(
    input_path: Path,
    output_path: Path,
    *,
    remove_metadata: bool = False,
    compress_content_streams: bool = True,
) -> CompressionResult:
    """Compress by rewriting with pypdf, optionally dropping metadata."""
    from pypdf import PdfReader, PdfWriter

    input_path, output_path = Path(input_path), Path(output_path)
    _check_input(input_path)
    initial = input_path.stat().st_size
    try:
        reader = PdfReader(str(input_path))
        writer = PdfWriter()
        original_metadata = reader.metadata
        for i, page in enumerate(reader.pages):
            writer.add_page(page)
            if compress_content_streams:
                writer.pages[i].compress_content_streams()
        if not remove_metadata and original_metadata:
            writer.add_metadata(original_metadata)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as fh:
            writer.write(fh)
    except Exception as exc:
        logger.error("pypdf compression failed for %s: %s", input_path, exc)
        return CompressionResult(
            False,
            input_path,
            output_path,
            "pypdf",
            initial_size=initial,
            error=str(exc),
        )
    return _finish(
        CompressionResult(
            True,
            input_path,
            output_path,
            "pypdf",
            initial_size=initial,
        )
    )


def find_ghostscript() -> str | None:
    """Return the Ghostscript executable name, or None if not on PATH."""
    return shutil.which("gs") or shutil.which("gswin64c") or shutil.which("gswin32c")


def compress_ghostscript(
    input_path: Path,
    output_path: Path,
    *,
    quality: str = "ebook",
) -> CompressionResult:
    """Compress with Ghostscript ``pdfwrite`` at the given preset."""
    if quality not in GHOSTSCRIPT_QUALITIES:
        raise ValueError(
            f"Unknown Ghostscript quality {quality!r}; "
            f"choose from {', '.join(GHOSTSCRIPT_QUALITIES)}"
        )
    input_path, output_path = Path(input_path), Path(output_path)
    _check_input(input_path)
    initial = input_path.stat().st_size
    gs = find_ghostscript()
    if not gs:
        return CompressionResult(
            False,
            input_path,
            output_path,
            "ghostscript",
            initial_size=initial,
            error="Ghostscript executable not found on PATH "
            "(install Ghostscript from ghostscript.com and add it to PATH)",
        )
    command = [
        gs,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS=/{quality}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={output_path}",
        str(input_path),
    ]
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.CalledProcessError as exc:
        logger.error("Ghostscript failed for %s: %s", input_path, exc.stderr)
        return CompressionResult(
            False,
            input_path,
            output_path,
            "ghostscript",
            initial_size=initial,
            error=f"Ghostscript exited {exc.returncode}",
        )
    except Exception as exc:
        logger.error("Ghostscript failed for %s: %s", input_path, exc)
        return CompressionResult(
            False,
            input_path,
            output_path,
            "ghostscript",
            initial_size=initial,
            error=str(exc),
        )
    return _finish(
        CompressionResult(
            True,
            input_path,
            output_path,
            "ghostscript",
            initial_size=initial,
        )
    )


def compress_pdf(
    input_path: Path,
    output_path: Path,
    method: str = "structural",
    **kwargs,
) -> CompressionResult:
    """Dispatch to one compression method by name."""
    if method == "structural":
        return compress_structural(input_path, output_path)
    if method == "pypdf":
        return compress_pypdf(input_path, output_path, **kwargs)
    if method == "ghostscript":
        return compress_ghostscript(input_path, output_path, **kwargs)
    raise ValueError(f"Unknown compression method {method!r}; choose from {', '.join(METHODS)}")


# Backwards-compatible name from ss-pdf-small (returns the new result type).
def compress_pdf_structural(input_path: Path, output_path: Path) -> CompressionResult:
    """Alias for :func:`compress_structural`."""
    return compress_structural(input_path, output_path)
