from __future__ import annotations

import argparse
import csv
import json
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from scripts.common.obb_utils import ROOT, resolve_path
from scripts.vlm.build_aliyun_vlm_mvp_requests import write_json


DEFAULT_REVIEW_XLSX = (
    ROOT
    / "local_data"
    / "review_inbox"
    / "current"
    / "ykj125_vlm_title_block_error_first_review"
    / "vlm_error_first_review.xlsx"
)
DEFAULT_RUN_SUMMARY = ROOT / "local_data" / "vlm_title_block_error_first_ykj125" / "run_summary.json"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "vlm_title_block_error_first_ykj125" / "manual_review_analysis"
RECORD_VERSION = "vlm-error-first-review-analysis-v0.1"
XLSX_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def as_posix(path: Path | str | None) -> str | None:
    if path is None:
        return None
    path_obj = Path(path)
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def xlsx_cell_col_index(cell_ref: str) -> int:
    letters = "".join(char for char in cell_ref if char.isalpha())
    value = 0
    for char in letters:
        value = value * 26 + (ord(char.upper()) - ord("A") + 1)
    return max(0, value - 1)


def read_xlsx_rows(path: Path) -> list[dict[str, str]]:
    resolved = resolve_path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"Review xlsx not found: {resolved}")

    with zipfile.ZipFile(resolved) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_root.findall("a:si", XLSX_NS):
                shared_strings.append("".join(text.text or "" for text in item.findall(".//a:t", XLSX_NS)))

        sheet_root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        matrix: list[list[str]] = []
        for row in sheet_root.findall(".//a:row", XLSX_NS):
            values: list[str] = []
            current_col = 0
            for cell in row.findall("a:c", XLSX_NS):
                ref = cell.attrib.get("r", "")
                col_index = xlsx_cell_col_index(ref)
                while current_col < col_index:
                    values.append("")
                    current_col += 1
                raw_value = cell.find("a:v", XLSX_NS)
                value = "" if raw_value is None else raw_value.text or ""
                if cell.attrib.get("t") == "s" and value:
                    value = shared_strings[int(value)]
                values.append(value)
                current_col += 1
            matrix.append(values)

    if not matrix:
        return []
    header = [item.strip() for item in matrix[0]]
    rows: list[dict[str, str]] = []
    for values in matrix[1:]:
        row = {header[index]: values[index] if index < len(values) else "" for index in range(len(header))}
        if any(value for value in row.values()):
            rows.append(row)
    return rows


