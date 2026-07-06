from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_VALIDATED_RESPONSES = (
    ROOT / "local_data" / "mcp_vlm_teacher_provider" / "validated_responses.json"
)
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "mcp_vlm_teacher_distillation"


def as_posix(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> Any:
    return json.loads(resolve_path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def task_kind(task_id: str) -> str:
    if "mcp_correction" in task_id:
        return "mcp_corrected_opencv"
    if "low_confidence" in task_id:
        return "confidence_calibration"
    if "rejected_candidate" in task_id:
        return "non_title_table_false_positive"
    if "sample_040" in task_id:
        return "small_angle_offset_tolerated"
    return "hardcase_positive"


def sample_name(task_id: str) -> str:
    markers = [
        "__sample_",
        "__aug90_",
        "__unclear90_",
    ]
    for marker in markers:
        if marker in task_id:
            tail = task_id.split(marker, 1)[1]
            if marker == "__sample_":
                return "sample_" + tail.split("__candidate_", 1)[0]
            if marker == "__aug90_":
                return "aug90_" + tail.split("__candidate_", 1)[0]
            if marker == "__unclear90_":
                return "unclear90_" + tail.split("__candidate_", 1)[0]
    return task_id


def action_targets(kind: str, judgment: dict[str, Any], parsed: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    is_true = bool(judgment.get("is_true_title_block"))
    field_strength = judgment.get("field_cluster_strength", "")
    false_positive_risk = judgment.get("ordinary_table_false_positive_risk", "")
    touches_frame = bool(judgment.get("touches_drawing_frame"))
    reject_reasons = set(judgment.get("reject_reasons_if_not_title_block") or [])

    if is_true and touches_frame and field_strength in {"medium", "strong"}:
        targets.append("rule")
    if is_true and kind in {"hardcase_positive", "small_angle_offset_tolerated"}:
        targets.append("data")
    if kind == "confidence_calibration":
        targets.append("rule")
        targets.append("provider")
    if false_positive_risk == "high" or reject_reasons:
        targets.append("rule")
        targets.append("data")
        targets.append("model")
    if kind == "mcp_corrected_opencv":
        targets.append("rule")
        targets.append("provider")
    if parsed.get("needs_human_review"):
        targets.append("provider")

    return list(dict.fromkeys(targets))


def recommendation(kind: str, judgment: dict[str, Any], parsed: dict[str, Any]) -> str:
    if not judgment.get("is_true_title_block"):
        return "作为普通表格/明细表反例，蒸馏到方向无关的误检拒绝规则，并保留为负样本。"
    if kind == "small_angle_offset_tolerated":
        return "作为小角度 OBB 偏差可接受正例，蒸馏为覆盖标题栏主体优先于微小角度误差的规则。"
    if kind == "confidence_calibration":
        return "作为低置信但可接受样本，蒸馏为字段簇和贴边证据的置信校准规则。"
    if kind == "mcp_corrected_opencv":
        return "作为 MCP 纠偏 OpenCV 样本，蒸馏为标题栏字段簇优先于普通线条密度的仲裁规则。"
    if parsed.get("confidence", 0) < 0.85:
        return "作为 hard-case 正例保留，用于后续候选 crop 小分类器或 provider 小实验。"
    return "作为稳定正例保留，用于验证贴边、字段簇和标题栏位置规则。"


def flatten_actions(validated: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for row in validated:
        task_id = row.get("task_id", "")
        parsed = row.get("parsed_response") or {}
        kind = task_kind(task_id)
        for judgment in parsed.get("candidate_judgments") or []:
            targets = action_targets(kind, judgment, parsed)
            actions.append(
                {
                    "task_id": task_id,
                    "sample": sample_name(task_id),
                    "task_kind": kind,
                    "candidate_index": judgment.get("candidate_index"),
                    "is_true_title_block": judgment.get("is_true_title_block"),
                    "title_block_position": parsed.get("title_block_position"),
                    "rotation_degrees": parsed.get("rotation_degrees"),
                    "touches_drawing_frame": judgment.get("touches_drawing_frame"),
                    "field_cluster_strength": judgment.get("field_cluster_strength"),
                    "ordinary_table_false_positive_risk": judgment.get(
                        "ordinary_table_false_positive_risk"
                    ),
                    "reject_reasons": ";".join(judgment.get("reject_reasons_if_not_title_block") or []),
                    "distill_targets": ";".join(targets),
                    "recommendation": recommendation(kind, judgment, parsed),
                    "layout_evidence": " | ".join(judgment.get("layout_evidence") or []),
                    "confidence": parsed.get("confidence"),
                    "needs_human_review": parsed.get("needs_human_review"),
                }
            )
    return actions


def summarize(validated: list[dict[str, Any]], actions: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(row.get("status", "") for row in validated)
    kind_counts = Counter(action["task_kind"] for action in actions)
    target_counts: Counter[str] = Counter()
    field_strength_counts = Counter(action["field_cluster_strength"] for action in actions)
    false_positive_counts = Counter(action["ordinary_table_false_positive_risk"] for action in actions)
    position_counts = Counter(action["title_block_position"] for action in actions)
    for action in actions:
        for target in str(action["distill_targets"]).split(";"):
            if target:
                target_counts[target] += 1
    true_count = sum(1 for action in actions if action["is_true_title_block"] is True)
    false_count = sum(1 for action in actions if action["is_true_title_block"] is False)
    review_count = sum(1 for action in actions if action["needs_human_review"] is True)
    return {
        "validated_response_count": len(validated),
        "action_count": len(actions),
        "status_counts": dict(sorted(status_counts.items())),
        "task_kind_counts": dict(sorted(kind_counts.items())),
        "distill_target_counts": dict(sorted(target_counts.items())),
        "field_cluster_strength_counts": dict(sorted(field_strength_counts.items())),
        "ordinary_table_false_positive_risk_counts": dict(sorted(false_positive_counts.items())),
        "title_block_position_counts": dict(sorted(position_counts.items())),
        "true_title_block_count": true_count,
        "false_title_block_count": false_count,
        "needs_human_review_count": review_count,
    }


def summary_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {"group": "summary", "name": "validated_response_count", "count": summary["validated_response_count"]},
        {"group": "summary", "name": "action_count", "count": summary["action_count"]},
        {"group": "summary", "name": "true_title_block_count", "count": summary["true_title_block_count"]},
        {"group": "summary", "name": "false_title_block_count", "count": summary["false_title_block_count"]},
        {"group": "summary", "name": "needs_human_review_count", "count": summary["needs_human_review_count"]},
    ]
    for group in (
        "status_counts",
        "task_kind_counts",
        "distill_target_counts",
        "field_cluster_strength_counts",
        "ordinary_table_false_positive_risk_counts",
        "title_block_position_counts",
    ):
        for name, count in summary[group].items():
            rows.append({"group": group, "name": name, "count": count})
    return rows


def rule_candidates_markdown(actions: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    true_actions = [action for action in actions if action["is_true_title_block"] is True]
    false_actions = [action for action in actions if action["is_true_title_block"] is False]
    lines = [
        "# MCP/VLM teacher rule candidates",
        "",
        "## Summary",
        "",
        f"- Validated responses: {summary['validated_response_count']}",
        f"- True title block judgments: {summary['true_title_block_count']}",
        f"- False title block judgments: {summary['false_title_block_count']}",
        f"- Needs human review: {summary['needs_human_review_count']}",
        "",
        "## Candidate rules",
        "",
        "1. When a candidate touches the drawing frame and has medium or strong title-block field clusters, prefer it over nearby ordinary table density.",
        "2. Reject uniform grid-like parts lists when they lack design/review/date/material/weight/scale field clusters, even if their table score is high.",
        "3. Treat ordinary table false positives as direction-independent; do not bind the rejection to top, bottom, left, or right.",
        "4. Allow small OBB angle or boundary offsets when the candidate still covers the title block body and field cluster.",
        "5. For faint scans, use frame contact plus field-cluster combination as confidence calibration evidence.",
        "",
        "## Positive evidence samples",
        "",
    ]
    for action in true_actions:
        lines.append(
            f"- `{action['sample']}`: {action['title_block_position']} / {action['rotation_degrees']} deg; "
            f"field={action['field_cluster_strength']}; {action['recommendation']}"
        )
    lines.extend(["", "## Negative evidence samples", ""])
    for action in false_actions:
        lines.append(
            f"- `{action['sample']}` candidate {action['candidate_index']}: "
            f"{action['reject_reasons']}; {action['recommendation']}"
        )
    lines.append("")
    return "\n".join(lines)


def build(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    validated = read_json(args.validated_responses)
    actions = flatten_actions(validated)
    summary = summarize(validated, actions)

    report = {
        "inputs": {
            "validated_responses": as_posix(resolve_path(args.validated_responses)),
        },
        "output_dir": as_posix(output_dir),
        "summary": summary,
        "actions": actions,
    }

    report_path = output_dir / "teacher_distillation_report.json"
    summary_path = output_dir / "teacher_distillation_summary.csv"
    actions_path = output_dir / "teacher_distillation_actions.csv"
    rules_path = output_dir / "teacher_rule_candidates.md"

    write_json(report_path, report)
    write_csv(summary_path, summary_rows(summary), ["group", "name", "count"])
    write_csv(
        actions_path,
        actions,
        [
            "task_id",
            "sample",
            "task_kind",
            "candidate_index",
            "is_true_title_block",
            "title_block_position",
            "rotation_degrees",
            "touches_drawing_frame",
            "field_cluster_strength",
            "ordinary_table_false_positive_risk",
            "reject_reasons",
            "distill_targets",
            "recommendation",
            "layout_evidence",
            "confidence",
            "needs_human_review",
        ],
    )
    rules_path.write_text(rule_candidates_markdown(actions, summary), encoding="utf-8")

    return {
        "output_dir": str(output_dir),
        "teacher_distillation_report": str(report_path),
        "teacher_distillation_summary": str(summary_path),
        "teacher_distillation_actions": str(actions_path),
        "teacher_rule_candidates": str(rules_path),
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MCP/VLM teacher response distillation analysis.")
    parser.add_argument("--validated-responses", type=Path, default=DEFAULT_VALIDATED_RESPONSES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    print(json.dumps(build(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

