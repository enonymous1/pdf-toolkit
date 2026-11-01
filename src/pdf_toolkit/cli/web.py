"""Web subcommand (``pdf-toolkit web``)."""

from __future__ import annotations

import argparse
from pathlib import Path


def run_web(args: argparse.Namespace) -> int:
    """Serve the web frontend, or freeze the demo to static HTML.

    ``--freeze-dir`` implies demo mode: it renders the seeded demo
    routes and exits without starting a server.
    """
    from ..web import freeze_demo, run_server

    if args.freeze_dir:
        written = freeze_demo(args.freeze_dir)
        for rel in written:
            print(f"Wrote {Path(args.freeze_dir) / rel}")
        return 0
    try:
        run_server(
            upload_dir=args.upload_dir,
            host=args.host,
            port=args.port,
            allow_remote=args.allow_remote,
            demo=args.demo,
        )
    except ValueError as exc:
        # The loopback guard: a usage error, not a traceback.
        print(f"Error: {exc}")
        return 2
    return 0
