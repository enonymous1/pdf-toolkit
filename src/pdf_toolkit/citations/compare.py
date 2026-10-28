"""Fuzzy comparison between DOCX chunks and PDF pages.

Fixes carried over from ss-missedCitations, not just ported:

- Scoring runs on *normalized* text (lowercase, punctuation and
  line-break hyphenation removed), so formatting noise no longer
  counts against a match.
- A token-overlap prefilter runs before any fuzzy score: a window is
  only scored when it shares at least ``min_overlap`` of the chunk's
  tokens. This is what kills the original's false positives, where
  ``fuzz.partial_ratio`` scored 100 for footnote fragments such as
  ``1.`` against any chunk containing a ``1``.
- The full-page fallback is gone. The original also compared every
  chunk against each whole page (truncated to 1000 chars), which made
  the "best snippet" a page of unrelated text and the context the
  whole page. Only sentence windows up to ``max_window`` are scored.
- A best snippet must be meaningful: at least ``min_pdf_snippet_length``
  alphanumeric characters *and* at least two tokens. Short chunks
  (fewer than ``min_chunk_tokens`` tokens) are skipped outright.
- Chunks carrying an explicit citation marker are flagged in the
  result (``has_citation_marker``) and can be dropped with
  ``skip_cited``. Similarity alone never proves a passage is
  uncited; every match is for manual review.
"""

from __future__ import annotations

import re
from pathlib import Path

from .extract import CitationError, extract_chunks_from_docx, extract_pages_from_pdf
from .models import Chunk, Match, SourcePage
from .text import has_citation_marker, normalize_text, token_set, tokens

__all__ = ["compare_chunks_to_pages", "compare_documents"]

MIN_CHUNK_TOKENS = 3


def _fuzz():
    try:
        from rapidfuzz import fuzz
    except ImportError as exc:
        raise ImportError(
            "Checking citations needs RapidFuzz, which is not installed.\n"
            "Install it with: pip install 'pdf-toolkit'\n"
            f"(import error: {exc})"
        ) from exc
    return fuzz


def _token_coverage(chunk_tokens: frozenset[str], window_tokens: frozenset[str]) -> float:
    """Fraction of the chunk's tokens present in the window."""
    if not chunk_tokens:
        return 0.0
    return len(chunk_tokens & window_tokens) / len(chunk_tokens)


def _is_meaningful_snippet(snippet: str | None, min_len: int) -> bool:
    if not snippet:
        return False
    normalized = normalize_text(snippet)
    alnum_len = len(re.sub(r"\W+", "", normalized))
    return alnum_len >= min_len and len(normalized.split()) >= 2


def _build_context(sentences: list[str], match_range: tuple[int, int], context: int) -> str:
    start = max(0, match_range[0] - context)
    end = min(len(sentences), match_range[1] + context + 1)
    return " ".join(sentences[start:end])


def compare_chunks_to_pages(
    chunks: list[Chunk],
    pages: list[SourcePage],
    threshold: int = 85,
    min_chunk_length: int = 0,
    context_sentences: int = 1,
    max_window: int = 3,
    min_pdf_snippet_length: int = 10,
    min_overlap: float = 0.5,
    skip_cited: bool = False,
    min_chunk_tokens: int = MIN_CHUNK_TOKENS,
) -> list[Match]:
    """Find each chunk's best matching PDF sentence window.

    Returns matches at or above ``threshold`` (0-100, RapidFuzz
    ``partial_ratio`` on normalized text). ``min_chunk_length`` is a
    character floor on the raw chunk, as in the original.
    """
    if not 0 <= threshold <= 100:
        raise ValueError(f"threshold must be 0-100, got {threshold}")
    if max_window < 1:
        raise ValueError(f"max_window must be at least 1, got {max_window}")
    if not 0.0 <= min_overlap <= 1.0:
        raise ValueError(f"min_overlap must be 0-1, got {min_overlap}")
    if context_sentences < 0:
        raise ValueError(f"context_sentences must be at least 0, got {context_sentences}")

    fuzz = _fuzz()

    prepared_pages: list[tuple[SourcePage, list[tuple[str, frozenset[str]]]]] = [
        (page, [(sentence, token_set(sentence)) for sentence in page.sentences]) for page in pages
    ]

    results: list[Match] = []
    for chunk in chunks:
        text = chunk.text.strip()
        if not text or len(text) < min_chunk_length:
            continue
        chunk_tokens = tokens(text)
        if len(chunk_tokens) < min_chunk_tokens:
            continue
        cited = has_citation_marker(text)
        if skip_cited and cited:
            continue
        chunk_token_set = frozenset(chunk_tokens)
        normalized_chunk = " ".join(chunk_tokens)

        best_score = 0
        best_page: int | None = None
        best_snippet: str | None = None
        best_match_range: tuple[int, int] = (0, 0)

        for page, sentence_data in prepared_pages:
            for i in range(len(sentence_data)):
                window_tokens: set[str] = set()
                window_sentences: list[str] = []
                for w in range(1, max_window + 1):
                    j = i + w
                    if j > len(sentence_data):
                        break
                    sentence, sentence_tokens = sentence_data[j - 1]
                    window_sentences.append(sentence)
                    window_tokens |= sentence_tokens
                    if _token_coverage(chunk_token_set, window_tokens) < min_overlap:
                        continue
                    window_text = " ".join(window_sentences)
                    raw_score = fuzz.partial_ratio(normalized_chunk, normalize_text(window_text))
                    score = int(round(raw_score))
                    # Prefer a higher score, then the shortest window that
                    # achieves it: partial_ratio hits 100 for any window
                    # containing the chunk verbatim, and the tightest
                    # window is the most precise snippet to review.
                    if score > best_score or (
                        score == best_score
                        and best_snippet is not None
                        and len(window_text) < len(best_snippet)
                    ):
                        best_score = score
                        best_snippet = window_text
                        best_page = page.page_number
                        best_match_range = (i, j - 1)

        if best_score >= threshold and best_page is not None:
            if not _is_meaningful_snippet(best_snippet, min_pdf_snippet_length):
                continue
            page_obj = next(
                (page for page, _ in prepared_pages if page.page_number == best_page),
                None,
            )
            pdf_context = ""
            if page_obj is not None:
                pdf_context = _build_context(
                    page_obj.sentences, best_match_range, context_sentences
                )
            results.append(
                Match(
                    doc_chunk_id=chunk.id,
                    doc_text=text,
                    pdf_snippet=best_snippet or "",
                    pdf_context=pdf_context,
                    page_number=best_page,
                    score=best_score,
                    matched_sentence_indices=best_match_range,
                    has_citation_marker=cited,
                    doc_source=chunk.source,
                )
            )

    return results


def compare_documents(
    docx_path: str | Path,
    pdf_path: str | Path,
    **kwargs,
) -> list[Match]:
    """Extract both files and compare them; see :func:`compare_chunks_to_pages`."""
    try:
        chunks = extract_chunks_from_docx(docx_path)
        pages = extract_pages_from_pdf(pdf_path)
    except FileNotFoundError:
        raise
    except ImportError:
        raise
    except Exception as exc:
        raise CitationError(str(exc)) from exc
    return compare_chunks_to_pages(chunks, pages, **kwargs)