def normalize_verdict(value: str) -> str:
    text = value.strip().lower()
    if text in {"正确", "对", "是", "ok", "yes", "true", "1"}:
        return "correct"
    if text in {"错误", "错", "否", "no", "false", "0"}:
        return "wrong"
    if text:
        return "other"
    return "blank"


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def analyze(rows: list[dict[str, str]], run_summary: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    required = {"页码", "模型", "模型派生当前旋转角度", "旋转角度是否正确", "正确旋转角度", "备注"}
    missing = sorted(required - set(rows[0])) if rows else []
    if missing:
        raise ValueError(f"Review xlsx missing columns: {missing}")

    detail_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        verdict = normalize_verdict(row.get("旋转角度是否正确", ""))
        detail_rows.append(
            {
                "序号": index,
                "页码": row.get("页码", ""),
                "模型": row.get("模型", ""),
                "模型派生当前旋转角度": row.get("模型派生当前旋转角度", ""),
                "人工判断": row.get("旋转角度是否正确", ""),
                "人工判断代码": verdict,
                "正确旋转角度": row.get("正确旋转角度", ""),
                "备注": row.get("备注", ""),
            }
        )

    by_model: dict[str, dict[str, Any]] = {}
    machine_by_model = run_summary.get("rotation_group_match_previous_truth_summary", {}).get("by_model", {})
    api_by_model = run_summary.get("decision_summary_by_model", {})
    for model in sorted({row["模型"] for row in detail_rows}):
        model_rows = [row for row in detail_rows if row["模型"] == model]
        verdict_counts = Counter(row["人工判断代码"] for row in model_rows)
        total = len(model_rows)
        correct = verdict_counts.get("correct", 0)
        wrong = verdict_counts.get("wrong", 0)
        blank = verdict_counts.get("blank", 0)
        other = verdict_counts.get("other", 0)
        by_model[model] = {
            "total": total,
            "manual_correct_count": correct,
            "manual_wrong_count": wrong,
            "manual_blank_count": blank,
            "manual_other_count": other,
            "manual_accuracy": round(correct / total, 6) if total else None,
            "wrong_pages": [row["页码"] for row in model_rows if row["人工判断代码"] == "wrong"],
            "blank_pages": [row["页码"] for row in model_rows if row["人工判断代码"] == "blank"],
            "remarks": [
                {"page": row["页码"], "remark": row["备注"]}
                for row in model_rows
                if row.get("备注", "").strip()
            ],
            "machine_rotation_summary": machine_by_model.get(model, {}),
            "api_summary": api_by_model.get(model, {}),
        }

    ranked = sorted(
        by_model.items(),
        key=lambda item: (
            item[1]["manual_accuracy"] if item[1]["manual_accuracy"] is not None else -1,
            item[1].get("api_summary", {}).get("api_ok_count", 0),
            item[1].get("api_summary", {}).get("schema_ok_count", 0),
        ),
        reverse=True,
    )
    summary = {
        "record_version": RECORD_VERSION,
        "row_count": len(rows),
        "filled_row_count": sum(1 for row in detail_rows if row["人工判断代码"] != "blank"),
        "model_count": len(by_model),
        "by_model": by_model,
        "ranked_models": [{"model": model, **stats} for model, stats in ranked],
        "recommended_primary_model": ranked[0][0] if ranked else "",
        "recommendation_basis": [
            "manual_rotation_accuracy",
            "api_success_count",
            "schema_success_count",
            "stability_before_latency_or_model_strength",
        ],
    }
    return summary, detail_rows


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = read_xlsx_rows(args.review_xlsx)
    run_summary = json.loads(resolve_path(args.run_summary).read_text(encoding="utf-8"))
    summary, detail_rows = analyze(rows, run_summary)

    summary_path = output_dir / "manual_review_analysis_summary.json"
    detail_json_path = output_dir / "manual_review_analysis_rows.json"
    detail_csv_path = output_dir / "manual_review_analysis_rows.csv"
    summary_md_path = output_dir / "manual_review_analysis_summary.md"

    summary.update(
        {
            "review_xlsx": as_posix(resolve_path(args.review_xlsx)),
            "run_summary": as_posix(resolve_path(args.run_summary)),
            "outputs": {
                "summary_json": as_posix(summary_path),
                "detail_json": as_posix(detail_json_path),
                "detail_csv": as_posix(detail_csv_path),
                "summary_md": as_posix(summary_md_path),
            },
        }
    )
    write_json(summary_path, summary)
    write_json(detail_json_path, detail_rows)
    write_csv(
        detail_csv_path,
        detail_rows,
        ["序号", "页码", "模型", "模型派生当前旋转角度", "人工判断", "人工判断代码", "正确旋转角度", "备注"],
    )
    summary_md_path.write_text(render_summary_md(summary), encoding="utf-8")
    return summary


def render_summary_md(summary: dict[str, Any]) -> str:
    lines = [
        "# VLM 错题集人工审核分析",
        "",
        f"- 记录数：{summary['row_count']}",
        f"- 已填写：{summary['filled_row_count']}",
        f"- 推荐主模型：`{summary['recommended_primary_model']}`",
        "",
        "| 模型 | 人工正确 | 人工错误 | 未填 | 正确率 | API 成功 | Schema 成功 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in summary["ranked_models"]:
        api = item.get("api_summary", {})
        lines.append(
            "| {model} | {correct} | {wrong} | {blank} | {accuracy:.4f} | {api_ok} | {schema_ok} |".format(
                model=item["model"],
                correct=item["manual_correct_count"],
                wrong=item["manual_wrong_count"],
                blank=item["manual_blank_count"],
                accuracy=item["manual_accuracy"] or 0,
                api_ok=api.get("api_ok_count", ""),
                schema_ok=api.get("schema_ok_count", ""),
            )
        )
    lines.append("")
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze manually reviewed VLM error-first rotation results.")
    parser.add_argument("--review-xlsx", type=Path, default=DEFAULT_REVIEW_XLSX)
    parser.add_argument("--run-summary", type=Path, default=DEFAULT_RUN_SUMMARY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
