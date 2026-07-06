from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "local_data" / "experiment_samples" / "all" / "png"
OUTPUT_DIR = ROOT / "outputs" / "rotation-detection" / "stage1"
DEBUG_DIR = OUTPUT_DIR / "debug"

ROTATION_BY_SIDE = {
    "bottom": 0,
    "left": 90,
    "top": 180,
    "right": 270,
}

CORRECTION_BY_SIDE = {
    "bottom": 0,
    "left": 270,
    "top": 180,
    "right": 90,
}

SIDE_LABEL_ZH = {
    "bottom": "下方或右下方",
    "left": "左侧",
    "top": "上方或左上方",
    "right": "右侧或右上方",
}


@dataclass
class CandidateScore:
    side: str
    score: float
    evidence_score: float
    margin_score: float
    ambiguity_score: float
    line_density: float
    intersection_density: float
    grid_balance: float
    edge_proximity: float
    size_reasonableness: float
    local_contrast: float
    bbox: list[int]


@dataclass
class SideScore:
    side: str
    score: float
    line_density: float
    intersection_density: float
    component_density: float
    bbox: list[int]


@dataclass
class DetectionResult:
    file: str
    title_block_side: str
    title_block_position: str
    clockwise_rotation_degrees: int
    correction_clockwise_degrees: int
    confidence: float
    needs_review: bool
    debug_image: str
    best_candidate: dict
    side_scores: list[dict]
    candidates: list[dict]


def read_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot read image: {path}")
    return image


