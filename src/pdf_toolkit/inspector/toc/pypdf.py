import re
from typing import Dict, List, Optional

TOC_LINE_RE = re.compile(r"^(?P<title>.+?)\s+(?:\.{2,}|\s+)\s*(?P<page>\d+)$")
PAGE_NUM_RE = re.compile(r"(\d+)$")


def _parse_lines(lines: List[str]) -> List[Dict]:
    entries = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        m = TOC_LINE_RE.match(ln)
        if m:
            title = m.group("title").strip()
            page = int(m.group("page"))
            entries.append({"title": title, "page": page, "raw": ln})
            continue
        m2 = PAGE_NUM_RE.search(ln)
        if m2:
            page = int(m2.group(1))
            title = ln[: m2.start()].rstrip(". ") or ln
            entries.append({"title": title.strip(), "page": page, "raw": ln})
    return entries


def extract_toc_from_pdf(
    path: str, hint_page: Optional[int] = 6, scan_after: int = 3
) -> List[Dict]:
    """Attempt to extract a TOC for a PDF using pypdf outlines or a text fallback (pdfplumber).

    Returns list of {title, page, raw} entries (may be empty).
    """
    # try to extract PDF outlines/bookmarks via pypdf first (caller may prefer this)
    try:
        from pypdf import PdfReader

        reader = PdfReader(path)
        outlines = None
        try:
            # pypdf may provide .outlines or get_outlines()
            if hasattr(reader, "outlines"):
                outlines = reader.outlines
            elif hasattr(reader, "get_outlines"):
                outlines = reader.get_outlines()
        except Exception:
            outlines = None

        entries = []
        if outlines:
            # outlines from pypdf can be nested; flatten shallowly
            def _walk(o):
                for item in o:
                    if isinstance(item, list):
                        yield from _walk(item)
                    else:
                        # an outline dict-like / Destination
                        title = getattr(item, "title", None) or (
                            item.get("/Title") if isinstance(item, dict) else None
                        )
                        page = None
                        try:
                            # attempt to resolve page number from destination
                            dest = getattr(item, "destination", None) or getattr(
                                item, "/Dest", None
                            )
                            if dest is not None:
                                # best-effort: convert to int if possible
                                page = int(dest) if isinstance(dest, int) else None
                        except Exception:
                            page = None
                        if title:
                            entries.append({"title": str(title), "page": page, "raw": str(item)})

            try:
                for e in _walk(outlines):
                    entries.append(e)
            except Exception:
                entries = []
        if entries:
            return entries
    except Exception:
        # pypdf outline extraction failed — fall back to text heuristics
        pass

    # fallback: scan pages near hint_page using pdfplumber to find TOC-like lines
    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            total = len(pdf.pages)
            start = max(0, (hint_page - 1) if hint_page else 0)
            end = min(total - 1, start + max(0, scan_after))
            lines = []
            # look for a page that contains the word 'contents' in the top lines
            toc_page = None
            for i in range(start, end + 1):
                text = (pdf.pages[i].extract_text() or "").strip()
                if not text:
                    continue
                lns = [ln.strip() for ln in text.splitlines() if ln.strip()]
                if any("contents" in ln.lower() for ln in lns[:6]):
                    toc_page = i
                    lines.extend(lns)
                    # also grab the following pages in case TOC spans multiple pages
                    for j in range(i + 1, min(total, i + 1 + scan_after)):
                        more = (pdf.pages[j].extract_text() or "").strip()
                        if more:
                            lines.extend([ln.strip() for ln in more.splitlines() if ln.strip()])
                    break
            if toc_page is None:
                # heuristic: collect lines that end with a page number on the hint pages
                for i in range(start, end + 1):
                    text = (pdf.pages[i].extract_text() or "").strip()
                    if not text:
                        continue
                    lns = [ln.strip() for ln in text.splitlines() if ln.strip()]
                    candidate = [ln for ln in lns if PAGE_NUM_RE.search(ln)]
                    if candidate:
                        lines.extend(candidate)
                        for j in range(i + 1, min(total, i + 1 + 2)):
                            more = (pdf.pages[j].extract_text() or "").strip()
                            if more:
                                lines.extend(
                                    [
                                        ln.strip()
                                        for ln in more.splitlines()
                                        if ln.strip() and PAGE_NUM_RE.search(ln)
                                    ]
                                )
                        break
            return _parse_lines(lines)
    except Exception:
        return []
