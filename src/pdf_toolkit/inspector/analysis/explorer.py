import argparse
from pathlib import Path

import fitz
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

console = Console()


class PDFExplorer:
    def __init__(self, path: str):
        self.path = path
        self.doc = fitz.open(path)

    def show_summary(self):
        table = Table(
            title=f"File Summary: {Path(self.path).name}",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Property", style="dim")
        table.add_column("Value")

        table.add_row("Pages", str(self.doc.page_count))
        table.add_row("Format", self.doc.metadata.get("format"))
        table.add_row("Encryption", self.doc.metadata.get("encryption", "None"))
        table.add_row("Producer", self.doc.metadata.get("producer"))

        # Check first page to guess if scanned
        p0 = self.doc[0]
        text_len = len(p0.get_text())
        img_count = len(p0.get_images())
        table.add_row("P1 Content", f"{text_len} chars, {img_count} images")

        console.print(table)

    def explore_structure(self, page_num: int, check_tables: bool = False):
        page = self.doc[page_num]
        tree = Tree(f"[bold cyan]Page {page_num + 1} Structure[/bold cyan]")

        # Images
        img_node = tree.add("Images", style="green")
        for i, img in enumerate(page.get_images()):
            img_node.add(f"Image {i}: {img[2]}x{img[3]} (Ref: {img[0]})")

        # Table Detection (optional)
        if check_tables:
            table_node = tree.add("Detected Tables (Camelot)", style="magenta")
            try:
                import camelot

                tables = camelot.read_pdf(self.path, pages=str(page_num + 1), flavor="stream")
                if len(tables) > 0:
                    for i, t in enumerate(tables):
                        table_node.add(
                            f"Table {i + 1}: {t.shape[0]} rows x {t.shape[1]} cols (Accuracy: {t.accuracy}%)"
                        )
                else:
                    table_node.add("[dim]No tables found via stream mode[/dim]")
            except Exception as e:
                table_node.add(f"[red]Error:[/red] {e}")

        # Text Blocks
        text_node = tree.add("Text Blocks", style="yellow")
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if b["type"] == 0:  # text
                content = "".join([s["text"] for line in b["lines"] for s in line["spans"]])
                text_node.add(
                    f"Block {b['number']}: '{content[:30]}...' (Fonts: {set([s['font'] for line in b['lines'] for s in line['spans']])})"
                )
            else:
                text_node.add(f"Block {b['number']}: [Image/Vector Block]")

        # Fonts
        font_node = tree.add("Fonts", style="blue")
        for f in page.get_fonts():
            font_node.add(f"{f[3]} ({f[1]})")

        console.print(tree)

    def show_metadata_xray(self):
        xmp = self.doc.get_xml_metadata()
        if xmp:
            console.print(
                Panel(
                    Syntax(xmp, "xml", theme="monokai", line_numbers=True),
                    title="XMP Metadata (Raw Strings)",
                )
            )
        else:
            console.print("[yellow]No XMP Metadata found.[/yellow]")


def main():
    parser = argparse.ArgumentParser(description="PDF X-Ray Explorer")
    parser.add_argument("path", help="Path to PDF")
    parser.add_argument("--page", type=int, default=1, help="Page to explore (1-indexed)")
    parser.add_argument("--xray", action="store_true", help="Show deep XMP metadata")
    parser.add_argument("--tables", action="store_true", help="Check for tables on this page")

    args = parser.parse_args()

    explorer = PDFExplorer(args.path)
    explorer.show_summary()

    if args.xray:
        explorer.show_metadata_xray()

    explorer.explore_structure(args.page - 1, check_tables=args.tables)


if __name__ == "__main__":
    main()
