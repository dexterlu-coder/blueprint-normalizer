from __future__ import annotations

import argparse
import csv
import html
import json
import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_SOURCE_DIR = ROOT / "local_data" / "js2207_real_pdf_vlm_title_block_prompt_retest"
DEFAULT_CURRENT_DIR = ROOT / "local_data" / "review_inbox" / "current"
RECORD_VERSION = "js2207-vlm-prompt-retest-review-pack-v0.1"

POSITION_LABELS = {
    "bottom_edge": "下方",
    "top_edge": "上方",
    "left_edge": "左侧",
    "right_edge": "右侧",
    "bottom_right": "右下方",
    "bottom_left": "左下方",
    "top_left": "左上方",
    "top_right": "右上方",
    "no_title_block": "无标题栏",
    "unknown": "未知",
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


def xlsx_col_name(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def write_xlsx(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    shared_strings: list[str] = []
    shared_index: dict[str, int] = {}

    def shared(value: Any) -> int:
        text = "" if value is None else str(value)
        if text not in shared_index:
            shared_index[text] = len(shared_strings)
            shared_strings.append(text)
        return shared_index[text]

    all_rows = [fieldnames] + [[row.get(field, "") for field in fieldnames] for row in rows]
    sheet_rows = []
    for row_index, row_values in enumerate(all_rows, start=1):
        cells = []
        for col_index, value in enumerate(row_values):
            cell_ref = f"{xlsx_col_name(col_index)}{row_index}"
            if isinstance(value, int | float) and not isinstance(value, bool):
                cells.append(f'<c r="{cell_ref}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{cell_ref}" t="s"><v>{shared(value)}</v></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    max_col = xlsx_col_name(len(fieldnames) - 1)
    max_row = len(all_rows)
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="A1:{max_col}{max_row}"/>'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultRowHeight="18"/>'
        '<cols>'
        '<col min="1" max="3" width="12" customWidth="1"/>'
        '<col min="4" max="8" width="20" customWidth="1"/>'
        '<col min="9" max="12" width="18" customWidth="1"/>'
        '</cols>'
        f'<sheetData>{"".join(sheet_rows)}</sheetData>'
        '</worksheet>'
    )
    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">'
        + "".join(f"<si><t>{escape(text)}</t></si>" for text in shared_strings)
        + "</sst>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="VLM复测审核" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
        '</Relationships>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        '</Types>'
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        archive.writestr("xl/sharedStrings.xml", shared_xml)


def archive_current_if_needed(current_dir: Path) -> str | None:
    resolved = resolve_path(current_dir)
    resolved.mkdir(parents=True, exist_ok=True)
    entries = [entry for entry in resolved.iterdir() if entry.name != ".gitkeep"]
    only_readme = len(entries) == 1 and entries[0].name == "README.md"
    readme_empty = False
    if only_readme:
        text = entries[0].read_text(encoding="utf-8", errors="replace")
        readme_empty = "当前没有待用户审核" in text
    if not entries or readme_empty:
        return None

    archive_root = ROOT / "local_data" / "review_inbox" / "archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    archive_dir = archive_root / f"current_archived_before_js2207_prompt_retest_review_{stamp}"
    shutil.move(str(resolved), str(archive_dir))
    resolved.mkdir(parents=True, exist_ok=True)
    return as_posix(archive_dir)


def review_rows(decisions: list[dict[str, Any]], evaluation_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evaluation_by_key = {
        (str(row["task_id"]), str(row["model"])): row
        for row in evaluation_rows
    }
    rows: list[dict[str, Any]] = []
    for index, decision in enumerate(
        sorted(decisions, key=lambda row: (int(row.get("page_number") or 9999), str(row.get("model", "")))),
        start=1,
    ):
        key = (str(decision.get("task_id", "")), str(decision.get("model", "")))
        evaluation = evaluation_by_key.get(key, {})
        position = str(decision.get("title_block_position", ""))
        rows.append(
            {
                "序号": index,
                "页码": decision.get("page_number", ""),
                "样本编号": decision.get("task_id", ""),
                "模型": decision.get("model", ""),
                "模型标题栏位置": POSITION_LABELS.get(position, position),
                "模型标题栏位置代码": position,
                "程序派生当前旋转角度": decision.get("derived_current_clockwise_degrees", ""),
                "程序派生校正角度": decision.get("derived_correction_clockwise_degrees", ""),
                "参考上一轮人工位置": POSITION_LABELS.get(str(evaluation.get("expected_position", "")), evaluation.get("expected_position", "")),
                "位置是否正确": "",
                "正确标题栏位置": "",
                "备注": "",
            }
        )
    return rows


def publish(args: argparse.Namespace) -> dict[str, Any]:
    source_dir = resolve_path(args.source_dir)
    current_dir = resolve_path(args.current_dir)
    decisions = load_jsonl(source_dir / "vlm_decisions.jsonl")
    evaluation_rows = load_json(source_dir / "evaluation" / "prompt_retest_evaluation_rows.json")
    evaluation_summary = load_json(source_dir / "evaluation" / "prompt_retest_evaluation_summary.json")

    archived = archive_current_if_needed(current_dir)
    review_dir = current_dir / "js2207_vlm_prompt_retest_review"
    image_dir = review_dir / "images"
    if review_dir.exists():
        shutil.rmtree(review_dir)
    image_dir.mkdir(parents=True, exist_ok=True)

    rendered_dir = source_dir / "rendered_png"
    image_map: dict[str, str] = {}
    for image_path in sorted(rendered_dir.glob("*.png")):
        target = image_dir / image_path.name
        shutil.copy2(image_path, target)
        image_map[image_path.stem] = rel_path(target, review_dir)

    rows = review_rows(decisions, evaluation_rows)
    fieldnames = [
        "序号",
        "页码",
        "样本编号",
        "模型",
        "模型标题栏位置",
        "模型标题栏位置代码",
        "程序派生当前旋转角度",
        "程序派生校正角度",
        "参考上一轮人工位置",
        "位置是否正确",
        "正确标题栏位置",
        "备注",
    ]
    csv_path = review_dir / "vlm_prompt_retest_review.csv"
    xlsx_path = review_dir / "vlm_prompt_retest_review.xlsx"
    html_path = review_dir / "review_index.html"
    manifest_path = review_dir / "review_manifest.json"
    write_csv(csv_path, rows, fieldnames)
    write_xlsx(xlsx_path, rows, fieldnames)

    by_page: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        by_page.setdefault(int(row["页码"]), []).append(row)

    cards = []
    for page_number in sorted(by_page):
        page_rows = by_page[page_number]
        task_id = str(page_rows[0]["样本编号"])
        image_src = image_map.get(task_id, "")
        table_rows = []
        for row in page_rows:
            table_rows.append(
                "<tr>"
                f"<td>{html.escape(str(row['模型']))}</td>"
                f"<td>{html.escape(str(row['模型标题栏位置']))}</td>"
                f"<td>{html.escape(str(row['模型标题栏位置代码']))}</td>"
                f"<td>{html.escape(str(row['程序派生当前旋转角度']))}</td>"
                f"<td>{html.escape(str(row['参考上一轮人工位置']))}</td>"
                "</tr>"
            )
        cards.append(
            f"""
    <article class="page-card" id="{html.escape(task_id)}">
      <div class="page-head">
        <h2>第 {page_number} 页</h2>
        <span>{html.escape(task_id)}</span>
      </div>
      <img src="{html.escape(image_src)}" alt="第 {page_number} 页原向图纸">
      <table>
        <thead><tr><th>模型</th><th>标题栏位置</th><th>位置代码</th><th>派生当前旋转</th><th>参考上一轮</th></tr></thead>
        <tbody>{''.join(table_rows)}</tbody>
      </table>
    </article>
"""
        )

    html_path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>JS2207 VLM Prompt 复测审核</title>
  <style>
    body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; color: #172033; background: #f6f7f9; }}
    header {{ position: sticky; top: 0; z-index: 2; padding: 14px 20px; background: #ffffff; border-bottom: 1px solid #d9dee7; }}
    h1 {{ margin: 0 0 6px; font-size: 20px; }}
    .meta {{ display: flex; gap: 14px; flex-wrap: wrap; color: #52606d; font-size: 13px; }}
    main {{ max-width: 1440px; margin: 0 auto; padding: 18px; }}
    .guide {{ margin-bottom: 16px; padding: 12px 14px; background: #ffffff; border: 1px solid #d9dee7; }}
    .page-card {{ margin-bottom: 18px; padding: 14px; background: #ffffff; border: 1px solid #d9dee7; }}
    .page-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 10px; }}
    .page-head h2 {{ margin: 0; font-size: 18px; }}
    .page-head span {{ color: #52606d; font-size: 13px; }}
    img {{ display: block; width: 100%; max-height: 78vh; object-fit: contain; background: #f8fafc; border: 1px solid #e2e8f0; }}
    table {{ width: 100%; margin-top: 10px; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border: 1px solid #d9dee7; padding: 7px 8px; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f6; }}
    @media (max-width: 760px) {{ main {{ padding: 10px; }} img {{ max-height: none; }} table {{ font-size: 12px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>JS2207 VLM Prompt 复测审核</h1>
    <div class="meta">
      <span>共 {len(by_page)} 页</span>
      <span>记录 {len(rows)} 条</span>
      <span>填写：vlm_prompt_retest_review.xlsx</span>
      <span>旧 {evaluation_summary.get('old_exact_correct')}/{evaluation_summary.get('old_row_count')}；新 {evaluation_summary.get('new_exact_correct')}/{evaluation_summary.get('row_count')}</span>
    </div>
  </header>
  <main>
    <section class="guide">
      <strong>审核说明：</strong>
      请只核对新版模型判断的标题栏当前位置是否正确。若错误，请在 Excel 中填写“位置是否正确”“正确标题栏位置”和备注。
    </section>
    {''.join(cards)}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )

    manifest = {
        "record_version": RECORD_VERSION,
        "task": "js2207_vlm_prompt_retest_review",
        "source_dir": as_posix(source_dir),
        "archived_previous_current": archived,
        "page_count": len(by_page),
        "row_count": len(rows),
        "image_count": len(image_map),
        "html": rel_path(html_path, current_dir),
        "xlsx": rel_path(xlsx_path, current_dir),
        "csv": rel_path(csv_path, current_dir),
        "evaluation_summary": evaluation_summary,
        "modified_pdf": False,
        "renamed_pdf": False,
        "network_call_executed": False,
    }
    write_json(manifest_path, manifest)
    (current_dir / "README.md").write_text(
        "\n".join(
            [
                "# 当前待审核任务",
                "",
                "任务：JS2207 VLM prompt 复测标题栏位置审核。",
                "",
                "请打开：",
                "",
                "- `js2207_vlm_prompt_retest_review/review_index.html`",
                "- `js2207_vlm_prompt_retest_review/vlm_prompt_retest_review.xlsx`",
                "",
                "本轮只审核新版模型标题栏当前位置。图片为原向 PNG，不旋转、不压缩。",
                "",
                "请在 Excel 中填写 `位置是否正确`、必要时填写 `正确标题栏位置` 和 `备注`。",
                "",
                "本入口不会生成正式旋正 PDF，也不会重命名 PDF。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    result = {
        "record_version": RECORD_VERSION,
        "review_dir": as_posix(review_dir),
        "review_html": as_posix(html_path),
        "review_xlsx": as_posix(xlsx_path),
        "review_csv": as_posix(csv_path),
        "review_manifest": as_posix(manifest_path),
        "page_count": len(by_page),
        "row_count": len(rows),
        "image_count": len(image_map),
        "archived_previous_current": archived,
        "network_call_executed": False,
        "modified_pdf": False,
        "renamed_pdf": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish JS2207 VLM prompt retest review pack.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--current-dir", type=Path, default=DEFAULT_CURRENT_DIR)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    publish(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
