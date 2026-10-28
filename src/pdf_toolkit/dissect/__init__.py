"""Form dissection: find templated form pages in PDFs and rebuild them as fillable forms.

Folded in from ss-documentDissection (0.4.0): keyword/SSIM template
detection, OpenCV field detection, OCR field labelling, reconstruction
to interactive HTML / fillable PDF / DOCX, and a confined Flask preview
server. Image, OCR, fillable-PDF, DOCX, and server features need
``pdf-toolkit[dissect]``; the keyword path needs only the core
dependencies. Importing this package never requires the extra — the
heavy imports are lazy, and the functions that need them raise a
readable error naming the extra.
"""

from .detect import DetectionError, find_template_pages, image_template_match, keyword_match
from .extract import ExtractionError, extract_pages_to_bytes, page_texts, split_pdf_to_pages
from .fieldmap import (
    FieldmapError,
    find_fieldmaps,
    load_fieldmap,
    page_number_from_name,
    save_fieldmap,
)
from .fields import detect_field_contours, render_page_to_image, render_pdf_pages
from .fill import FillError, fill_pdf_fields
from .models import DetectionResult, FieldBox, PageData
from .ocr import OCRError, assign_labels_to_fields
from .reconstruct import (
    ReconstructionError,
    create_fillable_pdf_from_image,
    create_html_overlay,
    export_html_to_file,
    reconstruct_pdf_pages,
)
from .server import create_app, run_server
from .to_docx import DocxError, export_document_to_docx, fill_docx_template, page_to_docx

__all__ = [
    "DetectionError",
    "DetectionResult",
    "DocxError",
    "ExtractionError",
    "FieldBox",
    "FieldmapError",
    "FillError",
    "OCRError",
    "PageData",
    "ReconstructionError",
    "assign_labels_to_fields",
    "create_app",
    "create_fillable_pdf_from_image",
    "create_html_overlay",
    "detect_field_contours",
    "export_document_to_docx",
    "export_html_to_file",
    "extract_pages_to_bytes",
    "fill_docx_template",
    "fill_pdf_fields",
    "find_fieldmaps",
    "find_template_pages",
    "image_template_match",
    "keyword_match",
    "load_fieldmap",
    "page_number_from_name",
    "page_texts",
    "page_to_docx",
    "reconstruct_pdf_pages",
    "render_page_to_image",
    "render_pdf_pages",
    "run_server",
    "save_fieldmap",
    "split_pdf_to_pages",
]
