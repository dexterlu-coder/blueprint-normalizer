from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_DIAGNOSTIC_REPORT = (
    ROOT / "local_data" / "title_block_ocr_diagnostic" / "diagnostic_report.json"
)
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "yolo_postprocess" / "round3_multicandidate"

EXPECTED_ACCEPTED = {
    ("round3_train", "sample_001"),
    ("round3_train", "sample_009"),
    ("round3_train", "unclear90_001_from_sample_001"),
    ("round3_val", "aug90_007_from_sample_020"),
    ("round3_val", "sample_040"),
}

EXPECTED_NON_TITLE_TABLE_REJECTIONS = {
    ("round3_val", "aug90_002_from_sample_010"): 1,
    ("round3_round2_test", "aug90_002_from_sample_010"): 1,
}


def as_posix(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def html_rel_path(target: str | Path, html_path: Path) -> str:
    target_path = resolve_path(Path(target))
    return Path(os.path.relpath(target_path, html_path.parent)).as_posix()


def load_json(path: Path) -> Any:
    return json.loads(resolve_path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalized_to_pixels(
    points: list[list[float]], width: int, height: int
) -> list[tuple[int, int]]:
    return [
        (
            int(round(max(0.0, min(1.0, float(x))) * (width - 1))),
            int(round(max(0.0, min(1.0, float(y))) * (height - 1))),
        )
        for x, y in points
    ]


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def candidate_score(candidate: dict[str, Any], config: dict[str, float]) -> float:
    confidence = float(candidate.get("confidence") or 0.0)
    frame_contact = float(candidate.get("frame_contact_score") or 0.0)
    bbox = candidate["bbox_xyxy_normalized"]
    xmin, ymin, xmax, ymax = [float(value) for value in bbox]
    min_edge_distance = min(xmin, ymin, 1.0 - xmax, 1.0 - ymax)
    edge_proximity = clamp(1.0 - max(0.0, min_edge_distance) / config["edge_threshold"], 0.0, 1.0)
    area = float(candidate.get("area_normalized") or 0.0)
    size_score = clamp(1.0 - abs(area - config["target_area"]) / config["target_area"], 0.0, 1.0)
    structure_score = clamp(float(candidate.get("cell_area_variance") or 0.0) / 2.0, 0.0, 1.0)
    uniform_grid_penalty = float(candidate.get("uniform_grid_penalty") or 0.0)
    center_penalty = float(candidate.get("inside_drawing_body_penalty") or 0.0)
    out_of_bounds_penalty = 1.0 if any(
        float(x) < 0.0 or float(x) > 1.0 or float(y) < 0.0 or float(y) > 1.0
        for x, y in candidate["points_normalized"]
    ) else 0.0

    return (
        confidence
        + frame_contact * config["frame_contact_weight"]
        + edge_proximity * config["edge_weight"]
        + size_score * config["size_weight"]
        + structure_score * config["structure_weight"]
        - uniform_grid_penalty * config["uniform_grid_penalty_weight"]
        - center_penalty * config["center_penalty_weight"]
        - out_of_bounds_penalty * config["out_of_bounds_penalty_weight"]
    )


def rejection_reasons(
    candidate: dict[str, Any],
    selected_index: int,
    expected_reject_index: int | None,
) -> list[str]:
    reasons = ["not_selected_by_single_title_block_rule"]
    if candidate["candidate_index"] == expected_reject_index:
        reasons.append("non_title_table_false_positive")
    if "uniform_grid_like" in candidate.get("diagnostic_flags", []):
        reasons.append("uniform_grid_like")
    if candidate["candidate_index"] != selected_index:
        reasons.append("lower_confidence_duplicate_or_neighbor")
    return list(dict.fromkeys(reasons))


def group_candidates(candidates: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for candidate in candidates:
        key = (candidate["prediction_dir"], candidate["sample"])
        grouped.setdefault(key, []).append(candidate)
    for rows in grouped.values():
        rows.sort(key=lambda item: item["candidate_index"])
    return grouped


def build_record(
    prediction_dir: str,
    sample: str,
    candidates: list[dict[str, Any]],
    config: dict[str, float],
) -> dict[str, Any]:
    expected_reject_index = EXPECTED_NON_TITLE_TABLE_REJECTIONS.get((prediction_dir, sample))
    scored = []
    for candidate in candidates:
        row = dict(candidate)
        row["multicandidate_score"] = candidate_score(candidate, config)
        scored.append(row)

    scored.sort(key=lambda item: item["multicandidate_score"], reverse=True)
    selected = scored[0] if scored else None
    selected_index = selected["candidate_index"] if selected else None
    rejected = []
    for candidate in scored[1:]:
        rejected.append(
            {
                **candidate,
                "rejection_reasons": rejection_reasons(candidate, selected_index, expected_reject_index),
            }
        )

    issue_types: list[str] = []
    status = "accepted"
    if not selected:
        status = "needs_review"
        issue_types.append("missing_title_block")
    elif len(candidates) > 1:
        issue_types.append("multi_candidate_resolved")

    if expected_reject_index is not None:
        rejected_indices = {row["candidate_index"] for row in rejected}
        if expected_reject_index not in rejected_indices:
            status = "needs_review"
            issue_types.append("expected_false_positive_not_rejected")

    if (prediction_dir, sample) in EXPECTED_ACCEPTED and status == "accepted":
        issue_types.append("manual_expected_accepted")

    if sample in {"aug90_007_from_sample_020", "sample_040"} and status == "accepted":
        issue_types.append("small_angle_offset_tolerated")

    return {
        "prediction_dir": prediction_dir,
        "sample": sample,
        "prediction_count": len(candidates),
        "status": status,
        "issue_types": issue_types,
        "selected_candidate": selected,
        "rejected_candidates": rejected,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def draw_overlay(record: dict[str, Any], output_path: Path) -> str:
    selected = record["selected_candidate"]
    all_candidates = [selected] + record["rejected_candidates"] if selected else record["rejected_candidates"]
    source_image = resolve_path(Path(all_candidates[0]["source_image"]))
    with Image.open(source_image) as image:
        canvas = image.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except OSError:
        font = ImageFont.load_default()

    width, height = canvas.size
    for candidate in all_candidates:
        is_selected = selected and candidate["candidate_index"] == selected["candidate_index"]
        color = "lime" if is_selected else "red"
        points = normalized_to_pixels(candidate["points_normalized"], width, height)
        draw.line(points + [points[0]], fill=color, width=6)
        x, y = points[0]
        label = "selected" if is_selected else "rejected"
        text = f"#{candidate['candidate_index']} {label} {candidate['multicandidate_score']:.2f}"
        draw.rectangle((x, max(0, y - 26), x + max(260, len(text) * 10), y), fill="white")
        draw.text((x + 4, max(0, y - 24)), text, fill=color, font=font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return as_posix(output_path)


def write_html(path: Path, records: list[dict[str, Any]]) -> None:
    sections = []
    for record in records:
        overlay = html.escape(html_rel_path(record["overlay_path"], path))
        selected = record["selected_candidate"]
        selected_text = ""
        if selected:
            selected_text = (
                f"selected #{selected['candidate_index']} "
                f"score={selected['multicandidate_score']:.3f} "
                f"conf={selected.get('confidence')}"
            )
        rejected_rows = []
        for rejected in record["rejected_candidates"]:
            rejected_rows.append(
                "<tr>"
                f"<td>{rejected['candidate_index']}</td>"
                f"<td>{rejected['confidence']}</td>"
                f"<td>{rejected['multicandidate_score']:.3f}</td>"
                f"<td>{';'.join(rejected['rejection_reasons'])}</td>"
                "</tr>"
            )
        sections.append(
            f"""
      <section>
        <h2>{html.escape(record['prediction_dir'])} / {html.escape(record['sample'])}</h2>
        <p>{html.escape(record['status'])} | {html.escape(';'.join(record['issue_types']))} | {html.escape(selected_text)}</p>
        <a href="{overlay}" target="_blank"><img src="{overlay}" alt="{html.escape(record['sample'])}" /></a>
        <table>
          <thead><tr><th>rejected #</th><th>conf</th><th>score</th><th>reasons</th></tr></thead>
          <tbody>{''.join(rejected_rows)}</tbody>
        </table>
      </section>
"""
        )

    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>YOLO/OBB round3 多候选仲裁摘要</title>
  <style>
    body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; background: #f6f7f9; color: #202124; }}
    header {{ padding: 14px 18px; background: #fff; border-bottom: 1px solid #d8dde3; position: sticky; top: 0; }}
    h1 {{ margin: 0; font-size: 20px; }}
    main {{ padding: 14px; display: grid; gap: 14px; }}
    section {{ background: #fff; border: 1px solid #d8dde3; border-radius: 6px; padding: 12px; }}
    h2 {{ margin: 0 0 6px; font-size: 17px; }}
    p {{ margin: 0 0 10px; color: #5f6368; font-size: 13px; }}
    img {{ display: block; width: 100%; max-height: 720px; object-fit: contain; background: #fafafa; border: 1px solid #edf0f2; }}
    table {{ width: 100%; margin-top: 10px; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border: 1px solid #e1e5ea; padding: 5px 6px; text-align: left; vertical-align: top; }}
    th {{ background: #f1f3f4; }}
  </style>
</head>
<body>
  <header><h1>YOLO/OBB round3 多候选仲裁摘要</h1></header>
  <main>{''.join(sections)}</main>
</body>
</html>
""",
        encoding="utf-8",
    )


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    rejected = [candidate for record in records for candidate in record["rejected_candidates"]]
    failed_expectations = [
        record
        for record in records
        if "expected_false_positive_not_rejected" in record["issue_types"]
    ]
    return {
        "records": len(records),
        "accepted": sum(1 for record in records if record["status"] == "accepted"),
        "needs_review": sum(1 for record in records if record["status"] == "needs_review"),
        "multi_candidate_records": sum(1 for record in records if record["prediction_count"] > 1),
        "rejected_candidates": len(rejected),
        "failed_expectations": len(failed_expectations),
        "expected_false_positive_rejected": len(EXPECTED_NON_TITLE_TABLE_REJECTIONS) - len(failed_expectations),
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    diagnostic_report = load_json(args.diagnostic_report)
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "edge_threshold": args.edge_threshold,
        "target_area": args.target_area,
        "frame_contact_weight": args.frame_contact_weight,
        "edge_weight": args.edge_weight,
        "size_weight": args.size_weight,
        "structure_weight": args.structure_weight,
        "uniform_grid_penalty_weight": args.uniform_grid_penalty_weight,
        "center_penalty_weight": args.center_penalty_weight,
        "out_of_bounds_penalty_weight": args.out_of_bounds_penalty_weight,
    }

    grouped = group_candidates(diagnostic_report["candidates"])
    records = [
        build_record(prediction_dir, sample, candidates, config)
        for (prediction_dir, sample), candidates in sorted(grouped.items())
    ]

    for record in records:
        overlay_path = output_dir / "overlays" / f"{record['prediction_dir']}__{record['sample']}.jpg"
        record["overlay_path"] = draw_overlay(record, overlay_path)

    selected_rows = []
    rejected_rows = []
    for record in records:
        selected = record["selected_candidate"]
        if selected:
            selected_rows.append(
                {
                    "prediction_dir": record["prediction_dir"],
                    "sample": record["sample"],
                    "status": record["status"],
                    "issue_types": ";".join(record["issue_types"]),
                    "selected_candidate_index": selected["candidate_index"],
                    "selected_confidence": selected["confidence"],
                    "selected_score": selected["multicandidate_score"],
                    "prediction_count": record["prediction_count"],
                }
            )
        for rejected in record["rejected_candidates"]:
            rejected_rows.append(
                {
                    "prediction_dir": record["prediction_dir"],
                    "sample": record["sample"],
                    "candidate_index": rejected["candidate_index"],
                    "confidence": rejected["confidence"],
                    "score": rejected["multicandidate_score"],
                    "rejection_reasons": ";".join(rejected["rejection_reasons"]),
                }
            )

    summary = summarize(records)
    report = {
        "config": config,
        "diagnostic_report": as_posix(resolve_path(args.diagnostic_report)),
        "output_dir": as_posix(output_dir),
        "summary": summary,
        "records": records,
    }

    report_path = output_dir / "postprocess_report.json"
    summary_csv = output_dir / "postprocess_summary.csv"
    selected_csv = output_dir / "selected_candidates.csv"
    rejected_csv = output_dir / "rejected_candidates.csv"
    html_path = output_dir / "review_summary.html"
    write_json(report_path, report)
    write_csv(
        summary_csv,
        selected_rows,
        [
            "prediction_dir",
            "sample",
            "status",
            "issue_types",
            "selected_candidate_index",
            "selected_confidence",
            "selected_score",
            "prediction_count",
        ],
    )
    write_csv(
        selected_csv,
        selected_rows,
        [
            "prediction_dir",
            "sample",
            "status",
            "issue_types",
            "selected_candidate_index",
            "selected_confidence",
            "selected_score",
            "prediction_count",
        ],
    )
    write_csv(
        rejected_csv,
        rejected_rows,
        ["prediction_dir", "sample", "candidate_index", "confidence", "score", "rejection_reasons"],
    )
    write_html(html_path, records)

    return {
        "output_dir": as_posix(output_dir),
        "postprocess_report": as_posix(report_path),
        "selected_candidates": as_posix(selected_csv),
        "rejected_candidates": as_posix(rejected_csv),
        "review_summary": as_posix(html_path),
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Postprocess round3 YOLO/OBB multi-candidate predictions.")
    parser.add_argument("--diagnostic-report", type=Path, default=DEFAULT_DIAGNOSTIC_REPORT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--edge-threshold", type=float, default=0.12)
    parser.add_argument("--target-area", type=float, default=0.04)
    parser.add_argument("--frame-contact-weight", type=float, default=0.25)
    parser.add_argument("--edge-weight", type=float, default=0.15)
    parser.add_argument("--size-weight", type=float, default=0.20)
    parser.add_argument("--structure-weight", type=float, default=0.10)
    parser.add_argument("--uniform-grid-penalty-weight", type=float, default=0.35)
    parser.add_argument("--center-penalty-weight", type=float, default=0.40)
    parser.add_argument("--out-of-bounds-penalty-weight", type=float, default=0.50)
    args = parser.parse_args()

    print(json.dumps(build(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

