from typing import Dict, List, Optional


def _normalize_title(t):
    if isinstance(t, bytes):
        try:
            return t.decode("utf-8", errors="ignore")
        except Exception:
            return str(t)
    return str(t)


def extract_toc_from_pdf(
    path: str, hint_page: Optional[int] = 6, scan_after: int = 3
) -> List[Dict]:
    """Attempt to extract outlines/TOC from a PDF using pdfminer low-level APIs.

    Returns list of {title: str, page: Optional[int], raw: object}
    """
    entries = []
    try:
        from pdfminer.pdfdocument import PDFDocument
        from pdfminer.pdfpage import PDFPage
        from pdfminer.pdfparser import PDFParser
    except Exception:
        return []

    try:
        with open(path, "rb") as fh:
            parser = PDFParser(fh)
            doc = PDFDocument(parser)
            try:
                outlines = list(doc.get_outlines())
            except Exception:
                outlines = []

            # outlines entries are tuple-like; attempt to extract title and page if possible
            for item in outlines:
                # item could be (level, title, dest, a, b) or similar
                title = None
                page_num = None
                try:
                    # try common positions
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        title = item[1]
                        # dest may be in item[2]
                        dest = item[2] if len(item) > 2 else None
                    elif isinstance(item, dict):
                        title = item.get("Title") or item.get("/Title")
                        dest = item.get("Dest") or item.get("/Dest")
                    else:
                        title = getattr(item, "title", None)
                        dest = getattr(item, "dest", None)
                except Exception:
                    title = None
                    dest = None

                # normalize title
                title = _normalize_title(title) if title is not None else None

                # best-effort page resolution: if dest references a PDF page object, try to find its index
                if dest is not None:
                    try:
                        # dest can be a PDF object; attempt to convert to int page number by scanning pages
                        with open(path, "rb") as fh2:
                            _pages = list(PDFPage.get_pages(fh2))
                            # dest may contain a reference to a page object; fall back to None
                            # we will not attempt deep resolution here — leave as None if unknown
                            page_num = None
                    except Exception:
                        page_num = None

                entries.append({"title": title or "", "page": page_num, "raw": item})
    except Exception:
        return []

    # if outlines were not found, return empty and let caller consider a text-based fallback
    return entries
