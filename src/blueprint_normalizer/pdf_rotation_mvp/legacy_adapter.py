"""Boundary notes for the legacy PDF rotation MVP script.

The legacy script is intentionally not imported here yet. Its current
``--dry-run`` mode still reads PDFs, calls Ghostscript, and writes outputs, so
the package-level dry-run must stay independent until the side effects are
parameterized and tested.
"""

from __future__ import annotations

from pathlib import Path


LEGACY_SCRIPT_RELATIVE_PATH = Path("tools") / "pdf_rotation_mvp" / "run_pdf_rotation_mvp.py"

