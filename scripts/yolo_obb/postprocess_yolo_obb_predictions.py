from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from scripts.common.obb_utils import ROOT, polygon_area, resolve_path


DEFAULT_PREDICTIONS_DIR = ROOT / "local_data" / "yolo_predictions"
DEFAULT_DATASET_DIR = ROOT / "local_data" / "yolo_obb_dataset_round2"
DEFAULT_REVIEW_FORM = (
    ROOT
    / "local_data"
    / "review_inbox"
    / "archive"
    / "round2_prediction_review_20260627_reviewed"
    / "prediction_review"
    / "review_form.csv"
)
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "yolo_postprocess" / "round2_first_train"

REQUIRED_REVIEW_FIELDS = {"数据集", "样本编号", "预测框是否可接受", "问题类型", "备注"}

ROUND3_EXPECTED_NON_TITLE_TABLE_REJECTIONS = {
    ("round3_val", "aug90_002_from_sample_010"): 1,
    ("round3_round2_test", "aug90_002_from_sample_010"): 1,
}


@dataclass(frozen=True)
class PredictionLabel:
    class_id: int
    points: list[tuple[float, float]]
    confidence: float | None
    raw_line: str
    line_number: int


def as_posix(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_text_with_encodings(path: Path, encodings: tuple[str, ...]) -> tuple[str, str]:
    data = path.read_bytes()
    last_error: UnicodeDecodeError | None = None
    for encoding in encodings:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise UnicodeDecodeError("unknown", b"", 0, 1, "no encodings provided")


def load_review_form(path: Path) -> tuple[dict[tuple[str, str], dict[str, str]], str]:
    resolved = resolve_path(path)
    if not resolved.exists():
        return {}, "missing"
    last_rows: list[dict[str, str]] = []
    for encoding in ("utf-8-sig", "gbk"):
        try:
            text, used_encoding = read_text_with_encodings(resolved, (encoding,))
        except UnicodeDecodeError:
            continue
        rows = list(csv.DictReader(text.splitlines()))
        last_rows = rows
        fieldnames = set(rows[0].keys()) if rows else set()
        if REQUIRED_REVIEW_FIELDS.issubset(fieldnames):
            return {(row["数据集"], row["样本编号"]): row for row in rows}, used_encoding

    fieldnames = set(last_rows[0].keys()) if last_rows else set()
    missing = sorted(REQUIRED_REVIEW_FIELDS - fieldnames)
    raise ValueError(f"Review form missing required fields: {', '.join(missing)}")


def load_diagnostic_candidates(path: Path | None) -> dict[tuple[str, str, int], dict[str, Any]]:
    if path is None:
        return {}
    resolved = resolve_path(path)
    if not resolved.exists():
        return {}
    report = json.loads(resolved.read_text(encoding="utf-8"))
    candidates: dict[tuple[str, str, int], dict[str, Any]] = {}
    for candidate in report.get("candidates", []):
        key = (
            candidate["prediction_dir"],
            candidate["sample"],
            int(candidate["candidate_index"]),
        )
        candidates[key] = candidate
    return candidates


def parse_prediction_label_line(line: str, line_number: int) -> PredictionLabel:
    parts = line.split()
    if len(parts) not in (9, 10):
        raise ValueError(f"line {line_number}: expected 9 or 10 fields, got {len(parts)}")

    try:
        class_id = int(parts[0])
        values = [float(value) for value in parts[1:]]
    except ValueError as exc:
        raise ValueError(f"line {line_number}: label fields must be numeric") from exc

    coords = values[:8]
    confidence = values[8] if len(values) == 9 else None
    points = [(coords[index], coords[index + 1]) for index in range(0, len(coords), 2)]
    return PredictionLabel(
        class_id=class_id,
        points=points,
        confidence=confidence,
        raw_line=line,
        line_number=line_number,
    )


def load_prediction_labels(path: Path) -> tuple[list[PredictionLabel], list[str]]:
    labels: list[PredictionLabel] = []
    errors: list[str] = []
    if not path.exists():
        return labels, ["missing_prediction_label"]

    with path.open("r", encoding="utf-8") as f:
        for line_number, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                labels.append(parse_prediction_label_line(line, line_number))
            except ValueError as exc:
                errors.append(f"format_error:{exc}")
    return labels, errors


def bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def obb_axis_offset_degrees(points: list[tuple[float, float]]) -> float | None:
    if len(points) < 2:
        return None
    edge_offsets: list[tuple[float, float]] = []
    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % len(points)]
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length <= 0.0:
            continue
        angle = abs(math.degrees(math.atan2(dy, dx))) % 90.0
        axis_offset = min(angle, 90.0 - angle)
        edge_offsets.append((length, axis_offset))
    if not edge_offsets:
        return None
    return min(offset for _, offset in sorted(edge_offsets, reverse=True)[:2])


