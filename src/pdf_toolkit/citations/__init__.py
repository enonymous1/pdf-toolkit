"""Flag DOCX manuscript text similar to a PDF source, for citation review.

Folded in from ss-missedCitations (0.5.0): the original compared raw
DOCX paragraphs against PDF pages with ``thefuzz`` ``partial_ratio``
and no normalization, prefilter, or citation awareness, so its
shipped reports were all score-100 footnote fragments. This port
normalizes both sides, prefilters windows by token overlap, requires
a meaningful snippet, extracts DOCX tables in document order, and
flags chunks carrying an explicit citation marker. Similarity alone
never proves a passage is uncited; matches are for manual review.

Needs ``pdf-toolkit[citations]`` for the DOCX reader (python-docx);
the PDF reader and fuzzy matcher are core dependencies.
"""

from .compare import compare_chunks_to_pages, compare_documents
from .extract import (
    CitationError,
    extract_chunks_from_docx,
    extract_pages_from_pdf,
)
from .models import Chunk, Match, SourcePage
from .text import has_citation_marker, normalize_text, split_sentences, token_set, tokens

__all__ = [
    "Chunk",
    "CitationError",
    "Match",
    "SourcePage",
    "compare_chunks_to_pages",
    "compare_documents",
    "extract_chunks_from_docx",
    "extract_pages_from_pdf",
    "has_citation_marker",
    "normalize_text",
    "split_sentences",
    "token_set",
    "tokens",
]
