"""Check a .docx file against a set of formatting rules.

From ss-toPDF's ``formatting.py`` and ``batch_formatting_check.py``,
with the fixes and cleanups the original needed:

- The rules are a parameter (``FormattingRules``), not module constants
  tied to one project, and there are no hardcoded input/output paths.
- The batch script's missing functions now exist: ``check_docx_formatting``,
  ``print_formatting_report``, and ``add_comments_to_docx``.
- The margin message no longer has mismatched quotes, and a caption or
  footnote size issue reports its own expected size, not the body size.
- Word COM (for actually adding comments) is a lazy import: the report
  works anywhere python-docx runs, and only annotation needs Windows
  with Word.

An ``Issue`` names a paragraph and a run range inside it, plus a
human-readable message. Margin issues point at the first run of the
first paragraph, since margins belong to a section, not a paragraph.
"""

import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FormattingRules:
    """Formatting a document is expected to follow."""

    font: str = "Calibri"
    body_size: float = 12.0
    caption_size: float = 10.0
    footnote_size: float = 10.0
    spacing: float = 1.0
    margin_inches: float = 1.0


@dataclass(frozen=True)
class Issue:
    """One formatting non-compliance in a document."""

    paragraph_index: int
    start_run: int | None
    end_run: int | None
    message: str


def _require_docx():
    try:
        from docx import Document
    except ImportError as exc:
        raise ImportError(
            "Checking .docx formatting needs python-docx. "
            "Install it with: pip install 'pdf-toolkit[office]'"
        ) from exc
    return Document


def _group_runs(runs, predicate):
    """Group consecutive run indexes where ``predicate(run)`` holds."""
    groups = []
    start = None
    last = None
    for r_idx, run in enumerate(runs):
        if predicate(run):
            if start is None:
                start = r_idx
            last = r_idx
        elif start is not None:
            groups.append((start, last))
            start = None
            last = None
    if start is not None:
        groups.append((start, last))
    return groups


def check_docx_formatting(
    docx_path: str | Path, rules: FormattingRules | None = None
) -> list[Issue]:
    """Return every formatting issue in ``docx_path`` under ``rules``."""
    Document = _require_docx()
    rules = rules or FormattingRules()
    docx_path = Path(docx_path)
    if not docx_path.is_file():
        raise FileNotFoundError(f"Input file not found: {docx_path}")
    doc = Document(str(docx_path))
    issues: list[Issue] = []

    for p_idx, para in enumerate(doc.paragraphs):
        style_name = para.style.name.lower() if para.style and para.style.name else ""
        is_caption = "caption" in style_name
        is_footnote = "footnote" in style_name

        spacing = para.paragraph_format.line_spacing
        if spacing is not None and spacing != rules.spacing and para.runs:
            issues.append(
                Issue(
                    p_idx,
                    0,
                    len(para.runs) - 1,
                    f"Spacing should be {rules.spacing}, but is {spacing:.2f}.",
                )
            )

        for start, end in _group_runs(
            para.runs, lambda run: run.font.name and run.font.name != rules.font
        ):
            issues.append(
                Issue(
                    p_idx,
                    start,
                    end,
                    f"Font should be '{rules.font}', but is '{para.runs[start].font.name}'.",
                )
            )

        def size_predicate(run, is_caption=is_caption, is_footnote=is_footnote):
            if not run.font.size:
                return False
            expected = rules.body_size
            if is_caption:
                expected = rules.caption_size
            elif is_footnote:
                expected = rules.footnote_size
            return run.font.size.pt != expected

        for start, end in _group_runs(para.runs, size_predicate):
            expected = rules.body_size
            if is_caption:
                expected = rules.caption_size
            elif is_footnote:
                expected = rules.footnote_size
            issues.append(
                Issue(
                    p_idx,
                    start,
                    end,
                    f"Font size should be {expected}pt, but is {para.runs[start].font.size.pt}pt.",
                )
            )

    for sec in doc.sections:
        margins = {
            "Top": sec.top_margin.inches,
            "Bottom": sec.bottom_margin.inches,
            "Left": sec.left_margin.inches,
            "Right": sec.right_margin.inches,
        }
        for name, measurement in margins.items():
            if abs(measurement - rules.margin_inches) >= 0.05:
                if doc.paragraphs and doc.paragraphs[0].runs:
                    issues.append(
                        Issue(
                            0,
                            0,
                            0,
                            f'{name} margin should be {rules.margin_inches}", '
                            f'but is {measurement:.2f}".',
                        )
                    )
    return issues


def print_formatting_report(
    docx_path: str | Path,
    rules: FormattingRules | None = None,
    file=None,
) -> list[Issue]:
    """Print a formatting report for ``docx_path``; return its issues."""
    out = file if file is not None else sys.stdout
    print(f"--- Starting analysis of '{Path(docx_path).name}' ---", file=out)
    issues = check_docx_formatting(docx_path, rules)
    print("\n--- Formatting Report ---", file=out)
    if not issues:
        print("Document is compliant with all formatting requirements.", file=out)
    else:
        print(f"Found {len(issues)} formatting issues:", file=out)
        for issue in issues:
            print(f"  - {issue.message}", file=out)
    return issues


def add_comments_with_word(
    docx_path: str | Path, output_path: str | Path, issues: list[Issue]
) -> Path:
    """Save a copy of ``docx_path`` with Word comments for ``issues``.

    This drives Microsoft Word through COM, so it only runs on Windows
    with Word installed. ``output_path`` may be the same as ``docx_path``.
    """
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise ImportError(
            "Adding Word comments needs Windows with Microsoft Word and pywin32. "
            "Install it with: pip install 'pdf-toolkit[office]'"
        ) from exc
    docx_path = Path(docx_path)
    output_path = Path(output_path)
    if not docx_path.is_file():
        raise FileNotFoundError(f"Input file not found: {docx_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pythoncom.CoInitialize()
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    doc = word.Documents.Open(str(docx_path))
    try:
        for issue in issues:
            try:
                para = doc.Paragraphs(issue.paragraph_index + 1)  # Word is 1-based
                if (
                    issue.start_run is not None
                    and issue.end_run is not None
                    and para.Range.Words.Count >= issue.end_run + 1
                ):
                    start = para.Range.Words(issue.start_run + 1).Start
                    end = para.Range.Words(issue.end_run + 1).End
                    rng = doc.Range(start, end)
                else:
                    rng = para.Range
                doc.Comments.Add(Range=rng, Text=issue.message)
            except Exception as exc:
                print(
                    f"Failed to add comment to paragraph {issue.paragraph_index + 1}, "
                    f"runs {issue.start_run}-{issue.end_run}: {exc}"
                )
        doc.SaveAs(str(output_path))
    finally:
        doc.Close(False)
        word.Quit()
        pythoncom.CoUninitialize()
    return output_path


def add_comments_to_docx(
    docx_path: str | Path, output_path: str | Path, issues: list[Issue]
) -> Path:
    """Save ``docx_path`` to ``output_path`` with comments for ``issues``.

    The copy is written with python-docx first, then Word COM adds the
    comments. Checking for COM availability first means a machine without
    Word fails before writing a copy that claims to be commented.
    """
    try:
        import win32com.client  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Adding Word comments needs Windows with Microsoft Word and pywin32. "
            "Install it with: pip install 'pdf-toolkit[office]'"
        ) from exc
    Document = _require_docx()
    docx_path = Path(docx_path)
    output_path = Path(output_path)
    if not docx_path.is_file():
        raise FileNotFoundError(f"Input file not found: {docx_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Document(str(docx_path)).save(str(output_path))
    return add_comments_with_word(output_path, output_path, issues)
