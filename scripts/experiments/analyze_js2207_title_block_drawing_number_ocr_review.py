from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_REVIEW_DIR = ROOT / "local_data" / "review_inbox" / "current" / "js2207_title_block_drawing_number_ocr_review"
DEFAULT_XLSX = DEFAULT_REVIEW_DIR / "js2207_title_block_drawing_number_ocr_review.xlsx"
DEFAULT_MACHINE_DIR = ROOT / "local_data" / "js2207_title_block_drawing_number_ocr_test"
DEFAULT_OUTPUT_DIR = DEFAULT_MACHINE_DIR / "review_analysis"
DEFAULT_CURRENT_DIR = ROOT / "local_data" / "review_inbox" / "current"
RECORD_VERSION = "js2207-title-block-drawing-number-ocr-review-analysis-v0.1"
RISK_PAGES = {3: "no_title_block_or_not_drawing", 22: "known_rotation_error"}

TRUE_VALUES = {"是", "正确", "对", "對", "y", "yes", "1", "true", "ok", "√", "✓"}
FALSE_VALUES = {"否", "错误", "錯誤", "错", "錯", "不正确", "不對", "不对", "n", "no", "0", "false", "x", "×"}
MODEL_ORDER = {
    "qwen3.7-plus": 0,
    "qwen3.7-max-2026-06-08": 1,
    "qwen3.5-ocr": 2,
    "qwen-vl-ocr-latest": 3,
}


def as_posix(path: Path | str | None) -> str | None:
    if path is None:
        return None
    path_obj = Path(path)
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return re.sub(r"\s+", "", text)


def normalize_drawing_number(value: Any) -> str:
    text = normalize_text(value)
    return text.replace("_", "-")


def judge_value(value: Any) -> str:
    text = normalize_text(value).lower()
    if not text:
        return "unreviewed_or_unknown"
    if text in TRUE_VALUES:
        return "correct"
    if text in FALSE_VALUES:
        return "incorrect"
    if "正确" in text and "不正确" not in text:
        return "correct"
    if "错误" in text or text == "錯誤":
        return "incorrect"
    return "unreviewed_or_unknown"


def cell_text(cell: ET.Element, shared_strings: list[str], ns: dict[str, str]) -> str:
    cell_type = cell.attrib.get("t")
    value_elem = cell.find("m:v", ns)
    if value_elem is None:
        inline_elem = cell.find("m:is/m:t", ns)
        return inline_elem.text if inline_elem is not None and inline_elem.text else ""
    raw = value_elem.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return ""
    return raw


def column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    value = 0
    for char in letters:
        value = value * 26 + (ord(char.upper()) - ord("A") + 1)
    return value - 1


