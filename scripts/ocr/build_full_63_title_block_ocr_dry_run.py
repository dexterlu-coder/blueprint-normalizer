from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw

from scripts.ocr.build_pdf_correction_dry_run import drawing_number_candidates
from scripts.ocr.build_title_block_ocr_diagnostic import (
    PROPERTY_FIELD_GROUPS,
    ROLE_FIELD_GROUPS,
    field_hits,
    try_ocr,
)
from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_INPUT_RECORDS = (
    ROOT / "local_data" / "full_63_pdf_dry_run" / "full_63_arbitration_records.jsonl"
)
DEFAULT_STAGE1_RESULTS = ROOT / "outputs" / "rotation-detection" / "stage1" / "results.json"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "full_63_title_block_ocr_dry_run" / "crop_recovery_v1"

RECORD_VERSION = "0.2"
CROP_PADDING_RATIO = 0.03
BOTTOM_CROP_TOP_MIN_RATIO = 0.62
BOTTOM_CROP_TOP_MAX_RATIO = 0.76
LANDSCAPE_RIGHT_BOTTOM_MIN_RATIO = 1.15
RIGHT_BOTTOM_SEARCH_LEFT_RATIO = 0.48
RIGHT_BOTTOM_SEARCH_TOP_RATIO = 0.55
RIGHT_BOTTOM_CROP_LEFT_MIN_RATIO = 0.45
RIGHT_BOTTOM_CROP_TOP_MIN_RATIO = 0.54


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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    resolved = resolve_path(path)
    with resolved.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{resolved}:{line_number}: invalid JSONL") from exc
    return records


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


def sample_from_stage1_file(filename: str) -> str:
    stem = Path(filename).stem
    if "_sample_" in stem:
        return stem.split("_sample_", 1)[0].split("__")[-1] + "_sample_" + stem.split("_sample_", 1)[1]
    if "sample_" in stem:
        index = stem.index("sample_")
        return stem[index:]
    return stem


def build_stage1_by_sample(results_path: Path) -> dict[str, dict[str, Any]]:
    rows = load_json(results_path)
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        sample = sample_from_stage1_file(row.get("file", ""))
        if sample.startswith("YKJ125-00-00-2525_"):
            sample = sample.replace("YKJ125-00-00-2525_", "", 1)
        result[sample] = row
    return result


def box_with_padding(
    image_size: tuple[int, int],
    bbox: list[int | float],
    padding_ratio: float,
) -> tuple[int, int, int, int]:
    width, height = image_size
    left, top, right, bottom = [float(value) for value in bbox]
    box_width = max(1.0, right - left)
    box_height = max(1.0, bottom - top)
    pad_x = box_width * padding_ratio
    pad_y = box_height * padding_ratio
    left_i = max(0, int(round(left - pad_x)))
    top_i = max(0, int(round(top - pad_y)))
    right_i = min(width, int(round(right + pad_x)))
    bottom_i = min(height, int(round(bottom + pad_y)))
    return left_i, top_i, right_i, bottom_i


