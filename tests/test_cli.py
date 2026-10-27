"""End-to-end CLI tests via ``pdf_toolkit.cli.main`` (no subprocess)."""

from pathlib import Path

import pytest

from pdf_toolkit.cli import main
from scripts.generate_sample_pdf import make_sample_pdf


@pytest.fixture()
def sample(tmp_path: Path) -> Path:
    return make_sample_pdf(str(tmp_path / "sample.pdf"))


def test_cli_inspect_json(sample: Path, capsys):
    assert main(["inspect", str(sample), "--json"]) == 0
    out = capsys.readouterr().out
    assert "scanned_page_ratio" in out or "document_type" in out


def test_cli_inspect_toc_on_fixture(tmp_path: Path, capsys):
    # A contents page is needed for the text heuristic; reuse the TOC
    # fixture builder so this test does not depend on an external PDF.
    from tests.test_toc_fixture import make_toc_fixture

    fixture = make_toc_fixture(tmp_path / "toc.pdf")
    assert main(["inspect", str(fixture), "--toc", "--hint", "2", "--json"]) == 0
    out = capsys.readouterr().out
    assert "Introduction" in out


def test_cli_compress_structural_and_pypdf(sample: Path, tmp_path: Path):
    out_dir = tmp_path / "compressed"
    assert main(["compress", str(sample), "-o", str(out_dir), "-y"]) == 0
    out = out_dir / "sample_compressed.pdf"
    assert out.exists() and out.stat().st_size > 0

    out_dir2 = tmp_path / "compressed2"
    assert main(["compress", str(sample), "-o", str(out_dir2), "-y", "--method", "pypdf"]) == 0
    assert (out_dir2 / "sample_compressed.pdf").exists()


def test_cli_compress_missing_file(tmp_path: Path):
    assert main(["compress", str(tmp_path / "missing.pdf"), "-o", str(tmp_path / "out"), "-y"]) == 1


def test_cli_gui_without_pyqt6_reports_helpfully(capsys):
    import importlib.util

    if importlib.util.find_spec("PyQt6") is not None:
        pytest.skip("PyQt6 is installed; launching the GUI is not a CI test")
    assert main(["gui"]) == 1
    assert "PyQt6" in capsys.readouterr().out
