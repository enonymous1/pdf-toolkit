import fitz


def extract_text(path: str) -> str:
    doc = fitz.open(path)
    txt = "\n".join(p.get_text() for p in doc)
    doc.close()
    return txt


if __name__ == "__main__":
    import sys
    from pathlib import Path

    flags = [a for a in sys.argv[1:] if a.startswith("-")]
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    metadata_only = ("--metadata-only" in flags) or ("-m" in flags)

    if len(args) < 1:
        print("Usage: python extract_text.py [--metadata-only|-m] <pdf-path> [out-file]")
    else:
        pdf = args[0]
        if metadata_only:
            import sys
            from pathlib import Path

            sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
            import json

            from examples.pymupdf.metadata import read_metadata

            meta = read_metadata(pdf)
            out = (
                Path(args[1])
                if len(args) > 1
                else Path(__file__).resolve().parent
                / "outputs"
                / (Path(pdf).stem + "_metadata.json")
            )
            out.parent.mkdir(parents=True, exist_ok=True)
            try:
                from pdf_toolkit.inspector import metadata_to_markdown, unique_output_path
            except Exception:
                import sys

                sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
                from pdf_toolkit.inspector import metadata_to_markdown, unique_output_path
            out = unique_output_path(out)
            out.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            md_out = out.with_name(out.stem + "_metadata.md")
            md_out = unique_output_path(md_out)
            md_out.write_text(metadata_to_markdown(meta), encoding="utf-8")
            print(f"Wrote metadata to: {out} and summary to: {md_out}")
            sys.exit(0)

        print(extract_text(pdf))
