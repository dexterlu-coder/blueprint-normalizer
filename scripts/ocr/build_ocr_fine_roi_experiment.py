from __future__ import annotations

import argparse
import csv
import html
import json
import os
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw

from scripts.ocr.build_full_63_title_block_ocr_dry_run import clamp_box, extract_line_masks
from scripts.ocr.build_pdf_correction_dry_run import drawing_number_candidates
from scripts.ocr.build_title_block_ocr_diagnostic import (
    PROPERTY_FIELD_GROUPS,
    ROLE_FIELD_GROUPS,
    field_hits,
    try_ocr,
)
from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_RECORDS = (
    ROOT
    / "local_data"
    / "full_63_title_block_ocr_dry_run"
    / "crop_recovery_v1"
    / "full_63_ocr_arbitration_records.jsonl"
)
DEFAULT_REVIEW_SUMMARY = (
    ROOT / "local_data" / "title_block_crop_recovery_review" / "filled_review_summary.json"
)
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "ocr_fine_roi_experiment"
DEFAULT_REVIEW_INBOX = ROOT / "local_data" / "review_inbox" / "current"

EXTRA_TARGET_SAMPLES = ["sample_009"]
ROI_COLORS = {
    "right_band_roi": (220, 38, 38),
    "bottom_right_band_roi": (37, 99, 235),
    "table_line_right_roi": (5, 150, 105),
}


def as_posix(path: Path | str | None) -> str | None:
    if path is None:
        return None
    path_obj = Path(path)
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def rel_path(target: Path | str, base: Path) -> str:
    return Path(os.path.relpath(resolve_path(Path(target)), base)).as_posix()


def safe_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    return safe.strip("._") or "record"