def detect_frame_lines(image_path: Path, config: dict[str, float]) -> dict[str, Any]:
    resolved = resolve_path(image_path)
    with Image.open(resolved) as image:
        gray = image.convert("L")
        width, height = gray.size
        pixels = gray.load()

        dark_threshold = int(config["frame_dark_threshold"])
        band = max(1, int(min(width, height) * config["frame_search_band"]))

        def dark_ratio_column(x: int) -> float:
            dark = 0
            for y in range(height):
                if pixels[x, y] <= dark_threshold:
                    dark += 1
            return dark / height

        def dark_ratio_row(y: int) -> float:
            dark = 0
            for x in range(width):
                if pixels[x, y] <= dark_threshold:
                    dark += 1
            return dark / width

        def strongest_column(start: int, stop: int) -> tuple[int, float]:
            best_index = start
            best_strength = -1.0
            for x in range(start, stop):
                strength = dark_ratio_column(x)
                if strength > best_strength:
                    best_index = x
                    best_strength = strength
            return best_index, best_strength

        def strongest_row(start: int, stop: int) -> tuple[int, float]:
            best_index = start
            best_strength = -1.0
            for y in range(start, stop):
                strength = dark_ratio_row(y)
                if strength > best_strength:
                    best_index = y
                    best_strength = strength
            return best_index, best_strength

        left_x, left_strength = strongest_column(0, min(band, width))
        right_x, right_strength = strongest_column(max(0, width - band), width)
        top_y, top_strength = strongest_row(0, min(band, height))
        bottom_y, bottom_strength = strongest_row(max(0, height - band), height)

    weak_threshold = config["frame_weak_threshold"]

    def side_record(axis_index: int, max_index: int, strength: float) -> dict[str, Any]:
        detected = strength >= weak_threshold
        return {
            "detected": detected,
            "position_normalized": axis_index / max(1, max_index) if detected else None,
            "strength": strength,
        }

    return {
        "image": as_posix(resolved),
        "width": width,
        "height": height,
        "config": {
            "frame_search_band": config["frame_search_band"],
            "frame_dark_threshold": config["frame_dark_threshold"],
            "frame_weak_threshold": config["frame_weak_threshold"],
        },
        "sides": {
            "left": side_record(left_x, width - 1, left_strength),
            "right": side_record(right_x, width - 1, right_strength),
            "top": side_record(top_y, height - 1, top_strength),
            "bottom": side_record(bottom_y, height - 1, bottom_strength),
        },
    }


def frame_contact_features(
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    frame_detection: dict[str, Any] | None,
    config: dict[str, float],
) -> dict[str, Any]:
    side_distances = {
        "left": abs(xmin),
        "right": abs(1.0 - xmax),
        "top": abs(ymin),
        "bottom": abs(1.0 - ymax),
    }
    page_nearest_side = min(side_distances, key=side_distances.get)
    if not frame_detection:
        return {
            "nearest_frame_side": page_nearest_side,
            "frame_line_position_normalized": None,
            "frame_contact_gap_normalized": None,
            "frame_contact_score": 0.0,
            "touches_frame_line": False,
            "frame_contact_status": "unknown",
        }

    candidate_edges = {
        "left": xmin,
        "right": xmax,
        "top": ymin,
        "bottom": ymax,
    }
    contact_options: list[tuple[float, str, float]] = []
    for side, candidate_edge in candidate_edges.items():
        side_record = frame_detection["sides"][side]
        frame_position = side_record["position_normalized"]
        if side_record["detected"] and frame_position is not None:
            contact_options.append((abs(candidate_edge - frame_position), side, frame_position))

    if not contact_options:
        return {
            "nearest_frame_side": page_nearest_side,
            "frame_line_position_normalized": None,
            "frame_contact_gap_normalized": None,
            "frame_contact_score": 0.0,
            "touches_frame_line": False,
            "frame_contact_status": "unknown",
        }

    gap, nearest_side, frame_position = min(contact_options, key=lambda item: item[0])
    side_record = frame_detection["sides"][nearest_side]
    frame_position = side_record["position_normalized"]
    if not side_record["detected"] or frame_position is None:
        return {
            "nearest_frame_side": nearest_side,
            "frame_line_position_normalized": None,
            "frame_contact_gap_normalized": None,
            "frame_contact_score": 0.0,
            "touches_frame_line": False,
            "frame_contact_status": "unknown",
        }

    threshold = config["frame_contact_threshold"]
    score = clamp(1.0 - (gap / threshold), 0.0, 1.0)
    touches = gap <= threshold
    return {
        "nearest_frame_side": nearest_side,
        "frame_line_position_normalized": frame_position,
        "frame_contact_gap_normalized": gap,
        "frame_contact_score": score,
        "touches_frame_line": touches,
        "frame_contact_status": "contact" if touches else "gap",
    }


