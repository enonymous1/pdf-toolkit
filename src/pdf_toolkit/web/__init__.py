"""Flask web frontend for pdf-toolkit (``pdf-toolkit web``).

This is the browser counterpart to the PyQt6 GUI, which is kept
alongside it: the GUI is a desktop app, this is a local web server.
It covers upload, inspection, and compression, plus a ``--demo``
mode that serves seeded fixture data so the frontend can be frozen
to static HTML for a GitHub Pages demo (see :func:`freeze_demo`).

The web app is a local tool with no authentication, exactly like
the dissect preview server: :func:`run_server` refuses a
non-loopback host unless ``allow_remote`` is set, and the guard
runs before Flask is imported.
"""

from __future__ import annotations

from .app import LOOPBACK_HOSTS, create_app, freeze_demo, run_server

__all__ = ["LOOPBACK_HOSTS", "create_app", "freeze_demo", "run_server"]
