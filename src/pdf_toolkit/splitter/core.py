"""Split a PDF into chapter PDFs by bookmarks, a CSV, or located headings.

This folds in the ss-HESI scripts, generalized: no book-specific paths,
no import-time side effects, one shared CSV parser and filename
sanitizer, and a single pass over the source PDF per operation.

Entry pages are 0-based inside this module. CSV files and the printed
TOC text use 1-based pages, converted on load; the ``offset`` argument
on the text-TOC path covers printed page numbers that do not match
physical pages (front matter), which the original scripts silently
conflated.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

import pdfplumber
from pypdf import PdfReader, PdfWriter

__all__ = [
    "Entry",
    "ProposedRange",
    "clean_filename",
    "extract_outline_entries",
    "extract_text_toc_entries",
    "load_entries_from_csv",
    "locate_headings",
    "propose_ranges",
    "resolve_entries",
    "sanitize_filename",
    "split_pdf",
    "write_entries_csv",
]

_ILLEGAL_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')

# Heuristics ported from ss-HESI's clean_split_filenames.py: candidates
# containing these words are usually boilerplate, not a chapter title.
UNDESIRABLE_SUBSTRINGS = (
    "chapter",
    "http",
    "ngn",
    "more information",
    "starting in",
    "the data",
    "include",
    "index",
    "preface",
    "copyright",
    "contributing",
    "authors",
)
_FILENAME_SEPARATORS = (" / ", " - ", " — ", "–", "—", "(", ")")


@dataclass(frozen=True)
class Entry:
    """A chapter start: title and 0-based page index."""

    title: str
    page: int


@dataclass(frozen=True)
class ProposedRange:
    """A chapter's page span, both ends 0-based and inclusive."""

    title: str
    start: int
    end: int


def sanitize_filename(name: str, max_len: int = 120) -> str:
    """Replace illegal filename characters and collapse whitespace.

    Truncates at a word boundary when possible instead of mid-word.
    """
    cleaned = _ILLEGAL_FILENAME_CHARS.sub("-", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) <= max_len:
        return cleaned
    cut = cleaned[:max_len]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.strip()


def _parse_title_page_rows(
    rows: Iterable[list[str]], source_name: str
) -> tuple[list[Entry], list[str]]:
    """Parse ``title,page`` rows (1-based pages) into entries.

    The CSV reader handles quoted titles containing commas; unquoted
    titles containing commas are also handled by treating everything
    before the last field as the title, matching the original scripts.
    Malformed rows are skipped with a warning instead of crashing.
    """
    entries: list[Entry] = []
    warnings: list[str] = []
    for lineno, row in enumerate(rows, start=1):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) < 2:
            warnings.append(f"{source_name}:{lineno}: skipping malformed line (no page number)")
            continue
        title = ",".join(row[:-1]).strip().strip("\"'")
        page_text = row[-1].strip()
        try:
            page = int(page_text)
        except ValueError:
            warnings.append(f"{source_name}:{lineno}: skipping invalid page number {page_text!r}")
            continue
        if page < 1:
            warnings.append(f"{source_name}:{lineno}: skipping page number {page} (< 1)")
            continue
        if not title:
            warnings.append(f"{source_name}:{lineno}: skipping entry with empty title")
            continue
        entries.append(Entry(title=title, page=page - 1))
    return entries, warnings


def load_entries_from_csv(csv_path: str | Path) -> tuple[list[Entry], list[str]]:
    """Load chapter entries from a ``title,page`` (1-based) CSV file."""
    path = Path(csv_path)
    with path.open(newline="", encoding="utf-8") as fh:
        return _parse_title_page_rows(csv.reader(fh), str(path))


def write_entries_csv(entries: Iterable[Entry], csv_path: str | Path) -> Path:
    """Write entries as ``title,page`` (1-based) CSV, quoting as needed."""
    path = Path(csv_path)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        for entry in entries:
            writer.writerow([entry.title, entry.page + 1])
    return path


def _walk_outlines(reader: PdfReader) -> list[object]:
    outline = getattr(reader, "outline", None)
    if outline is None:
        outline = getattr(reader, "outlines", None)
    if outline is None and hasattr(reader, "get_outlines"):
        outline = reader.get_outlines()
    flat: list[object] = []

    def walk(obj: object) -> None:
        if isinstance(obj, list):
            for item in obj:
                walk(item)
        else:
            flat.append(obj)

    if outline:
        walk(outline)
    return flat


