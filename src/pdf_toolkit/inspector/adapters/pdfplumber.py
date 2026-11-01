from typing import Any

import pdfplumber

from ..._defaults import TOC_HINT_PAGE
from ..core.base import PDFAdapter
from ..utils import normalize_metadata


class PDFPlumberAdapter(PDFAdapter):
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.pdf = pdfplumber.open(file_path)

    def get_metadata(self) -> dict[str, Any]:
        meta = normalize_metadata(self.pdf.metadata)
        meta["library"] = "pdfplumber"
        return meta

    def get_page_count(self) -> int:
        return len(self.pdf.pages)

    def extract_text(self, page_range: str | None = None) -> str:
        text = ""
        for page in self.pdf.pages:
            text += page.extract_text() or ""
        return text

    def get_toc(
        self, use_ocr: bool = False, hint_page: int = TOC_HINT_PAGE
    ) -> list[dict[str, Any]]:
        # pdfplumber doesn't have a built-in TOC extractor for outlines
        # but we could implement a heuristic one here.
        return []

    def close(self):
        self.pdf.close()
