"""pdf-toolkit: inspect, compress, split, dissect, and convert PDFs from one package.

The version lives here and only here. ``pyproject.toml`` reads it via
``[tool.setuptools.dynamic]`` so the installed distribution and this
module can never drift apart again (0.5.0 in pyproject vs 0.4.0 here
was a real bug, caught by the 0.6.0 staff review).
"""

__version__ = "0.6.1"

__all__ = ["__version__"]