def read_xlsx(path: Path) -> list[dict[str, str]]:
    resolved = resolve_path(path)
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(resolved) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for si in shared_root.findall("m:si", ns):
                parts = [node.text or "" for node in si.findall(".//m:t", ns)]
                shared_strings.append("".join(parts))
        sheet_root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    rows: list[list[str]] = []
    for row_elem in sheet_root.findall(".//m:sheetData/m:row", ns):
        row_values: dict[int, str] = {}
        max_col = -1
        for cell in row_elem.findall("m:c", ns):
            ref = cell.attrib.get("r", "")
            col = column_index(ref)
            row_values[col] = cell_text(cell, shared_strings, ns)
            max_col = max(max_col, col)
        rows.append([row_values.get(index, "") for index in range(max_col + 1)])
    if not rows:
        return []
    headers = rows[0]
    result: list[dict[str, str]] = []
    for row in rows[1:]:
        if not any(str(item).strip() for item in row):
            continue
        result.append({header: row[index] if index < len(row) else "" for index, header in enumerate(headers)})
    return result


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    resolved = resolve_path(path)
    if not resolved.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in resolved.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def safe_reset_child_dir(path: Path, allowed_root: Path) -> None:
    resolved = path.resolve()
    allowed = allowed_root.resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise ValueError(f"Refusing to reset outside allowed root: {resolved}") from exc
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def build_review_rows(human_rows: list[dict[str, str]], machine_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    machine_by_key = {
        (int(row["page_number"]), row["model"]): row
        for row in machine_rows
        if row.get("page_number") is not None and row.get("model")
    }
    review_rows: list[dict[str, Any]] = []
    for index, row in enumerate(human_rows, start=1):
        page_number = int(float(row.get("页码", "0") or 0))
        model = row.get("模型", "")
        machine = machine_by_key.get((page_number, model), {})
        model_value = normalize_drawing_number(row.get("模型提取图号", ""))
        correct_value = normalize_drawing_number(row.get("正确图号", ""))
        status = judge_value(row.get("图号是否正确", ""))
        effective_truth = model_value if status == "correct" else correct_value
        review_rows.append(
            {
                "row_index": index,
                "page_number": page_number,
                "model": model,
                "model_extracted": model_value,
                "human_status_raw": row.get("图号是否正确", ""),
                "human_status": status,
                "correct_drawing_number": correct_value,
                "effective_truth": effective_truth,
                "remark": row.get("备注", ""),
                "risk": RISK_PAGES.get(page_number, ""),
                "machine_parse_status": machine.get("parse_status", ""),
                "machine_schema_status": machine.get("schema_status", ""),
                "machine_needs_review": machine.get("needs_review", ""),
            }
        )
    return sorted(review_rows, key=lambda item: (item["page_number"], MODEL_ORDER.get(item["model"], 999), item["model"]))


def summarize(rows: list[dict[str, Any]], exclude_risk_pages: bool = False) -> dict[str, Any]:
    filtered = [row for row in rows if not exclude_risk_pages or not row["risk"]]
    by_model: dict[str, dict[str, Any]] = {}
    for model in sorted({row["model"] for row in filtered}, key=lambda item: (MODEL_ORDER.get(item, 999), item)):
        model_rows = [row for row in filtered if row["model"] == model]
        status_counts = Counter(row["human_status"] for row in model_rows)
        reviewed = status_counts["correct"] + status_counts["incorrect"]
        correct = status_counts["correct"]
        incorrect = status_counts["incorrect"]
        empty_predictions = sum(1 for row in model_rows if not row["model_extracted"])
        corrected_values = sum(1 for row in model_rows if row["human_status"] == "incorrect" and row["correct_drawing_number"])
        by_model[model] = {
            "total_rows": len(model_rows),
            "reviewed_rows": reviewed,
            "correct": correct,
            "incorrect": incorrect,
            "unreviewed_or_unknown": status_counts["unreviewed_or_unknown"],
            "accuracy_reviewed": round(correct / reviewed, 6) if reviewed else None,
            "empty_predictions": empty_predictions,
            "incorrect_with_correct_value": corrected_values,
        }
    status_counts = Counter(row["human_status"] for row in filtered)
    reviewed_total = status_counts["correct"] + status_counts["incorrect"]
    return {
        "exclude_risk_pages": exclude_risk_pages,
        "row_count": len(filtered),
        "reviewed_rows": reviewed_total,
        "correct": status_counts["correct"],
        "incorrect": status_counts["incorrect"],
        "unreviewed_or_unknown": status_counts["unreviewed_or_unknown"],
        "accuracy_reviewed": round(status_counts["correct"] / reviewed_total, 6) if reviewed_total else None,
        "by_model": by_model,
    }


def build_markdown(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# JS2207 标题栏图号 OCR 审核结果统计",
        "",
        "## 整体统计",
        "",
        f"- 审核记录：{summary['overall']['row_count']} 条。",
        f"- 已明确审核：{summary['overall']['reviewed_rows']} 条。",
        f"- 正确：{summary['overall']['correct']} 条。",
        f"- 错误：{summary['overall']['incorrect']} 条。",
        f"- 未识别审核值：{summary['overall']['unreviewed_or_unknown']} 条。",
        "",
        "## 按模型统计",
        "",
        "| 模型 | 已审核 | 正确 | 错误 | 正确率 | 空预测 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for model, stats in summary["overall"]["by_model"].items():
        acc = "" if stats["accuracy_reviewed"] is None else f"{stats['accuracy_reviewed']:.2%}"
        lines.append(
            f"| `{model}` | {stats['reviewed_rows']} | {stats['correct']} | {stats['incorrect']} | {acc} | {stats['empty_predictions']} |"
        )
    lines.extend(
        [
            "",
            "## 去除风险页统计",
            "",
            "| 模型 | 已审核 | 正确 | 错误 | 正确率 | 空预测 |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for model, stats in summary["without_risk_pages"]["by_model"].items():
        acc = "" if stats["accuracy_reviewed"] is None else f"{stats['accuracy_reviewed']:.2%}"
        lines.append(
            f"| `{model}` | {stats['reviewed_rows']} | {stats['correct']} | {stats['incorrect']} | {acc} | {stats['empty_predictions']} |"
        )
    risk_rows = [row for row in rows if row["risk"]]
    lines.extend(["", "## 风险页明细", ""])
    if risk_rows:
        lines.append("| 页码 | 风险 | 模型 | 模型提取图号 | 审核 | 正确图号 | 备注 |")
        lines.append("| ---: | --- | --- | --- | --- | --- | --- |")
        for row in risk_rows:
            lines.append(
                f"| {row['page_number']} | {row['risk']} | `{row['model']}` | {row['model_extracted']} | {row['human_status_raw']} | {row['correct_drawing_number']} | {row['remark']} |"
            )
    else:
        lines.append("- 无风险页记录。")
    lines.append("")
    return "\n".join(lines)


def archive_current(current_dir: Path, review_slug: str) -> str | None:
    current = resolve_path(current_dir)
    entries = [entry for entry in current.iterdir() if entry.name != ".gitkeep"]
    if not entries:
        return None
    archive_root = ROOT / "local_data" / "review_inbox" / "archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    archive_dir = archive_root / f"current_archived_after_{review_slug}_{stamp}"
    shutil.move(str(current), str(archive_dir))
    current.mkdir(parents=True, exist_ok=True)
    (current / "README.md").write_text("# 当前待审核任务\n\n当前没有待用户审核的任务。\n", encoding="utf-8")
    return as_posix(archive_dir)


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir)
    safe_reset_child_dir(output_dir, resolve_path(args.machine_dir))
    human_rows = read_xlsx(args.xlsx)
    machine_rows = read_jsonl(resolve_path(args.machine_dir) / "decisions.jsonl")
    review_rows = build_review_rows(human_rows, machine_rows)
    summary = {
        "record_version": RECORD_VERSION,
        "xlsx": as_posix(resolve_path(args.xlsx)),
        "machine_dir": as_posix(resolve_path(args.machine_dir)),
        "output_dir": as_posix(output_dir),
        "human_row_count": len(human_rows),
        "review_row_count": len(review_rows),
        "machine_row_count": len(machine_rows),
        "overall": summarize(review_rows, exclude_risk_pages=False),
        "without_risk_pages": summarize(review_rows, exclude_risk_pages=True),
        "risk_pages": RISK_PAGES,
    }
    write_json(output_dir / "summary.json", summary)
    write_json(output_dir / "review_rows.json", review_rows)
    write_csv(
        output_dir / "review_rows.csv",
        review_rows,
        [
            "row_index",
            "page_number",
            "risk",
            "model",
            "model_extracted",
            "human_status_raw",
            "human_status",
            "correct_drawing_number",
            "effective_truth",
            "remark",
            "machine_parse_status",
            "machine_schema_status",
            "machine_needs_review",
        ],
    )
    (output_dir / "summary.md").write_text(build_markdown(summary, review_rows), encoding="utf-8")
    if args.archive_current:
        summary["archived_current"] = archive_current(args.current_dir, "js2207_title_block_drawing_number_ocr_review")
        write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze filled JS2207 drawing-number OCR review workbook.")
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    parser.add_argument("--machine-dir", type=Path, default=DEFAULT_MACHINE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--current-dir", type=Path, default=DEFAULT_CURRENT_DIR)
    parser.add_argument("--archive-current", action="store_true")
    return parser


def main() -> int:
    run(build_arg_parser().parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
