"""Tests for the ss-toPDF merge: conversion dispatch, page setup, and
the .docx formatting checker.

The checker tests build synthetic .docx files in-test (the original
sample documents were real work files and are not shipped). They skip
when python-docx is not installed, so CI without the office extra still
passes. Conversion itself needs Word/Excel and is not run here; only
the dispatch and missing-dependency errors are tested, and those skip
when the dependency happens to be present.
"""

import pytest

from pdf_toolkit.cli import main as cli_main
from pdf_toolkit.to_pdf import convert_file, decide_page_setup

docx = pytest.importorskip("docx")


def _make_docx(path, font="Calibri", size=12.0, spacing=1.0, margin=1.0):
    from docx import Document
    from docx.shared import Inches, Pt

    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(margin)
        section.bottom_margin = Inches(margin)
        section.left_margin = Inches(margin)
        section.right_margin = Inches(margin)
    para = doc.add_paragraph("Sample paragraph.")
    para.paragraph_format.line_spacing = spacing
    run = para.add_run("Some text.")
    run.font.name = font
    run.font.size = Pt(size)
    doc.save(str(path))
    return path


def test_decide_page_setup_narrow_is_portrait():
    setup = decide_page_setup(5)
    assert setup["orientation"] == 1
    assert setup["zoom"] == 100


def test_decide_page_setup_wide_is_landscape():
    setup = decide_page_setup(12)
    assert setup["orientation"] == 2
    assert setup["fit_to_pages_wide"] is False


def test_decide_page_setup_very_wide_fits_one_page():
    setup = decide_page_setup(20)
    assert setup["orientation"] == 2
    assert setup["fit_to_pages_wide"] == 1
    assert setup["zoom"] is False


def test_convert_unsupported_extension(tmp_path):
    target = tmp_path / "note.txt"
    target.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        convert_file(target)


def test_convert_missing_input():
    with pytest.raises(FileNotFoundError):
        convert_file("/nonexistent/file.docx")


def test_convert_xlsx_without_excel(tmp_path):
    try:
        import win32com  # noqa: F401
    except ImportError:
        pass
    else:
        pytest.skip("win32com present; conversion would run")
    target = tmp_path / "book.xlsx"
    target.write_bytes(b"not a real workbook")
    with pytest.raises(ImportError, match="Excel"):
        convert_file(target)


def test_convert_docx_without_docx2pdf(tmp_path):
    try:
        import docx2pdf  # noqa: F401
    except ImportError:
        pass
    else:
        pytest.skip("docx2pdf present; conversion would run")
    target = tmp_path / "doc.docx"
    target.write_bytes(b"not a real document")
    with pytest.raises(ImportError, match="docx2pdf"):
        convert_file(target)


def test_checker_compliant_document(tmp_path):
    from pdf_toolkit.to_pdf import check_docx_formatting

    docx_path = _make_docx(tmp_path / "good.docx")
    assert check_docx_formatting(docx_path) == []


def test_checker_flags_font_size_spacing_and_margin(tmp_path):
    from pdf_toolkit.to_pdf import check_docx_formatting

    docx_path = _make_docx(tmp_path / "bad.docx", font="Arial", size=14.0, spacing=1.5, margin=0.5)
    messages = [issue.message for issue in check_docx_formatting(docx_path)]
    assert any("Arial" in msg for msg in messages)
    assert any("14.0pt" in msg for msg in messages)
    assert any("Spacing" in msg for msg in messages)
    assert any("margin" in msg for msg in messages)


def test_checker_caption_uses_caption_size(tmp_path):
    from docx import Document
    from docx.shared import Pt

    from pdf_toolkit.to_pdf import check_docx_formatting

    doc = Document()
    para = doc.add_paragraph("A caption.", style="Caption")
    run = para.add_run("Caption text.")
    run.font.name = "Calibri"
    run.font.size = Pt(12.0)
    path = tmp_path / "caption.docx"
    doc.save(str(path))
    messages = [issue.message for issue in check_docx_formatting(path)]
    assert any("10.0pt" in msg for msg in messages)


def test_print_report_compliant(capsys, tmp_path):
    from pdf_toolkit.to_pdf import print_formatting_report

    docx_path = _make_docx(tmp_path / "good.docx")
    issues = print_formatting_report(docx_path)
    assert issues == []
    assert "compliant" in capsys.readouterr().out


def test_cli_check_format_exit_codes(tmp_path):
    good = _make_docx(tmp_path / "good.docx")
    bad = _make_docx(tmp_path / "bad.docx", font="Arial")
    assert cli_main(["check-format", str(good)]) == 0
    assert cli_main(["check-format", str(bad)]) == 1
    assert cli_main(["check-format", str(tmp_path / "missing.docx")]) == 2


def test_cli_check_format_directory(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    _make_docx(in_dir / "good.docx")
    _make_docx(in_dir / "bad.docx", font="Arial")
    assert cli_main(["check-format", str(in_dir), "-o", str(out_dir)]) == 1
    report = out_dir / "formatting_report.txt"
    assert report.is_file()
    assert "bad.docx" in report.read_text(encoding="utf-8")


def test_cli_convert_unsupported(tmp_path):
    target = tmp_path / "note.txt"
    target.write_text("hello", encoding="utf-8")
    assert cli_main(["convert", str(target)]) == 2
