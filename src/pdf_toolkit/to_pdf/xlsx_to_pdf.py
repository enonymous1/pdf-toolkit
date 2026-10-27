"""Convert an Excel workbook to PDF via Microsoft Excel.

From ss-toPDF's ``xlsx_to_pdf.py``. This drives Excel through COM, so
it only runs on Windows with Excel installed. The page-setup rules are
kept as a pure function (``decide_page_setup``) so they can be tested
without Excel; the COM import is lazy and only happens on conversion.
"""

import os
from pathlib import Path

# Excel constants, kept from the original.
XL_PAPER_A4 = 9
XL_PORTRAIT = 1
XL_LANDSCAPE = 2
XL_TYPE_PDF = 0


def decide_page_setup(num_cols: int) -> dict:
    """Return page-setup settings for a sheet with ``num_cols`` columns.

    Wide sheets go landscape; very wide sheets fit to one page wide.
    Narrow sheets stay portrait at 100% zoom. Print gridlines and
    headings are always on (set by the caller, not returned here).
    """
    if num_cols > 10:
        orientation = XL_LANDSCAPE
        if num_cols > 15:
            return {
                "orientation": orientation,
                "paper_size": XL_PAPER_A4,
                "zoom": False,
                "fit_to_pages_wide": 1,
                "fit_to_pages_tall": False,
            }
        return {
            "orientation": orientation,
            "paper_size": XL_PAPER_A4,
            "zoom": 100,
            "fit_to_pages_wide": False,
            "fit_to_pages_tall": False,
        }
    return {
        "orientation": XL_PORTRAIT,
        "paper_size": XL_PAPER_A4,
        "zoom": 100,
        "fit_to_pages_wide": False,
        "fit_to_pages_tall": False,
    }


def convert_xlsx_to_pdf(input_path: str | Path, output_path: str | Path) -> Path:
    """Convert ``input_path`` (.xlsx) to ``output_path`` (.pdf) via Excel."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    try:
        import win32com.client
    except ImportError as exc:
        raise ImportError(
            "Converting .xlsx needs Windows with Microsoft Excel and pywin32. "
            "Install it with: pip install 'pdf-toolkit[office]'"
        ) from exc
    output_path.parent.mkdir(parents=True, exist_ok=True)
    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    wb = excel.Workbooks.Open(os.path.abspath(input_path))
    try:
        for ws in wb.Worksheets:
            num_cols = ws.UsedRange.Columns.Count
            setup = decide_page_setup(num_cols)
            ws.PageSetup.PaperSize = setup["paper_size"]
            ws.PageSetup.Orientation = setup["orientation"]
            ws.PageSetup.Zoom = setup["zoom"]
            ws.PageSetup.FitToPagesWide = setup["fit_to_pages_wide"]
            ws.PageSetup.FitToPagesTall = setup["fit_to_pages_tall"]
            ws.PageSetup.PrintGridlines = True
            ws.PageSetup.PrintHeadings = True
        wb.ExportAsFixedFormat(XL_TYPE_PDF, os.path.abspath(output_path))
    finally:
        wb.Close(False)
        excel.Quit()
    return output_path