def write_image(path: Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise ValueError(f"Cannot encode image: {path}")
    encoded.tofile(str(path))


def extract_line_masks(image: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
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


def side_regions(width: int, height: int) -> dict[str, tuple[int, int, int, int]]:
    band_x = int(width * 0.40)
    band_y = int(height * 0.40)
    return {
        "top": (0, 0, width, band_y),
        "bottom": (0, height - band_y, width, height),
        "left": (0, 0, band_x, height),
        "right": (width - band_x, 0, width, height),
    }


def clamp_bbox(bbox: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    return max(0, x1), max(0, y1), min(width, x2), min(height, y2)


def expand_bbox(
    bbox: tuple[int, int, int, int],
    width: int,
    height: int,
    padding: int = 24,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    return clamp_bbox((x1 - padding, y1 - padding, x2 + padding, y2 + padding), width, height)


def bbox_union(boxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int] | None:
    if not boxes:
        return None
    x1 = min(box[0] for box in boxes)
    y1 = min(box[1] for box in boxes)
    x2 = max(box[2] for box in boxes)
    y2 = max(box[3] for box in boxes)
    return x1, y1, x2, y2


def bbox_overlap_area(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    return max(0, x2 - x1) * max(0, y2 - y1)


def side_from_bbox(
    bbox: tuple[int, int, int, int],
    width: int,
    height: int,
) -> str:
    x1, y1, x2, y2 = bbox
    distances = {
        "left": x1,
        "right": width - x2,
        "top": y1,
        "bottom": height - y2,
    }
    return min(distances, key=distances.get)


def build_candidate_boxes(
    line_mask: np.ndarray,
    width: int,
    height: int,
) -> list[tuple[str, tuple[int, int, int, int]]]:
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (85, 65))
    closed = cv2.morphologyEx(line_mask, cv2.MORPH_CLOSE, close_kernel, iterations=1)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    image_area = width * height
    raw_boxes: list[tuple[int, int, int, int]] = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        if w < width * 0.12 or h < height * 0.08:
            continue
        if area < image_area * 0.003:
            continue
        if area > image_area * 0.45:
            continue
        raw_boxes.append(expand_bbox((x, y, x + w, y + h), width, height, 16))

    regions = side_regions(width, height)
    candidates: list[tuple[str, tuple[int, int, int, int]]] = []
    for side, region in regions.items():
        region_area = max(1, (region[2] - region[0]) * (region[3] - region[1]))
        side_boxes = [
            box
            for box in raw_boxes
            if bbox_overlap_area(box, region) / max(1, (box[2] - box[0]) * (box[3] - box[1])) >= 0.40
        ]

        for box in side_boxes:
            box_area = max(1, (box[2] - box[0]) * (box[3] - box[1]))
            if bbox_overlap_area(box, region) / box_area >= 0.40:
                candidates.append((side, box))

        # Keep a fallback aggregate candidate for sparse or broken title blocks.
        union = bbox_union(side_boxes)
        if union is not None:
            union_area = max(1, (union[2] - union[0]) * (union[3] - union[1]))
            if union_area <= region_area * 0.85:
                candidates.append((side, expand_bbox(union, width, height, 12)))

    unique: dict[tuple[str, int, int, int, int], tuple[str, tuple[int, int, int, int]]] = {}
    for side, box in candidates:
        key = (side, box[0] // 8, box[1] // 8, box[2] // 8, box[3] // 8)
        unique[key] = (side, box)
    return list(unique.values())


def build_edge_window_candidates(width: int, height: int) -> list[tuple[str, tuple[int, int, int, int]]]:
    """Add deterministic edge windows so sparse title blocks are not lost in one giant contour."""
    candidates: list[tuple[str, tuple[int, int, int, int]]] = []

    vertical_windows = [
        (0.00, 0.45),
        (0.00, 0.60),
        (0.10, 0.55),
        (0.25, 0.60),
        (0.40, 0.60),
    ]
    for side in ("left", "right"):
        x1 = 0 if side == "left" else int(width * 0.60)
        x2 = int(width * 0.40) if side == "left" else width
        for y_start, y_size in vertical_windows:
            y1 = int(height * y_start)
            y2 = min(height, int(height * (y_start + y_size)))
            candidates.append((side, (x1, y1, x2, y2)))

    horizontal_windows = [
        (0.00, 0.55),
        (0.15, 0.70),
        (0.35, 0.65),
        (0.00, 1.00),
        (0.45, 0.55),
    ]
    for side in ("top", "bottom"):
        y1 = 0 if side == "top" else int(height * 0.60)
        y2 = int(height * 0.40) if side == "top" else height
        for x_start, x_size in horizontal_windows:
            x1 = int(width * x_start)
            x2 = min(width, int(width * (x_start + x_size)))
            candidates.append((side, (x1, y1, x2, y2)))

    return candidates


def unique_candidate_boxes(
    boxes: list[tuple[str, tuple[int, int, int, int]]],
) -> list[tuple[str, tuple[int, int, int, int]]]:
    unique: dict[tuple[str, int, int, int, int], tuple[str, tuple[int, int, int, int]]] = {}
    for side, box in boxes:
        key = (side, box[0] // 8, box[1] // 8, box[2] // 8, box[3] // 8)
        unique[key] = (side, box)
    return list(unique.values())


def normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return max(0.0, min(1.0, (value - low) / (high - low)))


def count_line_components(mask: np.ndarray, min_area: int = 40) -> int:
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    count = 0
    for idx in range(1, num_labels):
        _, _, comp_w, comp_h, comp_area = stats[idx]
        if comp_area >= min_area and (comp_w >= 15 or comp_h >= 15):
            count += 1
    return count


def score_candidate(
    side: str,
    bbox: tuple[int, int, int, int],
    horizontal: np.ndarray,
    vertical: np.ndarray,
    line_mask: np.ndarray,
) -> CandidateScore:
    height, width = line_mask.shape
    x1, y1, x2, y2 = bbox
    area = max(1, (x2 - x1) * (y2 - y1))

    candidate_lines = line_mask[y1:y2, x1:x2]
    candidate_h = horizontal[y1:y2, x1:x2]
    candidate_v = vertical[y1:y2, x1:x2]
    candidate_intersections = cv2.bitwise_and(candidate_h, candidate_v)

    line_density = float(np.count_nonzero(candidate_lines) / area)
    intersection_density = float(np.count_nonzero(candidate_intersections) / area)

    h_count = count_line_components(candidate_h)
    v_count = count_line_components(candidate_v)
    grid_balance = min(h_count, v_count) / max(1, max(h_count, v_count))

    edge_distance = {
        "left": x1,
        "right": width - x2,
        "top": y1,
        "bottom": height - y2,
    }[side]
    edge_proximity = 1.0 - min(1.0, edge_distance / max(width, height) / 0.08)

    box_w = max(1, x2 - x1)
    box_h = max(1, y2 - y1)
    aspect = box_w / box_h
    if side in {"left", "right"}:
        aspect_score = 1.0 - min(1.0, abs(aspect - 0.32) / 0.70)
        area_score = normalize(area / (width * height), 0.025, 0.20)
    else:
        aspect_score = 1.0 - min(1.0, abs(aspect - 2.80) / 3.00)
        area_score = normalize(area / (width * height), 0.025, 0.24)
    size_reasonableness = 0.55 * aspect_score + 0.45 * area_score

    outer = expand_bbox(bbox, width, height, 90)
    ox1, oy1, ox2, oy2 = outer
    outer_area = max(1, (ox2 - ox1) * (oy2 - oy1))
    outer_lines = line_mask[oy1:oy2, ox1:ox2]
    outer_density = np.count_nonzero(outer_lines) / outer_area
    local_contrast = min(1.0, line_density / max(outer_density, 1e-6) / 2.0)

    line_score = normalize(line_density, 0.015, 0.080)
    intersection_score = normalize(intersection_density, 0.00008, 0.0015)
    evidence_score = (
        0.28 * line_score
        + 0.24 * intersection_score
        + 0.18 * grid_balance
        + 0.14 * edge_proximity
        + 0.10 * size_reasonableness
        + 0.06 * local_contrast
    )

    # Score remains separate from confidence; it ranks candidates.
    score = evidence_score * 100.0
    return CandidateScore(
        side=side,
        score=round(score, 6),
        evidence_score=round(evidence_score, 6),
        margin_score=0.0,
        ambiguity_score=0.0,
        line_density=round(line_density, 6),
        intersection_density=round(intersection_density, 6),
        grid_balance=round(grid_balance, 6),
        edge_proximity=round(edge_proximity, 6),
        size_reasonableness=round(size_reasonableness, 6),
        local_contrast=round(local_contrast, 6),
        bbox=[x1, y1, x2, y2],
    )


def score_side_region(
    side: str,
    bbox: tuple[int, int, int, int],
    horizontal: np.ndarray,
    vertical: np.ndarray,
    line_mask: np.ndarray,
) -> SideScore:
    x1, y1, x2, y2 = bbox
    area = max(1, (x2 - x1) * (y2 - y1))
    region_lines = line_mask[y1:y2, x1:x2]
    region_intersections = cv2.bitwise_and(horizontal[y1:y2, x1:x2], vertical[y1:y2, x1:x2])

    component_density = count_line_components(region_lines, 60) / max(1, area / 10000)
    line_density = float(np.count_nonzero(region_lines) / area)
    intersection_density = float(np.count_nonzero(region_intersections) / area)
    score = (line_density * 100.0) + (intersection_density * 1500.0) + component_density
    return SideScore(
        side=side,
        score=round(score, 6),
        line_density=round(line_density, 6),
        intersection_density=round(intersection_density, 6),
        component_density=round(component_density, 6),
        bbox=[x1, y1, x2, y2],
    )


def choose_side(side_scores: list[SideScore]) -> SideScore:
    ordered = sorted(side_scores, key=lambda item: item.score, reverse=True)
    chosen = ordered[0]
    by_side = {score.side: score for score in ordered}
    right = by_side.get("right")

    # Assembly drawings can contain a large BOM near the top. If top wins while
    # the right band has strong table evidence, prefer the right-side title block.
    if (
        chosen.side == "top"
        and right is not None
        and right.score >= chosen.score * 0.60
        and right.component_density >= 0.25
    ):
        return right
    if (
        chosen.side == "top"
        and right is not None
        and right.score >= chosen.score * 0.90
        and right.intersection_density > chosen.intersection_density
    ):
        return right
    return chosen


def choose_detection_side(
    side_scores: list[SideScore],
    candidates: list[CandidateScore],
) -> tuple[str, CandidateScore | None, SideScore]:
    side_fallback = choose_side(side_scores)
    if not candidates:
        return side_fallback.side, None, side_fallback

    ordered_candidates = sorted(candidates, key=lambda item: item.score, reverse=True)
    best_candidate = ordered_candidates[0]
    side_scores_by_side = {score.side: score for score in side_scores}
    candidates_by_side: dict[str, CandidateScore] = {}
    for candidate in ordered_candidates:
        candidates_by_side.setdefault(candidate.side, candidate)

    # A real title block is a local structured table. Prefer that evidence when
    # it is strong enough; otherwise keep the broad edge-band fallback.
    #
    # Dense assembly views often create top/left window false positives. When
    # the fallback already points to the right-side title block, keep it unless
    # the local candidate is a plausible bottom/right correction.
    if side_fallback.side == "right" and best_candidate.side in {"top", "left"}:
        fallback_candidate = next(
            (candidate for candidate in ordered_candidates if candidate.side == side_fallback.side),
            None,
        )
        return side_fallback.side, fallback_candidate or best_candidate, side_fallback

    left_candidate = candidates_by_side.get("left")
    best_side_score = side_scores_by_side.get(best_candidate.side)
    left_side_score = side_scores_by_side.get("left")
    if (
        left_candidate is not None
        and left_side_score is not None
        and best_side_score is not None
        and best_candidate.side in {"bottom", "right"}
        and side_fallback.side != "right"
        and left_candidate.evidence_score >= best_candidate.evidence_score * 0.93
        and left_side_score.score >= best_side_score.score * 0.75
    ):
        return "left", left_candidate, side_fallback

    if (
        side_fallback.side == "left"
        and left_candidate is not None
        and best_candidate.side != "left"
        and left_candidate.evidence_score >= best_candidate.evidence_score * 0.88
    ):
        return "left", left_candidate, side_fallback

    if best_candidate.evidence_score >= 0.43:
        return best_candidate.side, best_candidate, side_fallback

    return side_fallback.side, best_candidate, side_fallback


def with_confidence_fields(candidates: list[CandidateScore]) -> list[CandidateScore]:
    ordered = sorted(candidates, key=lambda item: item.score, reverse=True)
    if not ordered:
        return []
    best = ordered[0]
    second = ordered[1] if len(ordered) > 1 else None
    if second is None or best.score <= 0:
        margin = 1.0
    else:
        margin = max(0.0, min(1.0, (best.score - second.score) / best.score))

    for candidate in ordered:
        side_competitors = [
            other for other in ordered if other.side != candidate.side and other.score >= candidate.score * 0.82
        ]
        ambiguity = min(1.0, len(side_competitors) / 3.0)
        candidate.margin_score = round(margin if candidate is best else 0.0, 6)
        candidate.ambiguity_score = round(ambiguity, 6)
    return ordered


def confidence_from_candidate(candidate: CandidateScore) -> float:
    confidence = (
        0.58 * candidate.evidence_score
        + 0.28 * candidate.margin_score
        + 0.14 * (1.0 - candidate.ambiguity_score)
    )
    return round(max(0.0, min(1.0, confidence)), 4)


def confidence_from_side(
    chosen: SideScore,
    side_scores: list[SideScore],
    side_candidate: CandidateScore | None,
) -> float:
    ordered = sorted(side_scores, key=lambda item: item.score, reverse=True)
    second = next((score for score in ordered if score.side != chosen.side), None)
    margin = 1.0 if second is None else max(0.0, min(1.0, (chosen.score - second.score) / chosen.score))
    evidence = normalize(chosen.score, 1.0, 7.0)
    if side_candidate is not None:
        evidence = max(evidence, side_candidate.evidence_score)
    ambiguity = 1.0 if second is not None and second.score >= chosen.score * 0.88 else 0.0
    confidence = 0.62 * evidence + 0.23 * margin + 0.15 * (1.0 - ambiguity)
    return round(max(0.0, min(1.0, confidence)), 4)


def apply_local_candidate_confidence_floor(
    confidence: float,
    chosen_candidate: CandidateScore | None,
    candidates: list[CandidateScore],
) -> float:
    if chosen_candidate is None or not candidates:
        return confidence
    best_score = max(candidate.score for candidate in candidates)
    if best_score <= 0:
        return confidence

    # Very faint drawings can have broad side-band disagreement even when the
    # local title-block candidate is the winner or a near tie. Keep these above
    # the review threshold only when local evidence is strong enough.
    if (
        chosen_candidate.evidence_score >= 0.45
        and chosen_candidate.score >= best_score * 0.97
        and confidence < 0.32
    ):
        return 0.32
    return confidence


def draw_debug(
    image: np.ndarray,
    candidates: list[CandidateScore],
    chosen_side: SideScore,
    chosen_candidate: CandidateScore | None,
) -> np.ndarray:
    debug = image.copy()
    for candidate in candidates[:12]:
        x1, y1, x2, y2 = candidate.bbox
        color = (0, 180, 255)
        thickness = 3
        if chosen_candidate is not None and candidate is chosen_candidate:
            color = (0, 255, 0)
            thickness = 6
        cv2.rectangle(debug, (x1, y1), (x2 - 1, y2 - 1), color, thickness)
        label = f"{candidate.side} {candidate.score:.1f}"
        cv2.putText(debug, label, (x1 + 8, max(35, y1 + 32)), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
    x1, y1, x2, y2 = chosen_side.bbox
    cv2.rectangle(debug, (x1, y1), (x2 - 1, y2 - 1), (0, 255, 0), 5)
    cv2.putText(
        debug,
        f"chosen side: {chosen_side.side} {chosen_side.score:.1f}",
        (x1 + 10, max(45, y1 + 45)),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 0),
        3,
    )
    return debug


def detect_one(path: Path) -> DetectionResult:
    image = read_image(path)
    height, width = image.shape[:2]
    horizontal, vertical, line_mask = extract_line_masks(image)

    side_scores = [
        score_side_region(side, bbox, horizontal, vertical, line_mask)
        for side, bbox in side_regions(width, height).items()
    ]
    side_fallback = choose_side(side_scores)

    boxes = unique_candidate_boxes(
        build_candidate_boxes(line_mask, width, height)
        + build_edge_window_candidates(width, height)
    )

    candidates = [
        score_candidate(side, bbox, horizontal, vertical, line_mask)
        for side, bbox in boxes
    ]
    candidates = with_confidence_fields(candidates)
    chosen_side_name, chosen_candidate, chosen_side_fallback = choose_detection_side(side_scores, candidates)
    chosen_side = next(
        (score for score in side_scores if score.side == chosen_side_name),
        chosen_side_fallback,
    )
    if chosen_candidate is None:
        chosen_candidate = next((candidate for candidate in candidates if candidate.side == chosen_side.side), None)
    if chosen_candidate is None and candidates:
        chosen_candidate = candidates[0]
    confidence = confidence_from_side(chosen_side, side_scores, chosen_candidate)
    confidence = apply_local_candidate_confidence_floor(confidence, chosen_candidate, candidates)
    needs_review = bool(confidence < 0.30)

    debug_path = DEBUG_DIR / f"{path.stem}_debug.png"
    write_image(debug_path, draw_debug(image, candidates, chosen_side, chosen_candidate))

    return DetectionResult(
        file=path.name,
        title_block_side=chosen_side.side,
        title_block_position=SIDE_LABEL_ZH[chosen_side.side],
        clockwise_rotation_degrees=ROTATION_BY_SIDE[chosen_side.side],
        correction_clockwise_degrees=CORRECTION_BY_SIDE[chosen_side.side],
        confidence=confidence,
        needs_review=needs_review,
        debug_image=str(debug_path.relative_to(ROOT)),
        best_candidate=asdict(chosen_candidate) if chosen_candidate is not None else {},
        side_scores=[asdict(score) for score in sorted(side_scores, key=lambda item: item.score, reverse=True)],
        candidates=[asdict(candidate) for candidate in candidates[:12]],
    )


def write_results(results: list[DetectionResult]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    json_path = OUTPUT_DIR / "results.json"
    json_path.write_text(
        json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    csv_path = OUTPUT_DIR / "results.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "file",
                "title_block_side",
                "title_block_position",
                "clockwise_rotation_degrees",
                "correction_clockwise_degrees",
                "confidence",
                "needs_review",
                "debug_image",
            ],
        )
        writer.writeheader()
        for result in results:
            row = asdict(result)
            row.pop("best_candidate")
            row.pop("side_scores")
            row.pop("candidates")
            writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect mechanical drawing rotation from PNG images.")
    parser.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    if not args.input_dir.is_absolute():
        args.input_dir = ROOT / args.input_dir
    if not args.output_dir.is_absolute():
        args.output_dir = ROOT / args.output_dir
    return args


def main() -> None:
    global INPUT_DIR, OUTPUT_DIR, DEBUG_DIR
    args = parse_args()
    INPUT_DIR = args.input_dir
    OUTPUT_DIR = args.output_dir
    DEBUG_DIR = OUTPUT_DIR / "debug"

    if not INPUT_DIR.exists():
        raise SystemExit(f"Input directory does not exist: {INPUT_DIR}")

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    images = sorted(INPUT_DIR.glob("*.png"))
    if not images:
        raise SystemExit(f"No PNG files found in: {INPUT_DIR}")

    results = [detect_one(path) for path in images]
    write_results(results)

    for result in results:
        print(
            f"{result.file}: {result.title_block_side} -> "
            f"{result.clockwise_rotation_degrees} deg, confidence={result.confidence}, "
            f"review={result.needs_review}"
        )


if __name__ == "__main__":
    main()
