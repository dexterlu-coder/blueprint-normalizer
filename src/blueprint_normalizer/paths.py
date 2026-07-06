"""Path discovery helpers for development and future packaged runs."""

from __future__ import annotations

from pathlib import Path
import sys


APP_CONFIG_FILENAME = "blueprint-normalizer.toml"
EXAMPLE_CONFIG_RELATIVE = Path("etc") / "blueprint-normalizer.example.toml"


def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    if is_frozen_app():
        return Path(sys.executable).resolve().parent
    return project_root()


def project_root(start: str | Path | None = None) -> Path:
    if start is None:
        start_path = Path(__file__).resolve()
    else:
        start_path = Path(start).resolve()

    current = start_path if start_path.is_dir() else start_path.parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "AGENTS.md").exists():
            return candidate
        if (candidate / ".git").exists() and (candidate / "AGENTS.md").exists():
            return candidate
    return Path.cwd().resolve()


def example_config_path() -> Path:
    return project_root() / EXAMPLE_CONFIG_RELATIVE


def config_candidates(explicit: str | Path | None = None) -> list[Path]:
    if explicit is not None:
        return [Path(explicit).expanduser().resolve()]

    candidates = [
        app_dir() / APP_CONFIG_FILENAME,
        project_root() / APP_CONFIG_FILENAME,
    ]

    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(resolved)
    return deduped
