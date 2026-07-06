from __future__ import annotations

import csv
import json
import random
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PNG_DIR = ROOT / "local_data" / "experiment_samples" / "all" / "png"
GROUND_TRUTH_PATH = ROOT / "local_data" / "ground_truth" / "rotation_ground_truth.json"
OUTPUT_PNG_DIR = ROOT / "local_data" / "experiment_samples" / "augmented_90" / "png"
OUTPUT_GT_JSON = ROOT / "local_data" / "ground_truth" / "rotation_ground_truth_augmented_90.json"
OUTPUT_GT_CSV = ROOT / "local_data" / "ground_truth" / "rotation_ground_truth_augmented_90.csv"

RANDOM_SEED = 20260625
TARGET_ROTATION = 90
TARGET_SIDE = "left"
TARGET_PRECISE_POSITION = "左侧"
TARGET_COUNTS = {
    "right": 10,
    "top": 9,
    "bottom": 1,
}


def read_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot read image: {path}")
    return image


def write_image(path: Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise ValueError(f"Cannot encode image: {path}")
    encoded.tofile(str(path))


def rotate_clockwise(image: np.ndarray, degrees: int) -> np.ndarray:
    normalized = degrees % 360
    if normalized == 0:
        return image.copy()
    if normalized == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    if normalized == 180:
        return cv2.rotate(image, cv2.ROTATE_180)
    if normalized == 270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    raise ValueError(f"Unsupported rotation: {degrees}")


def source_image_for(sample: str) -> Path:
    matches = sorted(SOURCE_PNG_DIR.glob(f"*{sample}.png"))
    if not matches:
        raise SystemExit(f"No source PNG found for {sample}")
    return matches[0]


def load_ground_truth() -> list[dict]:
    return json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))


def choose_sources(records: list[dict]) -> list[dict]:
    rng = random.Random(RANDOM_SEED)
    selected: list[dict] = []
    by_side: dict[str, list[dict]] = {}
    for record in records:
        by_side.setdefault(record["title_block_position"], []).append(record)

    for side, count in TARGET_COUNTS.items():
        available = sorted(by_side.get(side, []), key=lambda item: item["sample"])
        if len(available) < count:
            raise SystemExit(f"Need {count} records for {side}, only found {len(available)}")
        selected.extend(rng.sample(available, count))

    return sorted(selected, key=lambda item: item["sample"])


def build_augmented_samples() -> list[dict]:
    OUTPUT_PNG_DIR.mkdir(parents=True, exist_ok=True)
    selected = choose_sources(load_ground_truth())
    augmented_records: list[dict] = []

    for index, source in enumerate(selected, start=1):
        source_rotation = int(source["rotation_degrees"])
        applied_rotation = (TARGET_ROTATION - source_rotation) % 360
        source_path = source_image_for(source["sample"])
        augmented_sample = f"aug90_{index:03d}_from_{source['sample']}"
        output_path = OUTPUT_PNG_DIR / f"{augmented_sample}.png"

        image = read_image(source_path)
        write_image(output_path, rotate_clockwise(image, applied_rotation))

        augmented_records.append(
            {
                "sample": augmented_sample,
                "source_sample": source["sample"],
                "source_rotation_degrees": source_rotation,
                "applied_clockwise_rotation_degrees": applied_rotation,
                "title_block_position": TARGET_SIDE,
                "precise_title_block_position": TARGET_PRECISE_POSITION,
                "rotation_degrees": TARGET_ROTATION,
                "source_level": "synthetic_augmented_90",
                "source_basis": "rotated_from_manual_review_full",
                "verified_by_human": True,
                "note": "Synthetic left-side title-block sample generated from human-reviewed source.",
            }
        )

    return augmented_records


def write_ground_truth(records: list[dict]) -> None:
    OUTPUT_GT_JSON.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    with OUTPUT_GT_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
        fieldnames = list(records[0].keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    records = build_augmented_samples()
    write_ground_truth(records)
    print(f"Augmented samples: {len(records)}")
    print(f"PNG directory: {OUTPUT_PNG_DIR.relative_to(ROOT)}")
    print(f"Ground truth JSON: {OUTPUT_GT_JSON.relative_to(ROOT)}")
    print(f"Ground truth CSV: {OUTPUT_GT_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
