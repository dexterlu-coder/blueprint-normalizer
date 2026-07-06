from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_TEACHER_REVIEW_DIR = ROOT / "local_data" / "mcp_vlm_teacher_review"
DEFAULT_CANDIDATES = DEFAULT_TEACHER_REVIEW_DIR / "distillation_candidates.csv"
DEFAULT_PROMPT = DEFAULT_TEACHER_REVIEW_DIR / "teacher_prompt_draft.md"
DEFAULT_DIAGNOSTIC_REPORT = (
    ROOT / "local_data" / "title_block_ocr_diagnostic" / "diagnostic_report.json"
)
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "mcp_vlm_teacher_call_prep"
DEFAULT_ORIGINAL_IMAGE_DIR = ROOT / "local_data" / "experiment_samples" / "all" / "png"

TASK_TARGETS = [
    ("three_way_mcp_correction", "sample_009", "", ""),
    ("three_way_mcp_correction", "sample_010", "", ""),
    ("three_way_low_confidence_agreement", "sample_042", "", ""),
    ("routing_hardcase", "aug90_002_from_sample_010", "round3_val", "0"),
    ("round3_rejected_candidate", "aug90_002_from_sample_010", "round3_val", "1"),
    ("routing_hardcase", "sample_001", "round3_train", "0"),
    ("routing_hardcase", "unclear90_001_from_sample_001", "round3_train", "0"),
    ("routing_hardcase", "sample_040", "round3_val", "0"),
]

FALLBACK_TASKS = {
    ("routing_hardcase", "sample_040", "round3_val", "0"): {
        "source": "round3_positive_control",
        "sample": "sample_040",
        "prediction_dir": "round3_val",
        "candidate_index": "0",
        "teacher_value": "small_angle_offset_tolerated",
        "distill_to_rule": "yes",
        "distill_to_data": "maybe",
        "distill_to_model": "no",
        "reason": "small_angle_offset_tolerated_positive_control",
        "expected_teacher_question": "Why is this slightly rotated OBB still an acceptable title block detection?",
    }
}


def as_posix(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> Any:
    return json.loads(resolve_path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with resolve_path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def candidate_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("source", ""),
        row.get("sample", ""),
        row.get("prediction_dir", ""),
        str(row.get("candidate_index", "")),
    )


def diagnostic_indexes(report: dict[str, Any]) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str, int], dict[str, Any]]]:
    records = {
        (record["prediction_dir"], record["sample"]): record
        for record in report.get("records", [])
    }
    candidates = {
        (candidate["prediction_dir"], candidate["sample"], int(candidate["candidate_index"])): candidate
        for candidate in report.get("candidates", [])
    }
    return records, candidates


def original_image(sample: str) -> Path:
    return DEFAULT_ORIGINAL_IMAGE_DIR / f"YKJ125-00-00-2525_{sample}.png"


def copy_asset(source: Path | None, target_dir: Path, target_name: str) -> str:
    if source is None:
        return ""
    resolved = resolve_path(source)
    if not resolved.exists():
        return ""
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / target_name
    shutil.copy2(resolved, target)
    return as_posix(target)


def task_question(row: dict[str, str]) -> str:
    teacher_value = row["teacher_value"]
    if teacher_value == "mcp_corrected_opencv":
        return "请解释为什么标题栏应位于 MCP/人工判断的位置，而不是 OpenCV 判断的位置。"
    if teacher_value == "confidence_calibration":
        return "请解释这个低置信样本有哪些视觉证据支持其仍可接受。"
    if teacher_value == "non_title_table_false_positive":
        return "请判断该候选为什么是普通表格误检，而不是真实标题栏。"
    return "请判断该候选是否应接受、人工复核，或作为 hard-case 蒸馏/训练信号。"


def response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": [
            "task_id",
            "selected_candidate_index",
            "title_block_position",
            "rotation_degrees",
            "candidate_judgments",
            "needs_human_review",
            "confidence",
        ],
        "properties": {
            "task_id": {"type": "string"},
            "selected_candidate_index": {"type": ["integer", "null"]},
            "title_block_position": {"enum": ["bottom", "left", "top", "right", "unknown"]},
            "rotation_degrees": {"enum": [0, 90, 180, 270, None]},
            "candidate_judgments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "candidate_index",
                        "is_true_title_block",
                        "touches_drawing_frame",
                        "ordinary_table_false_positive_risk",
                        "field_cluster_strength",
                        "layout_evidence",
                        "reject_reasons_if_not_title_block",
                    ],
                    "properties": {
                        "candidate_index": {"type": ["integer", "null"]},
                        "is_true_title_block": {"type": "boolean"},
                        "touches_drawing_frame": {"type": "boolean"},
                        "ordinary_table_false_positive_risk": {"enum": ["low", "medium", "high"]},
                        "field_cluster_strength": {"enum": ["none", "weak", "medium", "strong"]},
                        "layout_evidence": {"type": "array", "items": {"type": "string"}},
                        "reject_reasons_if_not_title_block": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "needs_human_review": {"type": "boolean"},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
    }


