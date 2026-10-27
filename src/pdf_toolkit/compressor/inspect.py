"""Quick pre-compression inspection (from ss-pdf-small).

This is deliberately shallow: page count, metadata, image and object
counts, and a heuristic compression estimate. For deep, multi-library
analysis use :mod:`pdf_toolkit.inspector` instead.
"""

from pathlib import Path
from typing import Any

import fitz


def quick_inspect(pdf_path: Path) -> dict[str, Any]:
    """Return basic structural facts about a PDF, or ``{}`` on failure."""
    pdf_path = Path(pdf_path)
    try:
        doc = fitz.open(str(pdf_path))
        try:
            info: dict[str, Any] = {
                "name": pdf_path.name,
                "page_count": len(doc),
                "metadata": doc.metadata,
                "is_encrypted": doc.is_encrypted,
                "file_size": pdf_path.stat().st_size,
            }
            try:
                info["object_count"] = doc.xref_length()
            except TypeError:  # older PyMuPDF exposed it as a property
                info["object_count"] = getattr(doc, "xref_length", 0)
            info["image_count"] = sum(len(page.get_images()) for page in doc)
            return info
        finally:
            doc.close()
    except Exception:
        return {}


def estimate_compression(pdf_info: dict[str, Any]) -> str:
    """Heuristic estimate of how much structural compression may save."""
    if not pdf_info:
        return "Unknown"
    size_mb = pdf_info.get("file_size", 0) / (1024 * 1024)
    if size_mb > 5 and pdf_info.get("image_count", 0) > 10:
        return "Estimated High (50% or more)"
    if pdf_info.get("object_count", 0) > 1000 or size_mb > 1:
        return "Estimated Moderate (20-40%)"
    return "Estimated Low (5-10%)"
