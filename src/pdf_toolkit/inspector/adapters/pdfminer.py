from io import StringIO
from typing import Any, Dict, List, Optional

from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser

from ..core.base import PDFAdapter
from ..utils import normalize_metadata


class PDFMinerAdapter(PDFAdapter):
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.fp = open(file_path, "rb")
        self.parser = PDFParser(self.fp)
        self.doc = PDFDocument(self.parser)

    def get_metadata(self) -> Dict[str, Any]:
        # pdfminer metadata is tricky (list of dicts)
        raw_info = self.doc.info[0] if self.doc.info else {}
        # convert bytes to str
        clean_raw = {}
        for k, v in raw_info.items():
            if isinstance(v, bytes):
                try:
                    clean_raw[k] = v.decode("utf-8", errors="ignore")
                except Exception:
                    clean_raw[k] = str(v)
            else:
                clean_raw[k] = v

        meta = normalize_metadata(clean_raw)
        meta["library"] = "pdfminer.six"
        return meta

    def get_page_count(self) -> int:
        return len(list(PDFPage.create_pages(self.doc)))

    def extract_text(self, page_range: Optional[str] = None) -> str:
        rsrcmgr = PDFResourceManager()
        retstr = StringIO()
        device = TextConverter(rsrcmgr, retstr, laparams=LAParams())
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        for page in PDFPage.create_pages(self.doc):
            interpreter.process_page(page)
        text = retstr.getvalue()
        device.close()
        retstr.close()
        return text

    def get_toc(self, use_ocr: bool = False, hint_page: int = 6) -> List[Dict[str, Any]]:
        # Returns native bookmarks if available
        try:
            outlines = self.doc.get_outlines()
            toc = []
            for level, title, dest, a, se in outlines:
                toc.append({"title": title, "level": level})
            return toc
        except Exception:
            return []

    def close(self):
        self.fp.close()
