from __future__ import annotations

import argparse
import csv
import importlib.util
import html
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from scripts.common.obb_utils import ROOT, polygon_area, resolve_path
from scripts.yolo_obb.postprocess_yolo_obb_predictions import (
    detect_frame_lines,
    frame_contact_features,
)


DEFAULT_PREDICTIONS_DIR = ROOT / "local_data" / "yolo_predictions"
DEFAULT_MANIFEST = ROOT / "local_data" / "yolo_obb_dataset_round3" / "round3_manifest.csv"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "title_block_ocr_diagnostic"

TARGET_SAMPLES = [
    "sample_001",
    "unclear90_001_from_sample_001",
    "sample_009",
    "sample_010",
    "sample_020",
    "aug90_002_from_sample_010",
    "aug90_007_from_sample_020",
    "sample_040",
]

PREDICTION_DIRS = [
    "round3_train",
    "round3_val",
    "round3_round2_test",
    "round3_round2_val",
]

ROLE_FIELD_GROUPS = {
    "设计": ["设计"],
    "制图": ["制图"],
    "校对": ["校对"],
    "工艺": ["工艺"],
    "标准": ["标准", "标准化"],
    "审核": ["审核"],
    "批准": ["批准"],
    "日期": ["日期"],
}

PROPERTY_FIELD_GROUPS = {
    "图名": ["图名", "名称"],
    "图号": ["图号", "图样代号"],
    "材料": ["材料"],
    "比例": ["比例"],
    "重量": ["重量"],
    "表面积": ["表面积"],
    "单位": ["单位"],
}

OCR_PYTHON_ENGINES = [
    "rapidocr",
    "pytesseract",
    "paddleocr",
    "easyocr",
    "rapidocr_onnxruntime",
    "cnocr",
]

_RAPIDOCR_ENGINE: Any | None = None


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


def html_rel_path(target: str | Path, html_path: Path) -> str:
    target_path = resolve_path(Path(target))
    return Path(os.path.relpath(target_path, html_path.parent)).as_posix()


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def detect_ocr_capability() -> dict[str, Any]:
    python_engines = {
        engine: bool(importlib.util.find_spec(engine))
        for engine in OCR_PYTHON_ENGINES
    }
    command_engines = {
        "tesseract": shutil.which("tesseract") is not None,
    }
    available_python = [name for name, available in python_engines.items() if available]
    available_commands = [name for name, available in command_engines.items() if available]
    available = bool(available_python or available_commands)
    missing = [
        *[name for name, available in python_engines.items() if not available],
        *[name for name, available in command_engines.items() if not available],
    ]
    return {
        "available": available,
        "python_engines": python_engines,
        "command_engines": command_engines,
        "available_engines": available_python + available_commands,
        "missing_engines": missing,
    }


