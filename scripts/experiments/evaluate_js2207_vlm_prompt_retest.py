from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_OLD_ROWS = ROOT / "local_data" / "js2207_real_vlm_title_block_review" / "excel_review_rows.json"
DEFAULT_OLD_SUMMARY = ROOT / "local_data" / "js2207_real_vlm_title_block_review" / "excel_review_summary.json"
DEFAULT_NEW_DECISIONS = ROOT / "local_data" / "js2207_real_pdf_vlm_title_block_prompt_retest" / "vlm_decisions.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "js2207_real_pdf_vlm_title_block_prompt_retest" / "evaluation"
RECORD_VERSION = "js2207-vlm-prompt-retest-evaluation-v0.1"

POSITION_ALIASES = {
    "bottom": "bottom_edge",
    "下方": "bottom_edge",
    "底部": "bottom_edge",
    "底边": "bottom_edge",
    "bottom_edge": "bottom_edge",
    "top": "top_edge",
    "上方": "top_edge",
    "顶部": "top_edge",
    "顶边": "top_edge",
    "top_edge": "top_edge",
    "left": "left_edge",
    "左侧": "left_edge",
    "left_edge": "left_edge",
    "right": "right_edge",
    "右侧": "right_edge",
    "right_edge": "right_edge",
    "bottom_right": "bottom_right",
    "右下方": "bottom_right",
    "右下角": "bottom_right",
    "bottom_left": "bottom_left",
    "左下方": "bottom_left",
    "左下角": "bottom_left",
    "top_right": "top_right",
    "右上方": "top_right",
    "右上角": "top_right",
    "top_left": "top_left",
    "左上方": "top_left",
    "左上角": "top_left",
    "no_title_block": "no_title_block",
    "无标题栏": "no_title_block",
    "没有标题栏": "no_title_block",
    "unknown": "unknown",
    "未知": "unknown",
}

POSITION_TO_ROTATION_GROUP = {
    "bottom_edge": 0,
    "bottom_right": 0,
    "bottom_left": 90,
    "left_edge": 90,
    "top_left": 180,
    "top_edge": 180,
    "top_right": 270,
    "right_edge": 270,
}


