"""One helper for lazy optional imports.

Before this module, every package grew its own ``_require_*`` helper
with a different error type and a different message format (``ImportError``
in to_pdf and citations, ``RuntimeError`` in the dissect server,
``DocxError`` in dissect's DOCX export, ``DetectionError`` for OpenCV).
Callers could not tell a missing extra from a real bug, and the CLI
had to catch a different exception per feature.

``require_module`` is the only place that turns a missing optional
dependency into a human-readable error. It returns the imported module
so call sites stay one line, and it keeps the original ``ImportError``
as the cause so a traceback still shows what was actually missing.
"""

from __future__ import annotations

import importlib
from types import ModuleType


def require_module(
    module_name: str,
    *,
    extra: str,
    purpose: str,
    error_type: type[Exception] = ImportError,
    message: str | None = None,
) -> ModuleType:
    """Import ``module_name`` or raise a readable missing-extra error.

    ``extra`` is the ``pdf-toolkit[...]`` extra that provides the module
    (for example ``"office"`` or ``"dissect"``), and ``purpose`` is what
    the caller needs it for, in plain words. ``error_type`` exists
    because some callers already commit to a domain error (the dissect
    server raises ``RuntimeError``, DOCX export raises ``DocxError``);
    new code should leave it as ``ImportError``.
    """
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        if message is None:
            message = (
                f"{purpose} needs the {module_name} package, which is not installed. "
                f"Install it with: pip install 'pdf-toolkit[{extra}]'"
            )
        raise error_type(message) from exc


def require_docx(extra: str, purpose: str) -> ModuleType:
    """Import ``docx`` (python-docx) for ``purpose`` under ``extra``."""
    return require_module("docx", extra=extra, purpose=purpose)