def extract_outline_entries(pdf_path: str | Path) -> tuple[list[Entry], list[str]]:
    """Resolve PDF bookmarks/outlines to (title, 0-based page) entries.

    Unlike the inspector's old TOC code, destinations are resolved with
    ``get_destination_page_number``; entries whose destination cannot be
    resolved are skipped with a warning. Exact duplicates are dropped,
    order is preserved.
    """
    reader = PdfReader(str(pdf_path))
    entries: list[Entry] = []
    warnings: list[str] = []
    seen: set[tuple[str, int]] = set()
    for obj in _walk_outlines(reader):
        title = getattr(obj, "title", None)
        if title is None and isinstance(obj, dict):
            title = obj.get("/Title")
        if not title:
            continue
        try:
            page = reader.get_destination_page_number(obj)
        except Exception:
            page = None
        if page is None:
            warnings.append(f"Skipping outline entry {str(title)!r}: no resolvable page")
            continue
        key = (str(title), page)
        if key in seen:
            continue
        seen.add(key)
        entries.append(Entry(title=str(title), page=page))
    return entries, warnings


def extract_text_toc_entries(
    pdf_path: str | Path, hint_page: int = 6, offset: int = 0
) -> tuple[list[Entry], list[str]]:
    """Extract entries from the printed TOC text via the inspector.

    Returned pages are the printed numbers shifted by ``offset`` and
    converted to 0-based. Entries without a numeric page are dropped:
    the inspector's outline branch can return titles with no page, and
    a split needs a page. ``offset`` is the printed-to-physical shift
    (physical = printed + offset); 0 means they already agree.
    """
    from ..inspector.toc.pypdf import extract_toc_from_pdf

    raw = extract_toc_from_pdf(str(pdf_path), hint_page=hint_page)
    entries: list[Entry] = []
    warnings: list[str] = []
    seen: set[tuple[str, int]] = set()
    for item in raw:
        title = item.get("title")
        page = item.get("page")
        if not title or not isinstance(page, int):
            warnings.append(f"Skipping TOC entry {str(title)!r}: no page number")
            continue
        entry = Entry(title=str(title), page=page - 1 + offset)
        if entry.page < 0:
            warnings.append(f"Skipping TOC entry {str(title)!r}: page resolves before page 1")
            continue
        key = (entry.title, entry.page)
        if key in seen:
            continue
        seen.add(key)
        entries.append(entry)
    return entries, warnings


