from __future__ import annotations

import argparse
import csv
import json
import shutil
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_CURRENT_DIR = ROOT / "local_data" / "review_inbox" / "current"
DEFAULT_REVIEW_DIR = DEFAULT_CURRENT_DIR / "js2207_real_vlm_title_block_review"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "js2207_real_vlm_title_block_review"
RECORD_VERSION = "js2207-real-vlm-excel-review-archive-v0.1"
EXPECTED_ROW_COUNT = 58

NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

FIELDNAMES = [
    "序号",
    "页码",
    "样本编号",
    "模型",
    "模型标题栏位置",
    "模型标题栏位置代码",
    "程序派生当前旋转角度",
    "程序派生校正角度",
    "位置是否正确",
    "正确标题栏位置",
    "备注",
]


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


def column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    value = 0
    for ch in letters:
        value = value * 26 + (ord(ch.upper()) - ord("A") + 1)
    return value - 1


def read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall("a:si", NS):
        text = "".join(node.text or "" for node in item.findall(".//a:t", NS))
        values.append(text)
    return values


def cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//a:t", NS))
    value = cell.find("a:v", NS)
    if value is None or value.text is None:
        return ""
    raw = value.text
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return ""
    return raw


def read_xlsx_rows(path: Path) -> list[dict[str, Any]]:
    resolved = resolve_path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"Excel review file not found: {resolved}")
    with zipfile.ZipFile(resolved) as archive:
        shared_strings = read_shared_strings(archive)
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        parsed_rows: list[list[str]] = []
        for row in sheet.findall(".//a:sheetData/a:row", NS):
            values = [""] * len(FIELDNAMES)
            for cell in row.findall("a:c", NS):
                ref = cell.attrib.get("r", "")
                index = column_index(ref)
                if 0 <= index < len(values):
                    values[index] = cell_text(cell, shared_strings)
            parsed_rows.append(values)

    rows: list[dict[str, Any]] = []
    for values in parsed_rows[1:]:
        if not any(str(value).strip() for value in values):
            continue
        row = dict(zip(FIELDNAMES, values, strict=False))
        row["人工已填写"] = bool(
            row.get("位置是否正确", "").strip()
            or row.get("正确标题栏位置", "").strip()
            or row.get("备注", "").strip()
        )
        rows.append(row)
    return rows


