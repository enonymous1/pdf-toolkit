"""Small file helpers for the compressor (from ss-pdf-small)."""

from pathlib import Path


def find_pdfs(path: Path) -> list[Path]:
    """Return PDFs for a file path, or for a directory (non-recursive).

    Already-compressed ``*_compressed.pdf`` files are excluded from a
    directory listing so a second run does not re-compress its own output.
    """
    path = Path(path)
    if path.is_file():
        return [path] if path.suffix.lower() == ".pdf" else []
    if path.is_dir():
        return [f for f in path.glob("*.pdf") if "_compressed.pdf" not in f.name]
    return []


def get_file_size(file_path: Path) -> int:
    """Return a file's size in bytes."""
    return Path(file_path).stat().st_size


def format_size(size_bytes: int) -> str:
    """Format bytes as ``B`` / ``KB`` / ``MB`` (two decimals above bytes)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"
