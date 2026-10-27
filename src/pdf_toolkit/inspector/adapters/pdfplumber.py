from typing import Any, Dict, List, Optional

import pdfplumber

from ..core.base import PDFAdapter
from ..utils import normalize_metadata


class PDFPlumberAdapter(PDFAdapter):
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.pdf = pdfplumber.open(file_path)

    def get_metadata(self) -> Dict[str, Any]:
        meta = normalize_metadata(self.pdf.metadata)
        meta["library"] = "pdfplumber"
        return meta

    def get_page_count(self) -> int:
        return len(self.pdf.pages)

    def extract_text(self, page_range: Optional[str] = None) -> str:
        text = ""
        for page in self.pdf.pages:
            text += page.extract_text() or ""
        return text

    def get_toc(self, use_ocr: bool = False, hint_page: int = 6) -> List[Dict[str, Any]]:
        # pdfplumber doesn't have a built-in TOC extractor for outlines
        # but we could implement a heuristic one here.
        return []

    def close(self):
        self.pdf.close()
