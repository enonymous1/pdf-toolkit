"""Fieldmap JSON I/O.

A fieldmap is a JSON list of :class:`FieldBox` dicts, one file per page,
named ``page_<n>_fieldmap.json``. This module is the only place fieldmaps
are read or written: the original ss-documentDissection wrote them with
``str()`` (Python repr, single quotes) and read them back with ``eval()``.
Both are gone; JSON is the format, and a malformed file raises
:class:`FieldmapError` instead of executing its contents.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import FieldBox

__all__ = [
    "FieldmapError",
    "find_fieldmaps",
    "load_fieldmap",
    "page_number_from_name",
    "save_fieldmap",
]


class FieldmapError(Exception):
    pass


def save_fieldmap(fields: list[FieldBox], path: str | Path) -> Path:
    """Write *fields* as JSON to *path*, creating parent directories."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([f.to_dict() for f in fields], indent=2), encoding="utf-8")
    return path


def load_fieldmap(path: str | Path) -> list[FieldBox]:
    """Read a fieldmap JSON file. Raises :class:`FieldmapError` on bad input."""
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FieldmapError(f"Cannot read fieldmap {path}: {exc}") from exc
    if not isinstance(raw, list):
        raise FieldmapError(f"Fieldmap {path} must contain a JSON list of fields")
    try:
        return [FieldBox.from_dict(item) for item in raw]
    except (KeyError, TypeError, ValueError) as exc:
        raise FieldmapError(f"Fieldmap {path} has an invalid field entry: {exc}") from exc


def page_number_from_name(path: str | Path) -> int:
    """Infer a 1-based page number from a filename like ``page_36_fieldmap.json``.

    Returns 0 when no digits are present (the caller treats 0 as unknown).
    """
    digits = "".join(ch for ch in Path(path).stem if ch.isdigit())
    return int(digits) if digits else 0


def find_fieldmaps(path: str | Path) -> list[Path]:
    """Resolve *path* to fieldmap files: a file itself, or every ``*fieldmap.json`` under a directory."""
    path = Path(path)
    if path.is_dir():
        return sorted(path.glob("**/*fieldmap.json"))
    return [path]
