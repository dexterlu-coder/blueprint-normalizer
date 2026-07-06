"""Title-block crop helpers for the PDF rotation MVP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised only when Pillow is unavailable.
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

from blueprint_normalizer.pdf_rotation_mvp.workflow import as_posix


def crop_title_block_candidate(
    image_path: Path,
    crop_path: Path,
    root: Path | None = None,
) -> dict[str, Any]:
    if Image is None:
        raise RuntimeError("Pillow is required for title-block crop generation. Install pillow.")
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        crop_ratio = 0.35 if height > width else 0.30
        y0 = int(height * (1.0 - crop_ratio))
        crop = rgb.crop((0, y0, width, height))
        crop_path.parent.mkdir(parents=True, exist_ok=True)
        crop.save(crop_path)
    return {
        "crop_path": as_posix(crop_path, root),
        "crop_strategy": "bottom_full_width_after_rotation_correction",
        "crop_ratio": crop_ratio,
        "crop_box": [0, y0, width, height],
        "rendered_width": width,
        "rendered_height": height,
    }