def teacher_rule_features(
    flags: list[str],
    frame_contact: dict[str, Any],
    diagnostic_candidate: dict[str, Any] | None,
    axis_offset_degrees: float | None,
    config: dict[str, float],
) -> dict[str, Any]:
    rule_flags: list[str] = []
    evidence: list[str] = []
    adjustment = 0.0

    diagnostic_flags = set(diagnostic_candidate.get("diagnostic_flags") or []) if diagnostic_candidate else set()
    cell_area_variance = (
        float(diagnostic_candidate.get("cell_area_variance") or 0.0)
        if diagnostic_candidate
        else 0.0
    )
    small_large_mix = (
        float(diagnostic_candidate.get("small_large_cell_mix_score") or 0.0)
        if diagnostic_candidate
        else 0.0
    )
    touches_frame = bool(frame_contact.get("touches_frame_line"))
    frame_contact_score = float(frame_contact.get("frame_contact_score") or 0.0)
    near_edge = "near_edge" in flags
    uniform_grid_like = "uniform_grid_like" in flags or "uniform_grid_like" in diagnostic_flags
    has_structure_proxy = (
        cell_area_variance >= config["teacher_cell_variance_threshold"]
        or small_large_mix >= config["teacher_small_large_mix_threshold"]
    )

    if touches_frame and near_edge and has_structure_proxy:
        rule_flags.append("teacher_frame_field_proxy_positive")
        evidence.append("frame_contact_and_non_uniform_structure_proxy")
        adjustment += config["teacher_positive_adjustment"]

    if (
        touches_frame
        and not uniform_grid_like
        and frame_contact_score >= config["teacher_faint_scan_frame_score"]
    ):
        rule_flags.append("teacher_faint_scan_confidence_proxy")
        evidence.append("strong_frame_contact_for_faint_or_ocr_unavailable_case")
        adjustment += config["teacher_faint_scan_adjustment"]

    if uniform_grid_like:
        rule_flags.append("teacher_uniform_table_negative")
        evidence.append("uniform_grid_like_without_title_block_field_proxy")
        adjustment -= config["teacher_uniform_table_penalty"]

    if (
        diagnostic_candidate
        and touches_frame
        and near_edge
        and not uniform_grid_like
        and axis_offset_degrees is not None
        and axis_offset_degrees <= config["teacher_small_angle_max_degrees"]
        and small_large_mix >= config["teacher_small_angle_mix_threshold"]
    ):
        rule_flags.append("teacher_small_angle_tolerated")
        evidence.append("candidate_covers_frame_contact_title_block_structure")
        adjustment += config["teacher_small_angle_adjustment"]

    return {
        "teacher_rule_flags": list(dict.fromkeys(rule_flags)),
        "teacher_rule_adjustment": adjustment,
        "teacher_rule_evidence": list(dict.fromkeys(evidence)),
    }


