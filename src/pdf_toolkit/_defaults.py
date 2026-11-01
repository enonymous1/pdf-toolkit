"""Shared defaults that used to be scattered as bare literals.

Each value has a why-comment because the value itself is a judgement
call, and the next person to change it needs to know what it was tuned
for, not just what it is. These are defaults, not constants carved in
stone: every one of them is overridable at the call site or on the CLI.
"""

# Printed manuals usually put their contents page near page 6; the TOC
# text heuristic starts scanning there unless --hint says otherwise.
TOC_HINT_PAGE = 6

# Rendering / detection resolution. 150 DPI is the tradeoff the dissect
# field detector was tuned at: lower misses thin box borders, higher
# costs render time and memory without finding more fields.
DEFAULT_DPI = 150

# Ghostscript compatibility level for the compressor's pdfwrite path.
# 1.4 keeps the output readable by older viewers while still allowing
# the compression features the presets rely on.
GHOSTSCRIPT_COMPATIBILITY_LEVEL = "1.4"

# Seconds before a Ghostscript run is treated as hung rather than slow.
# A normal book compresses in well under a minute; 300 leaves room for
# large documents without letting a stuck `gs` hang the CLI forever.
GHOSTSCRIPT_TIMEOUT_SECONDS = 300