def as_posix(path: Path | str | None) -> str | None:
    if path is None:
        return None
    path_obj = Path(path)
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_json(path: Path) -> Any:
    return json.loads(resolve_path(path).read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in resolve_path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def normalize_position(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    return POSITION_ALIASES.get(text, text)


def normalize_judgment(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if text in {"正确", "对", "是", "ok", "OK"}:
        return "正确"
    if text in {"错误", "错", "否", "不正确"}:
        return "错误"
    return text


def has_no_title_note(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return "没有标题栏" in value or "无标题栏" in value or "只有零件表格" in value


def truth_from_excel_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_page: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_page[str(row.get("页码", ""))].append(row)

    truth: dict[str, dict[str, Any]] = {}
    for page_number, page_rows in by_page.items():
        expected_positions: list[str] = []
        notes: list[str] = []
        source_rows: list[dict[str, Any]] = []
        for row in page_rows:
            notes.append(row.get("备注", ""))
            judgment = normalize_judgment(row.get("位置是否正确"))
            if judgment == "正确":
                expected_positions.append(normalize_position(row.get("模型标题栏位置代码")))
                source_rows.append(row)
            elif judgment == "错误":
                correct_position = normalize_position(row.get("正确标题栏位置"))
                if correct_position:
                    expected_positions.append(correct_position)
                    source_rows.append(row)
                elif has_no_title_note(row.get("备注")):
                    expected_positions.append("no_title_block")
                    source_rows.append(row)

        cleaned = [position for position in expected_positions if position]
        counts = Counter(cleaned)
        expected = counts.most_common(1)[0][0] if counts else "unknown"
        truth[page_number] = {
            "page_number": page_number,
            "expected_position": expected,
            "expected_rotation_group": POSITION_TO_ROTATION_GROUP.get(expected),
            "position_votes": dict(counts),
            "notes": [note for note in notes if note],
            "source_row_count": len(source_rows),
            "needs_manual_truth_check": len(counts) > 1,
        }
    return truth


def evaluate_decisions(decisions: list[dict[str, Any]], truth: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for decision in decisions:
        page_number = str(decision.get("page_number", ""))
        truth_row = truth.get(page_number, {})
        predicted = normalize_position(decision.get("title_block_position"))
        expected = truth_row.get("expected_position", "unknown")
        predicted_rotation = POSITION_TO_ROTATION_GROUP.get(predicted)
        expected_rotation = truth_row.get("expected_rotation_group")
        exact_match = predicted == expected
        rotation_match = (
            predicted_rotation == expected_rotation
            if predicted_rotation is not None and expected_rotation is not None
            else exact_match
        )
        rows.append(
            {
                "page_number": page_number,
                "task_id": decision.get("task_id", ""),
                "model": decision.get("model", ""),
                "expected_position": expected,
                "predicted_position": predicted,
                "exact_match": exact_match,
                "expected_rotation_group": expected_rotation,
                "predicted_rotation_group": predicted_rotation,
                "rotation_group_match": rotation_match,
                "orientation_confidence": decision.get("orientation_confidence", ""),
                "needs_review": decision.get("needs_review", ""),
                "review_reasons": ";".join(decision.get("review_reasons") or []),
                "truth_votes": json.dumps(truth_row.get("position_votes", {}), ensure_ascii=False),
                "truth_notes": "；".join(truth_row.get("notes", [])),
            }
        )
    return rows


def summarize(rows: list[dict[str, Any]], old_summary: dict[str, Any]) -> dict[str, Any]:
    model_names = sorted({str(row.get("model", "")) for row in rows})
    by_model = {}
    for model in model_names:
        model_rows = [row for row in rows if row.get("model") == model]
        by_model[model] = {
            "row_count": len(model_rows),
            "exact_correct": sum(1 for row in model_rows if row.get("exact_match") is True),
            "exact_accuracy": round(sum(1 for row in model_rows if row.get("exact_match") is True) / len(model_rows), 4)
            if model_rows
            else 0,
            "rotation_group_correct": sum(1 for row in model_rows if row.get("rotation_group_match") is True),
            "rotation_group_accuracy": round(
                sum(1 for row in model_rows if row.get("rotation_group_match") is True) / len(model_rows), 4
            )
            if model_rows
            else 0,
        }

    exact_correct = sum(1 for row in rows if row.get("exact_match") is True)
    rotation_correct = sum(1 for row in rows if row.get("rotation_group_match") is True)
    old_correct = int((old_summary.get("judgment_counts") or {}).get("正确", 0))
    old_total = int(old_summary.get("row_count") or 0)
    total = len(rows)
    return {
        "record_version": RECORD_VERSION,
        "row_count": total,
        "old_exact_correct": old_correct,
        "old_row_count": old_total,
        "old_exact_accuracy": round(old_correct / old_total, 4) if old_total else 0,
        "new_exact_correct": exact_correct,
        "new_exact_accuracy": round(exact_correct / total, 4) if total else 0,
        "new_rotation_group_correct": rotation_correct,
        "new_rotation_group_accuracy": round(rotation_correct / total, 4) if total else 0,
        "exact_correct_delta": exact_correct - old_correct,
        "by_model": by_model,
        "position_counts": dict(Counter(row.get("predicted_position", "") for row in rows)),
        "expected_position_counts": dict(Counter(row.get("expected_position", "") for row in rows)),
        "modified_pdf": False,
        "renamed_pdf": False,
        "csv_used_as_human_source": False,
    }


def write_markdown(path: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    failed = [row for row in rows if row.get("exact_match") is not True]
    lines = [
        "# JS2207 VLM Prompt 复测评估摘要",
        "",
        f"- 旧版精确正确率：{summary['old_exact_correct']}/{summary['old_row_count']} ({summary['old_exact_accuracy']})",
        f"- 新版精确正确率：{summary['new_exact_correct']}/{summary['row_count']} ({summary['new_exact_accuracy']})",
        f"- 新版旋转分组正确率：{summary['new_rotation_group_correct']}/{summary['row_count']} ({summary['new_rotation_group_accuracy']})",
        f"- 精确正确数变化：{summary['exact_correct_delta']}",
        "- CSV 是否作为人工来源：False",
        "- 是否生成正式 PDF：False",
        "- 是否重命名 PDF：False",
        "",
        "## 分模型",
        "",
    ]
    for model, stats in summary["by_model"].items():
        lines.append(
            f"- {model}：精确 {stats['exact_correct']}/{stats['row_count']} ({stats['exact_accuracy']})；"
            f"旋转分组 {stats['rotation_group_correct']}/{stats['row_count']} ({stats['rotation_group_accuracy']})"
        )
    lines.extend(["", "## 精确错误记录", ""])
    if not failed:
        lines.append("- 无。")
    else:
        for row in failed:
            lines.append(
                "- 第 {page} 页 {model}：预测 {predicted}，期望 {expected}，备注 {notes}".format(
                    page=row["page_number"],
                    model=row["model"],
                    predicted=row["predicted_position"],
                    expected=row["expected_position"],
                    notes=row["truth_notes"],
                )
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    old_rows = load_json(args.old_rows)
    old_summary = load_json(args.old_summary)
    decisions = load_jsonl(args.new_decisions)
    truth = truth_from_excel_rows(old_rows)
    rows = evaluate_decisions(decisions, truth)
    summary = summarize(rows, old_summary)

    rows_json = output_dir / "prompt_retest_evaluation_rows.json"
    rows_csv = output_dir / "prompt_retest_evaluation_rows.csv"
    truth_json = output_dir / "prompt_retest_truth_by_page.json"
    summary_json = output_dir / "prompt_retest_evaluation_summary.json"
    summary_md = output_dir / "prompt_retest_evaluation_summary.md"
    write_json(rows_json, rows)
    write_csv(
        rows_csv,
        rows,
        [
            "page_number",
            "task_id",
            "model",
            "expected_position",
            "predicted_position",
            "exact_match",
            "expected_rotation_group",
            "predicted_rotation_group",
            "rotation_group_match",
            "orientation_confidence",
            "needs_review",
            "review_reasons",
            "truth_votes",
            "truth_notes",
        ],
    )
    write_json(truth_json, truth)
    write_json(summary_json, summary)
    write_markdown(summary_md, summary, rows)
    result = {
        **summary,
        "outputs": {
            "rows_json": as_posix(rows_json),
            "rows_csv": as_posix(rows_csv),
            "truth_json": as_posix(truth_json),
            "summary_json": as_posix(summary_json),
            "summary_md": as_posix(summary_md),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate JS2207 VLM prompt retest against Excel review truth.")
    parser.add_argument("--old-rows", type=Path, default=DEFAULT_OLD_ROWS)
    parser.add_argument("--old-summary", type=Path, default=DEFAULT_OLD_SUMMARY)
    parser.add_argument("--new-decisions", type=Path, default=DEFAULT_NEW_DECISIONS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
