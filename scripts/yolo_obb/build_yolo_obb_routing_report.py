from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_REPORTS = [
    ROOT / "local_data" / "yolo_postprocess" / "round2_first_train" / "postprocess_report.json",
    ROOT / "local_data" / "yolo_postprocess" / "general_round3_diagnostic" / "postprocess_report.json",
]
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "yolo_postprocess" / "routing"

BLOCKING_ISSUES = {
    "missing_title_block",
    "missing_prediction_label",
    "manual_rejected",
    "partial_title_block",
    "part_false_positive",
    "out_of_page_bounds",
    "boundary_too_large",
    "expected_false_positive_not_rejected",
}

OCR_HINT_FLAGS = {
    "ocr_unavailable",
    "role_cluster_weak",
    "property_cluster_weak",
}


def as_posix(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> Any:
    return json.loads(resolve_path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def route_record(report_name: str, record: dict[str, Any]) -> dict[str, Any]:
    issue_types = set(record.get("issue_types") or [])
    selected = record.get("selected_title_block") or {}
    rejected_candidates = record.get("rejected_candidates") or []
    candidate_flags = set(selected.get("candidate_flags") or [])
    diagnostic_flags = set(selected.get("diagnostic_flags") or [])
    selected_confidence = float(record.get("selected_confidence") or selected.get("confidence") or 0.0)
    selected_score = float(record.get("selected_score") or selected.get("candidate_score") or 0.0)
    touches_frame = bool(selected.get("touches_frame_line"))
    frame_status = selected.get("frame_contact_status") or ""
    has_selected = bool(selected)
    has_blocking_issue = bool(issue_types.intersection(BLOCKING_ISSUES))
    has_unexplained_rejected = any(
        not candidate.get("rejection_reasons") for candidate in rejected_candidates
    )

    routes: list[str] = []
    reasons: list[str] = []

    if record.get("status") == "needs_review" or has_blocking_issue or not has_selected:
        routes.append("human_review")
        if record.get("status") == "needs_review":
            reasons.append("postprocess_needs_review")
        if has_blocking_issue:
            reasons.append("blocking_issue")
        if not has_selected:
            reasons.append("missing_selected_title_block")
    elif frame_status == "gap" and not touches_frame:
        routes.append("human_review")
        reasons.append("selected_candidate_not_touching_frame")
    else:
        routes.append("auto_accept")
        if "multi_candidate_resolved" in issue_types:
            reasons.append("multi_candidate_resolved")
        else:
            reasons.append("postprocess_accepted")

    if diagnostic_flags.intersection(OCR_HINT_FLAGS):
        routes.append("ocr_candidate")
        reasons.append("ocr_or_field_cluster_evidence_incomplete")
    if "uniform_grid_like" in candidate_flags and "auto_accept" not in routes:
        routes.append("ocr_candidate")
        reasons.append("selected_candidate_uniform_grid_like")

    if has_unexplained_rejected:
        routes.append("human_review")
        routes.append("vlm_candidate")
        reasons.append("rejected_candidate_without_reason")
    if (
        "human_review" in routes
        and selected_confidence < 0.50
        and not issue_types.intersection({"manual_rejected", "boundary_too_large"})
    ):
        routes.append("vlm_candidate")
        reasons.append("low_confidence_human_review")

    if issue_types.intersection({"missing_title_block", "part_false_positive", "partial_title_block"}):
        routes.append("retrain_candidate")
        reasons.append("model_failure_pattern_candidate")
    if record.get("manual_acceptance") == "不可接受":
        routes.append("retrain_candidate")
        reasons.append("manual_rejected_training_signal")

    routes = list(dict.fromkeys(routes))
    reasons = list(dict.fromkeys(reasons))

    return {
        "report": report_name,
        "prediction_dir": record.get("prediction_dir", ""),
        "split": record.get("split", ""),
        "sample": record.get("sample", ""),
        "status": record.get("status", ""),
        "routes": routes,
        "route_reasons": reasons,
        "issue_types": list(record.get("issue_types") or []),
        "prediction_count": record.get("prediction_count", 0),
        "selected_candidate_index": record.get("selected_candidate_index"),
        "selected_confidence": selected_confidence,
        "selected_score": selected_score,
        "touches_frame_line": touches_frame,
        "frame_contact_status": frame_status,
        "rejected_candidate_count": len(rejected_candidates),
        "rejected_reasons": [
            ";".join(candidate.get("rejection_reasons") or [])
            for candidate in rejected_candidates
        ],
        "manual_acceptance": record.get("manual_acceptance", ""),
        "paths": record.get("paths", {}),
    }


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    route_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    report_counts: Counter[str] = Counter()
    for record in records:
        status_counts[record["status"]] += 1
        report_counts[record["report"]] += 1
        for route in record["routes"]:
            route_counts[route] += 1
    return {
        "records": len(records),
        "status_counts": dict(sorted(status_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "report_counts": dict(sorted(report_counts.items())),
    }


def write_route_csv(path: Path, records: list[dict[str, Any]]) -> None:
    fieldnames = [
        "report",
        "prediction_dir",
        "split",
        "sample",
        "status",
        "routes",
        "route_reasons",
        "issue_types",
        "prediction_count",
        "selected_candidate_index",
        "selected_confidence",
        "selected_score",
        "touches_frame_line",
        "frame_contact_status",
        "rejected_candidate_count",
        "rejected_reasons",
        "manual_acceptance",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    **{field: record.get(field, "") for field in fieldnames},
                    "routes": ";".join(record["routes"]),
                    "route_reasons": ";".join(record["route_reasons"]),
                    "issue_types": ";".join(record["issue_types"]),
                    "rejected_reasons": " | ".join(record["rejected_reasons"]),
                }
            )


def write_summary_csv(path: Path, summary: dict[str, Any]) -> None:
    rows = []
    for group_name in ("status_counts", "route_counts", "report_counts"):
        for key, count in summary[group_name].items():
            rows.append({"group": group_name, "name": key, "count": count})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["group", "name", "count"])
        writer.writeheader()
        writer.writerows(rows)


def build(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    route_records: list[dict[str, Any]] = []
    report_paths = [resolve_path(path) for path in args.reports]
    for report_path in report_paths:
        report = load_json(report_path)
        report_name = report_path.parent.name
        for record in report.get("records", []):
            route_records.append(route_record(report_name, record))

    summary = summarize(route_records)
    result = {
        "reports": [as_posix(path) for path in report_paths],
        "output_dir": as_posix(output_dir),
        "summary": summary,
        "records": route_records,
    }

    report_path = output_dir / "routing_report.json"
    route_csv_path = output_dir / "route_records.csv"
    summary_csv_path = output_dir / "routing_summary.csv"
    write_json(report_path, result)
    write_route_csv(route_csv_path, route_records)
    write_summary_csv(summary_csv_path, summary)

    return {
        "output_dir": str(output_dir),
        "routing_report": str(report_path),
        "route_records": str(route_csv_path),
        "routing_summary": str(summary_csv_path),
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build YOLO/OBB difficult case routing report.")
    parser.add_argument("--reports", nargs="+", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    print(json.dumps(build(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

