import pytest

from pdf_toolkit.inspector import parse_page_range


def test_parse_full_range():
    assert parse_page_range(5, start=1) == (0, 4)


def test_parse_start_end():
    assert parse_page_range(10, start=2, end=4) == (1, 3)


def test_parse_start_count():
    assert parse_page_range(10, start=3, count=2) == (2, 3)


def test_parse_invalid_start():
    with pytest.raises(ValueError):
        parse_page_range(5, start=0)


def test_parse_out_of_range_end():
    with pytest.raises(ValueError):
        parse_page_range(3, start=2, end=5)


def test_parse_count_exceeds():
    with pytest.raises(ValueError):
        parse_page_range(3, start=3, count=2)
