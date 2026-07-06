from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PNG_DIR = ROOT / "local_data" / "experiment_samples" / "all" / "png"
GROUND_TRUTH_PATH = ROOT / "local_data" / "ground_truth" / "rotation_ground_truth.json"
OUTPUT_PNG_DIR = ROOT / "local_data" / "experiment_samples" / "augmented_90_unclear" / "png"
OUTPUT_GT_JSON = ROOT / "local_data" / "ground_truth" / "rotation_ground_truth_augmented_90_unclear.json"
OUTPUT_GT_CSV = ROOT / "local_data" / "ground_truth" / "rotation_ground_truth_augmented_90_unclear.csv"
OUTPUT_METRICS_CSV = ROOT / "local_data" / "ground_truth" / "unclear_source_quality_metrics.csv"

TARGET_ROTATION = 90
TARGET_SIDE = "left"
TARGET_PRECISE_POSITION = "左侧"
FORCED_SAMPLES = {"sample_001", "sample_042"}


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
        raise FileNotFoundError(f"No source PNG found for {sample}")
    if len(matches) > 1:
        raise ValueError(f"Multiple source PNG files found for {sample}: {matches}")
    return matches[0]


def load_ground_truth() -> list[dict]:
    return json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))


def quality_metrics(image: np.ndarray) -> dict[str, float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (0, 0), fx=0.35, fy=0.35, interpolation=cv2.INTER_AREA)
    sharpness = float(cv2.Laplacian(resized, cv2.CV_64F).var())
    contrast = float(resized.std())
    edges = cv2.Canny(resized, 60, 160)
    edge_density = float(np.count_nonzero(edges) / edges.size)
    dark_ratio = float(np.count_nonzero(resized < 180) / resized.size)
    return {
        "sharpness": sharpness,
        "contrast": contrast,
        "edge_density": edge_density,
        "dark_ratio": dark_ratio,
    }


def rank_sources(records: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for record in records:
        image_path = source_image_for(record["sample"])
        metrics = quality_metrics(read_image(image_path))
        # Lower values mean weaker visual evidence. Use a conservative composite,
        # then force in known hard samples even if their global metric is imperfect.
        unclear_score = (
            metrics["sharpness"] * 0.55
            + metrics["contrast"] * 10.0
            + metrics["edge_density"] * 1500.0
            + metrics["dark_ratio"] * 200.0
        )
        rows.append(
            {
                **record,
                "source_image_path": image_path,
                "sharpness": round(metrics["sharpness"], 6),
                "contrast": round(metrics["contrast"], 6),
                "edge_density": round(metrics["edge_density"], 6),
                "dark_ratio": round(metrics["dark_ratio"], 6),
                "unclear_score": round(float(unclear_score), 6),
            }
        )
    return sorted(rows, key=lambda row: (row["unclear_score"], row["sample"]))


def choose_sources(records: list[dict], count: int) -> list[dict]:
    ranked = rank_sources(records)
    selected: list[dict] = []
    selected_samples: set[str] = set()

    for sample in sorted(FORCED_SAMPLES):
        match = next((row for row in ranked if row["sample"] == sample), None)
        if match:
            selected.append(match)
            selected_samples.add(sample)

    for row in ranked:
        if len(selected) >= count:
            break
        if row["sample"] in selected_samples:
            continue
        selected.append(row)
        selected_samples.add(row["sample"])

    return selected


def build_augmented_samples(count: int) -> tuple[list[dict], list[dict]]:
    OUTPUT_PNG_DIR.mkdir(parents=True, exist_ok=True)
    ranked = rank_sources(load_ground_truth())
    selected = choose_sources(load_ground_truth(), count)
    selected_samples = {record["sample"] for record in selected}

    augmented_records: list[dict] = []
    for index, source in enumerate(selected, start=1):
        source_rotation = int(source["rotation_degrees"])
        applied_rotation = (TARGET_ROTATION - source_rotation) % 360
        output_sample = f"unclear90_{index:03d}_from_{source['sample']}"
        output_path = OUTPUT_PNG_DIR / f"{output_sample}.png"

        image = read_image(source["source_image_path"])
        write_image(output_path, rotate_clockwise(image, applied_rotation))

        augmented_records.append(
            {
                "sample": output_sample,
                "source_sample": source["sample"],
                "source_rotation_degrees": source_rotation,
                "applied_clockwise_rotation_degrees": applied_rotation,
                "title_block_position": TARGET_SIDE,
                "precise_title_block_position": TARGET_PRECISE_POSITION,
                "rotation_degrees": TARGET_ROTATION,
                "source_level": "synthetic_augmented_90_unclear",
                "source_basis": "rotated_from_low_quality_manual_review_full",
                "verified_by_human": True,
                "quality_rank_source": "forced" if source["sample"] in FORCED_SAMPLES else "metric_ranked",
                "unclear_score": source["unclear_score"],
                "sharpness": source["sharpness"],
                "contrast": source["contrast"],
                "edge_density": source["edge_density"],
                "dark_ratio": source["dark_ratio"],
                "note": "Synthetic left-side title-block sample generated from visually unclear or hard source.",
            }
        )

    metric_rows = []
    for rank, row in enumerate(ranked, start=1):
        metric_rows.append(
            {
                "rank": rank,
                "selected": row["sample"] in selected_samples,
                "sample": row["sample"],
                "title_block_position": row["title_block_position"],
                "precise_title_block_position": row.get("precise_title_block_position", ""),
                "rotation_degrees": row["rotation_degrees"],
                "unclear_score": row["unclear_score"],
                "sharpness": row["sharpness"],
                "contrast": row["contrast"],
                "edge_density": row["edge_density"],
                "dark_ratio": row["dark_ratio"],
            }
        )

    return augmented_records, metric_rows


def write_csv(path: Path, records: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create unclear-source clockwise-90 augmented samples.")
    parser.add_argument("--count", type=int, default=12)
    args = parser.parse_args()

    augmented, metrics = build_augmented_samples(args.count)
    OUTPUT_GT_JSON.write_text(json.dumps(augmented, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(OUTPUT_GT_CSV, augmented)
    write_csv(OUTPUT_METRICS_CSV, metrics)

    print(
        json.dumps(
            {
                "augmented_count": len(augmented),
                "png_dir": str(OUTPUT_PNG_DIR),
                "ground_truth_json": str(OUTPUT_GT_JSON),
                "metrics_csv": str(OUTPUT_METRICS_CSV),
                "selected_sources": [record["source_sample"] for record in augmented],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
