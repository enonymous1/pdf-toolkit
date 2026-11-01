"""Allow ``python -m pdf_toolkit.cli`` (the console script calls main() directly)."""

import sys

from . import main

sys.exit(main())