def normalize_judgment(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return "空白"
    if text in {"正确", "对", "是", "ok", "OK", "right", "Right"}:
        return "正确"
    if text in {"错误", "错", "否", "不正确", "wrong", "Wrong"}:
        return "错误"
    if text in {"不确定", "无法判断", "看不清", "存疑"}:
        return "不确定"
    return text


def summarize(
    rows: list[dict[str, Any]],
    excel_path: Path,
    archived_path: str | None,
    archived_excel_path: Path | None,
) -> dict[str, Any]:
    judgment_counter = Counter(normalize_judgment(row.get("位置是否正确", "")) for row in rows)
    model_counter = Counter(row.get("模型", "") for row in rows)
    position_counter = Counter(row.get("模型标题栏位置代码", "") for row in rows)
    filled_rows = [row for row in rows if row.get("人工已填写")]
    incorrect_rows = [row for row in rows if normalize_judgment(row.get("位置是否正确", "")) == "错误"]
    uncertain_rows = [row for row in rows if normalize_judgment(row.get("位置是否正确", "")) == "不确定"]

    by_page: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_page[str(row.get("页码", ""))].append(row)

    page_summaries = []
    for page_number in sorted(by_page, key=lambda value: int(value) if value.isdigit() else 9999):
        page_rows = by_page[page_number]
        judgments = [normalize_judgment(row.get("位置是否正确", "")) for row in page_rows]
        page_summaries.append(
            {
                "page_number": page_number,
                "sample_ids": sorted({row.get("样本编号", "") for row in page_rows}),
                "models": [row.get("模型", "") for row in page_rows],
                "machine_positions": {row.get("模型", ""): row.get("模型标题栏位置代码", "") for row in page_rows},
                "human_judgments": {row.get("模型", ""): normalize_judgment(row.get("位置是否正确", "")) for row in page_rows},
                "correct_positions": {row.get("模型", ""): row.get("正确标题栏位置", "") for row in page_rows},
                "notes": {row.get("模型", ""): row.get("备注", "") for row in page_rows},
                "needs_attention": any(judgment in {"错误", "不确定", "空白"} for judgment in judgments),
            }
        )

    return {
        "record_version": RECORD_VERSION,
        "excel_review_path": as_posix(excel_path),
        "archived_excel_review_path": as_posix(archived_excel_path),
        "csv_used_as_human_source": False,
        "archived_review_inbox": archived_path,
        "row_count": len(rows),
        "filled_row_count": len(filled_rows),
        "blank_row_count": len(rows) - len(filled_rows),
        "judgment_counts": dict(judgment_counter),
        "model_counts": dict(model_counter),
        "machine_position_counts": dict(position_counter),
        "incorrect_count": len(incorrect_rows),
        "uncertain_count": len(uncertain_rows),
        "attention_page_count": sum(1 for page in page_summaries if page["needs_attention"]),
        "incorrect_rows": incorrect_rows,
        "uncertain_rows": uncertain_rows,
        "page_summaries": page_summaries,
        "modified_pdf": False,
        "renamed_pdf": False,
    }


def validate_review_rows(rows: list[dict[str, Any]], expected_rows: int, allow_empty_review: bool) -> None:
    if len(rows) != expected_rows:
        raise ValueError(f"Expected {expected_rows} Excel review rows, got {len(rows)}")
    if not allow_empty_review and not any(row.get("人工已填写") for row in rows):
        raise ValueError("Excel review rows were parsed, but no human-filled cells were found")


def archive_current(current_dir: Path) -> Path:
    resolved = resolve_path(current_dir)
    if not resolved.exists():
        raise FileNotFoundError(f"Current review inbox not found: {resolved}")
    archive_root = ROOT / "local_data" / "review_inbox" / "archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    archive_dir = archive_root / f"js2207_real_vlm_title_block_review_{stamp}_reviewed"
    if archive_dir.exists():
        raise FileExistsError(f"Archive directory already exists: {archive_dir}")
    shutil.move(str(resolved), str(archive_dir))
    resolved.mkdir(parents=True, exist_ok=True)
    return archive_dir


def reset_current_readme(current_dir: Path) -> None:
    current_dir.mkdir(parents=True, exist_ok=True)
    (current_dir / "README.md").write_text(
        "\n".join(
            [
                "# 当前待审核任务",
                "",
                "当前没有待用户审核、填写或标注的文件。",
                "",
                "上一轮 JS2207 真实 VLM 标题栏位置审核结果已归档。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_human_summary(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# JS2207 真实 VLM 标题栏位置 Excel 审核摘要",
        "",
        f"- Excel 记录数：{summary['row_count']}",
        f"- 已填写记录数：{summary['filled_row_count']}",
        f"- 空白记录数：{summary['blank_row_count']}",
        f"- 判断分布：{json.dumps(summary['judgment_counts'], ensure_ascii=False)}",
        f"- 需关注页数：{summary['attention_page_count']}",
        f"- 错误记录数：{summary['incorrect_count']}",
        f"- 不确定记录数：{summary['uncertain_count']}",
        f"- CSV 是否作为人工来源：{summary['csv_used_as_human_source']}",
        f"- 归档位置：{summary['archived_review_inbox']}",
        "",
        "## 需关注页",
        "",
    ]
    attention_pages = [page for page in summary["page_summaries"] if page["needs_attention"]]
    if not attention_pages:
        lines.append("- 无。")
    else:
        for page in attention_pages:
            lines.append(
                "- 第 {page} 页：机器位置 {positions}；人工判断 {judgments}；正确位置 {correct_positions}".format(
                    page=page["page_number"],
                    positions=json.dumps(page["machine_positions"], ensure_ascii=False),
                    judgments=json.dumps(page["human_judgments"], ensure_ascii=False),
                    correct_positions=json.dumps(page["correct_positions"], ensure_ascii=False),
                )
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    current_dir = resolve_path(args.current_dir)
    review_dir = resolve_path(args.review_dir)
    excel_path = review_dir / "vlm_title_block_review.xlsx"
    rows = read_xlsx_rows(excel_path)
    validate_review_rows(rows, args.expected_rows, args.allow_empty_review)

    try:
        review_relative = review_dir.relative_to(current_dir)
    except ValueError:
        review_relative = Path(review_dir.name)

    archived_dir = archive_current(current_dir)
    archived = as_posix(archived_dir)
    archived_excel_path = archived_dir / review_relative / "vlm_title_block_review.xlsx"
    reset_current_readme(current_dir)

    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows_json_path = output_dir / "excel_review_rows.json"
    rows_csv_path = output_dir / "excel_review_rows.csv"
    summary_json_path = output_dir / "excel_review_summary.json"
    summary_csv_path = output_dir / "excel_review_summary.csv"
    human_summary_path = output_dir / "human_summary.md"

    summary = summarize(rows, excel_path, archived, archived_excel_path)
    write_json(rows_json_path, rows)
    write_csv(rows_csv_path, rows, [*FIELDNAMES, "人工已填写"])
    write_json(summary_json_path, summary)
    write_csv(
        summary_csv_path,
        [
            {
                "row_count": summary["row_count"],
                "filled_row_count": summary["filled_row_count"],
                "blank_row_count": summary["blank_row_count"],
                "incorrect_count": summary["incorrect_count"],
                "uncertain_count": summary["uncertain_count"],
                "attention_page_count": summary["attention_page_count"],
                "judgment_counts": json.dumps(summary["judgment_counts"], ensure_ascii=False),
                "archived_review_inbox": summary["archived_review_inbox"],
            }
        ],
        [
            "row_count",
            "filled_row_count",
            "blank_row_count",
            "incorrect_count",
            "uncertain_count",
            "attention_page_count",
            "judgment_counts",
            "archived_review_inbox",
        ],
    )
    write_human_summary(human_summary_path, summary)

    result = {
        "record_version": RECORD_VERSION,
        "excel_review_path": as_posix(excel_path),
        "archived_excel_review_path": as_posix(archived_excel_path),
        "csv_used_as_human_source": False,
        "archived_review_inbox": archived,
        "output_dir": as_posix(output_dir),
        "row_count": summary["row_count"],
        "filled_row_count": summary["filled_row_count"],
        "blank_row_count": summary["blank_row_count"],
        "incorrect_count": summary["incorrect_count"],
        "uncertain_count": summary["uncertain_count"],
        "attention_page_count": summary["attention_page_count"],
        "modified_pdf": False,
        "renamed_pdf": False,
        "outputs": {
            "rows_json": as_posix(rows_json_path),
            "rows_csv": as_posix(rows_csv_path),
            "summary_json": as_posix(summary_json_path),
            "summary_csv": as_posix(summary_csv_path),
            "human_summary": as_posix(human_summary_path),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Archive JS2207 real VLM title-block Excel review results.")
    parser.add_argument("--review-dir", type=Path, default=DEFAULT_REVIEW_DIR)
    parser.add_argument("--current-dir", type=Path, default=DEFAULT_CURRENT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--expected-rows", type=int, default=EXPECTED_ROW_COUNT)
    parser.add_argument("--allow-empty-review", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