def candidate_features(
    label: PredictionLabel,
    candidate_index: int,
    config: dict[str, float],
    frame_detection: dict[str, Any] | None,
    diagnostic_candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    xmin, ymin, xmax, ymax = bbox(label.points)
    width = max(0.0, xmax - xmin)
    height = max(0.0, ymax - ymin)
    center_x = (xmin + xmax) / 2.0
    center_y = (ymin + ymax) / 2.0
    area = polygon_area(label.points)
    min_edge_distance = min(xmin, ymin, 1.0 - xmax, 1.0 - ymax)
    edge_threshold = config["edge_threshold"]
    edge_proximity_score = clamp(1.0 - (max(0.0, min_edge_distance) / edge_threshold), 0.0, 1.0)

    in_center = (
        config["center_min"] <= center_x <= config["center_max"]
        and config["center_min"] <= center_y <= config["center_max"]
    )
    out_of_bounds = any(x < 0.0 or x > 1.0 or y < 0.0 or y > 1.0 for x, y in label.points)
    size_abnormal = area < config["min_area"] or area > config["max_area"]
    near_edge = min_edge_distance <= edge_threshold
    frame_contact = frame_contact_features(xmin, ymin, xmax, ymax, frame_detection, config)

    flags: list[str] = []
    if in_center:
        flags.append("center_region")
    if out_of_bounds:
        flags.append("out_of_page_bounds")
    if size_abnormal:
        flags.append("size_abnormal")
    if near_edge:
        flags.append("near_edge")
    if frame_contact["touches_frame_line"]:
        flags.append("touches_frame_line")
    elif frame_contact["frame_contact_status"] == "gap":
        flags.append("frame_contact_gap")
    else:
        flags.append("frame_contact_unknown")

    confidence = label.confidence if label.confidence is not None else 0.0
    target_area = config["target_area"]
    size_score = clamp(1.0 - abs(area - target_area) / target_area, 0.0, 1.0)
    center_penalty = 1.0 if in_center else 0.0
    boundary_penalty = 1.0 if out_of_bounds else 0.0
    size_penalty = 0.5 if size_abnormal else 0.0
    uniform_grid_penalty = 0.0
    cell_area_variance = None
    diagnostic_flags: list[str] = []
    if diagnostic_candidate:
        uniform_grid_penalty = float(diagnostic_candidate.get("uniform_grid_penalty") or 0.0)
        cell_area_variance = diagnostic_candidate.get("cell_area_variance")
        diagnostic_flags = list(diagnostic_candidate.get("diagnostic_flags") or [])
        if "uniform_grid_like" in diagnostic_flags:
            flags.append("uniform_grid_like")

    axis_offset_degrees = obb_axis_offset_degrees(label.points)
    teacher_rules = teacher_rule_features(
        flags,
        frame_contact,
        diagnostic_candidate,
        axis_offset_degrees,
        config,
    )

    score = (
        confidence
        + 0.25 * edge_proximity_score
        + 0.25 * frame_contact["frame_contact_score"]
        + 0.20 * size_score
        - 0.55 * center_penalty
    )
    score -= 0.50 * boundary_penalty + size_penalty + 0.35 * uniform_grid_penalty
    score += teacher_rules["teacher_rule_adjustment"]

    return {
        "candidate_index": candidate_index,
        "class_id": label.class_id,
        "confidence": label.confidence,
        "points_normalized": [[x, y] for x, y in label.points],
        "area_normalized": area,
        "bbox_xyxy_normalized": [xmin, ymin, xmax, ymax],
        "width_normalized": width,
        "height_normalized": height,
        "center_xy_normalized": [center_x, center_y],
        "touches_or_near_edge": near_edge,
        "center_region_penalty": center_penalty,
        "boundary_penalty": boundary_penalty,
        "size_score": size_score,
        "edge_proximity_score": edge_proximity_score,
        "uniform_grid_penalty": uniform_grid_penalty,
        "cell_area_variance": cell_area_variance,
        "axis_offset_degrees": axis_offset_degrees,
        "diagnostic_flags": diagnostic_flags,
        **teacher_rules,
        **frame_contact,
        "candidate_score": score,
        "candidate_flags": flags,
        "raw_line": label.raw_line,
    }


def rejection_reasons(
    record_key: tuple[str, str],
    candidate: dict[str, Any],
    selected_index: int | None,
) -> list[str]:
    reasons = ["not_selected_by_single_title_block_rule"]
    if candidate["candidate_index"] != selected_index:
        reasons.append("lower_score_duplicate_or_neighbor")
    if "uniform_grid_like" in candidate["candidate_flags"]:
        reasons.append("uniform_grid_like")
    if "teacher_uniform_table_negative" in candidate.get("teacher_rule_flags", []):
        reasons.append("teacher_uniform_table_negative")
    if (
        record_key in ROUND3_EXPECTED_NON_TITLE_TABLE_REJECTIONS
        and candidate["candidate_index"] == ROUND3_EXPECTED_NON_TITLE_TABLE_REJECTIONS[record_key]
    ):
        reasons.append("non_title_table_false_positive")
    if (
        "center_region" in candidate["candidate_flags"]
        and "touches_frame_line" not in candidate["candidate_flags"]
    ):
        reasons.append("center_region_without_frame_contact")
    if "out_of_page_bounds" in candidate["candidate_flags"]:
        reasons.append("out_of_page_bounds")
    if "size_abnormal" in candidate["candidate_flags"]:
        reasons.append("size_abnormal")
    return list(dict.fromkeys(reasons))


def classify_record(
    prediction_dir_name: str,
    split: str,
    sample: str,
    labels: list[PredictionLabel],
    label_errors: list[str],
    review_row: dict[str, str] | None,
    config: dict[str, float],
    frame_detection: dict[str, Any] | None,
    diagnostic_candidates: dict[tuple[str, str, int], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    candidates = [
        candidate_features(
            label,
            index,
            config,
            frame_detection,
            (diagnostic_candidates or {}).get((prediction_dir_name, sample, index)),
        )
        for index, label in enumerate(labels)
    ]
    candidates.sort(key=lambda item: item["candidate_score"], reverse=True)
    selected = candidates[0] if candidates else None
    selected_index = selected["candidate_index"] if selected else None
    rejected_candidates = [
        {
            **candidate,
            "rejection_reasons": rejection_reasons(
                (prediction_dir_name, sample),
                candidate,
                selected_index,
            ),
        }
        for candidate in candidates[1:]
    ]

    issue_types: list[str] = []
    if label_errors:
        issue_types.extend(label_errors)
    if not labels:
        issue_types.append("missing_title_block")

    prediction_count = len(labels)
    if prediction_count > 1:
        issue_types.append("multi_candidate_resolved")

    if selected:
        selected_flags = set(selected["candidate_flags"])
        if "center_region" in selected_flags and "touches_frame_line" not in selected_flags:
            issue_types.append("part_false_positive")
        if "out_of_page_bounds" in selected_flags:
            issue_types.append("out_of_page_bounds")
        if "size_abnormal" in selected_flags:
            issue_types.append("boundary_too_large")

    for candidate in rejected_candidates:
        flags = set(candidate["candidate_flags"])
        if (
            "center_region" in flags
            and "touches_frame_line" not in flags
            and "part_false_positive" not in issue_types
        ):
            issue_types.append("part_false_positive")
        if "out_of_page_bounds" in flags and "out_of_page_bounds" not in issue_types:
            issue_types.append("out_of_page_bounds")
        if "size_abnormal" in flags and "boundary_too_large" not in issue_types:
            issue_types.append("boundary_too_large")

    manual_acceptance = ""
    manual_problem_type = ""
    notes = ""
    if review_row:
        manual_acceptance = review_row.get("预测框是否可接受", "")
        manual_problem_type = review_row.get("问题类型", "")
        notes = review_row.get("备注", "")
        if manual_acceptance == "不可接受":
            issue_types.append("manual_rejected")
            if "没有被完全框住" in manual_problem_type:
                issue_types.append("partial_title_block")
            if "超出" in manual_problem_type or "延展" in manual_problem_type:
                issue_types.append("boundary_too_large")
            if "零件" in manual_problem_type:
                issue_types.append("part_false_positive")

    issue_types = list(dict.fromkeys(issue_types))
    if not labels:
        status = "needs_review"
    elif "manual_rejected" in issue_types:
        status = "needs_review"
    elif "expected_false_positive_not_rejected" in issue_types:
        status = "needs_review"
    elif issue_types:
        blocking_issues = {
            "part_false_positive",
            "out_of_page_bounds",
            "boundary_too_large",
            "partial_title_block",
            "format_error",
        }
        status = "needs_review" if blocking_issues.intersection(issue_types) else "accepted"
    else:
        status = "accepted"

    expected_reject_index = ROUND3_EXPECTED_NON_TITLE_TABLE_REJECTIONS.get(
        (prediction_dir_name, sample)
    )
    if expected_reject_index is not None:
        rejected_indices = {candidate["candidate_index"] for candidate in rejected_candidates}
        if expected_reject_index not in rejected_indices:
            issue_types.append("expected_false_positive_not_rejected")
            status = "needs_review"

    return {
        "prediction_dir": prediction_dir_name,
        "split": split,
        "sample": sample,
        "prediction_count": prediction_count,
        "status": status,
        "issue_types": issue_types,
        "selected_candidate_index": selected["candidate_index"] if selected else None,
        "selected_confidence": selected["confidence"] if selected else None,
        "selected_score": selected["candidate_score"] if selected else None,
        "selected_title_block": selected,
        "rejected_candidates": rejected_candidates,
        "manual_acceptance": manual_acceptance,
        "manual_problem_type": manual_problem_type,
        "notes": notes,
        "frame_detection": frame_detection,
        "candidates": candidates,
    }


def collect_samples(predictions_dir: Path, splits: list[str]) -> list[tuple[str, str]]:
    samples: list[tuple[str, str, str]] = []
    for split in splits:
        split_dir = predictions_dir / f"round2_{split}"
        if not split_dir.exists():
            raise FileNotFoundError(f"Missing prediction directory: {split_dir}")
        for image_path in sorted(split_dir.glob("*.jpg")):
            samples.append((f"round2_{split}", split, image_path.stem))
    return samples


def infer_split_from_prediction_dir(prediction_dir_name: str) -> str:
    if prediction_dir_name.endswith("_train"):
        return "train"
    if prediction_dir_name.endswith("_val"):
        return "val"
    if prediction_dir_name.endswith("_test"):
        return "test"
    if prediction_dir_name in {"train", "val", "test"}:
        return prediction_dir_name
    return prediction_dir_name.rsplit("_", 1)[-1]


def collect_samples_from_prediction_dirs(
    predictions_dir: Path,
    prediction_dirs: list[str],
    diagnostic_candidates: dict[tuple[str, str, int], dict[str, Any]],
    diagnostic_only: bool,
) -> list[tuple[str, str, str]]:
    samples: list[tuple[str, str, str]] = []
    if diagnostic_only:
        keys = sorted({(key[0], key[1]) for key in diagnostic_candidates})
        return [
            (prediction_dir_name, infer_split_from_prediction_dir(prediction_dir_name), sample)
            for prediction_dir_name, sample in keys
            if not prediction_dirs or prediction_dir_name in prediction_dirs
        ]
    for prediction_dir_name in prediction_dirs:
        split_dir = predictions_dir / prediction_dir_name
        if not split_dir.exists():
            raise FileNotFoundError(f"Missing prediction directory: {split_dir}")
        split = infer_split_from_prediction_dir(prediction_dir_name)
        for image_path in sorted(split_dir.glob("*.jpg")):
            samples.append((prediction_dir_name, split, image_path.stem))
    return samples


def path_record(
    predictions_dir: Path,
    dataset_dir: Path,
    prediction_dir_name: str,
    split: str,
    sample: str,
    dataset_image_path: Path | None = None,
) -> dict[str, str]:
    dataset_image = dataset_image_path or dataset_dir / "images" / split / f"{sample}.png"
    return {
        "prediction_image": as_posix(predictions_dir / prediction_dir_name / f"{sample}.jpg"),
        "prediction_label": as_posix(predictions_dir / prediction_dir_name / "labels" / f"{sample}.txt"),
        "dataset_image": as_posix(dataset_image),
        "ground_truth_label": as_posix(dataset_dir / "labels" / split / f"{sample}.txt"),
    }


def build_failure_manifest(
    records: list[dict[str, Any]],
    predictions_dir: Path,
    dataset_dir: Path,
    positive_controls: int,
) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str]] = set()

    def add(record: dict[str, Any], group: str) -> None:
        key = (record["prediction_dir"], record["sample"])
        if key in selected_keys:
            return
        selected_keys.add(key)
        paths = record["paths"]
        manifest.append(
            {
                "split": record["split"],
                "sample": record["sample"],
                "reason": ";".join(record["issue_types"]) or "positive_control",
                "status": record["status"],
                "suggested_review_group": group,
                **paths,
            }
        )

    for record in records:
        if record["status"] != "accepted" or record["manual_acceptance"] == "不可接受":
            add(record, "failure")

    controls_added = 0
    for record in records:
        if controls_added >= positive_controls:
            break
        if record["status"] == "accepted" and record["manual_acceptance"] == "可以接受":
            add(record, "positive_control")
            controls_added += 1

    return manifest


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_summary_csv(path: Path, records: list[dict[str, Any]]) -> None:
    fieldnames = [
        "prediction_dir",
        "split",
        "sample",
        "prediction_count",
        "status",
        "issue_types",
        "selected_candidate_index",
        "selected_confidence",
        "selected_score",
        "manual_acceptance",
        "manual_problem_type",
        "notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "split": record["split"],
                    "prediction_dir": record["prediction_dir"],
                    "sample": record["sample"],
                    "prediction_count": record["prediction_count"],
                    "status": record["status"],
                    "issue_types": ";".join(record["issue_types"]),
                    "selected_candidate_index": record["selected_candidate_index"],
                    "selected_confidence": record["selected_confidence"],
                    "selected_score": record["selected_score"],
                    "manual_acceptance": record["manual_acceptance"],
                    "manual_problem_type": record["manual_problem_type"],
                    "notes": record["notes"],
                }
            )


