"""Tests for the citations checker (text handling + comparison).

Fictional data only. The regression case that matters most is the
original's: footnote fragments (``1.``, ``P.``) must never match at
score 100, and a verbatim sentence must.
"""

import pytest

from pdf_toolkit.citations import Chunk, SourcePage, compare_chunks_to_pages
from pdf_toolkit.citations.text import (
    has_citation_marker,
    normalize_text,
    split_sentences,
    token_set,
)

rapidfuzz = pytest.importorskip("rapidfuzz")


def _chunk(text, chunk_id=0):
    return Chunk(id=chunk_id, text=text, source=f"paragraph {chunk_id}")


def _page(sentences, page_number=1):
    return SourcePage(page_number=page_number, text=" ".join(sentences), sentences=list(sentences))


def test_normalize_text_drops_case_punctuation_and_hyphen_breaks():
    assert normalize_text("Tax Reform, 2026!") == "tax reform 2026"
    assert normalize_text("moderniza-\ntion of the system") == "modernization of the system"
    assert normalize_text("  spaced   out  ") == "spaced out"


def test_split_sentences_shared_splitter():
    assert split_sentences("First sentence. Second sentence! Third?") == [
        "First sentence.",
        "Second sentence!",
        "Third?",
    ]
    assert split_sentences("") == []


def test_has_citation_marker_forms():
    assert has_citation_marker("As shown previously [12].")
    assert has_citation_marker("Rivera (2020) argues otherwise.")
    assert has_citation_marker("Prior work (Rivera, 2020) supports this.")
    assert has_citation_marker("Must follow the format provided 1, 2.")
    assert has_citation_marker("Must follow the format provided (see guide) 3.")
    assert not has_citation_marker("The quick brown fox jumps over the lazy dog.")
    assert not has_citation_marker("See section 2 for details.")
    assert not has_citation_marker("Version 2 was released in March.")


def test_verbatim_match_scores_100():
    chunks = [_chunk("The quick brown fox jumps over the lazy dog.")]
    pages = [_page(["The quick brown fox jumps over the lazy dog.", "Unrelated text."])]
    results = compare_chunks_to_pages(chunks, pages, threshold=85)
    assert len(results) == 1
    assert results[0].score == 100
    assert results[0].page_number == 1
    assert results[0].matched_sentence_indices == (0, 0)
    assert "quick brown fox" in results[0].pdf_snippet
    assert not results[0].has_citation_marker


def test_footnote_fragments_never_match():
    # The original reported all of these at score 100: partial_ratio
    # matches a lone "1" inside any chunk. The token prefilter plus
    # the meaningful-snippet rule must reject every one.
    chunks = [
        _chunk("Must follow the specific format provided in the guide.", 1),
        _chunk("Describe the qualifications and experience relevant here.", 4),
        _chunk("A written statement signed by the expert is required.", 7),
    ]
    pages = [_page(["1.", "P.", "2.", "l.", "Some unrelated source sentence here."], 203)]
    results = compare_chunks_to_pages(chunks, pages, threshold=50)
    assert results == []


def test_sliding_window_spanning_two_sentences():
    chunks = [_chunk("The river valley supports three farming villages")]
    pages = [_page(["The river valley supports", "three farming villages nearby.", "Other."])]
    results = compare_chunks_to_pages(chunks, pages, threshold=80, max_window=2)
    assert len(results) == 1
    assert "river valley" in results[0].pdf_snippet


def test_unrelated_text_does_not_match():
    chunks = [_chunk("Harbor tides follow a predictable lunar cycle each month.")]
    pages = [
        _page(["Desert rainfall is scarce and highly seasonal.", "Cactus flowers bloom briefly."])
    ]
    assert compare_chunks_to_pages(chunks, pages, threshold=85) == []


def test_min_chunk_length_and_short_chunks_skipped():
    chunks = [_chunk("1.", 0), _chunk("This is a longer test sentence.", 1)]
    pages = [_page(["This is a longer test sentence.", "Something else."])]
    results = compare_chunks_to_pages(chunks, pages, threshold=80, min_chunk_length=5)
    assert [r.doc_chunk_id for r in results] == [1]


def test_citation_marker_flagged_and_skip_cited_drops_it():
    chunks = [_chunk("The river valley supports three villages (Rivera, 2020).")]
    pages = [_page(["The river valley supports three villages nearby."])]
    results = compare_chunks_to_pages(chunks, pages, threshold=80)
    assert len(results) == 1
    assert results[0].has_citation_marker
    assert compare_chunks_to_pages(chunks, pages, threshold=80, skip_cited=True) == []


def test_context_sentences_around_match():
    chunks = [_chunk("Middle sentence matches the source exactly here.")]
    pages = [
        _page(
            [
                "Before context sentence one.",
                "Middle sentence matches the source exactly here.",
                "After context sentence two.",
            ]
        )
    ]
    results = compare_chunks_to_pages(chunks, pages, threshold=85, context_sentences=1)
    assert len(results) == 1
    assert "Before context" in results[0].pdf_context
    assert "After context" in results[0].pdf_context


def test_best_match_wins_across_pages():
    chunks = [_chunk("The harbor lighthouse was built in eighteen forty two.")]
    pages = [
        _page(["The harbor lighthouse was built in eighteen forty two."], 1),
        _page(["A lighthouse stands near the harbor entrance."], 2),
    ]
    results = compare_chunks_to_pages(chunks, pages, threshold=85)
    assert len(results) == 1
    assert results[0].page_number == 1


def test_threshold_validation():
    chunks = [_chunk("The quick brown fox jumps over the lazy dog.")]
    pages = [_page(["The quick brown fox jumps over the lazy dog."])]
    with pytest.raises(ValueError):
        compare_chunks_to_pages(chunks, pages, threshold=101)
    with pytest.raises(ValueError):
        compare_chunks_to_pages(chunks, pages, max_window=0)
    with pytest.raises(ValueError):
        compare_chunks_to_pages(chunks, pages, min_overlap=1.5)


def test_token_coverage_prefilter_blocks_low_overlap():
    # High partial_ratio on a shared word alone must not survive:
    # only one of five chunk tokens appears in the window.
    chunks = [_chunk("Alpine glaciers retreat during warm summer seasons")]
    pages = [_page(["Warm breezes cross the meadow."])]
    assert compare_chunks_to_pages(chunks, pages, threshold=50, min_overlap=0.5) == []
    assert token_set("Alpine glaciers retreat") == {"alpine", "glaciers", "retreat"}
