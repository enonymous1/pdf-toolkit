from datetime import datetime
from pathlib import Path


def unique_output_path(path: Path) -> Path:
    """Return a Path that won't overwrite an existing file.

    - If `path` does not exist, returns it unchanged.
    - If it exists, append `_YYYYMMDDTHHMMSS` (and a counter if needed).
    """
    path = Path(path)
    if not path.exists():
        return path

    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    new = path.with_name(f"{path.stem}_{ts}{path.suffix}")
    counter = 1
    while new.exists():
        new = path.with_name(f"{path.stem}_{ts}_{counter}{path.suffix}")
        counter += 1
    return new


# Metadata normalization --------------------------------------------------
CANONICAL_METADATA_KEYS = [
    "Title",
    "Author",
    "Subject",
    "Keywords",
    "Creator",
    "Producer",
    "CreationDate",
    "ModDate",
    "Trapped",
    "Format",
    "PDFVersion",
    "IsEncrypted",
    # additional recommended fields
    "PDFVersion",
    "IsEncrypted",
    "Permissions",
    "HasOutlines",
    "HasAttachments",
    "FormFieldsCount",
    "AnnotationsCount",
    "ImageCount",
    "TextLength",
    "Fonts",
    "PageSizes",
]


def _normalize_key(k: str) -> str:
    """Normalize metadata key names for matching (strip leading slash, lower)."""
    if not isinstance(k, str):
        try:
            k = k.decode("utf-8")
        except Exception:
            k = str(k)
    return k.lstrip("/").strip().lower()


def extract_xmp_from_file(path: str) -> str | None:
    """Best-effort: scan file bytes for XMP XML block and return as string."""
    try:
        b = Path(path).read_bytes()
    except Exception:
        return None
    start = b.find(b"<x:xmpmeta")
    if start == -1:
        start = b.find(b"<?xpacket begin")
    if start == -1:
        return None
    end = b.find(b"</x:xmpmeta>")
    if end == -1:
        # try end of xpacket
        end = b.find(b"<?xpacket end")
        if end == -1:
            end = len(b)
        else:
            end += len(b"<?xpacket end")
    else:
        end += len(b"</x:xmpmeta>")
    try:
        return b[start:end].decode("utf-8", errors="ignore")
    except Exception:
        return None


# Page-range utilities ----------------------------------------------------
def parse_page_range(
    total_pages: int, *, start: int | None = None, end: int | None = None, count: int | None = None
) -> tuple[int, int]:
    """Parse and validate page-range inputs.

    - Parameters are 1-indexed and inclusive.
    - Returns a tuple (start_idx0, end_idx0) where both are 0-indexed and inclusive.
    - Raises ValueError on invalid ranges.

    Usage examples:
    - parse_page_range(10, start=1, end=3) -> (0, 2)
    - parse_page_range(10, start=5, count=2) -> (4, 5)
    - parse_page_range(10, start=3) -> (2, 9)  # to end
    """
    if total_pages <= 0:
        raise ValueError("total_pages must be > 0")

    if start is None and end is None and count is None:
        # default: full document
        return 0, total_pages - 1

    if start is None:
        raise ValueError("start must be provided (1-indexed)")

    if start < 1 or start > total_pages:
        raise ValueError(f"start ({start}) out of range [1..{total_pages}]")

    if count is not None:
        if count < 1:
            raise ValueError("count must be >= 1")
        end_calc = start + count - 1
    elif end is not None:
        end_calc = end
    else:
        end_calc = total_pages

    if end_calc < start:
        raise ValueError("end must be >= start")
    if end_calc > total_pages:
        raise ValueError(f"end ({end_calc}) out of range [1..{total_pages}]")

    # convert to 0-index inclusive
    return start - 1, end_calc - 1