def summarize(records: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "total": len(records),
        "accepted": 0,
        "needs_review": 0,
        "rejected": 0,
        "missing_prediction_label": 0,
        "multi_candidate": 0,
        "part_false_positive": 0,
        "boundary_or_size_issue": 0,
        "manual_rejected": 0,
        "multi_candidate_resolved": 0,
        "rejected_candidates": 0,
    }
    for record in records:
        status = record["status"]
        if status in summary:
            summary[status] += 1
        issues = set(record["issue_types"])
        if "missing_prediction_label" in issues or "missing_title_block" in issues:
            summary["missing_prediction_label"] += 1
        if "multi_candidate" in issues or "multi_candidate_resolved" in issues:
            summary["multi_candidate"] += 1
        if "multi_candidate_resolved" in issues:
            summary["multi_candidate_resolved"] += 1
        if "part_false_positive" in issues:
            summary["part_false_positive"] += 1
        if "boundary_too_large" in issues or "out_of_page_bounds" in issues:
            summary["boundary_or_size_issue"] += 1
        if "manual_rejected" in issues:
            summary["manual_rejected"] += 1
        summary["rejected_candidates"] += len(record.get("rejected_candidates") or [])
    return summary


def write_candidate_csvs(output_dir: Path, records: list[dict[str, Any]]) -> dict[str, str]:
    selected_path = output_dir / "selected_candidates.csv"
    rejected_path = output_dir / "rejected_candidates.csv"
    selected_fields = [
        "prediction_dir",
        "split",
        "sample",
        "status",
        "issue_types",
        "selected_candidate_index",
        "selected_confidence",
        "selected_score",
        "frame_contact_score",
        "candidate_flags",
        "teacher_rule_flags",
        "teacher_rule_adjustment",
        "teacher_rule_evidence",
    ]
    rejected_fields = [
        "prediction_dir",
        "split",
        "sample",
        "candidate_index",
        "confidence",
        "candidate_score",
        "rejection_reasons",
        "candidate_flags",
        "teacher_rule_flags",
        "teacher_rule_adjustment",
        "teacher_rule_evidence",
    ]
    with selected_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=selected_fields)
        writer.writeheader()
        for record in records:
            selected = record.get("selected_title_block")
            if not selected:
                continue
            writer.writerow(
                {
                    "prediction_dir": record["prediction_dir"],
                    "split": record["split"],
                    "sample": record["sample"],
                    "status": record["status"],
                    "issue_types": ";".join(record["issue_types"]),
                    "selected_candidate_index": selected["candidate_index"],
                    "selected_confidence": selected["confidence"],
                    "selected_score": selected["candidate_score"],
                    "frame_contact_score": selected["frame_contact_score"],
                    "candidate_flags": ";".join(selected["candidate_flags"]),
                    "teacher_rule_flags": ";".join(selected["teacher_rule_flags"]),
                    "teacher_rule_adjustment": selected["teacher_rule_adjustment"],
                    "teacher_rule_evidence": ";".join(selected["teacher_rule_evidence"]),
                }
            )
    with rejected_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rejected_fields)
        writer.writeheader()
        for record in records:
            for candidate in record.get("rejected_candidates") or []:
                writer.writerow(
                    {
                        "prediction_dir": record["prediction_dir"],
                        "split": record["split"],
                        "sample": record["sample"],
                        "candidate_index": candidate["candidate_index"],
                        "confidence": candidate["confidence"],
                        "candidate_score": candidate["candidate_score"],
                        "rejection_reasons": ";".join(candidate["rejection_reasons"]),
                        "candidate_flags": ";".join(candidate["candidate_flags"]),
                        "teacher_rule_flags": ";".join(candidate["teacher_rule_flags"]),
                        "teacher_rule_adjustment": candidate["teacher_rule_adjustment"],
                        "teacher_rule_evidence": ";".join(candidate["teacher_rule_evidence"]),
                    }
                )
    return {
        "selected_candidates": str(selected_path),
        "rejected_candidates": str(rejected_path),
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    predictions_dir = resolve_path(args.predictions_dir)
    dataset_dir = resolve_path(args.dataset_dir)
    review_form = resolve_path(args.review_form)
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    diagnostic_candidates = load_diagnostic_candidates(args.diagnostic_report)

    config = {
        "center_min": args.center_min,
        "center_max": args.center_max,
        "edge_threshold": args.edge_threshold,
        "frame_search_band": args.frame_search_band,
        "frame_contact_threshold": args.frame_contact_threshold,
        "frame_dark_threshold": args.frame_dark_threshold,
        "frame_weak_threshold": args.frame_weak_threshold,
        "min_area": args.min_area,
        "max_area": args.max_area,
        "target_area": args.target_area,
        "teacher_cell_variance_threshold": args.teacher_cell_variance_threshold,
        "teacher_small_large_mix_threshold": args.teacher_small_large_mix_threshold,
        "teacher_small_angle_mix_threshold": args.teacher_small_angle_mix_threshold,
        "teacher_small_angle_max_degrees": args.teacher_small_angle_max_degrees,
        "teacher_faint_scan_frame_score": args.teacher_faint_scan_frame_score,
        "teacher_positive_adjustment": args.teacher_positive_adjustment,
        "teacher_faint_scan_adjustment": args.teacher_faint_scan_adjustment,
        "teacher_small_angle_adjustment": args.teacher_small_angle_adjustment,
        "teacher_uniform_table_penalty": args.teacher_uniform_table_penalty,
    }

    review_rows, review_encoding = load_review_form(review_form)
    records: list[dict[str, Any]] = []
    if args.prediction_dirs:
        sample_records = collect_samples_from_prediction_dirs(
            predictions_dir,
            args.prediction_dirs,
            diagnostic_candidates,
            args.diagnostic_only,
        )
    else:
        sample_records = collect_samples(predictions_dir, args.splits)

    for prediction_dir_name, split, sample in sample_records:
        label_path = predictions_dir / prediction_dir_name / "labels" / f"{sample}.txt"
        diagnostic_source = None
        for index in range(0, 100):
            diagnostic = diagnostic_candidates.get((prediction_dir_name, sample, index))
            if diagnostic and diagnostic.get("source_image"):
                diagnostic_source = resolve_path(Path(diagnostic["source_image"]))
                break
        dataset_image_path = diagnostic_source or dataset_dir / "images" / split / f"{sample}.png"
        labels, label_errors = load_prediction_labels(label_path)
        review_row = review_rows.get((split, sample))
        frame_detection = detect_frame_lines(dataset_image_path, config)
        record = classify_record(
            prediction_dir_name,
            split,
            sample,
            labels,
            label_errors,
            review_row,
            config,
            frame_detection,
            diagnostic_candidates,
        )
        record["paths"] = path_record(
            predictions_dir,
            dataset_dir,
            prediction_dir_name,
            split,
            sample,
            dataset_image_path,
        )
        records.append(record)

    summary = summarize(records)
    report = {
        "config": config,
        "review_form": as_posix(review_form),
        "review_form_encoding": review_encoding,
        "predictions_dir": as_posix(predictions_dir),
        "dataset_dir": as_posix(dataset_dir),
        "summary": summary,
        "records": records,
    }
    manifest = build_failure_manifest(records, predictions_dir, dataset_dir, args.positive_controls)

    report_path = output_dir / "postprocess_report.json"
    summary_path = output_dir / "postprocess_summary.csv"
    manifest_path = output_dir / "failure_case_manifest.json"
    write_json(report_path, report)
    write_summary_csv(summary_path, records)
    write_json(manifest_path, manifest)
    candidate_paths = write_candidate_csvs(output_dir, records)

    return {
        "output_dir": str(output_dir),
        "postprocess_report": str(report_path),
        "postprocess_summary": str(summary_path),
        "failure_case_manifest": str(manifest_path),
        **candidate_paths,
        "summary": summary,
        "manifest_records": len(manifest),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Postprocess YOLO/OBB prediction labels.")
    parser.add_argument("--predictions-dir", type=Path, default=DEFAULT_PREDICTIONS_DIR)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--review-form", type=Path, default=DEFAULT_REVIEW_FORM)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--splits", nargs="+", default=["val", "test"])
    parser.add_argument("--prediction-dirs", nargs="*", default=None)
    parser.add_argument("--diagnostic-report", type=Path, default=None)
    parser.add_argument("--diagnostic-only", action="store_true")
    parser.add_argument("--positive-controls", type=int, default=3)
    parser.add_argument("--center-min", type=float, default=0.20)
    parser.add_argument("--center-max", type=float, default=0.80)
    parser.add_argument("--edge-threshold", type=float, default=0.12)
    parser.add_argument("--frame-search-band", type=float, default=0.18)
    parser.add_argument("--frame-contact-threshold", type=float, default=0.025)
    parser.add_argument("--frame-dark-threshold", type=float, default=190)
    parser.add_argument("--frame-weak-threshold", type=float, default=0.004)
    parser.add_argument("--min-area", type=float, default=0.001)
    parser.add_argument("--max-area", type=float, default=0.20)
    parser.add_argument("--target-area", type=float, default=0.04)
    parser.add_argument("--teacher-cell-variance-threshold", type=float, default=0.80)
    parser.add_argument("--teacher-small-large-mix-threshold", type=float, default=0.55)
    parser.add_argument("--teacher-small-angle-mix-threshold", type=float, default=0.80)
    parser.add_argument("--teacher-small-angle-max-degrees", type=float, default=5.0)
    parser.add_argument("--teacher-faint-scan-frame-score", type=float, default=0.65)
    parser.add_argument("--teacher-positive-adjustment", type=float, default=0.08)
    parser.add_argument("--teacher-faint-scan-adjustment", type=float, default=0.04)
    parser.add_argument("--teacher-small-angle-adjustment", type=float, default=0.03)
    parser.add_argument("--teacher-uniform-table-penalty", type=float, default=0.12)
    args = parser.parse_args()

    summary = build(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

