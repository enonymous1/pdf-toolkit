"""Atomic file writes: never leave a partial output behind.

Before this module, a failed compression, split, or fill left whatever
had been written so far at the output path, next to a failure result.
A caller that only checked "does the file exist" would treat a partial
file as a success. The pattern here is the standard one: write to a
temporary file in the same directory (so the rename stays on one
filesystem), then ``os.replace`` it into place only on success. On any
exception the temporary file is deleted and the destination is left
exactly as it was — untouched if it did not exist, intact if it did.
"""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def atomic_output(destination: str | Path):
    """Yield a temporary path to write to; replace ``destination`` on success.

    Usage::

        with atomic_output(out_path) as tmp_path:
            write_something(tmp_path)
        # out_path now holds the completed file, or is unchanged on error.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        yield tmp_path
        os.replace(tmp_path, destination)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
