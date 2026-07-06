from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from scripts.common.obb_utils import ROOT, label_path_for, load_manifest, resolve_path


DEFAULT_MANIFEST = ROOT / "local_data" / "yolo_obb_annotation_pack" / "smoke" / "smoke_manifest.csv"
DEFAULT_LABELS_DIR = ROOT / "local_data" / "yolo_obb_annotation_pack" / "smoke" / "labels"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "yolo_obb_dataset_smoke"


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_sample(record, labels_dir: Path, output_dir: Path, split: str) -> dict:
    image_src = record.image_path
    label_src = label_path_for(record, labels_dir)

    if not image_src.exists():
        raise FileNotFoundError(f"Missing image for {record.sample}: {image_src}")
    if not label_src.exists():
        raise FileNotFoundError(f"Missing label for {record.sample}: {label_src}")

    image_ext = image_src.suffix.lower()
    image_dst = output_dir / "images" / split / f"{record.sample}{image_ext}"
    label_dst = output_dir / "labels" / split / f"{record.sample}.txt"

    image_dst.parent.mkdir(parents=True, exist_ok=True)
    label_dst.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(image_src, image_dst)
    shutil.copy2(label_src, label_dst)

    return {
        "sample": record.sample,
        "source_sample": record.source_sample,
        "split": split,
        "image": str(image_dst.relative_to(output_dir)),
        "label": str(label_dst.relative_to(output_dir)),
        "title_block_position": record.title_block_position,
        "rotation_degrees": record.rotation_degrees,
    }


def write_data_yaml(output_dir: Path) -> None:
    yaml_text = "\n".join(
        [
            f"path: {output_dir.as_posix()}",
            "train: images/train",
            "val: images/val",
            "names:",
            "  0: title_block",
            "",
        ]
    )
    (output_dir / "data.yaml").write_text(yaml_text, encoding="utf-8")


def count_files(path: Path, pattern: str) -> int:
    return len(list(path.glob(pattern)))


def build_dataset(args: argparse.Namespace) -> dict:
    manifest = load_manifest(resolve_path(args.manifest))
    labels_dir = resolve_path(args.labels_dir)
    output_dir = resolve_path(args.output_dir)

    if args.clean:
        clean_dir(output_dir)
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []

    # Overfit smoke dataset: train and val intentionally contain the same 16 samples.
    for split in ("train", "val"):
        for record in manifest:
            records.append(copy_sample(record, labels_dir, output_dir, split))

    write_data_yaml(output_dir)

    summary = {
        "dataset_dir": str(output_dir),
        "strategy": "overfit_smoke_train_equals_val",
        "source_manifest": str(resolve_path(args.manifest)),
        "source_labels_dir": str(labels_dir),
        "train_images": count_files(output_dir / "images" / "train", "*.png"),
        "train_labels": count_files(output_dir / "labels" / "train", "*.txt"),
        "val_images": count_files(output_dir / "images" / "val", "*.png"),
        "val_labels": count_files(output_dir / "labels" / "val", "*.txt"),
        "classes": {"0": "title_block"},
        "records": records,
    }

    (output_dir / "dataset_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local Ultralytics YOLO/OBB smoke dataset.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--labels-dir", type=Path, default=DEFAULT_LABELS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--clean", action="store_true", default=True)
    args = parser.parse_args()

    summary = build_dataset(args)
    printable = {
        key: value
        for key, value in summary.items()
        if key != "records"
    }
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

