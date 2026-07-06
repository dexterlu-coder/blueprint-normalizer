"""Input discovery and path-safety helpers for the PDF rotation MVP."""

from __future__ import annotations

from pathlib import Path


def collect_input_pdfs(input_dir: Path) -> list[Path]:
    """Collect one-level PDF file paths without reading PDF contents."""

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: {input_dir}")

    pdfs = sorted(path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf")
    if not pdfs:
        raise FileNotFoundError(f"No PDF files found in input directory: {input_dir}")
    return pdfs


def ensure_path_under_root(path: Path, allowed_root: Path, *, reject_root: bool = True) -> Path:
    """Resolve a path and ensure it stays inside an allowed root."""

    resolved = path.resolve()
    allowed = allowed_root.resolve()
    if reject_root and resolved == allowed:
        raise ValueError(f"Refusing to use allowed root itself: {resolved}")
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise ValueError(f"Refusing to use path outside allowed root: {resolved}") from exc
    return resolved


def ensure_child_dir(path: Path, allowed_root: Path) -> Path:
    """Create a controlled child directory without deleting existing contents."""

    resolved = ensure_path_under_root(path, allowed_root, reject_root=True)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved
