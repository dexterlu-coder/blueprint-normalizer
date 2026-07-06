from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from PIL import Image

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_SOURCE_IMAGE = ROOT / "local_data" / "js2207_generalization_test" / "rendered_png" / "js2207_page_001.png"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "aliyun_vlm_position_probe"
RECORD_VERSION = "aliyun-vlm-position-probe-images-v0.1"


VARIANTS = [
    {
        "variant_id": "pos_top_right_from_js2207_page_001",
        "clockwise_rotation_applied": 0,
        "expected_title_block_position": "top_right",
        "expected_current_clockwise_degrees": 270,
        "expected_correction_clockwise_degrees": 90,
    },
    {
        "variant_id": "pos_bottom_right_from_js2207_page_001_cw090",
        "clockwise_rotation_applied": 90,
        "expected_title_block_position": "bottom_right",
        "expected_current_clockwise_degrees": 0,
        "expected_correction_clockwise_degrees": 0,
    },
    {
        "variant_id": "pos_bottom_left_from_js2207_page_001_cw180",
        "clockwise_rotation_applied": 180,
        "expected_title_block_position": "bottom_left",
        "expected_current_clockwise_degrees": 90,
        "expected_correction_clockwise_degrees": 270,
    },
    {
        "variant_id": "pos_top_left_from_js2207_page_001_cw270",
        "clockwise_rotation_applied": 270,
        "expected_title_block_position": "top_left",
        "expected_current_clockwise_degrees": 180,
        "expected_correction_clockwise_degrees": 180,
    },
]


def as_posix(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def rotate_clockwise(image: Image.Image, degrees: int) -> Image.Image:
    if degrees == 0:
        return image.copy()
    if degrees == 90:
        return image.transpose(Image.Transpose.ROTATE_270)
    if degrees == 180:
        return image.transpose(Image.Transpose.ROTATE_180)
    if degrees == 270:
        return image.transpose(Image.Transpose.ROTATE_90)
    raise ValueError(f"Unsupported rotation: {degrees}")


def build(args: argparse.Namespace) -> dict[str, Any]:
    source_image = resolve_path(args.source_image)
    if not source_image.exists():
        raise FileNotFoundError(f"Source image not found: {source_image}")
    output_dir = resolve_path(args.output_dir)
    image_dir = output_dir / "position_probe_images"
    image_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    with Image.open(source_image) as image:
        image = image.convert("RGB")
        source_width, source_height = image.size
        for variant in VARIANTS:
            rotated = rotate_clockwise(image, variant["clockwise_rotation_applied"])
            output_path = image_dir / f"{variant['variant_id']}.png"
            rotated.save(output_path)
            width, height = rotated.size
            records.append(
                {
                    "record_version": RECORD_VERSION,
                    "task_id": variant["variant_id"],
                    "source_image_path": as_posix(source_image),
                    "rendered_image_path": as_posix(output_path),
                    "page_number": len(records) + 1,
                    "clockwise_rotation_applied": variant["clockwise_rotation_applied"],
                    "expected_title_block_position": variant["expected_title_block_position"],
                    "expected_current_clockwise_degrees": variant["expected_current_clockwise_degrees"],
                    "expected_correction_clockwise_degrees": variant["expected_correction_clockwise_degrees"],
                    "source_width": source_width,
                    "source_height": source_height,
                    "width": width,
                    "height": height,
                }
            )

    manifest_json_path = output_dir / "position_probe_manifest.json"
    manifest_csv_path = output_dir / "position_probe_manifest.csv"
    summary_path = output_dir / "position_probe_summary.json"
    write_json(manifest_json_path, records)
    write_csv(
        manifest_csv_path,
        records,
        [
            "task_id",
            "page_number",
            "source_image_path",
            "rendered_image_path",
            "clockwise_rotation_applied",
            "expected_title_block_position",
            "expected_current_clockwise_degrees",
            "expected_correction_clockwise_degrees",
            "source_width",
            "source_height",
            "width",
            "height",
        ],
    )
    summary = {
        "record_version": RECORD_VERSION,
        "source_image_path": as_posix(source_image),
        "output_dir": as_posix(output_dir),
        "image_dir": as_posix(image_dir),
        "variant_count": len(records),
        "manifest_json": as_posix(manifest_json_path),
        "manifest_csv": as_posix(manifest_csv_path),
        "modified_pdf": False,
        "renamed_pdf": False,
    }
    write_json(summary_path, summary)
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build controlled Aliyun VLM title-block position probe images.")
    parser.add_argument("--source-image", type=Path, default=DEFAULT_SOURCE_IMAGE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    print(json.dumps(build(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
