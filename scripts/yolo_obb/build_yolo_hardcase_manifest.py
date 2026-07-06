from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DATASET_DIR = ROOT / "local_data" / "yolo_obb_dataset_round2"
PREDICTIONS_DIR = ROOT / "local_data" / "yolo_predictions"
POSTPROCESS_REPORT = ROOT / "local_data" / "yolo_postprocess" / "round2_first_train" / "postprocess_report.json"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "yolo_hardcases" / "round3_retraining_prep"

TARGET_CASES = [
    {
        "sample": "sample_009",
        "split": "val",
        "group": "part_false_positive_multi_candidate",
        "source_reason": "左下角零件误检为标题栏；多候选；真实标题栏候选未完整覆盖",
        "decision": "include_as_hardcase",
        "use_existing_label": "yes",
        "negative_note": "误检零件只记录为负例说明，不写入 YOLO 标签",
    },
    {
        "sample": "sample_001",
        "split": "test",
        "group": "part_false_positive",
        "source_reason": "图纸主体零件误检为标题栏",
        "decision": "include_as_hardcase",
        "use_existing_label": "yes",
        "negative_note": "误检零件只记录为负例说明，不写入 YOLO 标签",
    },
    {
        "sample": "unclear90_001_from_sample_001",
        "split": "test",
        "group": "part_false_positive_multi_candidate",
        "source_reason": "多候选；多个零件误检为标题栏",
        "decision": "include_as_hardcase",
        "use_existing_label": "yes",
        "negative_note": "误检零件只记录为负例说明，不写入 YOLO 标签",
    },
    {
        "sample": "sample_020",
        "split": "val",
        "group": "boundary_or_size_issue",
        "source_reason": "预测框越界或范围过大",
        "decision": "include_as_boundary_quality_hardcase",
        "use_existing_label": "yes",
        "negative_note": "",
    },
    {
        "sample": "sample_010",
        "split": "test",
        "group": "boundary_or_size_issue",
        "source_reason": "预测框范围过大",
        "decision": "include_as_boundary_quality_hardcase",
        "use_existing_label": "yes",
        "negative_note": "",
    },
    {
        "sample": "aug90_002_from_sample_010",
        "split": "test",
        "group": "protective_positive",
        "source_reason": "曾被后处理误拦截，用户确认识别无误；用于防止 hard-case 策略过严",
        "decision": "include_as_protective_positive",
        "use_existing_label": "yes",
        "negative_note": "",
    },
    {
        "sample": "aug90_007_from_sample_020",
        "split": "val",
        "group": "protective_positive",
        "source_reason": "正例对照",
        "decision": "include_as_protective_positive",
        "use_existing_label": "yes",
        "negative_note": "",
    },
    {
        "sample": "sample_040",
        "split": "val",
        "group": "protective_positive",
        "source_reason": "正例对照，侧边标题栏参考",
        "decision": "include_as_protective_positive",
        "use_existing_label": "yes",
        "negative_note": "",
    },
]


def rel_path(path: Path) -> str:
    return Path(os.path.relpath(path, ROOT)).as_posix()


def prediction_dir(split: str) -> Path:
    return PREDICTIONS_DIR / f"round2_{split}"


def label_line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def load_postprocess_records(path: Path) -> dict[tuple[str, str], dict]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        report = json.load(f)
    return {(row["split"], row["sample"]): row for row in report.get("records", [])}


def path_status(path: Path) -> str:
    return "exists" if path.exists() else "missing"


def build_records() -> list[dict]:
    postprocess_records = load_postprocess_records(POSTPROCESS_REPORT)
    records: list[dict] = []

    for case in TARGET_CASES:
        split = case["split"]
        sample = case["sample"]
        image_path = DATASET_DIR / "images" / split / f"{sample}.png"
        label_path = DATASET_DIR / "labels" / split / f"{sample}.txt"
        pred_image = prediction_dir(split) / f"{sample}.jpg"
        pred_label = prediction_dir(split) / "labels" / f"{sample}.txt"
        post = postprocess_records.get((split, sample), {})
        label_count = label_line_count(label_path)

        row = {
            **case,
            "image_path": rel_path(image_path),
            "label_path": rel_path(label_path),
            "prediction_image": rel_path(pred_image),
            "prediction_label": rel_path(pred_label),
            "image_status": path_status(image_path),
            "label_status": path_status(label_path),
            "prediction_image_status": path_status(pred_image),
            "prediction_label_status": path_status(pred_label),
            "title_block_label_count": label_count,
            "label_quality_status": "ok_single_title_block" if label_count == 1 else "invalid_label_count",
            "postprocess_status": post.get("status", ""),
            "postprocess_issue_types": ";".join(post.get("issue_types", [])),
            "selected_confidence": post.get("selected_confidence", ""),
            "selected_score": post.get("selected_score", ""),
            "manual_acceptance": post.get("manual_acceptance", ""),
            "manual_problem_type": post.get("manual_problem_type", ""),
        }
        records.append(row)

    return records


def summarize(records: list[dict]) -> dict:
    required_samples = [case["sample"] for case in TARGET_CASES]
    present_samples = [record["sample"] for record in records]
    missing_required = sorted(set(required_samples) - set(present_samples))

    by_group: dict[str, int] = {}
    missing_files: list[dict] = []
    invalid_labels: list[dict] = []
    for record in records:
        by_group[record["group"]] = by_group.get(record["group"], 0) + 1
        for field in ("image_status", "label_status", "prediction_image_status", "prediction_label_status"):
            if record[field] != "exists":
                missing_files.append({"sample": record["sample"], "field": field})
        if record["label_quality_status"] != "ok_single_title_block":
            invalid_labels.append(
                {
                    "sample": record["sample"],
                    "title_block_label_count": record["title_block_label_count"],
                }
            )

    return {
        "total": len(records),
        "by_group": by_group,
        "required_samples": required_samples,
        "missing_required_samples": missing_required,
        "missing_files": missing_files,
        "invalid_labels": invalid_labels,
        "negative_label_policy": "false-positive parts are metadata only; YOLO labels remain true title_block only",
        "quality_gate_passed": not missing_required and not missing_files and not invalid_labels,
    }


def write_csv(path: Path, records: list[dict]) -> None:
    fieldnames = [
        "sample",
        "split",
        "group",
        "source_reason",
        "decision",
        "use_existing_label",
        "negative_note",
        "image_path",
        "label_path",
        "prediction_image",
        "prediction_label",
        "title_block_label_count",
        "label_quality_status",
        "postprocess_status",
        "postprocess_issue_types",
        "selected_confidence",
        "selected_score",
        "manual_acceptance",
        "manual_problem_type",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({key: record.get(key, "") for key in fieldnames})


def build(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    records = build_records()
    summary = summarize(records)

    (output_dir / "hardcase_manifest.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(output_dir / "hardcase_manifest.csv", records)
    (output_dir / "hardcase_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        **summary,
        "output_dir": rel_path(output_dir),
        "manifest_json": rel_path(output_dir / "hardcase_manifest.json"),
        "manifest_csv": rel_path(output_dir / "hardcase_manifest.csv"),
        "summary_json": rel_path(output_dir / "hardcase_summary.json"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build YOLO/OBB hard-case manifest for round-3 retraining prep.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    summary = build(args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["quality_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
