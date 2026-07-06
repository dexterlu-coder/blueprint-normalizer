from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_GROUND_TRUTH = ROOT / "local_data" / "ground_truth" / "rotation_ground_truth.json"
DEFAULT_PDF_DIR = ROOT / "local_data" / "experiment_samples" / "all" / "pdf"
DEFAULT_PNG_DIR = ROOT / "local_data" / "experiment_samples" / "all" / "png"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "full_63_pdf_dry_run"

RECORD_VERSION = "0.1"
PDF_PREFIX = "YKJ125-00-00-2525"


def as_posix(path: Path | str | None) -> str | None:
    if path is None:
        return None
    path_obj = Path(path)
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def load_json(path: Path) -> Any:
    return json.loads(resolve_path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def correction_from_rotation(rotation_degrees: int | None) -> int | None:
    if rotation_degrees is None:
        return None
    return (360 - rotation_degrees) % 360


def sample_file_stem(sample: str) -> str:
    return f"{PDF_PREFIX}_{sample}"


def build_record(
    truth: dict[str, Any],
    pdf_dir: Path,
    png_dir: Path,
    output_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    sample = truth["sample"]
    rotation_degrees = int(truth["rotation_degrees"])
    correction_degrees = correction_from_rotation(rotation_degrees)
    stem = sample_file_stem(sample)
    pdf_path = resolve_path(pdf_dir) / f"{stem}.pdf"
    png_path = resolve_path(png_dir) / f"{stem}.png"
    pdf_exists = pdf_path.exists()
    png_exists = png_path.exists()
    missing = None
    if not pdf_exists or not png_exists:
        missing = {
            "sample_id": sample,
            "expected_pdf_path": as_posix(pdf_path),
            "expected_png_path": as_posix(png_path),
            "pdf_exists": pdf_exists,
            "png_exists": png_exists,
        }

    record_id = f"full_63_ground_truth:{sample}"
    record = {
        "record_version": RECORD_VERSION,
        "record_id": record_id,
        "sample_id": sample,
        "page": {
            "source_pdf_path": None,
            "page_index": None,
            "single_page_pdf_path": as_posix(pdf_path),
            "rendered_image_path": as_posix(png_path),
            "dataset_name": "full_63_ground_truth",
            "prediction_dir": "full_63",
            "split": "all",
            "source_status": "ground_truth_pdf_mapping",
        },
        "title_block_candidates": [],
        "evidence": {
            "yolo_obb": {
                "status": "not_used",
            },
            "opencv": {
                "status": "not_used_for_this_record",
            },
            "ocr": {
                "status": "not_attempted",
                "field_cluster_level": "missing",
            },
            "vlm": {
                "status": "not_triggered",
            },
            "manual": {
                "status": "ground_truth_source",
                "source_level": truth.get("source_level", ""),
                "source_basis": truth.get("source_basis", ""),
                "verified_by_human": bool(truth.get("verified_by_human")),
            },
        },
        "arbitration": {
            "selected_candidate_id": None,
            "selected_candidate_index": None,
            "title_block_position": truth["title_block_position"],
            "title_block_position_source": "manual_ground_truth",
            "position_source_comparable_with_opencv": True,
            "decision_status": "auto_accept",
            "confidence_level": "high",
            "decision_reasons": [
                "manual_ground_truth_full_63_mapping",
                "pdf_path_mapping_dry_run",
            ],
            "conflicts": [],
            "missing_evidence": ["ocr_not_attempted_for_full_63_mapping"],
            "review_route": "auto",
        },
        "rotation": {
            "detected_rotation_degrees": rotation_degrees,
            "correction_degrees": correction_degrees,
            "rotation_rule_version": "rules/mechanical-drawing-rotation.md",
            "rotation_ready": True,
        },
        "ocr": {
            "title_block_crop_path": None,
            "normalized_crop_path": None,
            "ocr_text": "",
            "ocr_tokens": [],
            "field_cluster_hits": {
                "role": [],
                "property": [],
            },
            "ocr_confidence": None,
            "ocr_ready_for_number_extraction": False,
        },
        "drawing_number": {
            "candidates": [],
            "selected_drawing_number": None,
            "selection_status": "not_attempted",
            "filename_safe_value": None,
            "naming_risks": ["drawing_number_extraction_not_attempted"],
        },
        "output_plan": {
            "corrected_pdf_path": None,
            "renamed_pdf_path": None,
            "dry_run_only": True,
            "would_overwrite": None,
            "duplicate_name_group": None,
        },
        "review_routing": {
            "route": "auto",
            "route_reason": ["manual_ground_truth_full_63_mapping"],
            "review_priority": "low",
            "human_visible_fields": [
                "sample_id",
                "rendered_image_path",
                "title_block_position",
                "detected_rotation_degrees",
                "correction_degrees",
            ],
        },
        "artifacts": {
            "source_ground_truth_path": as_posix(DEFAULT_GROUND_TRUTH),
            "arbitration_record_path": as_posix(
                output_dir / "full_63_arbitration_records.jsonl"
            ),
            "selected_candidate_id": None,
        },
    }
    manifest = {
        "sample_id": sample,
        "single_page_pdf_path": as_posix(pdf_path),
        "rendered_image_path": as_posix(png_path),
        "title_block_position": truth["title_block_position"],
        "precise_title_block_position": truth.get("precise_title_block_position", ""),
        "rotation_degrees": rotation_degrees,
        "correction_degrees": correction_degrees,
        "pdf_exists": pdf_exists,
        "png_exists": png_exists,
        "source_level": truth.get("source_level", ""),
        "source_basis": truth.get("source_basis", ""),
        "verified_by_human": bool(truth.get("verified_by_human")),
    }
    return record, manifest, missing


def build(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    truth_rows = sorted(load_json(args.ground_truth), key=lambda row: row["sample"])
    records: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []

    for truth in truth_rows:
        record, manifest, missing = build_record(
            truth,
            args.pdf_dir,
            args.png_dir,
            output_dir,
        )
        records.append(record)
        manifest_rows.append(manifest)
        if missing:
            missing_rows.append(missing)

    records_path = output_dir / "full_63_arbitration_records.jsonl"
    manifest_path = output_dir / "full_63_input_manifest.csv"
    missing_path = output_dir / "missing_assets.csv"
    summary_path = output_dir / "full_63_input_summary.json"

    write_jsonl(records_path, records)
    write_csv(
        manifest_path,
        manifest_rows,
        [
            "sample_id",
            "single_page_pdf_path",
            "rendered_image_path",
            "title_block_position",
            "precise_title_block_position",
            "rotation_degrees",
            "correction_degrees",
            "pdf_exists",
            "png_exists",
            "source_level",
            "source_basis",
            "verified_by_human",
        ],
    )
    write_csv(
        missing_path,
        missing_rows,
        ["sample_id", "expected_pdf_path", "expected_png_path", "pdf_exists", "png_exists"],
    )
    summary = {
        "record_count": len(records),
        "manifest_count": len(manifest_rows),
        "missing_asset_count": len(missing_rows),
        "pdf_exists_count": sum(1 for row in manifest_rows if row["pdf_exists"]),
        "png_exists_count": sum(1 for row in manifest_rows if row["png_exists"]),
        "ground_truth_path": as_posix(resolve_path(args.ground_truth)),
        "pdf_dir": as_posix(resolve_path(args.pdf_dir)),
        "png_dir": as_posix(resolve_path(args.png_dir)),
        "dry_run_only": True,
    }
    write_json(summary_path, summary)

    return {
        "output_dir": as_posix(output_dir),
        "full_63_arbitration_records": as_posix(records_path),
        "full_63_input_manifest": as_posix(manifest_path),
        "missing_assets": as_posix(missing_path),
        "full_63_input_summary": as_posix(summary_path),
        "summary": summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build full-63 dry-run arbitration inputs from ground truth and single-page PDFs."
    )
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    parser.add_argument("--png-dir", type=Path, default=DEFAULT_PNG_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    result = build(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

