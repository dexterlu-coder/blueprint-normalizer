from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_COMPARISON_DIR = ROOT / "outputs" / "rotation-detection" / "comparison"
DEFAULT_MCP_RESULTS = DEFAULT_COMPARISON_DIR / "mcp_results.json"
DEFAULT_THREE_WAY = DEFAULT_COMPARISON_DIR / "three_way_comparison.csv"
DEFAULT_DISAGREEMENTS = DEFAULT_COMPARISON_DIR / "disagreements.csv"
DEFAULT_ROUTING_REPORT = (
    ROOT / "local_data" / "yolo_postprocess" / "routing" / "routing_report.json"
)
DEFAULT_ROUND3_REPORT = (
    ROOT / "local_data" / "yolo_postprocess" / "general_round3_diagnostic" / "postprocess_report.json"
)
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "mcp_vlm_teacher_review"

HARDCASE_SAMPLES = {
    "sample_001",
    "sample_009",
    "sample_010",
    "unclear90_001_from_sample_001",
    "aug90_002_from_sample_010",
}


def as_posix(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> Any:
    return json.loads(resolve_path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with resolve_path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def bool_text(value: str) -> bool:
    return str(value).strip().lower() == "true"


def summarize_three_way(rows: list[dict[str, str]]) -> dict[str, Any]:
    total = len(rows)
    mcp_matches_manual = sum(1 for row in rows if bool_text(row["mcp_matches_manual"]))
    opencv_matches_manual = sum(1 for row in rows if bool_text(row["opencv_matches_manual"]))
    three_way_agree = sum(1 for row in rows if bool_text(row["three_way_agree"]))
    mcp_corrects_opencv = [
        row
        for row in rows
        if bool_text(row["mcp_matches_manual"]) and not bool_text(row["opencv_matches_manual"])
    ]
    low_confidence_agreements = [
        row
        for row in rows
        if bool_text(row["mcp_matches_manual"])
        and bool_text(row["opencv_matches_manual"])
        and str(row.get("opencv_needs_review", "")).lower() == "true"
    ]
    return {
        "total": total,
        "mcp_matches_manual": mcp_matches_manual,
        "opencv_matches_manual": opencv_matches_manual,
        "three_way_agree": three_way_agree,
        "mcp_match_rate": round(mcp_matches_manual / total, 6) if total else 0.0,
        "opencv_match_rate": round(opencv_matches_manual / total, 6) if total else 0.0,
        "mcp_corrects_opencv_count": len(mcp_corrects_opencv),
        "mcp_corrects_opencv_samples": [row["sample"] for row in mcp_corrects_opencv],
        "low_confidence_agreement_samples": [row["sample"] for row in low_confidence_agreements],
    }


def distillation_rows(
    three_way_rows: list[dict[str, str]],
    routing_report: dict[str, Any],
    round3_report: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for row in three_way_rows:
        sample = row["sample"]
        if bool_text(row["mcp_matches_manual"]) and not bool_text(row["opencv_matches_manual"]):
            rows.append(
                {
                    "source": "three_way_mcp_correction",
                    "sample": sample,
                    "prediction_dir": "",
                    "candidate_index": "",
                    "teacher_value": "mcp_corrected_opencv",
                    "distill_to_rule": "yes",
                    "distill_to_data": "yes",
                    "distill_to_model": "maybe",
                    "reason": "MCP matched manual while OpenCV was wrong",
                    "expected_teacher_question": "Why is the title block at the MCP/manual position rather than the OpenCV position?",
                }
            )
        elif bool_text(row["mcp_matches_manual"]) and bool_text(row["opencv_matches_manual"]) and sample == "sample_042":
            rows.append(
                {
                    "source": "three_way_low_confidence_agreement",
                    "sample": sample,
                    "prediction_dir": "",
                    "candidate_index": "",
                    "teacher_value": "confidence_calibration",
                    "distill_to_rule": "yes",
                    "distill_to_data": "maybe",
                    "distill_to_model": "no",
                    "reason": "MCP and OpenCV agreed with manual while OpenCV requested review",
                    "expected_teacher_question": "What visual evidence makes this low-confidence case still reliable?",
                }
            )

    for record in routing_report.get("records", []):
        sample = record.get("sample", "")
        routes = set(record.get("routes") or [])
        if sample in HARDCASE_SAMPLES or "retrain_candidate" in routes:
            rows.append(
                {
                    "source": "routing_hardcase",
                    "sample": sample,
                    "prediction_dir": record.get("prediction_dir", ""),
                    "candidate_index": record.get("selected_candidate_index", ""),
                    "teacher_value": "hardcase_explanation",
                    "distill_to_rule": "maybe",
                    "distill_to_data": "yes",
                    "distill_to_model": "maybe",
                    "reason": ";".join(record.get("route_reasons") or []),
                    "expected_teacher_question": "Should this selected candidate be accepted, reviewed, or used as a hard-case training signal?",
                }
            )

    for record in round3_report.get("records", []):
        if record.get("sample") != "aug90_002_from_sample_010":
            continue
        for candidate in record.get("rejected_candidates") or []:
            rows.append(
                {
                    "source": "round3_rejected_candidate",
                    "sample": record.get("sample", ""),
                    "prediction_dir": record.get("prediction_dir", ""),
                    "candidate_index": candidate.get("candidate_index", ""),
                    "teacher_value": "non_title_table_false_positive",
                    "distill_to_rule": "yes",
                    "distill_to_data": "yes",
                    "distill_to_model": "yes",
                    "reason": ";".join(candidate.get("rejection_reasons") or []),
                    "expected_teacher_question": "Why is this table-like candidate not the true title block?",
                }
            )

    unique: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            str(row["source"]),
            str(row["prediction_dir"]),
            str(row["sample"]),
            str(row["candidate_index"]),
        )
        unique[key] = row
    return list(unique.values())


def teacher_prompt() -> str:
    return """# MCP/VLM Teacher Prompt Draft

你是机械图纸标题栏判断 teacher。请只根据当前屏幕坐标和图像内容判断，不要按零件自然方向猜测。

任务：

1. 判断图纸标题栏位于当前图像的哪个方向：bottom / left / top / right / unknown。
2. 判断候选框是否是真实标题栏，而不是普通表格、明细栏、技术要求表或零件表格。
3. 判断标题栏或候选框是否贴住图纸外框线，标题栏与外框线之间是否存在空隙。
4. 判断候选内部是否具有标题栏字段组合，而不是只命中单个词。
5. 输出是否建议人工复核。

必须输出 JSON，不要输出额外解释：

```json
{
  "title_block_position": "bottom|left|top|right|unknown",
  "rotation_degrees": 0,
  "is_true_title_block": true,
  "touches_drawing_frame": true,
  "ordinary_table_false_positive_risk": "low|medium|high",
  "field_cluster_evidence": {
    "role_fields": ["设计", "校对", "审核", "批准"],
    "property_fields": ["材料", "比例", "重量", "图号"],
    "cluster_strength": "none|weak|medium|strong"
  },
  "layout_evidence": [
    "标题栏贴住图框线",
    "内部表格格子大小不完全一致",
    "候选不像普通明细表"
  ],
  "reject_reasons_if_not_title_block": [],
  "needs_human_review": false,
  "confidence": 0.0
}
```

若输入包含多个候选框，请对每个候选输出一条 candidate 判断，并给出最终 selected_candidate_index。
"""


def build(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    mcp_results = read_json(args.mcp_results)
    three_way_rows = read_csv(args.three_way)
    disagreements = read_csv(args.disagreements)
    routing_report = read_json(args.routing_report)
    round3_report = read_json(args.round3_report)

    summary = {
        "mcp_result_count": len(mcp_results),
        "three_way": summarize_three_way(three_way_rows),
        "disagreement_count": len(disagreements),
        "mcp_confidence_counts": dict(
            sorted(Counter(str(row.get("confidence", "")) for row in mcp_results).items())
        ),
    }
    candidates = distillation_rows(three_way_rows, routing_report, round3_report)
    candidate_type_counts = Counter(row["teacher_value"] for row in candidates)
    summary["distillation_candidate_count"] = len(candidates)
    summary["distillation_candidate_type_counts"] = dict(sorted(candidate_type_counts.items()))

    report = {
        "inputs": {
            "mcp_results": as_posix(resolve_path(args.mcp_results)),
            "three_way": as_posix(resolve_path(args.three_way)),
            "disagreements": as_posix(resolve_path(args.disagreements)),
            "routing_report": as_posix(resolve_path(args.routing_report)),
            "round3_report": as_posix(resolve_path(args.round3_report)),
        },
        "output_dir": as_posix(output_dir),
        "summary": summary,
        "disagreements": disagreements,
        "distillation_candidates": candidates,
    }

    report_path = output_dir / "teacher_review_report.json"
    summary_path = output_dir / "teacher_review_summary.csv"
    candidates_path = output_dir / "distillation_candidates.csv"
    prompt_path = output_dir / "teacher_prompt_draft.md"

    write_json(report_path, report)
    write_csv(
        summary_path,
        [
            {"metric": "mcp_result_count", "value": summary["mcp_result_count"]},
            {"metric": "three_way_total", "value": summary["three_way"]["total"]},
            {"metric": "mcp_match_rate", "value": summary["three_way"]["mcp_match_rate"]},
            {"metric": "opencv_match_rate", "value": summary["three_way"]["opencv_match_rate"]},
            {"metric": "mcp_corrects_opencv_count", "value": summary["three_way"]["mcp_corrects_opencv_count"]},
            {"metric": "distillation_candidate_count", "value": summary["distillation_candidate_count"]},
        ],
        ["metric", "value"],
    )
    write_csv(
        candidates_path,
        candidates,
        [
            "source",
            "sample",
            "prediction_dir",
            "candidate_index",
            "teacher_value",
            "distill_to_rule",
            "distill_to_data",
            "distill_to_model",
            "reason",
            "expected_teacher_question",
        ],
    )
    prompt_path.write_text(teacher_prompt(), encoding="utf-8")

    return {
        "output_dir": str(output_dir),
        "teacher_review_report": str(report_path),
        "teacher_review_summary": str(summary_path),
        "teacher_prompt_draft": str(prompt_path),
        "distillation_candidates": str(candidates_path),
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MCP/VLM teacher review report.")
    parser.add_argument("--mcp-results", type=Path, default=DEFAULT_MCP_RESULTS)
    parser.add_argument("--three-way", type=Path, default=DEFAULT_THREE_WAY)
    parser.add_argument("--disagreements", type=Path, default=DEFAULT_DISAGREEMENTS)
    parser.add_argument("--routing-report", type=Path, default=DEFAULT_ROUTING_REPORT)
    parser.add_argument("--round3-report", type=Path, default=DEFAULT_ROUND3_REPORT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    print(json.dumps(build(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

