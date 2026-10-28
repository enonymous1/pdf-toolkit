"""Chunk and page models for the citations checker."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Chunk:
    """One comparable unit from the DOCX manuscript."""

    id: int
    text: str
    source: str = ""


@dataclass
class SourcePage:
    """One PDF page: raw text plus its sentences, in order."""

    page_number: int
    text: str
    sentences: list[str] = field(default_factory=list)


@dataclass
class Match:
    """One chunk whose best source snippet reached the threshold."""

    doc_chunk_id: int
    doc_text: str
    pdf_snippet: str
    pdf_context: str
    page_number: int
    score: int
    matched_sentence_indices: tuple[int, int]
    has_citation_marker: bool = False
    doc_source: str = ""

    def to_dict(self) -> dict:
        """JSON-ready form (the sentence range becomes a list)."""
        return {
            "doc_chunk_id": self.doc_chunk_id,
            "doc_text": self.doc_text,
            "pdf_snippet": self.pdf_snippet,
            "pdf_context": self.pdf_context,
            "page_number": self.page_number,
            "score": self.score,
            "matched_sentence_indices": list(self.matched_sentence_indices),
            "has_citation_marker": self.has_citation_marker,
            "doc_source": self.doc_source,
        }
