from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_YOLO_REPORTS = [
    ROOT / "local_data" / "yolo_postprocess" / "round2_first_train" / "postprocess_report.json",
    ROOT / "local_data" / "yolo_postprocess" / "general_round3_diagnostic" / "postprocess_report.json",
]
DEFAULT_OCR_REPORT = ROOT / "local_data" / "title_block_ocr_diagnostic" / "diagnostic_report.json"
DEFAULT_OPENCV_RESULTS = [
    ROOT / "outputs" / "rotation-detection" / "stage1" / "results.json",
    ROOT / "outputs" / "rotation-detection" / "augmented_90" / "results.json",
]
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "title_block_arbitration"

RECORD_VERSION = "0.1"

SIDE_TO_ROTATION = {
    "bottom": 0,
    "left": 90,
    "top": 180,
    "right": 270,
}

ORIENTATION_RATIO_THRESHOLD = 1.15
COMPARABLE_POSITION_SOURCES = {
    "bbox_aspect_center_vertical",
    "bbox_aspect_center_horizontal",
    "bbox_nearest_page_side",
}


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
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def sample_id_from_filename(filename: str) -> str:
    path = Path(filename)
    stem = path.stem
    match = re.search(r"(unclear90_\d+_from_sample_\d+|aug90_\d+_from_sample_\d+|sample_\d+)", stem)
    if match:
        return match.group(1)
    return stem


def normalize_side(side: str | None) -> str | None:
    if not side:
        return None
    side = side.lower()
    aliases = {
        "left": "left",
        "right": "right",
        "top": "top",
        "bottom": "bottom",
    }
    return aliases.get(side)


def rotation_from_side(side: str | None) -> int | None:
    if side is None:
        return None
    return SIDE_TO_ROTATION.get(side)


def correction_from_detected_rotation(rotation: int | None) -> int | None:
    if rotation is None:
        return None
    return (360 - rotation) % 360


def normalized_bbox(candidate: dict[str, Any] | None) -> list[float] | None:
    if not candidate:
        return None
    bbox = candidate.get("bbox_xyxy_normalized") or candidate.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    try:
        return [float(value) for value in bbox]
    except (TypeError, ValueError):
        return None


def nearest_page_side_from_bbox(bbox: list[float]) -> str:
    xmin, ymin, xmax, ymax = bbox
    distances = {
        "left": abs(xmin),
        "right": abs(1.0 - xmax),
        "top": abs(ymin),
        "bottom": abs(1.0 - ymax),
    }
    return min(distances, key=distances.get)


