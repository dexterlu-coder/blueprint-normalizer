from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2

from scripts.common.obb_utils import ROOT, label_path_for, load_manifest, load_obb_labels, polygon_area, resolve_path


DEFAULT_MANIFEST = ROOT / "local_data" / "yolo_obb_annotation_pack" / "smoke" / "smoke_manifest.csv"
DEFAULT_LABELS_DIR = ROOT / "local_data" / "yolo_obb_annotation_pack" / "smoke" / "labels"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "yolo_obb_annotation_pack" / "smoke" / "validation"


def add_issue(issues: list[dict], severity: str, sample: str, code: str, message: str) -> None:
    issues.append(
        {
            "severity": severity,
            "sample": sample,
            "code": code,
            "message": message,
        }
    )


def validate(args: argparse.Namespace) -> tuple[dict, list[dict]]:
    manifest_path = resolve_path(args.manifest)
    labels_dir = resolve_path(args.labels_dir)
    records = load_manifest(manifest_path)
    issues: list[dict] = []
    per_sample: list[dict] = []

    source_splits: dict[str, set[str]] = {}
    label_count = 0
    samples_with_labels = 0
    samples_missing_labels = 0

    for record in records:
        source_splits.setdefault(record.source_sample, set()).add(record.suggested_split)
        image_exists = record.image_path.exists()
        image_readable = False
        image_shape = ""

        if not image_exists:
            add_issue(issues, "error", record.sample, "missing_image", f"Image not found: {record.image_path}")
        else:
            image = cv2.imread(str(record.image_path))
            if image is None:
                add_issue(issues, "error", record.sample, "unreadable_image", f"Image unreadable: {record.image_path}")
            else:
                image_readable = True
                image_shape = f"{image.shape[1]}x{image.shape[0]}"

        label_path = label_path_for(record, labels_dir)
        sample_label_count = 0
        if not label_path.exists():
            samples_missing_labels += 1
            add_issue(issues, "warning", record.sample, "missing_label", f"Label not found: {label_path}")
        else:
            try:
                labels = load_obb_labels(label_path)
            except ValueError as exc:
                add_issue(issues, "error", record.sample, "label_parse_error", str(exc))
                labels = []

            if not labels:
                add_issue(issues, "warning", record.sample, "empty_label", f"Label file is empty: {label_path}")
            else:
                samples_with_labels += 1

            for label in labels:
                sample_label_count += 1
                label_count += 1

                if label.class_id != 0:
                    add_issue(
                        issues,
                        "error",
                        record.sample,
                        "invalid_class_id",
                        f"line {label.line_number}: expected class id 0, got {label.class_id}",
                    )

                for point_index, (x, y) in enumerate(label.points, start=1):
                    if not 0.0 <= x <= 1.0 or not 0.0 <= y <= 1.0:
                        add_issue(
                            issues,
                            "error",
                            record.sample,
                            "coordinate_out_of_range",
                            f"line {label.line_number} point {point_index}: ({x}, {y})",
                        )

                area = polygon_area(label.points)
                if area <= args.min_area:
                    add_issue(
                        issues,
                        "error",
                        record.sample,
                        "zero_or_tiny_polygon",
                        f"line {label.line_number}: normalized polygon area {area:.8f}",
                    )

        per_sample.append(
            {
                "sample": record.sample,
                "dataset": record.dataset,
                "source_sample": record.source_sample,
                "suggested_split": record.suggested_split,
                "image_exists": image_exists,
                "image_readable": image_readable,
                "image_shape": image_shape,
                "label_path": str(label_path),
                "label_count": sample_label_count,
            }
        )

    leakage_sources = {
        source: sorted(splits)
        for source, splits in source_splits.items()
        if len({split for split in splits if split}) > 1
    }
    if not args.allow_source_split_overlap:
        for source, splits in leakage_sources.items():
            add_issue(
                issues,
                "error",
                source,
                "source_split_leakage",
                f"source_sample appears in multiple splits: {', '.join(splits)}",
            )

    issue_counts: dict[str, int] = {}
    for issue in issues:
        issue_counts[issue["code"]] = issue_counts.get(issue["code"], 0) + 1

    summary = {
        "manifest": str(manifest_path),
        "labels_dir": str(labels_dir),
        "total_samples": len(records),
        "samples_with_labels": samples_with_labels,
        "samples_missing_labels": samples_missing_labels,
        "total_labels": label_count,
        "issue_count": len(issues),
        "error_count": sum(1 for issue in issues if issue["severity"] == "error"),
        "warning_count": sum(1 for issue in issues if issue["severity"] == "warning"),
        "issue_counts": issue_counts,
        "source_split_leakage_count": len(leakage_sources),
    }
    return {"summary": summary, "samples": per_sample, "issues": issues}, issues


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a YOLO/OBB dataset manifest and labels.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--labels-dir", type=Path, default=DEFAULT_LABELS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-area", type=float, default=1e-8)
    parser.add_argument("--allow-source-split-overlap", action="store_true")
    args = parser.parse_args()

    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report, issues = validate(args)
    (output_dir / "validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(
        output_dir / "validation_issues.csv",
        issues,
        ["severity", "sample", "code", "message"],
    )
    write_csv(
        output_dir / "validation_samples.csv",
        report["samples"],
        [
            "sample",
            "dataset",
            "source_sample",
            "suggested_split",
            "image_exists",
            "image_readable",
            "image_shape",
            "label_path",
            "label_count",
        ],
    )

    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 1 if report["summary"]["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

