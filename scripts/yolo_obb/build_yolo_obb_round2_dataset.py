from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_ARCHIVE_DIR = ROOT / "local_data" / "review_inbox" / "archive" / "round2_overlay_review_20260626_approved"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "yolo_obb_dataset_round2"

TEST_SOURCES = {"sample_001", "sample_010", "sample_042"}
VAL_SOURCES = {"sample_009", "sample_020", "sample_034", "sample_040"}


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def read_manifest(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def split_for(source_sample: str) -> str:
    if source_sample in TEST_SOURCES:
        return "test"
    if source_sample in VAL_SOURCES:
        return "val"
    return "train"


def copy_one(record: dict, archive_dir: Path, output_dir: Path) -> dict:
    sample = record["sample"]
    split = split_for(record["source_sample"])
    image_src = archive_dir / "to_label" / f"{sample}.png"
    label_src = archive_dir / "labels" / f"{sample}.txt"

    if not image_src.exists():
        raise FileNotFoundError(f"Missing image: {image_src}")
    if not label_src.exists():
        raise FileNotFoundError(f"Missing label: {label_src}")

    image_dst = output_dir / "images" / split / image_src.name
    label_dst = output_dir / "labels" / split / label_src.name
    image_dst.parent.mkdir(parents=True, exist_ok=True)
    label_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(image_src, image_dst)
    shutil.copy2(label_src, label_dst)

    return {
        "dataset": record["dataset"],
        "sample": sample,
        "source_sample": record["source_sample"],
        "split": split,
        "image": str(image_dst.relative_to(output_dir)),
        "label": str(label_dst.relative_to(output_dir)),
        "title_block_position": record["title_block_position"],
        "precise_title_block_position": record.get("precise_title_block_position", ""),
        "rotation_degrees": int(record["rotation_degrees"]),
        "reason": record.get("reason", ""),
    }


def write_data_yaml(output_dir: Path) -> None:
    yaml_text = "\n".join(
        [
            f"path: {output_dir.as_posix()}",
            "train: images/train",
            "val: images/val",
            "test: images/test",
            "names:",
            "  0: title_block",
            "",
        ]
    )
    (output_dir / "data.yaml").write_text(yaml_text, encoding="utf-8")


def count_files(path: Path, pattern: str) -> int:
    return len(list(path.glob(pattern)))


def summarize(records: list[dict], output_dir: Path, archive_dir: Path) -> dict:
    by_split: dict[str, int] = {}
    by_dataset: dict[str, int] = {}
    by_position: dict[str, int] = {}
    source_splits: dict[str, set[str]] = {}

    for record in records:
        by_split[record["split"]] = by_split.get(record["split"], 0) + 1
        by_dataset[record["dataset"]] = by_dataset.get(record["dataset"], 0) + 1
        by_position[record["title_block_position"]] = by_position.get(record["title_block_position"], 0) + 1
        source_splits.setdefault(record["source_sample"], set()).add(record["split"])

    leakage = {
        source: sorted(splits)
        for source, splits in source_splits.items()
        if len(splits) > 1
    }

    return {
        "dataset_dir": str(output_dir),
        "source_archive_dir": str(archive_dir),
        "strategy": "round2_human_verified_grouped_by_source_sample",
        "total_records": len(records),
        "by_split": by_split,
        "by_dataset": by_dataset,
        "by_title_block_position": by_position,
        "source_split_leakage_count": len(leakage),
        "source_split_leakage": leakage,
        "train_images": count_files(output_dir / "images" / "train", "*.png"),
        "train_labels": count_files(output_dir / "labels" / "train", "*.txt"),
        "val_images": count_files(output_dir / "images" / "val", "*.png"),
        "val_labels": count_files(output_dir / "labels" / "val", "*.txt"),
        "test_images": count_files(output_dir / "images" / "test", "*.png"),
        "test_labels": count_files(output_dir / "labels" / "test", "*.txt"),
        "test_sources": sorted(TEST_SOURCES),
        "val_sources": sorted(VAL_SOURCES),
        "classes": {"0": "title_block"},
        "records": records,
    }


def build_dataset(archive_dir: Path, output_dir: Path, clean: bool) -> dict:
    archive_dir = resolve_path(archive_dir)
    output_dir = resolve_path(output_dir)
    manifest_path = archive_dir / "round2_manifest.csv"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest: {manifest_path}")

    if clean:
        clean_dir(output_dir)
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    records = [
        copy_one(record, archive_dir, output_dir)
        for record in read_manifest(manifest_path)
    ]
    write_data_yaml(output_dir)

    summary = summarize(records, output_dir, archive_dir)
    (output_dir / "dataset_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build round-2 human-verified Ultralytics YOLO/OBB dataset.")
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--clean", action="store_true", default=True)
    args = parser.parse_args()

    summary = build_dataset(args.archive_dir, args.output_dir, args.clean)
    printable = {key: value for key, value in summary.items() if key != "records"}
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 1 if summary["source_split_leakage_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

