from typing import Any, Dict, List, Optional

import fitz

from ..analysis.scanning import analyze_document_scanning
from ..core.base import PDFAdapter
from ..toc.pymupdf import extract_toc_from_pdf
from ..utils import normalize_metadata


class PyMuPDFAdapter(PDFAdapter):
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.doc = fitz.open(file_path)

    def get_metadata(self) -> Dict[str, Any]:
        meta = normalize_metadata(self.doc.metadata)
        # Add scanning analysis
        scanning_info = analyze_document_scanning(self.doc)
        meta.update(scanning_info)
        meta["library"] = "PyMuPDF"
        return meta

    def get_page_count(self) -> int:
        return self.doc.page_count

    def extract_text(self, page_range: Optional[str] = None) -> str:
        # Simplification: just get all text for now if no range
        # In a real impl, we'd use the range utilities we created
        text = ""
        for page in self.doc:
            text += page.get_text()
        return text

    def get_toc(self, use_ocr: bool = False, hint_page: int = 6) -> List[Dict[str, Any]]:
        # Use our existing heuristic-based TOC extractor
        return extract_toc_from_pdf(str(self.file_path), use_ocr=use_ocr, hint_page=hint_page)

    def close(self):
        self.doc.close()