def parse_right_angle_degrees(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        degrees = int(value) % 360
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid correction_degrees: {value!r}") from exc
    if degrees not in {0, 90, 180, 270}:
        raise ValueError(f"unsupported correction_degrees: {value!r}")
    return degrees


def rotate_clockwise(image: Image.Image, degrees: int) -> Image.Image:
    if degrees == 0:
        return image.copy()
    return image.rotate(-degrees, expand=True)


def corrected_size(image_size: tuple[int, int], degrees: int) -> tuple[int, int]:
    width, height = image_size
    if degrees in {90, 270}:
        return height, width
    return width, height


def transform_point_clockwise(
    x: float,
    y: float,
    image_size: tuple[int, int],
    degrees: int,
) -> tuple[float, float]:
    width, height = image_size
    if degrees == 0:
        return x, y
    if degrees == 90:
        return height - y, x
    if degrees == 180:
        return width - x, height - y
    if degrees == 270:
        return y, width - x
    raise ValueError(f"unsupported correction_degrees: {degrees}")


def transform_box_clockwise(
    box: tuple[int, int, int, int],
    image_size: tuple[int, int],
    degrees: int,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    points = [
        transform_point_clockwise(left, top, image_size, degrees),
        transform_point_clockwise(right, top, image_size, degrees),
        transform_point_clockwise(right, bottom, image_size, degrees),
        transform_point_clockwise(left, bottom, image_size, degrees),
    ]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    out_width, out_height = corrected_size(image_size, degrees)
    return (
        max(0, min(out_width, int(round(min(xs))))),
        max(0, min(out_height, int(round(min(ys))))),
        max(0, min(out_width, int(round(max(xs))))),
        max(0, min(out_height, int(round(max(ys))))),
    )


def clamp_box(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    left = max(0, min(width - 1, left))
    top = max(0, min(height - 1, top))
    right = max(left + 1, min(width, right))
    bottom = max(top + 1, min(height, bottom))
    return left, top, right, bottom


def draw_box(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], color: tuple[int, int, int], width: int) -> None:
    left, top, right, bottom = box
    for offset in range(width):
        draw.rectangle(
            (
                left + offset,
                top + offset,
                max(left, right - offset),
                max(top, bottom - offset),
            ),
            outline=color,
        )


def pil_to_cv2_rgb(image: Image.Image) -> np.ndarray:
    return np.array(image.convert("RGB"))


def extract_line_masks(image: Image.Image) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rgb = pil_to_cv2_rgb(image)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        41,
        9,
    )
    height, width = binary.shape
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(25, width // 45), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(25, height // 45)))
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=1)
    line_mask = cv2.bitwise_or(horizontal, vertical)
    return horizontal, vertical, line_mask


def count_line_components(mask: np.ndarray, min_area: int = 35) -> int:
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    count = 0
    for idx in range(1, num_labels):
        _, _, comp_width, comp_height, area = stats[idx]
        if area >= min_area and (comp_width >= 12 or comp_height >= 12):
            count += 1
    return count


def refine_right_bottom_left_from_lower_table(
    line_mask: np.ndarray,
    candidate_box: tuple[int, int, int, int],
) -> tuple[int, dict[str, Any]]:
    page_height, page_width = line_mask.shape
    left, top, right, bottom = candidate_box
    box_width = max(1, right - left)
    box_height = max(1, bottom - top)
    band_top = top + int(round(box_height * 0.60))
    band = line_mask[band_top:bottom, left:right]
    if band.size == 0:
        return left, {"applied": False, "reason": "empty_lower_band"}

    column_counts = np.count_nonzero(band, axis=0)
    if column_counts.size < 40 or int(column_counts.max(initial=0)) < 6:
        return left, {"applied": False, "reason": "insufficient_column_signal"}

    smooth_width = max(11, min(31, box_width // 28))
    if smooth_width % 2 == 0:
        smooth_width += 1
    kernel = np.ones(smooth_width, dtype=np.float32) / smooth_width
    smoothed = np.convolve(column_counts, kernel, mode="same")
    threshold = max(3.0, float(smoothed.max()) * 0.25)
    min_run_width = max(8, int(round(page_width * 0.008)))
    intervals: list[tuple[int, int]] = []
    run_start: int | None = None
    for index, value in enumerate(smoothed):
        if value >= threshold and run_start is None:
            run_start = index
        elif value < threshold and run_start is not None:
            if index - run_start >= min_run_width:
                intervals.append((left + run_start, left + index))
            run_start = None
    if run_start is not None and len(smoothed) - run_start >= min_run_width:
        intervals.append((left + run_start, left + len(smoothed)))
    if len(intervals) < 2:
        return left, {
            "applied": False,
            "reason": "not_enough_projection_intervals",
            "intervals": [list(item) for item in intervals],
        }

    merge_gap = max(24, int(round(page_width * 0.025)))
    clusters: list[tuple[int, int]] = []
    current_left, current_right = intervals[0]
    for start, end in intervals[1:]:
        if start - current_right <= merge_gap:
            current_right = end
        else:
            clusters.append((current_left, current_right))
            current_left, current_right = start, end
    clusters.append((current_left, current_right))

    min_gap_before = max(80, int(round(page_width * 0.05)))
    min_cluster_width = max(160, int(round(page_width * 0.18)))
    selected_cluster: tuple[int, int] | None = None
    selected_gap = 0
    for index, cluster in enumerate(clusters[1:], start=1):
        previous = clusters[index - 1]
        gap = cluster[0] - previous[1]
        cluster_width = cluster[1] - cluster[0]
        reaches_right_title_area = cluster[1] >= page_width * 0.88
        if gap >= min_gap_before and cluster_width >= min_cluster_width and reaches_right_title_area:
            selected_cluster = cluster
            selected_gap = gap
            break

    if selected_cluster is None:
        return left, {
            "applied": False,
            "reason": "no_separated_right_table_cluster",
            "intervals": [list(item) for item in intervals],
            "clusters": [list(item) for item in clusters],
        }

    refined_left = max(left, selected_cluster[0])
    return refined_left, {
        "applied": refined_left > left,
        "band_top": band_top,
        "threshold": round(threshold, 4),
        "intervals": [list(item) for item in intervals],
        "clusters": [list(item) for item in clusters],
        "selected_cluster": list(selected_cluster),
        "selected_gap": selected_gap,
    }


def right_bottom_table_crop_box(
    image: Image.Image,
    hint_corrected_box: tuple[int, int, int, int],
    full_width_box: tuple[int, int, int, int],
) -> tuple[tuple[int, int, int, int] | None, dict[str, Any]]:
    corrected_width, corrected_height = image.size
    if corrected_width <= corrected_height * LANDSCAPE_RIGHT_BOTTOM_MIN_RATIO:
        return None, {"attempted": False, "reason": "not_landscape"}
    hint_left, hint_top, hint_right, hint_bottom = hint_corrected_box
    hint_width = max(1, hint_right - hint_left)
    hint_is_suspect = (
        hint_left < corrected_width * 0.30
        or hint_right < corrected_width * 0.85
        or (hint_width > corrected_width * 0.60 and hint_left < corrected_width * 0.40)
    )
    if not hint_is_suspect:
        return None, {
            "attempted": False,
            "reason": "stage1_hint_already_right_bottom",
            "hint_box_px_corrected": list(hint_corrected_box),
        }

    horizontal, vertical, line_mask = extract_line_masks(image)
    search_left = int(round(corrected_width * RIGHT_BOTTOM_SEARCH_LEFT_RATIO))
    search_top = int(round(corrected_height * RIGHT_BOTTOM_SEARCH_TOP_RATIO))
    search_box = (search_left, search_top, corrected_width, corrected_height)
    search = line_mask[search_top:corrected_height, search_left:corrected_width]
    close_width = max(31, corrected_width // 42)
    close_height = max(25, corrected_height // 42)
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (close_width, close_height))
    closed = cv2.morphologyEx(search, cv2.MORPH_CLOSE, close_kernel, iterations=1)
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(closed, 8)

    candidates: list[dict[str, Any]] = []
    for idx in range(1, num_labels):
        x, y, box_width, box_height, area = [int(value) for value in stats[idx]]
        left = search_left + x
        top = search_top + y
        right = left + box_width
        bottom = top + box_height
        box_area = max(1, box_width * box_height)
        width_ratio = box_width / corrected_width
        height_ratio = box_height / corrected_height
        left_ratio = left / corrected_width
        top_ratio = top / corrected_height
        bottom_gap_ratio = (corrected_height - bottom) / corrected_height
        line_density = float(np.count_nonzero(line_mask[top:bottom, left:right]) / box_area)
        h_components = count_line_components(horizontal[top:bottom, left:right])
        v_components = count_line_components(vertical[top:bottom, left:right])
        grid_balance = min(h_components, v_components) / max(1, max(h_components, v_components))
        touches_right_frame = right >= corrected_width * 0.88
        near_bottom = bottom_gap_ratio <= 0.12
        if width_ratio < 0.22 or height_ratio < 0.12:
            continue
        if left_ratio < RIGHT_BOTTOM_CROP_LEFT_MIN_RATIO or top_ratio < RIGHT_BOTTOM_CROP_TOP_MIN_RATIO:
            continue
        if not near_bottom:
            continue
        if line_density < 0.025:
            continue
        if h_components < 2 or v_components < 2:
            continue
        score = (
            line_density * 80.0
            + grid_balance * 10.0
            + min(1.0, width_ratio / 0.38) * 6.0
            + min(1.0, height_ratio / 0.20) * 4.0
            + (3.0 if touches_right_frame else 0.0)
        )
        candidates.append(
            {
                "box": (left, top, right, bottom),
                "area": area,
                "width_ratio": round(width_ratio, 4),
                "height_ratio": round(height_ratio, 4),
                "line_density": round(line_density, 6),
                "h_components": h_components,
                "v_components": v_components,
                "grid_balance": round(grid_balance, 4),
                "touches_right_frame": touches_right_frame,
                "score": round(score, 6),
            }
        )

    if not candidates:
        return None, {
            "attempted": True,
            "search_box_px_corrected": list(search_box),
            "candidate_count": 0,
            "reason": "no_right_bottom_table_candidate",
        }

    selected = max(candidates, key=lambda item: (item["score"], item["area"]))
    selected_box = selected["box"]
    refined_left, left_refinement = refine_right_bottom_left_from_lower_table(line_mask, selected_box)
    left, top, right, bottom = selected_box
    left = refined_left
    pad_x = max(12, int(round((right - left) * 0.025)))
    pad_y = max(12, int(round((bottom - top) * 0.045)))
    recovered = clamp_box(
        (
            left - pad_x,
            max(full_width_box[1], top - pad_y),
            min(corrected_width, right + pad_x),
            min(corrected_height, bottom + pad_y),
        ),
        corrected_width,
        corrected_height,
    )
    selected_summary = dict(selected)
    selected_summary["box"] = list(selected_summary["box"])
    selected_summary["left_refinement"] = left_refinement
    return recovered, {
        "attempted": True,
        "search_box_px_corrected": list(search_box),
        "candidate_count": len(candidates),
        "selected_candidate": selected_summary,
    }


def recover_title_block_crop(
    image: Image.Image,
    bbox: list[int | float],
    correction_degrees: int,
    output_dir: Path,
    record_id: str,
) -> dict[str, Any]:
    original_size = image.size
    corrected = rotate_clockwise(image.convert("RGB"), correction_degrees)
    corrected_width, corrected_height = corrected.size
    hint_original_box = box_with_padding(original_size, bbox, CROP_PADDING_RATIO)
    hint_corrected_box = transform_box_clockwise(hint_original_box, original_size, correction_degrees)
    hint_left, hint_top, hint_right, hint_bottom = hint_corrected_box

    min_top = int(round(corrected_height * BOTTOM_CROP_TOP_MIN_RATIO))
    max_top = int(round(corrected_height * BOTTOM_CROP_TOP_MAX_RATIO))
    recovered_top = min(max(hint_top, min_top), max_top)
    full_width_box = clamp_box(
        (0, recovered_top, corrected_width, corrected_height),
        corrected_width,
        corrected_height,
    )
    table_box, table_detection = right_bottom_table_crop_box(corrected, hint_corrected_box, full_width_box)
    if table_box is not None:
        recovered_box = table_box
        crop_strategy = "corrected_right_bottom_table_from_line_evidence"
        bottom_band_fallback = False
    else:
        recovered_box = full_width_box
        crop_strategy = "corrected_bottom_full_width_from_stage1_hint"
        bottom_band_fallback = True
    crop = corrected.crop(recovered_box)

    safe_name = safe_record_name(record_id)
    crop_path = output_dir / "crops" / f"{safe_name}.png"
    corrected_page_path = output_dir / "pages_corrected" / f"{safe_name}.png"
    overlay_path = output_dir / "overlays" / f"{safe_name}.png"
    for path in (crop_path, corrected_page_path, overlay_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    crop.save(crop_path)
    corrected.save(corrected_page_path)

    overlay = corrected.copy()
    draw = ImageDraw.Draw(overlay)
    draw_box(draw, hint_corrected_box, (245, 158, 11), 4)
    draw_box(draw, recovered_box, (220, 38, 38), 6)
    overlay.save(overlay_path)

    hint_width = max(1, hint_right - hint_left)
    right_extension = max(0, recovered_box[2] - hint_right)
    left_extension = max(0, hint_left - recovered_box[0])
    weak_hint_requires_fallback = (
        hint_width < corrected_width * 0.65
        or hint_right < corrected_width * 0.90
        or hint_left > corrected_width * 0.10
        or hint_top < corrected_height * 0.62
    )

    metadata = {
        "crop_strategy": crop_strategy,
        "crop_coordinate_space": "corrected_page",
        "correction_degrees": correction_degrees,
        "source_image_size": list(original_size),
        "corrected_image_size": [corrected_width, corrected_height],
        "stage1_hint_box_px_original": list(hint_original_box),
        "stage1_hint_box_px_corrected": list(hint_corrected_box),
        "bottom_full_width_box_px_corrected": list(full_width_box),
        "crop_box_px_corrected": list(recovered_box),
        "right_bottom_table_detection": table_detection,
        "right_extension_px": right_extension,
        "left_extension_px": left_extension,
        "right_extension_applied": right_extension > max(8, int(hint_width * 0.20)),
        "bottom_band_fallback_applied": bottom_band_fallback,
        "weak_stage1_hint_requires_fallback": weak_hint_requires_fallback,
        "crop_path": as_posix(crop_path),
        "corrected_page_path": as_posix(corrected_page_path),
        "overlay_path": as_posix(overlay_path),
    }

    return {
        "crop": crop,
        "crop_path": crop_path,
        "corrected_page_path": corrected_page_path,
        "overlay_path": overlay_path,
        "metadata": metadata,
    }


def ocr_capability() -> dict[str, Any]:
    return {
        "rapidocr": bool(importlib.util.find_spec("rapidocr")),
        "pytesseract": bool(importlib.util.find_spec("pytesseract")),
    }


def field_cluster_level(ocr_status: str, score: float, role_hits: list[str], property_hits: list[str]) -> str:
    if ocr_status != "ok":
        return "unavailable"
    if score >= 0.55 and len(role_hits) >= 2 and len(property_hits) >= 2:
        return "strong"
    if score > 0:
        return "weak"
    return "none"


def safe_record_name(record_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "__" for ch in record_id).strip("._")


def process_record(
    record: dict[str, Any],
    stage1_by_sample: dict[str, dict[str, Any]],
    output_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    updated = json.loads(json.dumps(record, ensure_ascii=False))
    sample = updated["sample_id"]
    record_id = updated["record_id"]
    page = updated.get("page") or {}
    blockers: list[str] = []
    crop_path = None
    corrected_page_path = None
    overlay_path = None
    crop_recovery: dict[str, Any] = {}
    ocr_text_path = None
    ocr_result = {
        "ocr_engine": "unavailable",
        "ocr_status": "not_attempted",
        "ocr_text": "",
        "ocr_confidence_summary": "",
        "ocr_rotation_angle": None,
    }

    stage1 = stage1_by_sample.get(sample)
    if not stage1:
        blockers.append("missing_stage1_result")
    best_candidate = (stage1 or {}).get("best_candidate") or {}
    bbox = best_candidate.get("bbox")
    if not bbox:
        blockers.append("missing_stage1_best_candidate_bbox")
    correction_degrees = parse_right_angle_degrees((updated.get("rotation") or {}).get("correction_degrees"))
    if correction_degrees is None:
        blockers.append("missing_correction_degrees")
    image_path = page.get("rendered_image_path")
    if not image_path:
        blockers.append("missing_rendered_image_path")
    elif not resolve_path(Path(image_path)).exists():
        blockers.append("rendered_image_path_not_found")

    if not blockers:
        image = Image.open(resolve_path(Path(image_path))).convert("RGB")
        recovered = recover_title_block_crop(
            image=image,
            bbox=bbox,
            correction_degrees=correction_degrees,
            output_dir=output_dir,
            record_id=record_id,
        )
        crop = recovered["crop"]
        crop_path_obj = recovered["crop_path"]
        crop_path = as_posix(crop_path_obj)
        corrected_page_path = as_posix(recovered["corrected_page_path"])
        overlay_path = as_posix(recovered["overlay_path"])
        crop_recovery = recovered["metadata"]

        rotation_angles = [0]
        ocr_result = try_ocr(crop, rotation_angles)
        text = ocr_result.get("ocr_text") or ""
        if text:
            text_path_obj = output_dir / "ocr_text" / f"{safe_record_name(record_id)}.txt"
            text_path_obj.parent.mkdir(parents=True, exist_ok=True)
            text_path_obj.write_text(text, encoding="utf-8")
            ocr_text_path = as_posix(text_path_obj)

    text = ocr_result.get("ocr_text") or ""
    role_hits = field_hits(text, ROLE_FIELD_GROUPS)
    property_hits = field_hits(text, PROPERTY_FIELD_GROUPS)
    role_score = len(role_hits) / max(1, len(ROLE_FIELD_GROUPS))
    property_score = len(property_hits) / max(1, len(PROPERTY_FIELD_GROUPS))
    field_cluster_score = (role_score + property_score) / 2.0
    level = field_cluster_level(
        ocr_result.get("ocr_status", ""),
        field_cluster_score,
        role_hits,
        property_hits,
    )
    number_candidates = drawing_number_candidates(text)

    updated["ocr"] = {
        "title_block_crop_path": crop_path,
        "normalized_crop_path": None,
        "ocr_text": text,
        "ocr_tokens": [],
        "field_cluster_hits": {
            "role": role_hits,
            "property": property_hits,
        },
        "ocr_confidence": ocr_result.get("ocr_confidence_summary"),
        "ocr_ready_for_number_extraction": level == "strong",
    }
    updated["ocr"]["crop_recovery"] = crop_recovery
    updated.setdefault("evidence", {})
    updated["evidence"]["ocr"] = {
        "status": ocr_result.get("ocr_status"),
        "source_report_path": as_posix(output_dir / "ocr_summary.json"),
        "ocr_probe_decision": "full_63_title_block_crop_ocr",
        "engine": ocr_result.get("ocr_engine"),
        "rotation_angle": ocr_result.get("ocr_rotation_angle"),
        "field_cluster_level": level,
        "field_cluster_score": field_cluster_score,
        "role_field_hits": role_hits,
        "property_field_hits": property_hits,
        "text_excerpt": " ".join(text.split())[:160],
        "crop_path": crop_path,
        "corrected_page_path": corrected_page_path,
        "overlay_path": overlay_path,
        "crop_recovery": crop_recovery,
    }
    updated["artifacts"]["ocr_text_path"] = ocr_text_path
    updated["artifacts"]["title_block_crop_path"] = crop_path
    updated["artifacts"]["corrected_page_path"] = corrected_page_path
    updated["artifacts"]["title_block_crop_overlay_path"] = overlay_path
    updated["artifacts"]["stage1_result_path"] = as_posix(DEFAULT_STAGE1_RESULTS)

    summary_row = {
        "record_id": record_id,
        "sample_id": sample,
        "crop_path": crop_path or "",
        "corrected_page_path": corrected_page_path or "",
        "overlay_path": overlay_path or "",
        "crop_strategy": crop_recovery.get("crop_strategy", ""),
        "crop_box_px_corrected": json.dumps(crop_recovery.get("crop_box_px_corrected") or [], ensure_ascii=False),
        "stage1_hint_box_px_corrected": json.dumps(crop_recovery.get("stage1_hint_box_px_corrected") or [], ensure_ascii=False),
        "right_extension_applied": crop_recovery.get("right_extension_applied", ""),
        "bottom_band_fallback_applied": crop_recovery.get("bottom_band_fallback_applied", ""),
        "ocr_text_path": ocr_text_path or "",
        "ocr_engine": ocr_result.get("ocr_engine"),
        "ocr_status": ocr_result.get("ocr_status"),
        "ocr_rotation_angle": ocr_result.get("ocr_rotation_angle"),
        "field_cluster_level": level,
        "field_cluster_score": field_cluster_score,
        "role_field_hits": ";".join(role_hits),
        "property_field_hits": ";".join(property_hits),
        "drawing_number_candidate_count": len(number_candidates),
        "top_drawing_number_candidate": number_candidates[0]["value"] if number_candidates else "",
        "blockers": ";".join(blockers),
        "ocr_text_excerpt": " ".join(text.split())[:160],
    }
    return updated, summary_row


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: Counter[str] = Counter(str(row["ocr_status"]) for row in rows)
    level_counts: Counter[str] = Counter(str(row["field_cluster_level"]) for row in rows)
    blocker_counts: Counter[str] = Counter()
    candidate_bucket_counts: Counter[str] = Counter()
    crop_strategy_counts: Counter[str] = Counter()
    right_extension_count = 0
    bottom_band_fallback_count = 0
    for row in rows:
        for blocker in str(row["blockers"]).split(";"):
            if blocker:
                blocker_counts[blocker] += 1
        count = int(row["drawing_number_candidate_count"])
        if count == 0:
            candidate_bucket_counts["none"] += 1
        elif count == 1:
            candidate_bucket_counts["single"] += 1
        else:
            candidate_bucket_counts["multiple"] += 1
        if row.get("crop_strategy"):
            crop_strategy_counts[str(row["crop_strategy"])] += 1
        if str(row.get("right_extension_applied")) == "True":
            right_extension_count += 1
        if str(row.get("bottom_band_fallback_applied")) == "True":
            bottom_band_fallback_count += 1

    return {
        "record_count": len(rows),
        "ocr_status_counts": dict(sorted(status_counts.items())),
        "field_cluster_level_counts": dict(sorted(level_counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "drawing_number_candidate_bucket_counts": dict(sorted(candidate_bucket_counts.items())),
        "crop_strategy_counts": dict(sorted(crop_strategy_counts.items())),
        "right_extension_applied_count": right_extension_count,
        "bottom_band_fallback_applied_count": bottom_band_fallback_count,
        "crop_count": sum(1 for row in rows if row["crop_path"]),
        "corrected_page_count": sum(1 for row in rows if row["corrected_page_path"]),
        "overlay_count": sum(1 for row in rows if row["overlay_path"]),
        "ocr_text_count": sum(1 for row in rows if row["ocr_text_path"]),
        "dry_run_only": True,
        "whole_page_ocr": False,
        "modified_pdf": False,
        "renamed_pdf": False,
        "ocr_capability": ocr_capability(),
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    records = load_jsonl(args.input_records)
    stage1_by_sample = build_stage1_by_sample(args.stage1_results)
    updated_records: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for record in records:
        updated, row = process_record(record, stage1_by_sample, output_dir)
        updated_records.append(updated)
        rows.append(row)

    records_path = output_dir / "full_63_ocr_arbitration_records.jsonl"
    summary_json_path = output_dir / "ocr_summary.json"
    summary_csv_path = output_dir / "ocr_summary.csv"
    candidates_csv_path = output_dir / "drawing_number_candidates.csv"
    write_jsonl(records_path, updated_records)
    summary = summarize(rows)
    write_json(summary_json_path, summary)
    write_csv(
        summary_csv_path,
        rows,
        [
            "record_id",
            "sample_id",
            "crop_path",
            "corrected_page_path",
            "overlay_path",
            "crop_strategy",
            "crop_box_px_corrected",
            "stage1_hint_box_px_corrected",
            "right_extension_applied",
            "bottom_band_fallback_applied",
            "ocr_text_path",
            "ocr_engine",
            "ocr_status",
            "ocr_rotation_angle",
            "field_cluster_level",
            "field_cluster_score",
            "role_field_hits",
            "property_field_hits",
            "drawing_number_candidate_count",
            "top_drawing_number_candidate",
            "blockers",
            "ocr_text_excerpt",
        ],
    )

    candidate_rows: list[dict[str, Any]] = []
    for record in updated_records:
        candidates = drawing_number_candidates(record.get("ocr", {}).get("ocr_text") or "")
        if not candidates:
            candidate_rows.append(
                {
                    "record_id": record["record_id"],
                    "sample_id": record["sample_id"],
                    "candidate": "",
                    "score": "",
                    "source": "",
                    "context": "",
                }
            )
        for candidate in candidates:
            candidate_rows.append(
                {
                    "record_id": record["record_id"],
                    "sample_id": record["sample_id"],
                    "candidate": candidate["value"],
                    "score": candidate["score"],
                    "source": candidate["source"],
                    "context": candidate["context"],
                }
            )
    write_csv(
        candidates_csv_path,
        candidate_rows,
        ["record_id", "sample_id", "candidate", "score", "source", "context"],
    )

    return {
        "output_dir": as_posix(output_dir),
        "full_63_ocr_arbitration_records": as_posix(records_path),
        "ocr_summary": as_posix(summary_json_path),
        "ocr_summary_csv": as_posix(summary_csv_path),
        "drawing_number_candidates": as_posix(candidates_csv_path),
        "summary": summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run full-63 title-block crop/OCR dry-run and write OCR-enriched records."
    )
    parser.add_argument("--input-records", type=Path, default=DEFAULT_INPUT_RECORDS)
    parser.add_argument("--stage1-results", type=Path, default=DEFAULT_STAGE1_RESULTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    result = build(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

