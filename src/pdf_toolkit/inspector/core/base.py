from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional


class PDFAdapter(ABC):
    """Abstract base class for PDF library adapters."""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return standardized metadata dictionary."""
        pass

    @abstractmethod
    def get_page_count(self) -> int:
        """Return total number of pages."""
        pass

    @abstractmethod
    def extract_text(self, page_range: Optional[str] = None) -> str:
        """Extract text from specified pages or all pages."""
        pass

    @abstractmethod
    def get_toc(self, use_ocr: bool = False, hint_page: int = 6) -> List[Dict[str, Any]]:
        """Return Table of Contents entries."""
        pass
        pass

    @abstractmethod
    def close(self):
        """Clean up resources."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
