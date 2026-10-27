"""Splitter tests against synthetic fixtures built in-test.

No book content: the fixture is a five-page manual with bookmarks and
a contents page, plus a contents-heavy variant for heading location.
"""

from pathlib import Path

import fitz
import pytest
from pypdf import PdfReader

from pdf_toolkit.cli import main
from pdf_toolkit.splitter import (
    Entry,
    clean_filename,
    extract_outline_entries,
    extract_text_toc_entries,
    load_entries_from_csv,
    locate_headings,
    propose_ranges,
    sanitize_filename,
    split_pdf,
)


def make_split_fixture(path: Path, outlines: bool = True) -> Path:
    doc = fitz.open()
    doc.set_metadata({"title": "Fixture Manual", "author": "Fixture Author"})
    page = doc.new_page()
    page.insert_text((72, 72), "Fixture Manual", fontsize=18)
    page = doc.new_page()
    page.insert_text((72, 72), "Contents", fontsize=18)
    page.insert_text((72, 110), "Introduction .......... 3", fontsize=12)
    page.insert_text((72, 130), "Methods .......... 4", fontsize=12)
    page.insert_text((72, 150), "Results .......... 5", fontsize=12)
    for title in ("Introduction", "Methods", "Results"):
        page = doc.new_page()
        page.insert_text((72, 72), title, fontsize=18)
        page.insert_text((72, 110), f"This is the {title} chapter.", fontsize=12)
    if outlines:
        doc.set_toc([[1, "Introduction", 3], [1, "Methods", 4], [1, "Results", 5]])
    doc.save(str(path))
    doc.close()
    return path


