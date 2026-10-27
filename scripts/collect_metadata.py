import csv
import json
from pathlib import Path


def find_metadata_files(root: Path) -> list[Path]:
    files = []
    for lib in (root / "examples").iterdir():
        out = lib / "outputs"
        if out.exists() and out.is_dir():
            files.extend(list(out.glob("*_metadata*.json")))
    return files


def collect(root: Path) -> dict:
    files = find_metadata_files(root)
    collected = {}
    for f in files:
        lib = f.parts[-3]
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        collected.setdefault(lib, []).append({"file": str(f), "data": data})
    return collected


def write_reports(collected: dict, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "combined_metadata.json"
    csv_path = out_dir / "combined_metadata.csv"

    json_path.write_text(json.dumps(collected, indent=2), encoding="utf-8")

    # Flatten for CSV
    rows = []
    for lib, entries in collected.items():
        for e in entries:
            d = e["data"]
            meta = d.get("metadata") or {}
            details = d.get("details") or {}
            rows.append(
                {
                    "library": lib,
                    "file": e["file"],
                    "n_pages": d.get("n_pages"),
                    "title": meta.get("Title"),
                    "author": meta.get("Author"),
                    "pdf_version": meta.get("PDFVersion"),
                    "is_encrypted": meta.get("IsEncrypted"),
                    "text_length": details.get("text_length"),
                    "image_count": details.get("image_count"),
                    "fonts": ",".join(details.get("fonts") or []),
                    "form_fields_count": details.get("form_fields_count"),
                    "annotations_count": details.get("annotations_count"),
                    "has_outlines": details.get("has_outlines"),
                    "has_attachments": details.get("has_attachments"),
                }
            )

    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    return json_path, csv_path


if __name__ == "__main__":
    root = Path(".")
    out_dir = Path("examples") / "outputs" / "aggregated"
    collected = collect(root)
    json_path, csv_path = write_reports(collected, out_dir)
    print("Wrote:", json_path, csv_path)