def load_json(path: Path) -> Any:
    return json.loads(resolve_path(path).read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    resolved = resolve_path(path)
    records: list[dict[str, Any]] = []
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def target_samples(review_summary: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    for sample in review_summary.get("too_large_samples") or []:
        if sample not in targets:
            targets.append(sample)
    for sample in EXTRA_TARGET_SAMPLES:
        if sample not in targets:
            targets.append(sample)
    return targets


def record_by_sample(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(record.get("sample_id")): record for record in records}


def box_area(box: tuple[int, int, int, int]) -> int:
    left, top, right, bottom = box
    return max(0, right - left) * max(0, bottom - top)


def fraction_box(
    image_size: tuple[int, int],
    left_ratio: float,
    top_ratio: float,
    right_ratio: float,
    bottom_ratio: float,
) -> tuple[int, int, int, int]:
    width, height = image_size
    return clamp_box(
        (
            int(round(width * left_ratio)),
            int(round(height * top_ratio)),
            int(round(width * right_ratio)),
            int(round(height * bottom_ratio)),
        ),
        width,
        height,
    )


def find_projection_intervals(values: np.ndarray, threshold: float, min_width: int) -> list[tuple[int, int]]:
    intervals: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(values):
        if value >= threshold and start is None:
            start = index
        elif value < threshold and start is not None:
            if index - start >= min_width:
                intervals.append((start, index))
            start = None
    if start is not None and len(values) - start >= min_width:
        intervals.append((start, len(values)))
    return intervals


def merge_intervals(intervals: list[tuple[int, int]], gap: int) -> list[tuple[int, int]]:
    if not intervals:
        return []
    merged: list[tuple[int, int]] = []
    left, right = intervals[0]
    for start, end in intervals[1:]:
        if start - right <= gap:
            right = end
        else:
            merged.append((left, right))
            left, right = start, end
    merged.append((left, right))
    return merged


def table_line_right_box(image: Image.Image) -> tuple[tuple[int, int, int, int] | None, dict[str, Any]]:
    width, height = image.size
    _, _, line_mask = extract_line_masks(image)
    if line_mask.size == 0:
        return None, {"status": "empty_line_mask"}

    column_counts = np.count_nonzero(line_mask, axis=0)
    smooth_width = max(9, min(35, width // 35))
    if smooth_width % 2 == 0:
        smooth_width += 1
    kernel = np.ones(smooth_width, dtype=np.float32) / smooth_width
    smoothed = np.convolve(column_counts, kernel, mode="same")
    max_signal = float(smoothed.max(initial=0.0))
    if max_signal < 4.0:
        return None, {"status": "insufficient_column_signal", "max_signal": max_signal}

    threshold = max(3.0, max_signal * 0.22)
    intervals = find_projection_intervals(smoothed, threshold, max(6, width // 140))
    clusters = merge_intervals(intervals, max(18, width // 40))
    candidates: list[tuple[int, int]] = []
    for left, right in clusters:
        cluster_width = right - left
        if right >= width * 0.78 and cluster_width >= width * 0.20:
            candidates.append((left, right))
    if not candidates:
        return None, {
            "status": "no_right_cluster",
            "threshold": round(threshold, 4),
            "intervals": [list(item) for item in intervals],
            "clusters": [list(item) for item in clusters],
        }

    selected_left, selected_right = min(candidates, key=lambda item: item[0])
    pad_x = max(12, int(round(width * 0.025)))
    pad_y = max(8, int(round(height * 0.025)))
    box = clamp_box(
        (
            max(0, selected_left - pad_x),
            pad_y,
            min(width, max(selected_right + pad_x, int(round(width * 0.92)))),
            height - pad_y,
        ),
        width,
        height,
    )
    return box, {
        "status": "ok",
        "threshold": round(threshold, 4),
        "intervals": [list(item) for item in intervals],
        "clusters": [list(item) for item in clusters],
        "selected_cluster": [selected_left, selected_right],
    }


def roi_candidates(image: Image.Image) -> list[dict[str, Any]]:
    width, height = image.size
    candidates = [
        {
            "roi_name": "right_band_roi",
            "box": fraction_box((width, height), 0.42, 0.0, 1.0, 1.0),
            "strategy": "right_58_percent_of_completeness_crop",
            "diagnostics": {"status": "fixed_ratio"},
        },
        {
            "roi_name": "bottom_right_band_roi",
            "box": fraction_box((width, height), 0.35, 0.22, 1.0, 1.0),
            "strategy": "right_65_percent_lower_78_percent_of_completeness_crop",
            "diagnostics": {"status": "fixed_ratio"},
        },
    ]
    table_box, diagnostics = table_line_right_box(image)
    if table_box is not None:
        candidates.append(
            {
                "roi_name": "table_line_right_roi",
                "box": table_box,
                "strategy": "right_table_cluster_from_line_projection",
                "diagnostics": diagnostics,
            }
        )
    else:
        candidates.append(
            {
                "roi_name": "table_line_right_roi",
                "box": None,
                "strategy": "right_table_cluster_from_line_projection",
                "diagnostics": diagnostics,
            }
        )
    return candidates


def field_cluster_level(ocr_status: str, role_hits: list[str], property_hits: list[str]) -> str:
    if ocr_status != "ok":
        return "unavailable"
    if len(role_hits) >= 2 and len(property_hits) >= 2:
        return "strong"
    if role_hits or property_hits:
        return "weak"
    return "none"


def ocr_image(image: Image.Image) -> dict[str, Any]:
    result = try_ocr(image, [0])
    text = result.get("ocr_text") or ""
    role_hits = field_hits(text, ROLE_FIELD_GROUPS)
    property_hits = field_hits(text, PROPERTY_FIELD_GROUPS)
    candidates = drawing_number_candidates(text)
    top_candidate = candidates[0] if candidates else None
    return {
        "ocr_engine": result.get("ocr_engine"),
        "ocr_status": result.get("ocr_status"),
        "ocr_rotation_angle": result.get("ocr_rotation_angle"),
        "ocr_confidence_summary": result.get("ocr_confidence_summary"),
        "ocr_text": text,
        "ocr_text_excerpt": " ".join(text.split())[:180],
        "role_field_hits": role_hits,
        "property_field_hits": property_hits,
        "field_cluster_level": field_cluster_level(result.get("ocr_status", ""), role_hits, property_hits),
        "drawing_number_candidates": candidates,
        "candidate_count": len(candidates),
        "top_candidate": top_candidate.get("value") if top_candidate else "",
        "top_candidate_score": top_candidate.get("score") if top_candidate else 0.0,
    }


def coarse_ocr_from_record(record: dict[str, Any]) -> dict[str, Any]:
    ocr = record.get("ocr") or {}
    evidence_ocr = (record.get("evidence") or {}).get("ocr") or {}
    text = ocr.get("ocr_text") or ""
    hit_groups = ocr.get("field_cluster_hits") or {}
    role_hits = list(hit_groups.get("role") or field_hits(text, ROLE_FIELD_GROUPS))
    property_hits = list(hit_groups.get("property") or field_hits(text, PROPERTY_FIELD_GROUPS))
    candidates = drawing_number_candidates(text)
    top_candidate = candidates[0] if candidates else None
    status = evidence_ocr.get("status") or ("ok" if text else "ocr_no_text")
    return {
        "ocr_engine": evidence_ocr.get("engine") or "reused",
        "ocr_status": status,
        "ocr_rotation_angle": evidence_ocr.get("rotation_angle"),
        "ocr_confidence_summary": ocr.get("ocr_confidence") or "",
        "ocr_text": text,
        "ocr_text_excerpt": " ".join(text.split())[:180],
        "role_field_hits": role_hits,
        "property_field_hits": property_hits,
        "field_cluster_level": evidence_ocr.get("field_cluster_level")
        or field_cluster_level(status, role_hits, property_hits),
        "drawing_number_candidates": candidates,
        "candidate_count": len(candidates),
        "top_candidate": top_candidate.get("value") if top_candidate else "",
        "top_candidate_score": top_candidate.get("score") if top_candidate else 0.0,
    }


def roi_score(
    roi_record: dict[str, Any],
    coarse_area: int,
) -> float:
    ocr = roi_record["ocr"]
    top_score = float(ocr.get("top_candidate_score") or 0.0)
    role_score = len(ocr.get("role_field_hits") or []) / max(1, len(ROLE_FIELD_GROUPS))
    property_score = len(ocr.get("property_field_hits") or []) / max(1, len(PROPERTY_FIELD_GROUPS))
    field_score = (role_score + property_score) / 2.0
    area_ratio = roi_record["area_ratio"]
    reduction_score = max(0.0, 1.0 - area_ratio)
    candidate_bonus = 0.25 if ocr.get("top_candidate") else 0.0
    return round(top_score + field_score * 0.18 + reduction_score * 0.10 + candidate_bonus, 6)


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


def build_overlay(
    image: Image.Image,
    rois: list[dict[str, Any]],
    selected_name: str,
    output_path: Path,
) -> None:
    canvas = image.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    for roi in rois:
        box = roi.get("box")
        if not box:
            continue
        color = ROI_COLORS.get(roi["roi_name"], (245, 158, 11))
        width = 7 if roi["roi_name"] == selected_name else 4
        draw_box(draw, tuple(box), color, width)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def save_ocr_text(path: Path, text: str) -> str | None:
    if not text:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return as_posix(path)


def compare_status(coarse_ocr: dict[str, Any], best_roi: dict[str, Any] | None) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if best_roi is None:
        return "needs_review", ["fine_roi_missing"]
    fine_ocr = best_roi["ocr"]
    coarse_top = coarse_ocr.get("top_candidate") or ""
    fine_top = fine_ocr.get("top_candidate") or ""
    if not fine_top and coarse_top:
        return "needs_review", ["fine_roi_lost_coarse_candidate"]
    if fine_top and coarse_top and fine_top != coarse_top:
        return "needs_review", ["coarse_fine_candidate_conflict"]
    if not fine_top:
        return "needs_review", ["drawing_number_missing_in_fine_roi"]
    if best_roi["area_ratio"] >= 0.82:
        reasons.append("fine_roi_not_much_smaller")
    if float(fine_ocr.get("top_candidate_score") or 0.0) < 0.72:
        reasons.append("fine_candidate_low_confidence")
    if fine_ocr.get("field_cluster_level") != "strong":
        reasons.append("fine_field_cluster_not_strong")
    if reasons:
        return "needs_review", reasons
    return "fine_roi_candidate", ["fine_roi_candidate_matches_quality_gate"]


def process_record(
    record: dict[str, Any],
    output_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    sample_id = record["sample_id"]
    safe_sample = safe_name(sample_id)
    artifacts = record.get("artifacts") or {}
    crop_path_value = artifacts.get("title_block_crop_path") or ((record.get("ocr") or {}).get("title_block_crop_path"))
    page_path_value = artifacts.get("corrected_page_path")
    coarse_overlay_value = artifacts.get("title_block_crop_overlay_path")
    if not crop_path_value:
        raise ValueError(f"{sample_id}: missing title_block_crop_path")
    crop_path = resolve_path(Path(crop_path_value))
    if not crop_path.exists():
        raise FileNotFoundError(f"{sample_id}: crop not found: {crop_path}")

    with Image.open(crop_path) as image:
        coarse_image = image.convert("RGB")
    coarse_area = coarse_image.width * coarse_image.height
    coarse_ocr = coarse_ocr_from_record(record)
    coarse_text_path = save_ocr_text(
        output_dir / "ocr_text" / f"{safe_sample}__coarse_crop.txt",
        coarse_ocr["ocr_text"],
    )

    roi_records: list[dict[str, Any]] = []
    for roi in roi_candidates(coarse_image):
        box = roi.get("box")
        roi_record = {
            "sample_id": sample_id,
            "record_id": record.get("record_id"),
            "roi_name": roi["roi_name"],
            "strategy": roi["strategy"],
            "status": "missing" if box is None else "ok",
            "box": list(box) if box else None,
            "area_ratio": 0.0,
            "roi_path": None,
            "ocr_text_path": None,
            "diagnostics": roi["diagnostics"],
            "ocr": {
                "ocr_engine": "not_attempted",
                "ocr_status": "not_attempted",
                "ocr_text": "",
                "ocr_text_excerpt": "",
                "role_field_hits": [],
                "property_field_hits": [],
                "field_cluster_level": "unavailable",
                "drawing_number_candidates": [],
                "candidate_count": 0,
                "top_candidate": "",
                "top_candidate_score": 0.0,
            },
            "score": 0.0,
        }
        if box is not None:
            roi_image = coarse_image.crop(box)
            roi_path = output_dir / "fine_rois" / f"{safe_sample}__{roi['roi_name']}.png"
            roi_path.parent.mkdir(parents=True, exist_ok=True)
            roi_image.save(roi_path)
            roi_ocr = ocr_image(roi_image)
            roi_text_path = save_ocr_text(
                output_dir / "ocr_text" / f"{safe_sample}__{roi['roi_name']}.txt",
                roi_ocr["ocr_text"],
            )
            roi_record.update(
                {
                    "area_ratio": round(box_area(box) / max(1, coarse_area), 6),
                    "roi_path": as_posix(roi_path),
                    "ocr_text_path": roi_text_path,
                    "ocr": roi_ocr,
                }
            )
            roi_record["score"] = roi_score(roi_record, coarse_area)
        roi_records.append(roi_record)

    usable_rois = [roi for roi in roi_records if roi["status"] == "ok"]
    best_roi = max(usable_rois, key=lambda item: item["score"]) if usable_rois else None
    status, reasons = compare_status(coarse_ocr, best_roi)
    overlay_path = output_dir / "overlays" / f"{safe_sample}__fine_roi_overlay.png"
    build_overlay(coarse_image, roi_records, best_roi["roi_name"] if best_roi else "", overlay_path)

    record_summary = {
        "sample_id": sample_id,
        "record_id": record.get("record_id"),
        "source_crop_path": as_posix(crop_path),
        "source_corrected_page_path": page_path_value,
        "source_coarse_overlay_path": coarse_overlay_value,
        "fine_roi_overlay_path": as_posix(overlay_path),
        "coarse_ocr": {
            key: value
            for key, value in coarse_ocr.items()
            if key not in {"ocr_text", "drawing_number_candidates"}
        },
        "coarse_ocr_text_path": coarse_text_path,
        "coarse_candidate_values": [
            candidate["value"] for candidate in coarse_ocr.get("drawing_number_candidates") or []
        ],
        "roi_count": len(roi_records),
        "usable_roi_count": len(usable_rois),
        "best_roi_name": best_roi["roi_name"] if best_roi else "",
        "best_roi_path": best_roi.get("roi_path") if best_roi else None,
        "best_roi_area_ratio": best_roi.get("area_ratio") if best_roi else None,
        "best_roi_score": best_roi.get("score") if best_roi else None,
        "best_roi_ocr": {
            key: value
            for key, value in (best_roi.get("ocr") if best_roi else {}).items()
            if key not in {"ocr_text", "drawing_number_candidates"}
        },
        "best_roi_candidate_values": [
            candidate["value"]
            for candidate in ((best_roi.get("ocr") if best_roi else {}).get("drawing_number_candidates") or [])
        ],
        "comparison_status": status,
        "comparison_reasons": reasons,
        "modified_pdf": False,
        "renamed_pdf": False,
    }
    return record_summary, roi_records


def comparison_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        rows.append(
            {
                "sample_id": record["sample_id"],
                "comparison_status": record["comparison_status"],
                "comparison_reasons": ";".join(record["comparison_reasons"]),
                "coarse_top_candidate": record["coarse_ocr"].get("top_candidate", ""),
                "coarse_top_score": record["coarse_ocr"].get("top_candidate_score", ""),
                "best_roi_name": record["best_roi_name"],
                "best_roi_area_ratio": record["best_roi_area_ratio"],
                "best_roi_top_candidate": record["best_roi_ocr"].get("top_candidate", ""),
                "best_roi_top_score": record["best_roi_ocr"].get("top_candidate_score", ""),
                "best_roi_field_cluster_level": record["best_roi_ocr"].get("field_cluster_level", ""),
                "source_crop_path": record["source_crop_path"],
                "best_roi_path": record["best_roi_path"] or "",
                "fine_roi_overlay_path": record["fine_roi_overlay_path"],
            }
        )
    return rows


def roi_result_rows(roi_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in roi_records:
        ocr = record["ocr"]
        rows.append(
            {
                "sample_id": record["sample_id"],
                "roi_name": record["roi_name"],
                "strategy": record["strategy"],
                "status": record["status"],
                "score": record["score"],
                "area_ratio": record["area_ratio"],
                "roi_path": record["roi_path"] or "",
                "ocr_status": ocr.get("ocr_status"),
                "ocr_engine": ocr.get("ocr_engine"),
                "field_cluster_level": ocr.get("field_cluster_level"),
                "role_field_hits": ";".join(ocr.get("role_field_hits") or []),
                "property_field_hits": ";".join(ocr.get("property_field_hits") or []),
                "candidate_count": ocr.get("candidate_count"),
                "top_candidate": ocr.get("top_candidate"),
                "top_candidate_score": ocr.get("top_candidate_score"),
                "ocr_text_excerpt": ocr.get("ocr_text_excerpt"),
                "diagnostic_status": (record.get("diagnostics") or {}).get("status", ""),
            }
        )
    return rows


def summarize(records: list[dict[str, Any]], roi_records: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(record["comparison_status"] for record in records)
    reason_counts: Counter[str] = Counter()
    for record in records:
        for reason in record.get("comparison_reasons") or []:
            reason_counts[reason] += 1
    best_roi_counts = Counter(record["best_roi_name"] or "missing" for record in records)
    roi_status_counts = Counter(record["status"] for record in roi_records)
    return {
        "sample_count": len(records),
        "roi_record_count": len(roi_records),
        "comparison_status_counts": dict(sorted(status_counts.items())),
        "comparison_reason_counts": dict(sorted(reason_counts.items())),
        "best_roi_counts": dict(sorted(best_roi_counts.items())),
        "roi_status_counts": dict(sorted(roi_status_counts.items())),
        "fine_roi_candidate_count": status_counts.get("fine_roi_candidate", 0),
        "needs_review_count": status_counts.get("needs_review", 0),
        "modified_pdf": False,
        "renamed_pdf": False,
    }


def summary_csv_row(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_count": summary.get("sample_count"),
        "roi_record_count": summary.get("roi_record_count"),
        "fine_roi_candidate_count": summary.get("fine_roi_candidate_count"),
        "needs_review_count": summary.get("needs_review_count"),
        "comparison_status_counts": json.dumps(
            summary.get("comparison_status_counts") or {},
            ensure_ascii=False,
            sort_keys=True,
        ),
        "comparison_reason_counts": json.dumps(
            summary.get("comparison_reason_counts") or {},
            ensure_ascii=False,
            sort_keys=True,
        ),
        "best_roi_counts": json.dumps(
            summary.get("best_roi_counts") or {},
            ensure_ascii=False,
            sort_keys=True,
        ),
        "roi_status_counts": json.dumps(
            summary.get("roi_status_counts") or {},
            ensure_ascii=False,
            sort_keys=True,
        ),
        "modified_pdf": summary.get("modified_pdf"),
        "renamed_pdf": summary.get("renamed_pdf"),
    }


def copy_asset(source_value: str | None, target_dir: Path, target_name: str) -> str | None:
    if not source_value:
        return None
    source = resolve_path(Path(source_value))
    if not source.exists():
        return None
    target = target_dir / target_name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return as_posix(target)


def review_items(records: list[dict[str, Any]], review_dir: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        sample = record["sample_id"]
        stem = safe_name(sample)
        page_asset = copy_asset(
            record.get("source_corrected_page_path"),
            review_dir / "assets" / "pages_corrected",
            f"{stem}__page_corrected.png",
        )
        coarse_asset = copy_asset(
            record.get("source_crop_path"),
            review_dir / "assets" / "coarse_crops",
            f"{stem}__coarse_crop.png",
        )
        fine_asset = copy_asset(
            record.get("best_roi_path"),
            review_dir / "assets" / "fine_rois",
            f"{stem}__fine_roi.png",
        )
        overlay_asset = copy_asset(
            record.get("fine_roi_overlay_path"),
            review_dir / "assets" / "overlays",
            f"{stem}__fine_roi_overlay.png",
        )
        items.append(
            {
                "index": index,
                "sample_id": sample,
                "page_asset": page_asset,
                "coarse_asset": coarse_asset,
                "fine_asset": fine_asset,
                "overlay_asset": overlay_asset,
                "comparison_status": record["comparison_status"],
                "comparison_reasons": record["comparison_reasons"],
                "coarse_top_candidate": record["coarse_ocr"].get("top_candidate", ""),
                "coarse_ocr_excerpt": record["coarse_ocr"].get("ocr_text_excerpt", ""),
                "best_roi_name": record["best_roi_name"],
                "best_roi_area_ratio": record["best_roi_area_ratio"],
                "fine_top_candidate": record["best_roi_ocr"].get("top_candidate", ""),
                "fine_ocr_excerpt": record["best_roi_ocr"].get("ocr_text_excerpt", ""),
            }
        )
    return items


def form_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "序号": item["index"],
            "样本编号": item["sample_id"],
            "细ROI判断": "",
            "图号判断": "",
            "人工确认图号": "",
            "备注": "",
        }
        for item in items
    ]


def review_manifest_rows(items: list[dict[str, Any]], review_dir: Path) -> list[dict[str, Any]]:
    def asset_rel(value: str | None) -> str | None:
        if not value:
            return None
        return rel_path(value, review_dir)

    rows: list[dict[str, Any]] = []
    for item in items:
        rows.append(
            {
                "序号": item["index"],
                "样本编号": item["sample_id"],
                "校正后整页": asset_rel(item.get("page_asset")),
                "完整性crop": asset_rel(item.get("coarse_asset")),
                "细ROI": asset_rel(item.get("fine_asset")),
                "细ROI位置示意": asset_rel(item.get("overlay_asset")),
            }
        )
    return rows


def image_html(asset: str | None, review_dir: Path, label: str) -> str:
    if not asset:
        return f'<div class="missing">{html.escape(label)}缺失</div>'
    src = html.escape(rel_path(asset, review_dir))
    return f'<a href="{src}" target="_blank"><img src="{src}" alt="{html.escape(label)}"></a>'


def roi_label(value: str | None) -> str:
    labels = {
        "right_band_roi": "右侧区域",
        "bottom_right_band_roi": "右下区域",
        "table_line_right_roi": "表格线右侧区域",
    }
    return labels.get(value or "", "无")


def status_label(value: str) -> str:
    labels = {
        "fine_roi_candidate": "细 ROI 候选可用",
        "needs_review": "需要人工确认",
    }
    return labels.get(value, value)


def reason_label(value: str) -> str:
    labels = {
        "coarse_fine_candidate_conflict": "粗框与细 ROI 候选不一致",
        "drawing_number_missing_in_fine_roi": "细 ROI 未识别出图号",
        "fine_candidate_low_confidence": "细 ROI 候选置信度偏低",
        "fine_roi_candidate_matches_quality_gate": "细 ROI 候选通过机器质量门",
        "fine_roi_missing": "细 ROI 缺失",
        "fine_roi_lost_coarse_candidate": "细 ROI 丢失粗框候选",
        "fine_roi_not_much_smaller": "细 ROI 缩小幅度不足",
        "fine_field_cluster_not_strong": "细 ROI 字段簇不足",
    }
    return labels.get(value, value)


def item_card(item: dict[str, Any], review_dir: Path) -> str:
    page_html = image_html(item.get("page_asset"), review_dir, "校正后整页")
    coarse_html = image_html(item.get("coarse_asset"), review_dir, "完整性 crop")
    fine_html = image_html(item.get("fine_asset"), review_dir, "细 ROI")
    overlay_html = image_html(item.get("overlay_asset"), review_dir, "细 ROI 位置示意")
    reasons = "；".join(reason_label(reason) for reason in (item.get("comparison_reasons") or []))
    area_ratio = item.get("best_roi_area_ratio")
    area_label = "" if area_ratio is None else f"{float(area_ratio):.2%}"
    return f"""
    <section class="card">
      <div class="card-head">
        <h2>{item['index']}. {html.escape(item['sample_id'])}</h2>
        <span>{html.escape(status_label(item['comparison_status']))}：{html.escape(reasons)}</span>
      </div>
      <div class="images">
        <figure>{page_html}<figcaption>校正后整页</figcaption></figure>
        <figure>{coarse_html}<figcaption>完整性 crop</figcaption></figure>
        <figure>{fine_html}<figcaption>细 ROI</figcaption></figure>
        <figure>{overlay_html}<figcaption>细 ROI 位置示意</figcaption></figure>
      </div>
      <dl>
        <dt>粗 crop 候选</dt><dd>{html.escape(item.get('coarse_top_candidate') or '未识别')}</dd>
        <dt>细 ROI 候选</dt><dd>{html.escape(item.get('fine_top_candidate') or '未识别')}</dd>
        <dt>细 ROI 类型</dt><dd>{html.escape(roi_label(item.get('best_roi_name')))}</dd>
        <dt>细 ROI 面积占比</dt><dd>{html.escape(area_label or '无')}</dd>
      </dl>
      <div class="ocr-grid">
        <p><strong>粗 crop OCR 摘要</strong><br>{html.escape(item.get('coarse_ocr_excerpt') or '')}</p>
        <p><strong>细 ROI OCR 摘要</strong><br>{html.escape(item.get('fine_ocr_excerpt') or '')}</p>
      </div>
    </section>
    """


def write_review_html(path: Path, items: list[dict[str, Any]]) -> None:
    cards = "\n".join(item_card(item, path.parent) for item in items)
    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>细 ROI 与图号候选复核</title>
  <style>
    body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; color: #202124; background: #f4f6f8; }}
    header {{ position: sticky; top: 0; z-index: 2; padding: 14px 18px; background: #fff; border-bottom: 1px solid #d8dde3; }}
    h1 {{ margin: 0 0 6px; font-size: 20px; }}
    .summary {{ display: flex; flex-wrap: wrap; gap: 12px; color: #52606d; font-size: 14px; }}
    main {{ max-width: 1560px; margin: 0 auto; padding: 14px; }}
    .guide {{ background: #fff; border: 1px solid #d8dde3; border-radius: 8px; padding: 12px 14px; margin-bottom: 14px; color: #334155; font-size: 14px; line-height: 1.7; }}
    .guide h2 {{ margin: 0 0 8px; font-size: 16px; }}
    .guide p {{ margin: 4px 0; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; }}
    .legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
    .swatch {{ width: 22px; height: 12px; border-radius: 2px; display: inline-block; }}
    .swatch-red {{ background: #dc2626; }}
    .swatch-blue {{ background: #2563eb; }}
    .swatch-green {{ background: #059669; }}
    .swatch-bold {{ border: 3px solid #111827; background: #f8fafc; box-sizing: border-box; }}
    .card {{ background: #fff; border: 1px solid #d8dde3; border-radius: 8px; padding: 14px; margin-bottom: 14px; }}
    .card-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; margin-bottom: 12px; }}
    h2 {{ margin: 0; font-size: 18px; }}
    .card-head span {{ color: #475569; font-size: 14px; text-align: right; }}
    .images {{ display: grid; grid-template-columns: minmax(320px, 1.3fr) minmax(280px, 1fr) minmax(240px, 0.9fr) minmax(280px, 1fr); gap: 12px; align-items: stretch; }}
    figure {{ margin: 0; min-width: 0; }}
    img {{ display: block; width: 100%; height: min(46vh, 540px); min-height: 240px; object-fit: contain; background: #f8fafc; border: 1px solid #e2e8f0; }}
    figcaption {{ padding-top: 6px; color: #52606d; font-size: 13px; }}
    dl {{ display: grid; grid-template-columns: 120px 1fr 120px 1fr; gap: 8px 12px; margin: 14px 0 0; font-size: 14px; }}
    dt {{ color: #52606d; }}
    dd {{ margin: 0; font-weight: 700; overflow-wrap: anywhere; }}
    .ocr-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }}
    .ocr-grid p {{ margin: 0; padding: 10px; background: #f8fafc; border-left: 4px solid #94a3b8; color: #334155; line-height: 1.6; font-size: 13px; }}
    .missing {{ display: grid; place-items: center; min-height: 240px; background: #fff7ed; border: 1px solid #fed7aa; color: #9a3412; }}
    @media (max-width: 1200px) {{ .images, .ocr-grid {{ grid-template-columns: 1fr; }} img {{ height: auto; }} dl {{ grid-template-columns: 120px 1fr; }} .card-head {{ display: block; }} .card-head span {{ display: block; padding-top: 6px; text-align: left; }} }}
  </style>
</head>
<body>
  <header>
    <h1>细 ROI 与图号候选复核</h1>
    <div class="summary">
      <span>总数：{len(items)}</span>
      <span>填写：review_form.csv</span>
      <span>位置示意图中粗线为当前选中的细 ROI</span>
    </div>
  </header>
  <main>
    <section class="guide">
      <h2>填写说明</h2>
      <p><strong>细ROI判断</strong>：填 正确、范围太大、范围太小、位置错误 或 看不清。</p>
      <p><strong>图号判断</strong>：填 正确、错误、未识别 或 不确定。若不是正确，请在人工确认图号中填写你看到的真实图号；看不清可留空并备注。</p>
      <p><strong>备注</strong>：简短写原因，例如裁掉右侧、仍包含图纸主体、字太浅、粗细候选冲突。</p>
      <div class="legend">
        <span><i class="swatch swatch-red"></i>红框：右侧区域候选</span>
        <span><i class="swatch swatch-blue"></i>蓝框：右下区域候选</span>
        <span><i class="swatch swatch-green"></i>绿框：表格线右侧区域候选</span>
        <span><i class="swatch swatch-bold"></i>粗线：当前机器选中的细 ROI</span>
      </div>
    </section>
    {cards}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def write_review_readme(path: Path, total: int) -> None:
    path.write_text(
        "\n".join(
            [
                "# 当前待审核任务",
                "",
                "任务：细 ROI 与图号候选复核。",
                "",
                "请打开：",
                "",
                "- `fine_roi_review/review_index.html`",
                "- `fine_roi_review/review_form.csv`",
                "",
                f"本轮共 {total} 条。",
                "",
                "请重点确认细 ROI 是否截到了图号栏、是否比完整性 crop 更适合作为 OCR 输入，以及细 ROI 候选图号是否可信。",
                "",
                "CSV 字段填写：",
                "",
                "- `序号`、`样本编号`：不用填写。",
                "- `细ROI判断`：填 `正确`、`范围太大`、`范围太小`、`位置错误` 或 `看不清`。",
                "- `图号判断`：填 `正确`、`错误`、`未识别` 或 `不确定`。",
                "- `人工确认图号`：当图号判断不是 `正确` 时，填写你看到的真实图号；看不清可留空。",
                "- `备注`：简短写原因，例如裁掉右侧、仍包含图纸主体、字太浅、粗细候选冲突。",
                "",
                "位置示意图颜色：",
                "",
                "- 红框：右侧区域候选。",
                "- 蓝框：右下区域候选。",
                "- 绿框：表格线右侧区域候选。",
                "- 较粗的框：当前机器选中的细 ROI。",
                "",
                "本入口只用于审核，不会生成或重命名 PDF。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build_review_pack(
    records: list[dict[str, Any]],
    output_dir: Path,
    review_inbox: Path,
) -> dict[str, Any]:
    if review_inbox.exists():
        shutil.rmtree(review_inbox)
    review_dir = review_inbox / "fine_roi_review"
    review_dir.mkdir(parents=True, exist_ok=True)
    items = review_items(records, review_dir)
    write_csv(
        review_dir / "review_form.csv",
        form_rows(items),
        ["序号", "样本编号", "细ROI判断", "图号判断", "人工确认图号", "备注"],
    )
    write_json(review_dir / "review_manifest.json", review_manifest_rows(items, review_dir))
    write_json(output_dir / "review_manifest.json", items)
    write_review_html(review_dir / "review_index.html", items)
    write_review_readme(review_inbox / "README.md", len(items))
    missing_asset_count = sum(
        1
        for item in items
        if not item.get("page_asset")
        or not item.get("coarse_asset")
        or not item.get("fine_asset")
        or not item.get("overlay_asset")
    )
    return {
        "review_record_count": len(items),
        "missing_asset_count": missing_asset_count,
        "review_inbox": as_posix(review_inbox),
        "review_index": as_posix(review_dir / "review_index.html"),
        "review_form": as_posix(review_dir / "review_form.csv"),
        "modified_pdf": False,
        "renamed_pdf": False,
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    records_path = resolve_path(args.records)
    review_summary_path = resolve_path(args.review_summary)
    output_dir = resolve_path(args.output_dir)
    review_inbox = resolve_path(args.review_inbox)
    output_dir.mkdir(parents=True, exist_ok=True)

    records = load_jsonl(records_path)
    review_summary = load_json(review_summary_path)
    samples = target_samples(review_summary)
    records_by_sample = record_by_sample(records)
    missing_samples = [sample for sample in samples if sample not in records_by_sample]

    summaries: list[dict[str, Any]] = []
    all_roi_records: list[dict[str, Any]] = []
    for sample in samples:
        if sample not in records_by_sample:
            continue
        record_summary, roi_records = process_record(records_by_sample[sample], output_dir)
        summaries.append(record_summary)
        all_roi_records.extend(roi_records)

    summary = summarize(summaries, all_roi_records)
    summary["target_samples"] = samples
    summary["missing_samples"] = missing_samples
    summary["records"] = as_posix(records_path)
    summary["review_summary"] = as_posix(review_summary_path)
    summary["output_dir"] = as_posix(output_dir)

    review_summary_out = build_review_pack(summaries, output_dir, review_inbox)
    summary["review_pack"] = review_summary_out

    write_json(output_dir / "experiment_summary.json", summary)
    write_csv(
        output_dir / "experiment_summary.csv",
        [summary_csv_row(summary)],
        [
            "sample_count",
            "roi_record_count",
            "fine_roi_candidate_count",
            "needs_review_count",
            "comparison_status_counts",
            "comparison_reason_counts",
            "best_roi_counts",
            "roi_status_counts",
            "modified_pdf",
            "renamed_pdf",
        ],
    )
    write_jsonl(output_dir / "fine_roi_records.jsonl", summaries)
    write_csv(
        output_dir / "fine_roi_records.csv",
        comparison_rows(summaries),
        [
            "sample_id",
            "comparison_status",
            "comparison_reasons",
            "coarse_top_candidate",
            "coarse_top_score",
            "best_roi_name",
            "best_roi_area_ratio",
            "best_roi_top_candidate",
            "best_roi_top_score",
            "best_roi_field_cluster_level",
            "source_crop_path",
            "best_roi_path",
            "fine_roi_overlay_path",
        ],
    )
    write_jsonl(output_dir / "fine_roi_ocr_results.jsonl", all_roi_records)
    write_csv(
        output_dir / "fine_roi_ocr_results.csv",
        roi_result_rows(all_roi_records),
        [
            "sample_id",
            "roi_name",
            "strategy",
            "status",
            "score",
            "area_ratio",
            "roi_path",
            "ocr_status",
            "ocr_engine",
            "field_cluster_level",
            "role_field_hits",
            "property_field_hits",
            "candidate_count",
            "top_candidate",
            "top_candidate_score",
            "ocr_text_excerpt",
            "diagnostic_status",
        ],
    )
    write_csv(
        output_dir / "drawing_number_comparison.csv",
        comparison_rows(summaries),
        [
            "sample_id",
            "comparison_status",
            "comparison_reasons",
            "coarse_top_candidate",
            "coarse_top_score",
            "best_roi_name",
            "best_roi_area_ratio",
            "best_roi_top_candidate",
            "best_roi_top_score",
            "best_roi_field_cluster_level",
            "source_crop_path",
            "best_roi_path",
            "fine_roi_overlay_path",
        ],
    )
    write_csv(
        output_dir / "needs_review.csv",
        [row for row in comparison_rows(summaries) if row["comparison_status"] == "needs_review"],
        [
            "sample_id",
            "comparison_status",
            "comparison_reasons",
            "coarse_top_candidate",
            "coarse_top_score",
            "best_roi_name",
            "best_roi_area_ratio",
            "best_roi_top_candidate",
            "best_roi_top_score",
            "best_roi_field_cluster_level",
            "source_crop_path",
            "best_roi_path",
            "fine_roi_overlay_path",
        ],
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build OCR fine ROI experiment and review pack.")
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--review-summary", type=Path, default=DEFAULT_REVIEW_SUMMARY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--review-inbox", type=Path, default=DEFAULT_REVIEW_INBOX)
    return parser.parse_args()


def main() -> int:
    result = build(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