def _normalize(text: str) -> str:
    text = text.replace("\u00ae", "").replace("\u2122", "")
    text = text.replace("\u2019", "'").replace("\u2013", "-")
    text = re.sub(r"[^\w\s-]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip().casefold()


def _detect_toc_pages(page_texts: list[str], look_pages: int = 12) -> set[int]:
    """Pages in the first ``look_pages`` that look like a contents page.

    Runs on raw extracted text (before normalization collapses line
    breaks), so the trailing-page-number heuristic sees real lines.
    """
    toc: set[int] = set()
    for i, text in enumerate(page_texts[:look_pages]):
        lowered = text.lower()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if "table of contents" in lowered or any(line.lower() == "contents" for line in lines):
            toc.add(i)
            continue
        if not lines:
            continue
        trailing = sum(1 for line in lines if re.search(r"\d+\s*$", line))
        if trailing >= 6 and trailing / len(lines) > 0.25:
            toc.add(i)
    return toc


def locate_headings(
    pdf_path: str | Path,
    headings: Iterable[str],
    skip_first: int = 0,
    skip_toc: bool = True,
    fuzzy: bool = False,
    fuzzy_threshold: float = 0.5,
) -> list[tuple[str, int | None]]:
    """Find the 0-based page of each heading with one pass over the PDF.

    The original script re-opened and re-extracted the PDF for every
    heading; here page text is extracted once and searched in memory.
    Contents pages are skipped so a heading named in the TOC does not
    resolve to the TOC page itself. With ``fuzzy``, a sliding-window
    similarity fallback runs only for headings no exact match found.
    """
    heading_list = [h.strip() for h in headings if h.strip()]
    with pdfplumber.open(pdf_path) as pdf:
        raw_texts = [page.extract_text() or "" for page in pdf.pages]
    page_texts = [_normalize(text) for text in raw_texts]
    skip: set[int] = set(range(max(0, skip_first)))
    if skip_toc:
        skip.update(_detect_toc_pages(raw_texts))

    results: list[tuple[str, int | None]] = []
    for heading in heading_list:
        norm_heading = _normalize(heading)
        found: int | None = None
        for i, text in enumerate(page_texts):
            if i in skip:
                continue
            if norm_heading and norm_heading in text:
                found = i
                break
        if found is None and fuzzy and norm_heading:
            best_page: int | None = None
            best_score = 0.0
            window = max(30, len(norm_heading))
            step = max(10, window // 2)
            for i, text in enumerate(page_texts):
                if i in skip or not text:
                    continue
                for start in range(0, max(1, len(text) - window), step):
                    score = SequenceMatcher(
                        None, norm_heading, text[start : start + window]
                    ).ratio()
                    if score > best_score:
                        best_score = score
                        best_page = i
            if best_score > fuzzy_threshold:
                found = best_page
        results.append((heading, found))
    return results


def propose_ranges(
    entries: Iterable[Entry], total_pages: int, merge_same_page: bool = True
) -> tuple[list[ProposedRange], list[str]]:
    """Turn sorted chapter starts into inclusive page ranges.

    Same-page starts are merged into one range (titles joined with
    ``" / "``) unless ``merge_same_page`` is false, in which case the
    later same-page entries produce empty ranges and are dropped with a
    warning. Out-of-range starts are dropped with a warning.
    """
    ordered = sorted(entries, key=lambda e: e.page)
    warnings: list[str] = []
    valid: list[Entry] = []
    for entry in ordered:
        if entry.page < 0 or entry.page >= total_pages:
            warnings.append(
                f"Skipping out-of-range entry {entry.title!r}: "
                f"page {entry.page + 1} of {total_pages}"
            )
        else:
            valid.append(entry)
    ordered = valid
    if merge_same_page and ordered:
        merged: list[Entry] = []
        for entry in ordered:
            if merged and entry.page == merged[-1].page:
                merged[-1] = Entry(title=f"{merged[-1].title} / {entry.title}", page=entry.page)
            else:
                merged.append(entry)
        ordered = merged
    ranges: list[ProposedRange] = []
    for idx, entry in enumerate(ordered):
        end = ordered[idx + 1].page - 1 if idx + 1 < len(ordered) else total_pages - 1
        if entry.page > end:
            warnings.append(
                f"Skipping invalid range for {entry.title!r}: "
                f"pages {entry.page + 1}-{end + 1} of {total_pages}"
            )
            continue
        ranges.append(ProposedRange(title=entry.title, start=entry.page, end=end))
    return ranges, warnings


def _choose_group(groups: list[Entry], page: int) -> str | None:
    """Title of the latest group starting at or before ``page``."""
    chosen: str | None = None
    for group in sorted(groups, key=lambda g: g.page):
        if page >= group.page:
            chosen = group.title
        else:
            break
    return chosen


def clean_filename(title: str, max_len: int = 100) -> str:
    """Pick the most chapter-like fragment of a messy split title.

    Ported from ss-HESI's clean_split_filenames.py: split on common
    separators, prefer longer fragments without boilerplate words, and
    sanitize the result. Used only with ``clean_names=True``.
    """
    text = title.strip().strip("\"'")
    text = re.sub(r"[\u2013\u2014]", "-", text)
    candidates = [text]
    for sep in _FILENAME_SEPARATORS:
        parts: list[str] = []
        for candidate in candidates:
            parts.extend(p.strip() for p in candidate.split(sep) if p.strip())
        candidates = parts
    scored: list[tuple[int, str]] = []
    for candidate in candidates:
        low = candidate.lower()
        score = len(candidate)
        if any(bad in low for bad in UNDESIRABLE_SUBSTRINGS):
            score -= 1000
        if sum(ch.isalpha() for ch in candidate) < 3:
            score -= 500
        scored.append((score, candidate))
    scored.sort(reverse=True)
    best = scored[0][1] if scored else title
    best = re.sub(r"[\-:;,_]+$", "", best).strip()
    return sanitize_filename(re.sub(r"\s+", " ", best), max_len=max_len)


def _plan_paths(
    ranges: list[ProposedRange],
    out_dir: Path,
    groups: list[Entry] | None,
    clean_names: bool,
) -> list[tuple[ProposedRange, Path]]:
    """Assign output paths, de-duplicating names within each folder."""
    planned: list[tuple[ProposedRange, Path]] = []
    used: dict[Path, set[str]] = {}
    groups_sorted = sorted(groups, key=lambda g: g.page) if groups else []
    for idx, chapter in enumerate(ranges, start=1):
        title = clean_filename(chapter.title) if clean_names else sanitize_filename(chapter.title)
        target_dir = out_dir
        if groups_sorted:
            group_name = _choose_group(groups_sorted, chapter.start)
            if group_name:
                target_dir = out_dir / sanitize_filename(group_name)
        fname = f"{idx:02d} - {title}.pdf"
        taken = used.setdefault(target_dir, set())
        candidate = fname
        suffix = 1
        while candidate.lower() in {name.lower() for name in taken}:
            suffix += 1
            candidate = f"{idx:02d} - {title} ({suffix}).pdf"
        taken.add(candidate)
        planned.append((chapter, target_dir / candidate))
    return planned


def split_pdf(
    pdf_path: str | Path,
    entries: Iterable[Entry],
    out_dir: str | Path,
    groups: Iterable[Entry] | None = None,
    merge_same_page: bool = True,
    clean_names: bool = False,
    overwrite: bool = False,
    preserve_metadata: bool = True,
) -> list[Path]:
    """Write one PDF per proposed range. Nothing is written on failure.

    Existing output files block the whole split (``FileExistsError``)
    unless ``overwrite`` is set, so a re-run cannot silently clobber
    earlier output. Source document metadata is copied onto each chunk.
    """
    source = Path(pdf_path)
    output = Path(out_dir)
    group_list = list(groups) if groups else []
    reader = PdfReader(str(source))
    total_pages = len(reader.pages)
    ranges, warnings = propose_ranges(entries, total_pages, merge_same_page=merge_same_page)
    if not ranges:
        detail = "; ".join(warnings) if warnings else "no entries inside the PDF's page range"
        raise ValueError(f"No valid chapter ranges: {detail}")
    planned = _plan_paths(ranges, output, group_list, clean_names)
    if not overwrite:
        existing = [str(path) for _, path in planned if path.exists()]
        if existing:
            raise FileExistsError(
                "Output file(s) already exist (re-run with overwrite=True to replace): "
                + ", ".join(existing)
            )
    metadata = None
    if preserve_metadata and reader.metadata:
        metadata = {str(k): str(v) for k, v in reader.metadata.items() if v is not None}
    written: list[Path] = []
    for chapter, path in planned:
        writer = PdfWriter()
        if metadata:
            writer.add_metadata(metadata)
        for page_index in range(chapter.start, chapter.end + 1):
            writer.add_page(reader.pages[page_index])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            writer.write(fh)
        written.append(path)
    return written


def resolve_entries(
    pdf_path: str | Path,
    csv_path: str | Path | None = None,
    headings_path: str | Path | None = None,
    toc_text: bool = False,
    hint_page: int = 6,
    offset: int = 0,
    fuzzy_headings: bool = False,
) -> tuple[list[Entry], str, list[str]]:
    """Resolve chapter entries from CSV, headings, or the PDF itself.

    Priority: explicit ``--csv`` first, then ``--headings``, then
    bookmarks, then (only with ``toc_text``) the printed TOC text.
    Returns ``(entries, source, warnings)`` where source is one of
    ``csv``, ``headings``, ``outlines``, ``text-toc``, or ``none``.
    """
    if csv_path is not None:
        entries, warnings = load_entries_from_csv(csv_path)
        return entries, "csv", warnings
    if headings_path is not None:
        headings: list[str] = []
        with Path(headings_path).open(encoding="utf-8") as fh:
            headings = [line.strip() for line in fh if line.strip()]
        located = locate_headings(pdf_path, headings, fuzzy=fuzzy_headings)
        entries: list[Entry] = []
        warnings = []
        for title, page in located:
            if page is None:
                warnings.append(f"Heading not found: {title!r}")
            else:
                entries.append(Entry(title=title, page=page))
        return entries, "headings", warnings
    entries, warnings = extract_outline_entries(pdf_path)
    if entries:
        return entries, "outlines", warnings
    if toc_text:
        entries, text_warnings = extract_text_toc_entries(
            pdf_path, hint_page=hint_page, offset=offset
        )
        return entries, "text-toc", warnings + text_warnings
    return [], "none", warnings
