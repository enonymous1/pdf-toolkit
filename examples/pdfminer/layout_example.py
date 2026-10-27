from io import StringIO

from pdfminer.high_level import extract_text_to_fp


def extract_with_layout(path: str) -> str:
    out = StringIO()
    with open(path, "rb") as fh:
        extract_text_to_fp(fh, out)
    return out.getvalue()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python layout_example.py <pdf-path>")
    else:
        print(extract_with_layout(sys.argv[1]))
