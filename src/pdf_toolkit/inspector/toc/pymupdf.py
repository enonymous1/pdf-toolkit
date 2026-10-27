import re
from typing import Dict, List, Optional

import fitz

from ..extraction.ocr_utils import get_ocr_text_robust

TOC_LINE_RE = re.compile(r"^(?P<title>.*?[A-Za-z].*?)\s+.*?[\.e_~x-]{2,}\s*(?P<page>\d+)")
# Even noisier: Title <junk> Number
TOC_NOISY_RE = re.compile(r"^(?P<title>[A-Za-z0-9\s\-\(\)\/]{5,})\s+.*?\s*(?P<page>\d+)\s*$")
PAGE_NUM_RE = re.compile(r"(\d+)\s*[\)\.]?\s*$")


def extract_toc_from_pdf(
    path: str, hint_page: Optional[int] = 6, scan_after: int = 15, use_ocr: bool = False
) -> List[Dict]:
    """Try to extract a textual Table of Contents from a PDF using PyMuPDF.

    - path: path to PDF
    - hint_page: 1-indexed page where TOC likely starts
    - scan_after: number of pages after the hint to include in the search
    - use_ocr: attempt OCR if page text is empty

    Returns a list of entries: {"title": str, "page": int, "raw": str}
    """
    doc = fitz.open(path)
    total = doc.page_count
    # convert hint to 0-index
    start_idx = max(0, (hint_page - 1) if hint_page else 0)
    # Search a bit more aggressively for scanned docs
    end_idx = min(total - 1, start_idx + (scan_after if not use_ocr else scan_after + 10))

    toc_lines = []
    toc_page_found = None

    def get_text_for_page(page_idx):
        page = doc.load_page(page_idx)
        if use_ocr:
            return get_ocr_text_robust(page)
        return page.get_text("text") or ""

    # fuzzy keywords
    keywords = ["contents", "table", "index", "summary", "general", "safety", "revisions"]
    for i in range(max(0, start_idx - 3), end_idx + 1):
        text = get_text_for_page(i)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        # Check if this page looks like a TOC start
        header_text = (" ".join(lines[:25])).lower()
        # Look for keywords or just high density of dots/page-numbers
        found_kw = any(kw in header_text for kw in keywords)
        # Check for sequences of dots/dashes
        has_dots = len(re.findall(r"[\.e_~x-]{5,}", text)) > 3
        # Check for high density of numbers at end of lines
        has_numbers = len([ln for ln in lines if PAGE_NUM_RE.search(ln)]) > 4

        if found_kw or has_dots or has_numbers:
            toc_page_found = i
            toc_lines.extend(lines)
            # Scan more pages if we found the start
            for j in range(i + 1, min(total, i + 1 + scan_after)):
                more_text = get_text_for_page(j)
                more = [ln.strip() for ln in more_text.splitlines() if ln.strip()]
                toc_lines.extend(more)
            break

    # if we didn't find a heading keyword, fall back to scanning all pages in range
    if toc_page_found is None:
        for i in range(start_idx, end_idx + 1):
            text = get_text_for_page(i)
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            candidate_lines = [ln for ln in lines if PAGE_NUM_RE.search(ln)]
            if len(candidate_lines) > 2:
                toc_lines.extend(candidate_lines)

    entries = []
    seen_titles = set()

    # Process lines with a sliding window to catch Title \n PageNum
    i = 0
    while i < len(toc_lines):
        line = toc_lines[i]
        match = TOC_LINE_RE.search(line) or TOC_NOISY_RE.search(line)

        found_title = None
        found_page = None
        raw_context = line

        if match:
            found_title = match.group("title")
            found_page = match.group("page")
        else:
            # Try joining with next line if current line looks like a title but has no number
            if len(line) > 5 and not any(c.isdigit() for c in line[-3:]):
                if i + 1 < len(toc_lines):
                    next_line = toc_lines[i + 1]
                    # Check if next line is JUST a number
                    if PAGE_NUM_RE.match(next_line):
                        found_title = line
                        found_page = PAGE_NUM_RE.match(next_line).group(1)
                        raw_context = f"{line} \n {next_line}"
                        i += 1  # Skip next line

        if found_title and found_page:
            try:
                title = found_title.strip().rstrip("._- ")
                # Clean up OCR junk from title
                title = re.sub(r"[^\w\s\-\(\)\/\.,]", "", title).strip()
                page_num = int(found_page)

                if len(title) > 3 and page_num > 0 and title not in seen_titles:
                    entries.append({"title": title, "page": page_num, "raw": raw_context})
                    seen_titles.add(title)
            except ValueError:
                pass
        i += 1

    doc.close()
    return entries
