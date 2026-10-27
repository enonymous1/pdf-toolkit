import pdfplumber


def extract_tables(path: str):
    tables = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            tables.extend(p.extract_tables())
    return tables


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python table_extract.py <pdf-path>")
    else:
        print(extract_tables(sys.argv[1]))
