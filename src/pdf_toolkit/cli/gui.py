"""GUI launcher (``pdf-toolkit gui``)."""

from __future__ import annotations


def run_gui() -> int:
    """Launch the GUI, with a readable error if PyQt6 is missing."""
    try:
        from ..gui.main_gui import main as gui_main
    except ImportError as exc:
        print(
            "The GUI needs PyQt6, which is not installed.\n"
            "Install it with: pip install 'pdf-toolkit[gui]'\n"
            f"(import error: {exc})"
        )
        return 1
    gui_main()
    return 0