def infer_title_block_position(
    candidate: dict[str, Any] | None,
    ocr_candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """推导标题栏页面侧，避免把贴图框侧误当成标题栏位置。"""

    diagnostic_candidate_side = normalize_side(
        (ocr_candidate or {}).get("candidate_side")
        or (candidate or {}).get("candidate_side")
    )
    nearest_frame_side = normalize_side(
        (candidate or {}).get("nearest_frame_side")
        or (ocr_candidate or {}).get("nearest_frame_side")
    )
    bbox = normalized_bbox(candidate) or normalized_bbox(ocr_candidate)
    if not bbox:
        proxy_side = diagnostic_candidate_side or nearest_frame_side
        return {
            "title_block_position": proxy_side,
            "position_source": "diagnostic_candidate_side_proxy"
            if diagnostic_candidate_side
            else "frame_contact_side_proxy"
            if nearest_frame_side
            else "missing",
            "position_source_comparable_with_opencv": False,
            "bbox_aspect_ratio": None,
            "diagnostic_candidate_side": diagnostic_candidate_side,
            "nearest_frame_side": nearest_frame_side,
        }

    xmin, ymin, xmax, ymax = bbox
    width = max(0.0, xmax - xmin)
    height = max(0.0, ymax - ymin)
    center_x = (xmin + xmax) / 2.0
    center_y = (ymin + ymax) / 2.0
    aspect_ratio = width / height if height > 0 else None

    if height > 0 and width >= height * ORIENTATION_RATIO_THRESHOLD:
        side = "bottom" if center_y >= 0.5 else "top"
        source = "bbox_aspect_center_horizontal"
    elif width > 0 and height >= width * ORIENTATION_RATIO_THRESHOLD:
        side = "right" if center_x >= 0.5 else "left"
        source = "bbox_aspect_center_vertical"
    else:
        side = nearest_page_side_from_bbox(bbox)
        source = "bbox_nearest_page_side"

    return {
        "title_block_position": side,
        "position_source": source,
        "position_source_comparable_with_opencv": source in COMPARABLE_POSITION_SOURCES,
        "bbox_aspect_ratio": aspect_ratio,
        "diagnostic_candidate_side": diagnostic_candidate_side,
        "nearest_frame_side": nearest_frame_side,
    }


def load_opencv_results(paths: list[Path]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for path in paths:
        resolved = resolve_path(path)
        if not resolved.exists():
            continue
        for row in load_json(resolved):
            sample = sample_id_from_filename(row.get("file", ""))
            if not sample:
                continue
            results[sample] = {
                "source_report_path": as_posix(resolved),
                "status": "ok",
                "title_block_side": normalize_side(row.get("title_block_side")),
                "title_block_position": row.get("title_block_position"),
                "clockwise_rotation_degrees": row.get("clockwise_rotation_degrees"),
                "correction_clockwise_degrees": row.get("correction_clockwise_degrees"),
                "confidence": row.get("confidence"),
                "needs_review": row.get("needs_review"),
                "debug_image": row.get("debug_image"),
                "best_candidate": row.get("best_candidate"),
            }
    return results


def load_ocr_candidates(path: Path) -> tuple[dict[tuple[str, str, int], dict[str, Any]], dict[str, Any]]:
    resolved = resolve_path(path)
    if not resolved.exists():
        return {}, {"status": "missing", "source_report_path": as_posix(resolved)}
    report = load_json(resolved)
    candidates: dict[tuple[str, str, int], dict[str, Any]] = {}
    for candidate in report.get("candidates", []):
        key = (
            candidate.get("prediction_dir", ""),
            candidate.get("sample", ""),
            int(candidate.get("candidate_index", -1)),
        )
        candidates[key] = candidate
    metadata = {
        "status": "ok",
        "source_report_path": as_posix(resolved),
        "ocr_probe_decision": report.get("ocr_probe_decision"),
        "ocr_capability": report.get("ocr_capability"),
        "summary": report.get("summary"),
    }
    return candidates, metadata


def candidate_id(source: str, index: int | None) -> str:
    if index is None:
        return f"{source}:missing"
    return f"{source}:{index}"


def compact_candidate(
    source: str,
    candidate: dict[str, Any],
    selected_candidate_index: int | None,
    ocr_candidate: dict[str, Any] | None,
    rejected: bool,
) -> dict[str, Any]:
    index = candidate.get("candidate_index")
    ocr_status = ocr_candidate.get("ocr_status") if ocr_candidate else "missing"
    field_cluster_score = ocr_candidate.get("field_cluster_score") if ocr_candidate else None
    position_evidence = infer_title_block_position(candidate, ocr_candidate)
    position = position_evidence["title_block_position"]
    return {
        "candidate_id": candidate_id(source, index),
        "source": source,
        "candidate_index": index,
        "class_id": candidate.get("class_id"),
        "bbox": candidate.get("bbox_xyxy_normalized"),
        "obb_points": candidate.get("points_normalized"),
        "position": position,
        "precise_position": position,
        "position_source": position_evidence["position_source"],
        "diagnostic_candidate_side": position_evidence["diagnostic_candidate_side"],
        "frame_contact_side": position_evidence["nearest_frame_side"],
        "confidence": candidate.get("confidence"),
        "accepted_by_source": index == selected_candidate_index and not rejected,
        "reject_reason": candidate.get("rejection_reasons") if rejected else [],
        "candidate_score": candidate.get("candidate_score"),
        "frame_contact_score": candidate.get("frame_contact_score"),
        "touches_frame_line": candidate.get("touches_frame_line"),
        "frame_contact_status": candidate.get("frame_contact_status"),
        "teacher_rule_flags": candidate.get("teacher_rule_flags") or [],
        "diagnostic_flags": candidate.get("diagnostic_flags") or [],
        "ocr_status": ocr_status,
        "field_cluster_score": field_cluster_score,
    }


def build_title_block_candidates(
    report_name: str,
    record: dict[str, Any],
    ocr_candidates: dict[tuple[str, str, int], dict[str, Any]],
) -> list[dict[str, Any]]:
    prediction_dir = record.get("prediction_dir", "")
    sample = record.get("sample", "")
    selected_index = record.get("selected_candidate_index")
    rejected_by_index = {
        candidate.get("candidate_index"): candidate
        for candidate in record.get("rejected_candidates", [])
    }

    candidates: list[dict[str, Any]] = []
    for candidate in record.get("candidates", []):
        index = int(candidate.get("candidate_index", -1))
        ocr_candidate = ocr_candidates.get((prediction_dir, sample, index))
        rejected = index in rejected_by_index
        if rejected:
            merged = {**candidate, **rejected_by_index[index]}
        else:
            merged = candidate
        candidates.append(
            compact_candidate(
                source=f"yolo_obb:{report_name}",
                candidate=merged,
                selected_candidate_index=selected_index,
                ocr_candidate=ocr_candidate,
                rejected=rejected,
            )
        )

    if not candidates and record.get("selected_title_block"):
        selected = record["selected_title_block"]
        index = int(selected.get("candidate_index", -1))
        ocr_candidate = ocr_candidates.get((prediction_dir, sample, index))
        candidates.append(
            compact_candidate(
                source=f"yolo_obb:{report_name}",
                candidate=selected,
                selected_candidate_index=index,
                ocr_candidate=ocr_candidate,
                rejected=False,
            )
        )
    return candidates


def selected_candidate(record: dict[str, Any]) -> dict[str, Any] | None:
    selected = record.get("selected_title_block")
    return selected if isinstance(selected, dict) and selected else None


def field_cluster_level(ocr_candidate: dict[str, Any] | None) -> str:
    if not ocr_candidate:
        return "missing"
    if ocr_candidate.get("ocr_status") != "ok":
        return "unavailable"
    score = float(ocr_candidate.get("field_cluster_score") or 0.0)
    role_hits = ocr_candidate.get("role_field_hits") or []
    property_hits = ocr_candidate.get("property_field_hits") or []
    if score >= 0.55 and len(role_hits) >= 2 and len(property_hits) >= 2:
        return "strong"
    if score > 0.0:
        return "weak"
    return "none"


def find_selected_ocr_candidate(
    record: dict[str, Any], ocr_candidates: dict[tuple[str, str, int], dict[str, Any]]
) -> dict[str, Any] | None:
    selected_index = record.get("selected_candidate_index")
    if selected_index is None:
        return None
    key = (record.get("prediction_dir", ""), record.get("sample", ""), int(selected_index))
    return ocr_candidates.get(key)


def build_evidence(
    report_name: str,
    record: dict[str, Any],
    selected: dict[str, Any] | None,
    ocr_candidate: dict[str, Any] | None,
    opencv_record: dict[str, Any] | None,
    source_report_path: Path,
    ocr_metadata: dict[str, Any],
    position_evidence: dict[str, Any],
) -> tuple[dict[str, Any], list[str], list[str]]:
    missing: list[str] = []
    conflicts: list[str] = []

    yolo_status = record.get("status") or "missing"
    if not selected:
        missing.append("yolo_selected_title_block")

    ocr_level = field_cluster_level(ocr_candidate)
    if ocr_level == "missing":
        missing.append("ocr_selected_candidate")
    elif ocr_level in {"weak", "none", "unavailable"}:
        conflicts.append(f"ocr_field_cluster_{ocr_level}")

    if not opencv_record:
        missing.append("opencv_rotation_result")
    else:
        opencv_side = normalize_side(opencv_record.get("title_block_side"))
        yolo_position = position_evidence["title_block_position"]
        if (
            yolo_position
            and opencv_side
            and position_evidence["position_source_comparable_with_opencv"]
            and yolo_position != opencv_side
        ):
            conflicts.append(f"yolo_opencv_position_conflict:{yolo_position}!={opencv_side}")
        elif (
            yolo_position
            and opencv_side
            and not position_evidence["position_source_comparable_with_opencv"]
            and yolo_position != opencv_side
        ):
            conflicts.append(
                "position_source_not_comparable:"
                f"{position_evidence['position_source']}:{yolo_position}!={opencv_side}"
            )

    evidence = {
        "yolo_obb": {
            "status": yolo_status,
            "source_report_path": as_posix(source_report_path),
            "report_name": report_name,
            "prediction_dir": record.get("prediction_dir"),
            "split": record.get("split"),
            "prediction_count": record.get("prediction_count"),
            "issue_types": record.get("issue_types") or [],
            "selected_candidate_index": record.get("selected_candidate_index"),
            "selected_confidence": record.get("selected_confidence"),
            "selected_score": record.get("selected_score"),
            "title_block_position": position_evidence["title_block_position"],
            "title_block_position_source": position_evidence["position_source"],
            "position_source_comparable_with_opencv": position_evidence[
                "position_source_comparable_with_opencv"
            ],
            "bbox_aspect_ratio": position_evidence["bbox_aspect_ratio"],
            "diagnostic_candidate_side": position_evidence["diagnostic_candidate_side"],
            "frame_contact_side": position_evidence["nearest_frame_side"],
            "touches_frame_line": selected.get("touches_frame_line") if selected else None,
            "frame_contact_status": selected.get("frame_contact_status") if selected else None,
            "frame_contact_score": selected.get("frame_contact_score") if selected else None,
            "teacher_rule_flags": selected.get("teacher_rule_flags") if selected else [],
            "teacher_rule_adjustment": selected.get("teacher_rule_adjustment") if selected else None,
            "candidate_flags": selected.get("candidate_flags") if selected else [],
            "diagnostic_flags": selected.get("diagnostic_flags") if selected else [],
            "manual_acceptance": record.get("manual_acceptance", ""),
        },
        "opencv": opencv_record
        or {
            "status": "missing",
        },
        "ocr": {
            "status": ocr_candidate.get("ocr_status") if ocr_candidate else "missing",
            "source_report_path": ocr_metadata.get("source_report_path"),
            "ocr_probe_decision": ocr_metadata.get("ocr_probe_decision"),
            "engine": ocr_candidate.get("ocr_engine") if ocr_candidate else None,
            "rotation_angle": ocr_candidate.get("ocr_rotation_angle") if ocr_candidate else None,
            "field_cluster_level": ocr_level,
            "field_cluster_score": ocr_candidate.get("field_cluster_score") if ocr_candidate else None,
            "role_field_hits": ocr_candidate.get("role_field_hits") if ocr_candidate else [],
            "property_field_hits": ocr_candidate.get("property_field_hits") if ocr_candidate else [],
            "text_excerpt": ocr_candidate.get("ocr_text_excerpt") if ocr_candidate else "",
            "crop_path": ocr_candidate.get("crop_path") if ocr_candidate else None,
        },
        "vlm": {
            "status": "not_triggered",
        },
        "manual": {
            "status": "not_triggered",
            "manual_acceptance": record.get("manual_acceptance", ""),
            "manual_problem_type": record.get("manual_problem_type", ""),
        },
    }
    return evidence, missing, conflicts


def decide_arbitration(
    record: dict[str, Any],
    selected: dict[str, Any] | None,
    position_evidence: dict[str, Any],
    missing: list[str],
    conflicts: list[str],
) -> dict[str, Any]:
    issue_types = set(record.get("issue_types") or [])
    status = record.get("status")
    touches_frame = bool(selected.get("touches_frame_line")) if selected else False
    selected_confidence = float(record.get("selected_confidence") or 0.0)

    decision_status = "auto_accept"
    route = "auto"
    reasons: list[str] = []

    if not selected or status != "accepted":
        decision_status = "needs_human_review"
        route = "human"
        reasons.append("yolo_postprocess_not_accepted")
    elif "yolo_opencv_position_conflict" in ";".join(conflicts):
        decision_status = "needs_vlm"
        route = "vlm"
        reasons.append("local_evidence_position_conflict")
    elif not touches_frame:
        decision_status = "needs_human_review"
        route = "human"
        reasons.append("selected_candidate_not_touching_frame")
    elif issue_types.intersection({"manual_rejected", "boundary_too_large", "out_of_page_bounds"}):
        decision_status = "needs_human_review"
        route = "human"
        reasons.append("blocking_issue_type")
    else:
        reasons.append("accepted_by_yolo_postprocess")
        if "multi_candidate_resolved" in issue_types:
            reasons.append("multi_candidate_resolved")
        if "ocr_selected_candidate" in missing:
            reasons.append("ocr_missing_but_geometry_available")

    if selected_confidence >= 0.8 and not conflicts and decision_status == "auto_accept":
        confidence_level = "high"
    elif selected_confidence >= 0.5 and decision_status in {"auto_accept", "needs_vlm"}:
        confidence_level = "medium"
    else:
        confidence_level = "low"

    selected_index = record.get("selected_candidate_index")
    selected_id = candidate_id(f"yolo_obb:{record.get('report_name', '')}", selected_index)
    return {
        "selected_candidate_id": selected_id if selected else None,
        "selected_candidate_index": selected_index,
        "title_block_position": position_evidence["title_block_position"],
        "title_block_position_source": position_evidence["position_source"],
        "position_source_comparable_with_opencv": position_evidence[
            "position_source_comparable_with_opencv"
        ],
        "decision_status": decision_status,
        "confidence_level": confidence_level,
        "decision_reasons": reasons,
        "conflicts": conflicts,
        "missing_evidence": missing,
        "review_route": route,
    }


def build_record(
    report_name: str,
    source_report_path: Path,
    record: dict[str, Any],
    ocr_candidates: dict[tuple[str, str, int], dict[str, Any]],
    ocr_metadata: dict[str, Any],
    opencv_results: dict[str, dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    sample = record.get("sample", "")
    prediction_dir = record.get("prediction_dir", "")
    selected = selected_candidate(record)
    selected_ocr = find_selected_ocr_candidate(record, ocr_candidates)
    opencv_record = opencv_results.get(sample)
    position_evidence = infer_title_block_position(selected, selected_ocr)
    detected_rotation = rotation_from_side(position_evidence["title_block_position"])
    correction = correction_from_detected_rotation(detected_rotation)
    evidence, missing, conflicts = build_evidence(
        report_name=report_name,
        record=record,
        selected=selected,
        ocr_candidate=selected_ocr,
        opencv_record=opencv_record,
        source_report_path=source_report_path,
        ocr_metadata=ocr_metadata,
        position_evidence=position_evidence,
    )
    record_with_report = {**record, "report_name": report_name}
    arbitration = decide_arbitration(
        record=record_with_report,
        selected=selected,
        position_evidence=position_evidence,
        missing=missing,
        conflicts=conflicts,
    )
    paths = record.get("paths") or {}
    selected_candidate_id = arbitration["selected_candidate_id"]

    return {
        "record_version": RECORD_VERSION,
        "record_id": f"{report_name}:{prediction_dir}:{sample}",
        "sample_id": sample,
        "page": {
            "source_pdf_path": None,
            "page_index": None,
            "single_page_pdf_path": None,
            "rendered_image_path": paths.get("dataset_image") or paths.get("prediction_image"),
            "dataset_name": report_name,
            "prediction_dir": prediction_dir,
            "split": record.get("split"),
            "source_status": "local_experiment_record",
        },
        "title_block_candidates": build_title_block_candidates(report_name, record, ocr_candidates),
        "evidence": evidence,
        "arbitration": arbitration,
        "rotation": {
            "detected_rotation_degrees": detected_rotation,
            "correction_degrees": correction,
            "rotation_rule_version": "rules/mechanical-drawing-rotation.md",
            "rotation_ready": detected_rotation is not None
            and arbitration["decision_status"] in {"auto_accept", "needs_vlm"},
        },
        "ocr": {
            "title_block_crop_path": selected_ocr.get("crop_path") if selected_ocr else None,
            "normalized_crop_path": None,
            "ocr_text": selected_ocr.get("ocr_text") if selected_ocr else "",
            "ocr_tokens": [],
            "field_cluster_hits": {
                "role": selected_ocr.get("role_field_hits") if selected_ocr else [],
                "property": selected_ocr.get("property_field_hits") if selected_ocr else [],
            },
            "ocr_confidence": selected_ocr.get("ocr_confidence_summary") if selected_ocr else None,
            "ocr_ready_for_number_extraction": selected_ocr is not None
            and field_cluster_level(selected_ocr) == "strong",
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
            "route": arbitration["review_route"],
            "route_reason": arbitration["decision_reasons"],
            "review_priority": "high"
            if arbitration["decision_status"] == "needs_human_review"
            else "medium"
            if arbitration["decision_status"] == "needs_vlm"
            else "low",
            "human_visible_fields": [
                "sample_id",
                "rendered_image_path",
                "title_block_position",
                "detected_rotation_degrees",
                "decision_status",
                "decision_reasons",
            ],
        },
        "artifacts": {
            "overlay_image_path": selected_ocr.get("overlay_path") if selected_ocr else None,
            "candidate_crop_paths": [
                candidate.get("crop_path")
                for key, candidate in ocr_candidates.items()
                if key[0] == prediction_dir and key[1] == sample
            ],
            "ocr_report_path": ocr_metadata.get("source_report_path"),
            "source_report_paths": [as_posix(source_report_path)],
            "arbitration_record_path": as_posix(
                output_dir / "arbitration_records.jsonl"
            ),
            "selected_candidate_id": selected_candidate_id,
        },
    }


def build_records(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ocr_candidates, ocr_metadata = load_ocr_candidates(args.ocr_report)
    opencv_results = load_opencv_results(args.opencv_results)
    output_dir = resolve_path(args.output_dir)

    records: list[dict[str, Any]] = []
    source_reports: list[str] = []
    for report_path in args.yolo_reports:
        resolved = resolve_path(report_path)
        if not resolved.exists():
            continue
        report = load_json(resolved)
        report_name = resolved.parent.name
        source_reports.append(as_posix(resolved) or str(resolved))
        for record in report.get("records", []):
            records.append(
                build_record(
                    report_name=report_name,
                    source_report_path=resolved,
                    record=record,
                    ocr_candidates=ocr_candidates,
                    ocr_metadata=ocr_metadata,
                    opencv_results=opencv_results,
                    output_dir=output_dir,
                )
            )

    metadata = {
        "record_version": RECORD_VERSION,
        "source_reports": source_reports,
        "ocr_report": ocr_metadata.get("source_report_path"),
        "opencv_result_count": len(opencv_results),
        "ocr_candidate_count": len(ocr_candidates),
    }
    return records, metadata


def summarize(records: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    decision_counts: Counter[str] = Counter()
    route_counts: Counter[str] = Counter()
    missing_counts: Counter[str] = Counter()
    conflict_counts: Counter[str] = Counter()
    dataset_counts: Counter[str] = Counter()
    for record in records:
        arbitration = record["arbitration"]
        decision_counts[arbitration["decision_status"]] += 1
        route_counts[record["review_routing"]["route"]] += 1
        dataset_counts[record["page"]["dataset_name"]] += 1
        for item in arbitration["missing_evidence"]:
            missing_counts[item] += 1
        for item in arbitration["conflicts"]:
            conflict_counts[item] += 1
    return {
        "record_count": len(records),
        "decision_status_counts": dict(sorted(decision_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "dataset_counts": dict(sorted(dataset_counts.items())),
        "missing_evidence_counts": dict(sorted(missing_counts.items())),
        "conflict_counts": dict(sorted(conflict_counts.items())),
        "metadata": metadata,
    }


def write_summary_csv(path: Path, records: list[dict[str, Any]]) -> None:
    fieldnames = [
        "record_id",
        "dataset_name",
        "prediction_dir",
        "sample_id",
        "decision_status",
        "review_route",
        "confidence_level",
        "title_block_position",
        "title_block_position_source",
        "frame_contact_side",
        "detected_rotation_degrees",
        "correction_degrees",
        "yolo_status",
        "selected_confidence",
        "opencv_status",
        "opencv_side",
        "ocr_status",
        "field_cluster_level",
        "missing_evidence",
        "conflicts",
        "dry_run_only",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            evidence = record["evidence"]
            arbitration = record["arbitration"]
            writer.writerow(
                {
                    "record_id": record["record_id"],
                    "dataset_name": record["page"]["dataset_name"],
                    "prediction_dir": record["page"]["prediction_dir"],
                    "sample_id": record["sample_id"],
                    "decision_status": arbitration["decision_status"],
                    "review_route": record["review_routing"]["route"],
                    "confidence_level": arbitration["confidence_level"],
                    "title_block_position": arbitration["title_block_position"],
                    "title_block_position_source": arbitration["title_block_position_source"],
                    "frame_contact_side": evidence["yolo_obb"]["frame_contact_side"],
                    "detected_rotation_degrees": record["rotation"]["detected_rotation_degrees"],
                    "correction_degrees": record["rotation"]["correction_degrees"],
                    "yolo_status": evidence["yolo_obb"]["status"],
                    "selected_confidence": evidence["yolo_obb"]["selected_confidence"],
                    "opencv_status": evidence["opencv"].get("status"),
                    "opencv_side": evidence["opencv"].get("title_block_side"),
                    "ocr_status": evidence["ocr"]["status"],
                    "field_cluster_level": evidence["ocr"]["field_cluster_level"],
                    "missing_evidence": ";".join(arbitration["missing_evidence"]),
                    "conflicts": ";".join(arbitration["conflicts"]),
                    "dry_run_only": record["output_plan"]["dry_run_only"],
                }
            )


def write_issue_csv(path: Path, records: list[dict[str, Any]], issue_key: str) -> None:
    fieldnames = [
        "record_id",
        "sample_id",
        "dataset_name",
        "decision_status",
        "review_route",
        "issue",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            issues = record["arbitration"].get(issue_key) or []
            for issue in issues:
                writer.writerow(
                    {
                        "record_id": record["record_id"],
                        "sample_id": record["sample_id"],
                        "dataset_name": record["page"]["dataset_name"],
                        "decision_status": record["arbitration"]["decision_status"],
                        "review_route": record["review_routing"]["route"],
                        "issue": issue,
                    }
                )


def write_needs_review_csv(path: Path, records: list[dict[str, Any]]) -> None:
    fieldnames = [
        "record_id",
        "sample_id",
        "dataset_name",
        "decision_status",
        "review_route",
        "review_priority",
        "title_block_position",
        "detected_rotation_degrees",
        "decision_reasons",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            if record["review_routing"]["route"] == "auto":
                continue
            writer.writerow(
                {
                    "record_id": record["record_id"],
                    "sample_id": record["sample_id"],
                    "dataset_name": record["page"]["dataset_name"],
                    "decision_status": record["arbitration"]["decision_status"],
                    "review_route": record["review_routing"]["route"],
                    "review_priority": record["review_routing"]["review_priority"],
                    "title_block_position": record["arbitration"]["title_block_position"],
                    "detected_rotation_degrees": record["rotation"]["detected_rotation_degrees"],
                    "decision_reasons": ";".join(record["arbitration"]["decision_reasons"]),
                }
            )


def build(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records, metadata = build_records(args)
    summary = summarize(records, metadata)

    records_path = output_dir / "arbitration_records.jsonl"
    summary_json_path = output_dir / "arbitration_summary.json"
    summary_csv_path = output_dir / "arbitration_summary.csv"
    missing_csv_path = output_dir / "missing_evidence.csv"
    conflicts_csv_path = output_dir / "conflicts.csv"
    needs_review_csv_path = output_dir / "needs_review.csv"

    write_jsonl(records_path, records)
    write_json(summary_json_path, summary)
    write_summary_csv(summary_csv_path, records)
    write_issue_csv(missing_csv_path, records, "missing_evidence")
    write_issue_csv(conflicts_csv_path, records, "conflicts")
    write_needs_review_csv(needs_review_csv_path, records)

    return {
        "output_dir": as_posix(output_dir),
        "arbitration_records": as_posix(records_path),
        "arbitration_summary": as_posix(summary_json_path),
        "arbitration_summary_csv": as_posix(summary_csv_path),
        "missing_evidence": as_posix(missing_csv_path),
        "conflicts": as_posix(conflicts_csv_path),
        "needs_review": as_posix(needs_review_csv_path),
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build read-only title block arbitration records from existing reports."
    )
    parser.add_argument("--yolo-reports", nargs="+", type=Path, default=DEFAULT_YOLO_REPORTS)
    parser.add_argument("--ocr-report", type=Path, default=DEFAULT_OCR_REPORT)
    parser.add_argument("--opencv-results", nargs="+", type=Path, default=DEFAULT_OPENCV_RESULTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    print(json.dumps(build(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

