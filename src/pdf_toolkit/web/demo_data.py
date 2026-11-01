"""Seeded demo data for the web frontend.

These values are real measurements of ``examples/sample_example.pdf``
taken with :func:`pdf_toolkit.compressor.inspect.quick_inspect` and
the structural compressor, frozen here so the demo never needs a
real file: the demo server and the frozen Pages demo serve exactly
these numbers, labelled as demo data in the UI. They are not
generated at request time and they are never presented as a live
result for an uploaded file — live uploads always run the real
inspector and compressor.

Measured 2026-11-01 from ``examples/sample_example.pdf`` with
:func:`pdf_toolkit.compressor.inspect.quick_inspect` (3 pages,
3,784 bytes, 29 objects, 0 images) and the structural compressor
(3,784 -> 1,756 bytes, 2,028 saved, 53.59%). ``tests/test_web.py``
asserts the demo pages render these values; if the sample PDF ever
changes, re-run those two calls and update this module, rather
than inventing rounder numbers.
"""

from __future__ import annotations

from typing import Any

DEMO_INSPECT: dict[str, Any] = {
    "name": "sample_example.pdf",
    "page_count": 3,
    "metadata": {"format": "PDF 1.7", "encryption": None},
    "is_encrypted": False,
    "file_size": 3784,
    "object_count": 29,
    "image_count": 0,
}

DEMO_ESTIMATE = "Estimated Low (5-10%)"

DEMO_COMPRESS: dict[str, Any] = {
    "method": "structural",
    "success": True,
    "initial_size": 3784,
    "final_size": 1756,
    "saved_bytes": 2028,
    "reduction_pct": 53.59,
    "error": None,
}
