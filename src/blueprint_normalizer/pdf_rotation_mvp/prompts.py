"""Prompt resource loader for the PDF rotation MVP."""

from __future__ import annotations

from importlib import resources


PROMPT_FILENAMES = {
    "title_block_only": "title_block_only.md",
    "drawing_number": "drawing_number.md",
}


def load_prompt(name: str) -> str:
    try:
        filename = PROMPT_FILENAMES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown prompt name: {name}") from exc
    return resources.files(__package__).joinpath("prompts", filename).read_text(encoding="utf-8")
