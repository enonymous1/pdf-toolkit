"""Tests for the 0.6.0 staff-review fixes (P0 + P1).

Each test pins one behaviour that used to be wrong or unguarded:
version drift, silent page-range fallbacks, partial outputs, an
unauthenticated server bound to a non-loopback host, and unvalidated
compression kwargs. They are deliberately small: the fix is the point,
not the test.
"""

import tomllib
from pathlib import Path
from unittest import mock

import pymupdf
import pytest
from pypdf import PdfWriter

from pdf_toolkit import __version__
from pdf_toolkit._atomic import atomic_output
from pdf_toolkit.compressor import compress_pdf
from pdf_toolkit.inspector.extraction.converters import _page_indices
from pdf_toolkit.splitter import Entry, split_pdf

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_single_sourced():
    """pyproject must read the version from pdf_toolkit.__version__.

    0.5.0 shipped with pyproject at 0.5.0 and __init__ at 0.4.0; this
    test fails the moment a hardcoded version creeps back in.
    """
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "version" not in pyproject["project"], "pyproject must not hardcode a version"
    assert pyproject["project"]["dynamic"] == ["version"]
    assert (
        pyproject["tool"]["setuptools"]["dynamic"]["version"]["attr"] == "pdf_toolkit.__version__"
    )
    assert __version__ == "0.7.0"


def test_page_indices_valid_and_invalid():
    assert list(_page_indices(None, 10)) == list(range(10))
    assert list(_page_indices("all", 10)) == list(range(10))
    assert list(_page_indices("3", 10)) == [2]
    assert list(_page_indices("2-5", 10)) == [1, 2, 3, 4]
    for bad in ("0", "11", "5-2", "abc", "2-", "-3", "1-11"):
        with pytest.raises(ValueError):
            _page_indices(bad, 10)


def _make_pdf(path: Path, pages: int = 3) -> Path:
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1}")
    doc.save(str(path))
    doc.close()
    return path


def test_atomic_output_leaves_destination_untouched_on_failure(tmp_path):
    dest = tmp_path / "out.pdf"
    dest.write_bytes(b"original")
    with pytest.raises(RuntimeError):
        with atomic_output(dest) as tmp:
            tmp.write_bytes(b"partial")
            raise RuntimeError("boom")
    assert dest.read_bytes() == b"original"
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_output_replaces_on_success(tmp_path):
    dest = tmp_path / "out.pdf"
    with atomic_output(dest) as tmp:
        tmp.write_bytes(b"done")
    assert dest.read_bytes() == b"done"


def test_compress_unknown_kwarg_returns_failed_result_not_type_error(tmp_path):
    src = _make_pdf(tmp_path / "in.pdf")
    out = tmp_path / "out.pdf"
    result = compress_pdf(src, out, "structural", remove_metadata=True)
    assert result.success is False
    assert "remove_metadata" in result.error
    assert not out.exists(), "a failed compression must not leave an output file"


def test_split_failure_leaves_no_chapter_files(tmp_path):
    src = _make_pdf(tmp_path / "book.pdf", pages=4)
    out_dir = tmp_path / "chapters"
    entries = [Entry(title="One", page=1), Entry(title="Two", page=3)]
    orig_write = PdfWriter.write
    calls = {"n": 0}

    def flaky(self, fh):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom while writing chapter two")
        return orig_write(self, fh)

    with mock.patch.object(PdfWriter, "write", flaky):
        with pytest.raises(RuntimeError):
            split_pdf(src, entries, out_dir)
    assert not list(out_dir.glob("*.pdf")), "a failed split must leave no chapters"


def test_serve_refuses_non_loopback_without_allow_remote():
    from pdf_toolkit.dissect.server import run_server

    # The guard runs before Flask is imported, so this works even
    # without the dissect extra installed.
    with pytest.raises(ValueError, match="Refusing to bind"):
        run_server(Path("/tmp"), host="0.0.0.0", port=5000)
    with pytest.raises(ValueError, match="Refusing to bind"):
        run_server(Path("/tmp"), host="192.168.1.10", port=5000)