def normalize_metadata(raw: dict) -> dict:
    """Return a dict containing all canonical keys (value or None) plus `raw`.

    - Attempts to find common variants (/Title, Title, title) in `raw`.
    - Preserves the original `raw` as `raw_metadata`.
    """
    normalized = {k: None for k in CANONICAL_METADATA_KEYS}

    if not raw:
        return {"metadata": normalized, "raw_metadata": raw or {}}

    # build lookup: normalized_key -> original_value
    lookup = {}
    for k, v in raw.items():
        nk = _normalize_key(k)
        lookup[nk] = v

    # helper to pick from lookup with several name variants
    def pick(*variants):
        for v in variants:
            if v is None:
                continue
            if isinstance(v, str):
                nk = _normalize_key(v)
                if nk in lookup:
                    return lookup[nk]
        return None

    # try common mappings
    mapping = {
        "Title": ["title"],
        "Author": ["author"],
        "Subject": ["subject"],
        "Keywords": ["keywords", "keyword"],
        "Creator": ["creator"],
        "Producer": ["producer"],
        "CreationDate": ["creationdate", "created", "creation_date"],
        "ModDate": ["moddate", "modified", "mod_date"],
        "Trapped": ["trapped"],
        "Format": ["format"],
        "PDFVersion": ["pdfversion", "pdf_version", "version"],
        "IsEncrypted": ["encrypt", "isencrypted", "is_encrypted"],
        "Permissions": ["permissions", "perms"],
        "XMP": ["xmp", "xmpmetadata"],
        "ObjectCount": ["objectcount", "object_count", "objects"],
    }

    for canon, variants in mapping.items():
        val = pick(*variants)
        # decode bytes if present
        if isinstance(val, bytes):
            try:
                val = val.decode("utf-8", errors="ignore")
            except Exception:
                val = str(val)
        normalized[canon] = val

    return {"metadata": normalized, "raw_metadata": raw}


def metadata_to_markdown(info: dict) -> str:
    """Render a human-friendly markdown summary for a normalized metadata dict.

    Expects the structure returned by `read_metadata` in examples/*.metadata modules.
    """
    lines = []
    md = info
    md_meta = md.get("metadata") or {}
    details = md.get("details") or {}

    lines.append(f"# PDF metadata — {md_meta.get('Title') or 'Untitled'}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Pages: **{md.get('n_pages')}**")
    lines.append(f"- Encrypted: **{bool(md_meta.get('IsEncrypted'))}**")
    pub = md_meta.get("Producer") or md_meta.get("Creator") or ""
    if pub:
        lines.append(f"- Producer / Creator: `{pub}`")
    if md_meta.get("Author"):
        lines.append(f"- Author: `{md_meta.get('Author')}`")
    if md_meta.get("CreationDate"):
        lines.append(f"- Created: `{md_meta.get('CreationDate')}`")

    lines.append("")
    lines.append("## Canonical metadata")
    lines.append("")
    for k, v in md_meta.items():
        lines.append(f"- **{k}**: `{v}`")

    # include XMP (raw XML) when available
    xmp = md_meta.get("XMP") or (md.get("raw_metadata") or {}).get("XMP")
    if xmp:
        lines.append("")
        lines.append("## XMP metadata (raw)")
        lines.append("")
        # show a trimmed snippet and full raw in a code block
        s = str(xmp)
        snippet = s[:1000] + ("..." if len(s) > 1000 else "")
        lines.append("<details><summary>Show XMP snippet</summary>")
        lines.append("")
        lines.append("```xml")
        lines.append(snippet)
        lines.append("```")
        lines.append("</details>")

    lines.append("")
    lines.append("## Details")
    lines.append("")
    if details:
        lines.append(f"- Text length: `{details.get('text_length')}` characters")
        lines.append(f"- Images: `{details.get('image_count')}`")
        lines.append(f"- Fonts: `{', '.join(details.get('fonts') or [])}`")
        lines.append(f"- Annotations: `{details.get('annotations_count')}`")
        lines.append(f"- Form fields: `{details.get('form_fields_count')}`")
        lines.append("")
        lines.append("### Page sizes")
        lines.append("")
        for i, p in enumerate(details.get("page_sizes") or []):
            lines.append(
                f"- Page {i + 1}: {p.get('width')} x {p.get('height')} px, text_len={p.get('text_length')}, images={p.get('image_count')}"
            )

    lines.append("")
    lines.append("> raw metadata included under `raw_metadata` in the JSON output")
    return "\n".join(lines)