def build_tasks(
    candidates: list[dict[str, str]],
    diagnostic_records: dict[tuple[str, str], dict[str, Any]],
    diagnostic_candidates: dict[tuple[str, str, int], dict[str, Any]],
    output_dir: Path,
) -> list[dict[str, Any]]:
    candidate_map = {candidate_key(row): row for row in candidates}
    tasks: list[dict[str, Any]] = []
    assets_dir = output_dir / "assets"

    for index, key in enumerate(TASK_TARGETS, start=1):
        row = candidate_map.get(key) or FALLBACK_TASKS.get(key)
        if row is None:
            continue

        source, sample, prediction_dir, candidate_index_text = key
        task_id = f"teacher_{index:02d}_{source}__{prediction_dir or 'three_way'}__{sample}"
        if candidate_index_text:
            task_id += f"__candidate_{candidate_index_text}"

        candidate_index = int(candidate_index_text) if candidate_index_text else None
        diag_record = diagnostic_records.get((prediction_dir, sample)) if prediction_dir else None
        diag_candidate = (
            diagnostic_candidates.get((prediction_dir, sample, candidate_index))
            if prediction_dir and candidate_index is not None
            else None
        )

        source_image_path = None
        overlay_path = None
        crop_path = None
        if diag_candidate:
            source_image_path = Path(diag_candidate["source_image"])
            crop_path = Path(diag_candidate["crop_path"])
        elif diag_record:
            source_image_path = Path(diag_record["source_image"])
        elif sample.startswith("sample_"):
            source_image_path = original_image(sample)

        if diag_record:
            overlay_path = Path(diag_record["overlay_path"])

        task_asset_dir = assets_dir / task_id
        source_asset = copy_asset(source_image_path, task_asset_dir, "source.png")
        overlay_asset = copy_asset(overlay_path, task_asset_dir, "overlay.jpg")
        crop_asset = copy_asset(crop_path, task_asset_dir, "candidate_crop.png")

        missing_assets = []
        if not source_asset:
            missing_assets.append("source")
        if prediction_dir and not overlay_asset:
            missing_assets.append("overlay")
        if candidate_index is not None and not crop_asset:
            missing_assets.append("candidate_crop")

        tasks.append(
            {
                "task_id": task_id,
                "task_type": row["teacher_value"],
                "source": source,
                "sample": sample,
                "prediction_dir": prediction_dir,
                "candidate_index": candidate_index_text,
                "question": task_question(row),
                "expected_teacher_question": row["expected_teacher_question"],
                "distill_to_rule": row["distill_to_rule"],
                "distill_to_data": row["distill_to_data"],
                "distill_to_model": row["distill_to_model"],
                "reason": row["reason"],
                "source_image": source_asset,
                "overlay_image": overlay_asset,
                "candidate_crop": crop_asset,
                "missing_assets": ";".join(missing_assets),
            }
        )

    return tasks


def build(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = read_csv(args.candidates)
    diagnostic_report = read_json(args.diagnostic_report)
    diagnostic_records, diagnostic_candidates = diagnostic_indexes(diagnostic_report)
    tasks = build_tasks(candidates, diagnostic_records, diagnostic_candidates, output_dir)

    prompt_text = resolve_path(args.prompt).read_text(encoding="utf-8")
    prompt_path = output_dir / "teacher_prompt.md"
    schema_path = output_dir / "teacher_response_schema.json"
    manifest_json_path = output_dir / "teacher_call_manifest.json"
    manifest_csv_path = output_dir / "teacher_call_manifest.csv"

    prompt_path.write_text(prompt_text, encoding="utf-8")
    write_json(schema_path, response_schema())
    write_json(
        manifest_json_path,
        {
            "output_dir": as_posix(output_dir),
            "task_count": len(tasks),
            "tasks": tasks,
        },
    )
    write_csv(
        manifest_csv_path,
        tasks,
        [
            "task_id",
            "task_type",
            "source",
            "sample",
            "prediction_dir",
            "candidate_index",
            "question",
            "expected_teacher_question",
            "distill_to_rule",
            "distill_to_data",
            "distill_to_model",
            "reason",
            "source_image",
            "overlay_image",
            "candidate_crop",
            "missing_assets",
        ],
    )

    return {
        "output_dir": str(output_dir),
        "teacher_call_manifest": str(manifest_json_path),
        "teacher_call_manifest_csv": str(manifest_csv_path),
        "teacher_prompt": str(prompt_path),
        "teacher_response_schema": str(schema_path),
        "task_count": len(tasks),
        "missing_asset_tasks": sum(1 for task in tasks if task["missing_assets"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MCP/VLM teacher call prep package.")
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--diagnostic-report", type=Path, default=DEFAULT_DIAGNOSTIC_REPORT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    print(json.dumps(build(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