def decide_ocr_probe(ocr_capability: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    if not ocr_capability["available"]:
        return "ocr_unavailable_locally"
    ok_candidates = [candidate for candidate in candidates if candidate["ocr_status"] == "ok"]
    if not ok_candidates:
        return "ocr_no_successful_candidate"
    strong_candidates = [
        candidate
        for candidate in ok_candidates
        if len(candidate["role_field_hits"]) >= 2 and len(candidate["property_field_hits"]) >= 2
    ]
    if len(strong_candidates) >= max(2, len(ok_candidates) // 2):
        return "ocr_field_cluster_candidate"
    return "ocr_not_reliable_for_current_scans"


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
    return PredictionLabel(class_id, points, confidence, line, line_number)


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


def load_manifest(path: Path) -> dict[str, dict[str, str]]:
    resolved = resolve_path(path)
    records: dict[str, dict[str, str]] = {}
    with resolved.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            sample = row["sample"]
            records[sample] = row
    return records


def bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def normalized_to_pixels(
    points: list[tuple[float, float]], width: int, height: int
) -> list[tuple[int, int]]:
    return [
        (
            int(round(clamp(x, 0.0, 1.0) * (width - 1))),
            int(round(clamp(y, 0.0, 1.0) * (height - 1))),
        )
        for x, y in points
    ]


def side_from_bbox(xmin: float, ymin: float, xmax: float, ymax: float) -> str:
    distances = {
        "left": xmin,
        "right": 1.0 - xmax,
        "top": ymin,
        "bottom": 1.0 - ymax,
    }
    return min(distances, key=distances.get)


def rotation_from_side(side: str) -> int:
    return {"bottom": 0, "left": 90, "top": 180, "right": 270}.get(side, -1)


def position_prior_score(side: str) -> float:
    return 1.0 if side in {"bottom", "left", "top", "right"} else 0.0


def find_source_image(
    sample: str,
    prediction_image: Path,
    manifest_records: dict[str, dict[str, str]],
) -> Path:
    row = manifest_records.get(sample)
    if row and row.get("image_path"):
        candidate = resolve_path(Path(row["image_path"]))
        if candidate.exists():
            return candidate
    return prediction_image


def collect_prediction_records(
    predictions_dir: Path,
    target_samples: list[str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    target_set = set(target_samples)
    for prediction_dir_name in PREDICTION_DIRS:
        prediction_dir = predictions_dir / prediction_dir_name
        if not prediction_dir.exists():
            continue
        for image_path in sorted(prediction_dir.glob("*.jpg")):
            sample = image_path.stem
            if sample not in target_set:
                continue
            label_path = prediction_dir / "labels" / f"{sample}.txt"
            records.append(
                {
                    "prediction_dir": prediction_dir_name,
                    "sample": sample,
                    "prediction_image": image_path,
                    "prediction_label": label_path,
                }
            )
    return records


def crop_candidate(
    image: Image.Image,
    label: PredictionLabel,
    padding_ratio: float,
) -> tuple[Image.Image, dict[str, int]]:
    width, height = image.size
    pixel_points = normalized_to_pixels(label.points, width, height)
    xs = [point[0] for point in pixel_points]
    ys = [point[1] for point in pixel_points]
    pad = int(round(max(width, height) * padding_ratio))
    left = max(0, min(xs) - pad)
    top = max(0, min(ys) - pad)
    right = min(width, max(xs) + pad)
    bottom = min(height, max(ys) + pad)
    if right <= left:
        right = min(width, left + 1)
    if bottom <= top:
        bottom = min(height, top + 1)
    return image.crop((left, top, right, bottom)), {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "width": right - left,
        "height": bottom - top,
    }


def draw_overlay(
    image: Image.Image,
    candidates: list[dict[str, Any]],
    output_path: Path,
) -> None:
    canvas = image.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()

    width, height = canvas.size
    colors = ["red", "blue", "green", "purple", "orange"]
    for candidate in candidates:
        index = candidate["candidate_index"]
        points = normalized_to_pixels(
            [(float(x), float(y)) for x, y in candidate["points_normalized"]],
            width,
            height,
        )
        color = colors[index % len(colors)]
        draw.line(points + [points[0]], fill=color, width=5)
        x, y = points[0]
        label = (
            f"#{index} {candidate['candidate_side']} "
            f"fc={candidate['frame_contact_score']:.2f} "
            f"grid={candidate['grid_line_density']:.2f}"
        )
        draw.rectangle((x, max(0, y - 24), x + max(260, len(label) * 9), y), fill="white")
        draw.text((x + 3, max(0, y - 22)), label, fill=color, font=font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def rotate_crop(crop: Image.Image, angle: int) -> Image.Image:
    if angle == 0:
        return crop
    return crop.rotate(angle, expand=True)


def rapidocr_engine() -> Any:
    global _RAPIDOCR_ENGINE
    if _RAPIDOCR_ENGINE is None:
        from rapidocr import RapidOCR  # type: ignore[import-not-found]

        _RAPIDOCR_ENGINE = RapidOCR()
    return _RAPIDOCR_ENGINE


def rapidocr_candidate_score(text: str, scores: list[float]) -> float:
    role_hits = field_hits(text, ROLE_FIELD_GROUPS)
    property_hits = field_hits(text, PROPERTY_FIELD_GROUPS)
    avg_score = sum(scores) / len(scores) if scores else 0.0
    return (len(role_hits) * 4.0) + (len(property_hits) * 4.0) + avg_score + min(len(text), 80) / 200.0


def ocr_rotation_angles_for_side(side: str, config: dict[str, Any]) -> list[int]:
    if config["ocr_rotation_mode"] == "all":
        return config["ocr_rotation_angles"]
    if config["ocr_rotation_mode"] == "none":
        return [0]
    side_angles = {
        "top": [180, 270],
        "bottom": [0, 90],
        "left": [90, 180],
        "right": [0, 270],
    }
    return side_angles.get(side, [0])


def try_rapidocr(crop: Image.Image, rotation_angles: list[int]) -> dict[str, Any]:
    try:
        engine = rapidocr_engine()
    except Exception as exc:  # pragma: no cover - depends on local OCR install.
        return {
            "ocr_engine": "rapidocr",
            "ocr_status": f"ocr_error:init:{exc}",
            "ocr_text": "",
            "ocr_confidence_summary": "",
            "ocr_rotation_angle": None,
        }

    best: dict[str, Any] | None = None
    for angle in rotation_angles:
        rotated = rotate_crop(crop.convert("RGB"), angle)
        try:
            result = engine(np.array(rotated))
        except Exception as exc:  # pragma: no cover - depends on local OCR runtime.
            candidate = {
                "ocr_engine": "rapidocr",
                "ocr_status": f"ocr_error:angle_{angle}:{exc}",
                "ocr_text": "",
                "ocr_confidence_summary": "",
                "ocr_rotation_angle": angle,
                "_selection_score": -1.0,
            }
        else:
            texts = [str(text) for text in getattr(result, "txts", ()) if str(text).strip()]
            scores = [float(score) for score in getattr(result, "scores", ()) if score is not None]
            text = "\n".join(texts)
            avg_score = sum(scores) / len(scores) if scores else 0.0
            min_score = min(scores) if scores else 0.0
            elapsed = float(getattr(result, "elapse", 0.0) or 0.0)
            candidate = {
                "ocr_engine": "rapidocr",
                "ocr_status": "ok" if texts else "ocr_no_text",
                "ocr_text": text,
                "ocr_confidence_summary": (
                    f"count={len(texts)};avg={avg_score:.4f};min={min_score:.4f};elapsed={elapsed:.3f}s"
                ),
                "ocr_rotation_angle": angle,
                "_selection_score": rapidocr_candidate_score(text, scores),
            }
        if best is None or candidate["_selection_score"] > best["_selection_score"]:
            best = candidate

    if best is None:
        return {
            "ocr_engine": "rapidocr",
            "ocr_status": "ocr_error:no_rotation_attempted",
            "ocr_text": "",
            "ocr_confidence_summary": "",
            "ocr_rotation_angle": None,
        }
    best.pop("_selection_score", None)
    return best


def try_pytesseract(crop: Image.Image) -> dict[str, Any]:
    try:
        import pytesseract  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return {
            "ocr_engine": "unavailable",
            "ocr_status": "ocr_unavailable",
            "ocr_text": "",
            "ocr_confidence_summary": "",
            "ocr_rotation_angle": None,
        }

    try:
        text = pytesseract.image_to_string(crop, lang="chi_sim+eng")
    except Exception as exc:  # pragma: no cover - depends on local OCR install.
        return {
            "ocr_engine": "pytesseract",
            "ocr_status": f"ocr_error:{exc}",
            "ocr_text": "",
            "ocr_confidence_summary": "",
            "ocr_rotation_angle": None,
        }
    return {
        "ocr_engine": "pytesseract",
        "ocr_status": "ok",
        "ocr_text": text,
        "ocr_confidence_summary": "",
        "ocr_rotation_angle": None,
    }


def try_ocr(crop: Image.Image, rotation_angles: list[int]) -> dict[str, Any]:
    if importlib.util.find_spec("rapidocr"):
        rapid_result = try_rapidocr(crop, rotation_angles)
        if rapid_result["ocr_status"] in {"ok", "ocr_no_text"}:
            return rapid_result
    return try_pytesseract(crop)


def field_hits(text: str, groups: dict[str, list[str]]) -> list[str]:
    hits: list[str] = []
    for group_name, variants in groups.items():
        if any(variant in text for variant in variants):
            hits.append(group_name)
    return hits


def structure_features(crop: Image.Image) -> dict[str, Any]:
    gray = np.array(crop.convert("L"))
    height, width = gray.shape[:2]
    if width < 20 or height < 20:
        return {
            "structure_status": "image_too_small",
            "grid_line_density": 0.0,
            "cell_count_estimate": 0,
            "cell_area_variance": 0.0,
            "small_large_cell_mix_score": 0.0,
            "uniform_grid_penalty": 0.0,
        }

    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    binary = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        12,
    )

    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(8, width // 18), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(8, height // 18)))
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=1)
    grid = cv2.bitwise_or(horizontal, vertical)

    grid_line_density = float(np.count_nonzero(grid)) / float(max(1, width * height))

    closed = cv2.morphologyEx(grid, cv2.MORPH_CLOSE, np.ones((3, 3), dtype=np.uint8), iterations=1)
    contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    areas: list[float] = []
    min_area = max(20.0, width * height * 0.0002)
    max_area = width * height * 0.80
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = float(w * h)
        if min_area <= area <= max_area and w >= 4 and h >= 4:
            areas.append(area)

    if len(areas) >= 2:
        mean_area = float(np.mean(areas))
        variance = float(np.var(areas) / (mean_area * mean_area)) if mean_area > 0 else 0.0
        sorted_areas = sorted(areas)
        small = float(np.mean(sorted_areas[: max(1, len(sorted_areas) // 3)]))
        large = float(np.mean(sorted_areas[-max(1, len(sorted_areas) // 3) :]))
        mix_score = clamp((large / max(1.0, small) - 1.0) / 5.0, 0.0, 1.0)
    else:
        variance = 0.0
        mix_score = 0.0

    uniform_penalty = 0.0
    if len(areas) >= 6 and variance < 0.20:
        uniform_penalty = 1.0
    elif len(areas) >= 4 and variance < 0.35:
        uniform_penalty = 0.5

    return {
        "structure_status": "ok" if len(areas) else "insufficient_grid",
        "grid_line_density": grid_line_density,
        "cell_count_estimate": len(areas),
        "cell_area_variance": variance,
        "small_large_cell_mix_score": mix_score,
        "uniform_grid_penalty": uniform_penalty,
    }


def candidate_diagnostic(
    record: dict[str, Any],
    label: PredictionLabel,
    candidate_index: int,
    source_image: Image.Image,
    source_image_path: Path,
    output_dir: Path,
    config: dict[str, Any],
    frame_detection: dict[str, Any] | None,
) -> dict[str, Any]:
    width, height = source_image.size
    xmin, ymin, xmax, ymax = bbox(label.points)
    area = polygon_area(label.points)
    side = side_from_bbox(xmin, ymin, xmax, ymax)
    frame_contact = frame_contact_features(xmin, ymin, xmax, ymax, frame_detection, config)

    nearest_side = frame_contact["nearest_frame_side"]
    gap_normalized = frame_contact["frame_contact_gap_normalized"]
    if gap_normalized is None:
        frame_gap_px = None
    elif nearest_side in {"left", "right"}:
        frame_gap_px = gap_normalized * width
    else:
        frame_gap_px = gap_normalized * height

    crop, crop_box = crop_candidate(source_image, label, config["crop_padding_ratio"])
    crop_name = f"{record['prediction_dir']}__{record['sample']}__candidate_{candidate_index}.png"
    crop_path = output_dir / "crops" / crop_name
    crop_path.parent.mkdir(parents=True, exist_ok=True)
    crop.save(crop_path)

    ocr = try_ocr(crop, ocr_rotation_angles_for_side(side, config))
    role_hits = field_hits(ocr["ocr_text"], ROLE_FIELD_GROUPS)
    property_hits = field_hits(ocr["ocr_text"], PROPERTY_FIELD_GROUPS)
    role_score = len(role_hits) / max(1, len(ROLE_FIELD_GROUPS))
    property_score = len(property_hits) / max(1, len(PROPERTY_FIELD_GROUPS))
    field_cluster_score = (role_score + property_score) / 2.0
    text_excerpt = " ".join(ocr["ocr_text"].split())[:120]
    structure = structure_features(crop)

    center_x = (xmin + xmax) / 2.0
    center_y = (ymin + ymax) / 2.0
    inside_body = 0.18 <= center_x <= 0.82 and 0.18 <= center_y <= 0.82

    flags: list[str] = []
    if len(role_hits) <= 1:
        flags.append("role_cluster_weak")
    if len(property_hits) <= 1:
        flags.append("property_cluster_weak")
    if not frame_contact["touches_frame_line"]:
        flags.append("no_frame_contact")
    if inside_body and not frame_contact["touches_frame_line"]:
        flags.append("inside_drawing_body")
    if ocr["ocr_status"] != "ok":
        flags.append(ocr["ocr_status"])
    if structure["structure_status"] != "ok":
        flags.append(structure["structure_status"])
    if structure["uniform_grid_penalty"] > 0:
        flags.append("uniform_grid_like")

    return {
        "prediction_dir": record["prediction_dir"],
        "sample": record["sample"],
        "candidate_index": candidate_index,
        "prediction_count": record["prediction_count"],
        "class_id": label.class_id,
        "confidence": label.confidence,
        "points_normalized": [[x, y] for x, y in label.points],
        "bbox_xyxy_normalized": [xmin, ymin, xmax, ymax],
        "area_normalized": area,
        "center_xy_normalized": [center_x, center_y],
        "candidate_side": side,
        "rotation_angle_from_candidate": rotation_from_side(side),
        "position_prior_score": position_prior_score(side),
        "crop_path": as_posix(crop_path),
        "crop_box_px": crop_box,
        "source_image": as_posix(source_image_path),
        "prediction_image": as_posix(record["prediction_image"]),
        "prediction_label": as_posix(record["prediction_label"]),
        "role_field_hits": role_hits,
        "property_field_hits": property_hits,
        "role_cluster_score": role_score,
        "property_cluster_score": property_score,
        "field_cluster_score": field_cluster_score,
        "ocr_engine": ocr["ocr_engine"],
        "ocr_status": ocr["ocr_status"],
        "ocr_confidence_summary": ocr["ocr_confidence_summary"],
        "ocr_rotation_angle": ocr["ocr_rotation_angle"],
        "ocr_text_excerpt": text_excerpt,
        "ocr_text": ocr["ocr_text"],
        "grid_line_density": structure["grid_line_density"],
        "cell_count_estimate": structure["cell_count_estimate"],
        "cell_area_variance": structure["cell_area_variance"],
        "small_large_cell_mix_score": structure["small_large_cell_mix_score"],
        "uniform_grid_penalty": structure["uniform_grid_penalty"],
        "structure_status": structure["structure_status"],
        "inside_drawing_body_penalty": 1.0 if inside_body and not frame_contact["touches_frame_line"] else 0.0,
        "single_word_only_penalty": 1.0 if len(role_hits) + len(property_hits) <= 1 else 0.0,
        "no_role_cluster_penalty": 1.0 if len(role_hits) <= 1 else 0.0,
        "no_property_cluster_penalty": 1.0 if len(property_hits) <= 1 else 0.0,
        "multi_candidate_relation": "multi_candidate" if record["prediction_count"] > 1 else "single_candidate",
        "diagnostic_flags": flags,
        **frame_contact,
        "frame_gap_px": frame_gap_px,
    }


def write_manifest_csv(path: Path, candidates: list[dict[str, Any]]) -> None:
    fieldnames = [
        "prediction_dir",
        "sample",
        "candidate_index",
        "prediction_count",
        "confidence",
        "candidate_side",
        "touches_frame_line",
        "frame_contact_score",
        "frame_gap_px",
        "ocr_engine",
        "ocr_status",
        "ocr_rotation_angle",
        "ocr_text_excerpt",
        "role_field_hits",
        "property_field_hits",
        "field_cluster_score",
        "grid_line_density",
        "cell_count_estimate",
        "cell_area_variance",
        "uniform_grid_penalty",
        "diagnostic_flags",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(
                {
                    "prediction_dir": candidate["prediction_dir"],
                    "sample": candidate["sample"],
                    "candidate_index": candidate["candidate_index"],
                    "prediction_count": candidate["prediction_count"],
                    "confidence": candidate["confidence"],
                    "candidate_side": candidate["candidate_side"],
                    "touches_frame_line": candidate["touches_frame_line"],
                    "frame_contact_score": candidate["frame_contact_score"],
                    "frame_gap_px": candidate["frame_gap_px"],
                    "ocr_engine": candidate["ocr_engine"],
                    "ocr_status": candidate["ocr_status"],
                    "ocr_rotation_angle": candidate["ocr_rotation_angle"],
                    "ocr_text_excerpt": candidate["ocr_text_excerpt"],
                    "role_field_hits": ";".join(candidate["role_field_hits"]),
                    "property_field_hits": ";".join(candidate["property_field_hits"]),
                    "field_cluster_score": candidate["field_cluster_score"],
                    "grid_line_density": candidate["grid_line_density"],
                    "cell_count_estimate": candidate["cell_count_estimate"],
                    "cell_area_variance": candidate["cell_area_variance"],
                    "uniform_grid_penalty": candidate["uniform_grid_penalty"],
                    "diagnostic_flags": ";".join(candidate["diagnostic_flags"]),
                }
            )


def write_html(path: Path, records: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> None:
    by_record: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for candidate in candidates:
        key = (candidate["prediction_dir"], candidate["sample"])
        by_record.setdefault(key, []).append(candidate)

    sections = []
    for record in records:
        key = (record["prediction_dir"], record["sample"])
        record_candidates = by_record.get(key, [])
        overlay = html.escape(html_rel_path(record.get("overlay_path", ""), path))
        rows = []
        for candidate in record_candidates:
            crop = html.escape(html_rel_path(candidate["crop_path"], path))
            rows.append(
                "<tr>"
                f"<td>{candidate['candidate_index']}</td>"
                f"<td>{candidate['confidence']}</td>"
                f"<td>{html.escape(candidate['candidate_side'])}</td>"
                f"<td>{candidate['touches_frame_line']}</td>"
                f"<td>{candidate['frame_contact_score']:.3f}</td>"
                f"<td>{html.escape(candidate['ocr_engine'])}</td>"
                f"<td>{html.escape(candidate['ocr_status'])}</td>"
                f"<td>{candidate['ocr_rotation_angle']}</td>"
                f"<td>{';'.join(candidate['role_field_hits'])}</td>"
                f"<td>{';'.join(candidate['property_field_hits'])}</td>"
                f"<td>{html.escape(candidate['ocr_text_excerpt'])}</td>"
                f"<td>{candidate['cell_count_estimate']}</td>"
                f"<td>{candidate['cell_area_variance']:.3f}</td>"
                f"<td>{';'.join(candidate['diagnostic_flags'])}</td>"
                f"<td><a href=\"{crop}\" target=\"_blank\">crop</a></td>"
                "</tr>"
            )
        sections.append(
            f"""
      <section>
        <h2>{html.escape(record['prediction_dir'])} / {html.escape(record['sample'])}</h2>
        <p>{record['prediction_count']} 个候选；源图：{html.escape(record.get('source_image', ''))}</p>
        <a href="{overlay}" target="_blank"><img src="{overlay}" alt="{html.escape(record['sample'])}" /></a>
        <table>
          <thead>
            <tr>
              <th>#</th><th>conf</th><th>side</th><th>贴框</th><th>贴框分</th>
              <th>OCR</th><th>状态</th><th>旋转</th><th>流程字段</th><th>属性字段</th>
              <th>文本摘要</th><th>格数</th><th>面积差异</th><th>flags</th><th>crop</th>
            </tr>
          </thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </section>
"""
        )

    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>标题栏 OCR 与后处理诊断摘要</title>
  <style>
    body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; background: #f6f7f9; color: #202124; }}
    header {{ padding: 14px 18px; background: #fff; border-bottom: 1px solid #d8dde3; position: sticky; top: 0; }}
    h1 {{ margin: 0; font-size: 20px; }}
    main {{ padding: 14px; display: grid; gap: 14px; }}
    section {{ background: #fff; border: 1px solid #d8dde3; border-radius: 6px; padding: 12px; }}
    h2 {{ margin: 0 0 6px; font-size: 17px; }}
    p {{ margin: 0 0 10px; color: #5f6368; font-size: 13px; }}
    img {{ display: block; width: 100%; max-height: 680px; object-fit: contain; background: #fafafa; border: 1px solid #edf0f2; }}
    table {{ width: 100%; margin-top: 10px; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border: 1px solid #e1e5ea; padding: 5px 6px; text-align: left; vertical-align: top; }}
    th {{ background: #f1f3f4; }}
  </style>
</head>
<body>
  <header>
    <h1>标题栏 OCR 与后处理诊断摘要</h1>
  </header>
  <main>
    {''.join(sections)}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def summarize(records: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    target_samples = set(TARGET_SAMPLES)
    covered_samples = {candidate["sample"] for candidate in candidates}
    return {
        "target_sample_count": len(target_samples),
        "covered_sample_count": len(covered_samples),
        "missing_target_samples": sorted(target_samples - covered_samples),
        "prediction_records": len(records),
        "candidate_records": len(candidates),
        "multi_candidate_records": sum(1 for record in records if record["prediction_count"] > 1),
        "ocr_status_counts": {
            status: sum(1 for candidate in candidates if candidate["ocr_status"] == status)
            for status in sorted({candidate["ocr_status"] for candidate in candidates})
        },
        "ocr_engine_counts": {
            engine: sum(1 for candidate in candidates if candidate["ocr_engine"] == engine)
            for engine in sorted({candidate["ocr_engine"] for candidate in candidates})
        },
        "frame_contact_candidates": sum(1 for candidate in candidates if candidate["touches_frame_line"]),
        "structure_status_counts": {
            status: sum(1 for candidate in candidates if candidate["structure_status"] == status)
            for status in sorted({candidate["structure_status"] for candidate in candidates})
        },
        "field_cluster_strong_candidates": sum(
            1
            for candidate in candidates
            if len(candidate["role_field_hits"]) >= 2 and len(candidate["property_field_hits"]) >= 2
        ),
    }


def json_ready_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ready: list[dict[str, Any]] = []
    for record in records:
        row: dict[str, Any] = {}
        for key, value in record.items():
            if isinstance(value, Path):
                row[key] = as_posix(value)
            else:
                row[key] = value
        ready.append(row)
    return ready


def build(args: argparse.Namespace) -> dict[str, Any]:
    predictions_dir = resolve_path(args.predictions_dir)
    manifest_path = resolve_path(args.manifest)
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "frame_search_band": args.frame_search_band,
        "frame_contact_threshold": args.frame_contact_threshold,
        "frame_dark_threshold": args.frame_dark_threshold,
        "frame_weak_threshold": args.frame_weak_threshold,
        "crop_padding_ratio": args.crop_padding_ratio,
        "ocr_rotation_mode": args.ocr_rotation_mode,
        "ocr_rotation_angles": [
            int(angle.strip()) for angle in args.ocr_rotation_angles.split(",") if angle.strip()
        ],
    }
    ocr_capability = detect_ocr_capability()

    manifest_records = load_manifest(manifest_path)
    records = collect_prediction_records(predictions_dir, TARGET_SAMPLES)
    candidates: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for record in records:
        labels, label_errors = load_prediction_labels(record["prediction_label"])
        record["prediction_count"] = len(labels)
        record["label_errors"] = label_errors
        source_image_path = find_source_image(record["sample"], record["prediction_image"], manifest_records)
        record["source_image"] = as_posix(source_image_path)
        if label_errors:
            errors.append(
                {
                    "prediction_dir": record["prediction_dir"],
                    "sample": record["sample"],
                    "errors": label_errors,
                }
            )
        if not source_image_path.exists():
            errors.append(
                {
                    "prediction_dir": record["prediction_dir"],
                    "sample": record["sample"],
                    "errors": ["missing_source_image"],
                }
            )
            continue

        with Image.open(source_image_path) as image:
            source_image = image.convert("RGB")
            frame_detection = detect_frame_lines(source_image_path, config)
            record_candidates: list[dict[str, Any]] = []
            for index, label in enumerate(labels):
                candidate = candidate_diagnostic(
                    record,
                    label,
                    index,
                    source_image,
                    source_image_path,
                    output_dir,
                    config,
                    frame_detection,
                )
                record_candidates.append(candidate)
                candidates.append(candidate)

            overlay_path = output_dir / "overlays" / f"{record['prediction_dir']}__{record['sample']}.jpg"
            draw_overlay(source_image, record_candidates, overlay_path)
            record["overlay_path"] = as_posix(overlay_path)

    summary = summarize(records, candidates)
    ocr_probe_decision = decide_ocr_probe(ocr_capability, candidates)
    summary["ocr_probe_decision"] = ocr_probe_decision
    report = {
        "config": config,
        "ocr_capability": ocr_capability,
        "ocr_missing_engines": ocr_capability["missing_engines"],
        "ocr_probe_decision": ocr_probe_decision,
        "predictions_dir": as_posix(predictions_dir),
        "manifest": as_posix(manifest_path),
        "output_dir": as_posix(output_dir),
        "summary": summary,
        "errors": errors,
        "records": json_ready_records(records),
        "candidates": candidates,
    }

    report_path = output_dir / "diagnostic_report.json"
    manifest_csv = output_dir / "diagnostic_manifest.csv"
    html_path = output_dir / "review_summary.html"
    write_json(report_path, report)
    write_manifest_csv(manifest_csv, candidates)
    write_html(html_path, records, candidates)

    return {
        "output_dir": as_posix(output_dir),
        "diagnostic_report": as_posix(report_path),
        "diagnostic_manifest": as_posix(manifest_csv),
        "review_summary": as_posix(html_path),
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build title block OCR/structure diagnostic report.")
    parser.add_argument("--predictions-dir", type=Path, default=DEFAULT_PREDICTIONS_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--frame-search-band", type=float, default=0.18)
    parser.add_argument("--frame-contact-threshold", type=float, default=0.025)
    parser.add_argument("--frame-dark-threshold", type=float, default=190)
    parser.add_argument("--frame-weak-threshold", type=float, default=0.004)
    parser.add_argument("--crop-padding-ratio", type=float, default=0.01)
    parser.add_argument("--ocr-rotation-mode", choices=["auto", "all", "none"], default="auto")
    parser.add_argument("--ocr-rotation-angles", default="0,90,180,270")
    args = parser.parse_args()

    print(json.dumps(build(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

