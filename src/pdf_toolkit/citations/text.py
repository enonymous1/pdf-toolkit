"""Shared text handling for the citations checker.

One sentence splitter and one normalizer serve both extractors, so a
chunk and a source sentence are compared in the same form. The original
project had two different splitters (one per extractor) and compared
raw text, so case, punctuation, and PDF line-break hyphenation all
counted against a match.
"""

from __future__ import annotations

import re

__all__ = [
    "SENTENCE_SPLIT_RE",
    "has_citation_marker",
    "normalize_text",
    "split_sentences",
    "token_set",
    "tokens",
]

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'\(\[])")
_HYPHEN_NEWLINE_RE = re.compile(r"([A-Za-z])-\s*\n\s*([a-z])")
_NON_WORD_RE = re.compile(r"[^\w\s]+")
_WHITESPACE_RE = re.compile(r"\s+")

_BRACKET_CITATION_RE = re.compile(r"\[\d+(?:\s*[,\-;]\s*\d+)*\]")
_AUTHOR_YEAR_RE = re.compile(
    r"\b[A-Z][A-Za-z]+(?:\s+(?:and|&)\s+[A-Z][A-Za-z]+)?\s*\(\d{4}[a-z]?\)"
)
_YEAR_PAREN_RE = re.compile(
    r"\(\s*[A-Z][A-Za-z]+(?:\s+(?:and|&)\s+[A-Z][A-Za-z]+)?\s*,\s*\d{4}[a-z]?\s*\)"
)
_TRAILING_REF_RE = re.compile(r"[\)\]\}\"']\s*\d+(?:\s*,\s*\d+)*\.?\s*$")
_TRAILING_MULTI_REF_RE = re.compile(r"\s\d+\s*,\s*\d+\.?\s*$")


def normalize_text(text: str) -> str:
    """Lowercase, dehyphenate line breaks, and drop punctuation.

    Returns the tokens joined by single spaces, so ``"Tax reform."``
    and ``"TAX\\nreform"`` normalize to the same string.
    """
    if not text:
        return ""
    text = text.replace("\u00ad", "")
    text = _HYPHEN_NEWLINE_RE.sub(r"\1\2", text)
    text = _NON_WORD_RE.sub(" ", text.lower())
    return _WHITESPACE_RE.sub(" ", text).strip()


def tokens(text: str) -> list[str]:
    """Normalized tokens, in order."""
    return normalize_text(text).split()


def token_set(text: str) -> frozenset[str]:
    """Normalized tokens as a set, for overlap checks."""
    return frozenset(tokens(text))


def split_sentences(text: str) -> list[str]:
    """Split text into sentences with the shared lightweight splitter.

    Newlines become spaces first (after dehyphenation in
    :func:`normalize_text`'s sense, the hyphen is kept out of the raw
    sentence here by joining the break). This is a heuristic, not an
    NLP tokenizer: abbreviations such as ``e.g.`` can split early.
    """
    if not text:
        return []
    flat = _HYPHEN_NEWLINE_RE.sub(r"\1\2", text.replace("\u00ad", ""))
    flat = _WHITESPACE_RE.sub(" ", flat).strip()
    parts = SENTENCE_SPLIT_RE.split(flat)
    return [part.strip() for part in parts if part.strip()]


def has_citation_marker(text: str) -> bool:
    """Heuristic check for an explicit citation marker in ``text``.

    Matches bracketed numbers (``[12]``), author-year forms
    (``Smith (2020)``, ``(Smith, 2020)``), and trailing footnote-style
    references (``... redesign) 1, 2.``). A lone trailing number such
    as ``Version 2.`` is *not* treated as a marker. This never proves
    a passage is cited; it only flags chunks a reviewer may want to
    skip with ``--skip-cited``.
    """
    if not text:
        return False
    return bool(
        _BRACKET_CITATION_RE.search(text)
        or _AUTHOR_YEAR_RE.search(text)
        or _YEAR_PAREN_RE.search(text)
        or _TRAILING_REF_RE.search(text)
        or _TRAILING_MULTI_REF_RE.search(text)
    )
