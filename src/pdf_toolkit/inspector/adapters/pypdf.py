from typing import Any

from pypdf import PdfReader

from ..._defaults import TOC_HINT_PAGE
from ..core.base import PDFAdapter


class PyPDFAdapter(PDFAdapter):
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.reader = PdfReader(file_path)

    def get_metadata(self) -> dict[str, Any]:
        # Sample PDFs (and many real ones) have no metadata at all, in
        # which case pypdf returns None -- the old code crashed on .get().
        raw_meta: dict = dict(self.reader.metadata or {})
        meta = {
            "title": str(raw_meta.get("/Title") or ""),
            "author": str(raw_meta.get("/Author") or ""),
            "subject": str(raw_meta.get("/Subject") or ""),
            "producer": str(raw_meta.get("/Producer") or ""),
            "library": "pypdf",
        }
        return meta

    def get_page_count(self) -> int:
        return len(self.reader.pages)

    def extract_text(self, page_range: str | None = None) -> str:
        text = ""
        for page in self.reader.pages:
            text += page.extract_text() or ""
        return text

    def get_toc(
        self, use_ocr: bool = False, hint_page: int = TOC_HINT_PAGE
    ) -> list[dict[str, Any]]:
        # Outlines first, then the text-TOC fallback in toc.pypdf.
        from ..toc.pypdf import extract_toc_from_pdf

        return extract_toc_from_pdf(str(self.file_path), hint_page=hint_page)

    def close(self):
        pass  # pypdf Reader doesn't need explicit close usually
