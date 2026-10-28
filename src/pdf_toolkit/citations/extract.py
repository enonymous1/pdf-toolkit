"""Extract comparable chunks from a DOCX and pages from a PDF.

The original project read only DOCX paragraphs, in paragraph order,
and silently dropped tables. This version walks the document body in
order, so table cells become chunks too (each cell's text is one
chunk, split into sentences when long). Headers, footers, and
footnotes are still not extracted: python-docx does not surface them
through the body walk, and the original did not read them either.
"""

from __future__ import annotations

from pathlib import Path

from .models import Chunk, SourcePage
from .text import split_sentences

__all__ = [
    "CitationError",
    "extract_chunks_from_docx",
    "extract_pages_from_pdf",
]

LONG_PARAGRAPH_CHARS = 300


class CitationError(Exception):
    """The input files could not be read for citation checking."""


def _require_docx():
    try:
        from docx import Document
    except ImportError as exc:
        raise ImportError(
            "Checking citations needs python-docx, which is not installed.\n"
            "Install it with: pip install 'pdf-toolkit[citations]'\n"
            f"(import error: {exc})"
        ) from exc
    return Document


def extract_chunks_from_docx(
    file_path: str | Path, long_paragraph_chars: int = LONG_PARAGRAPH_CHARS
) -> list[Chunk]:
    """Return chunks from a .docx, in document order.

    Each chunk is a paragraph (or one sentence of a paragraph longer
    than ``long_paragraph_chars``) or a table cell, labelled by its
    ``source`` (``paragraph N`` or ``table N, row R, cell C``).
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"DOCX file not found: {file_path}")
    Document = _require_docx()
    from docx.table import Table as DocxTable
    from docx.text.paragraph import Paragraph as DocxParagraph

    try:
        doc = Document(str(path))
    except Exception as exc:
        raise CitationError(f"Failed to read DOCX '{file_path}': {exc}") from exc

    chunks: list[Chunk] = []
    paragraph_index = 0
    table_index = 0

    def _add(text: str, source: str) -> None:
        text = text.strip()
        if not text:
            return
        if len(text) > long_paragraph_chars:
            for sentence in split_sentences(text):
                chunks.append(Chunk(id=len(chunks), text=sentence, source=source))
        else:
            chunks.append(Chunk(id=len(chunks), text=text, source=source))

    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            para = DocxParagraph(child, doc)
            _add(para.text, f"paragraph {paragraph_index}")
            paragraph_index += 1
        elif child.tag.endswith("}tbl"):
            table = DocxTable(child, doc)
            seen_cells: set[int] = set()
            for row_index, row in enumerate(table.rows):
                for cell_index, cell in enumerate(row.cells):
                    if id(cell._tc) in seen_cells:
                        continue
                    seen_cells.add(id(cell._tc))
                    cell_text = " ".join(
                        paragraph.text.strip()
                        for paragraph in cell.paragraphs
                        if paragraph.text.strip()
                    )
                    _add(
                        cell_text,
                        f"table {table_index}, row {row_index + 1}, cell {cell_index + 1}",
                    )
            table_index += 1

    return chunks


def extract_pages_from_pdf(file_path: str | Path) -> list[SourcePage]:
    """Return one :class:`SourcePage` per PDF page (1-based numbers)."""
    import fitz

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found: {file_path}")
    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        raise CitationError(f"Failed to open PDF '{file_path}': {exc}") from exc
    try:
        pages = []
        for i in range(len(doc)):
            text = doc.load_page(i).get_text("text")
            pages.append(
                SourcePage(
                    page_number=i + 1,
                    text=text,
                    sentences=split_sentences(text),
                )
            )
        return pages
    except Exception as exc:
        raise CitationError(f"Failed to read PDF '{file_path}': {exc}") from exc
    finally:
        doc.close()