def make_locate_fixture(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Fixture Manual", fontsize=18)
    page = doc.new_page()
    page.insert_text((72, 72), "Contents", fontsize=18)
    lines = [
        "Introduction .......... 3",
        "Methods .......... 4",
        "Results .......... 5",
        "Appendix .......... 6",
        "Glossary .......... 7",
        "Index .......... 8",
    ]
    for i, line in enumerate(lines):
        page.insert_text((72, 110 + i * 20), line, fontsize=12)
    for title in ("Introduction", "Methods", "Results", "Appendix", "Glossary", "Index"):
        page = doc.new_page()
        page.insert_text((72, 72), title, fontsize=18)
        page.insert_text((72, 110), f"This is the {title} chapter.", fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture()
def fixture(tmp_path: Path) -> Path:
    return make_split_fixture(tmp_path / "manual.pdf")


def test_outline_entries_resolve_to_pages(fixture: Path):
    entries, warnings = extract_outline_entries(fixture)
    assert warnings == []
    assert entries == [
        Entry("Introduction", 2),
        Entry("Methods", 3),
        Entry("Results", 4),
    ]


def test_text_toc_entries_use_printed_pages(tmp_path: Path):
    plain = make_split_fixture(tmp_path / "plain.pdf", outlines=False)
    entries, _warnings = extract_text_toc_entries(plain, hint_page=2)
    titles = {e.title: e.page for e in entries}
    assert titles["Introduction"] == 2
    assert titles["Methods"] == 3
    assert titles["Results"] == 4


def test_text_toc_offset_shifts_pages(tmp_path: Path):
    plain = make_split_fixture(tmp_path / "plain.pdf", outlines=False)
    entries, _warnings = extract_text_toc_entries(plain, hint_page=2, offset=1)
    titles = {e.title: e.page for e in entries}
    assert titles["Introduction"] == 3


def test_csv_loader_handles_quoted_commas_and_bad_rows(tmp_path: Path):
    csv_path = tmp_path / "chapters.csv"
    csv_path.write_text(
        '"Smith, J.: Intro",3\nMethods,4\nbad line\nResults,not-a-page\n,5\n',
        encoding="utf-8",
    )
    entries, warnings = load_entries_from_csv(csv_path)
    assert entries == [Entry("Smith, J.: Intro", 2), Entry("Methods", 3)]
    assert len(warnings) == 3


def test_propose_ranges_merges_same_page_and_drops_out_of_range():
    entries = [Entry("A", 0), Entry("B", 0), Entry("C", 2), Entry("Late", 99)]
    ranges, warnings = propose_ranges(entries, total_pages=3)
    assert [(r.title, r.start, r.end) for r in ranges] == [("A / B", 0, 1), ("C", 2, 2)]
    assert len(warnings) == 1
    ranges, _ = propose_ranges(entries, total_pages=3, merge_same_page=False)
    # Without merging, the first same-page entry has an empty range and
    # is dropped, matching the original script's invalid-range skip.
    assert [r.title for r in ranges] == ["B", "C"]


def test_sanitize_and_clean_filename():
    assert sanitize_filename("A/B: C? D") == "A-B- C- D"
    assert len(sanitize_filename("x" * 200)) <= 120
    assert clean_filename("Chapter 1 - Introduction (more information)") == "Introduction"
    assert clean_filename("Methods - http://example.test") == "Methods"


def test_split_pdf_writes_correct_pages_and_metadata(fixture: Path, tmp_path: Path):
    entries, _ = extract_outline_entries(fixture)
    out_dir = tmp_path / "split"
    written = split_pdf(fixture, entries, out_dir)
    assert len(written) == 3
    for path, title in zip(written, ("Introduction", "Methods", "Results")):
        reader = PdfReader(str(path))
        assert len(reader.pages) == 1
        assert title in (reader.pages[0].extract_text() or "")
        assert reader.metadata.title == "Fixture Manual"


def test_split_pdf_refuses_overwrite_by_default(fixture: Path, tmp_path: Path):
    entries, _ = extract_outline_entries(fixture)
    out_dir = tmp_path / "split"
    split_pdf(fixture, entries, out_dir)
    with pytest.raises(FileExistsError):
        split_pdf(fixture, entries, out_dir)
    written = split_pdf(fixture, entries, out_dir, overwrite=True)
    assert len(written) == 3


def test_split_pdf_groups_into_subfolders(fixture: Path, tmp_path: Path):
    entries, _ = extract_outline_entries(fixture)
    groups = [Entry("Part One", 2), Entry("Part Two", 4)]
    written = split_pdf(fixture, entries, tmp_path / "split", groups=groups)
    assert written[0].parent.name == "Part One"
    assert written[1].parent.name == "Part One"
    assert written[2].parent.name == "Part Two"


def test_locate_headings_skips_contents_page(tmp_path: Path):
    fixture = make_locate_fixture(tmp_path / "manual.pdf")
    found = locate_headings(fixture, ["Introduction", "Methods", "Missing Heading"])
    assert found == [("Introduction", 2), ("Methods", 3), ("Missing Heading", None)]


def test_cli_split_dry_run_writes_nothing(fixture: Path, tmp_path: Path, capsys):
    out_dir = tmp_path / "split"
    assert main(["split", str(fixture), str(out_dir)]) == 0
    assert "Introduction" in capsys.readouterr().out
    assert not out_dir.exists()


def test_cli_split_yes_writes_and_export_csv(fixture: Path, tmp_path: Path):
    out_dir = tmp_path / "split"
    assert main(["split", str(fixture), str(out_dir), "--yes"]) == 0
    assert sorted(p.name for p in out_dir.glob("*.pdf")) == [
        "01 - Introduction.pdf",
        "02 - Methods.pdf",
        "03 - Results.pdf",
    ]
    csv_path = tmp_path / "entries.csv"
    assert main(["split", str(fixture), "--export-csv", str(csv_path)]) == 0
    assert csv_path.read_text(encoding="utf-8").splitlines() == [
        "Introduction,3",
        "Methods,4",
        "Results,5",
    ]


def test_cli_split_missing_file_and_no_entries(tmp_path: Path):
    assert main(["split", str(tmp_path / "missing.pdf")]) == 2
    plain = make_split_fixture(tmp_path / "plain.pdf", outlines=False)
    assert main(["split", str(plain)]) == 2
    out_dir = tmp_path / "split"
    assert main(["split", str(plain), str(out_dir), "--toc-text", "--hint", "2", "--yes"]) == 0
    assert len(list(out_dir.glob("*.pdf"))) == 3
