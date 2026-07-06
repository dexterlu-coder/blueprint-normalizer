from __future__ import annotations

import argparse
import csv
import html
import json
import os
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from PIL import Image

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:  # pragma: no cover - local fallback for older environments
    from PyPDF2 import PdfReader, PdfWriter

from scripts.common.obb_utils import ROOT, resolve_path
from scripts.vlm.run_aliyun_vlm_mvp_smoke import (
    build_decision_row,
    compare_decisions,
    endpoint_from_base_url,
    load_env,
    parse_models,
    post_chat_completion,
)
from scripts.vlm.build_aliyun_vlm_mvp_requests import (
    build_request,
    data_url_for,
    write_json,
    write_jsonl,
)


DEFAULT_SOURCE_PDF = ROOT / "local_data" / "source_pdfs" / "JS2207-00-00升降平台.pdf"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "js2207_real_pdf_vlm_title_block"
DEFAULT_REVIEW_INBOX = ROOT / "local_data" / "review_inbox" / "current"
DEFAULT_ENV_FILE = ROOT / ".env" / ".env"
DEFAULT_MODELS = "qwen3-vl-flash,qwen3-vl-plus"
RECORD_VERSION = "js2207-real-vlm-title-block-v0.2"
SAMPLE_PREFIX = "js2207_real_page"

POSITION_LABELS = {
    "bottom_edge": "下方",
    "top_edge": "上方",
    "left_edge": "左侧",
    "right_edge": "右侧",
    "bottom_right": "右下方",
    "bottom_left": "左下方",
    "top_left": "左上方",
    "top_right": "右上方",
    "bottom": "下方",
    "left": "左侧",
    "top": "上方",
    "right": "右侧",
    "no_title_block": "无标题栏",
    "unknown": "未知",
}


Image.MAX_IMAGE_PIXELS = None


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


def safe_reset_child_dir(path: Path, allowed_root: Path) -> None:
    resolved = path.resolve()
    allowed = allowed_root.resolve()
    if resolved == allowed:
        raise ValueError(f"Refusing to remove allowed root itself: {resolved}")
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise ValueError(f"Refusing to remove path outside allowed root: {resolved}") from exc
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def page_sample_id(page_number: int) -> str:
    return f"{SAMPLE_PREFIX}_{page_number:03d}"


def split_pdf(source_pdf: Path, output_dir: Path) -> list[dict[str, Any]]:
    resolved = resolve_path(source_pdf)
    if not resolved.exists():
        raise FileNotFoundError(f"Source PDF not found: {resolved}")
    pdf_dir = output_dir / "single_page_pdfs"
    safe_reset_child_dir(pdf_dir, output_dir)
    reader = PdfReader(str(resolved))
    records: list[dict[str, Any]] = []
    for page_index, page in enumerate(reader.pages):
        page_number = page_index + 1
        task_id = page_sample_id(page_number)
        page_pdf = pdf_dir / f"{task_id}.pdf"
        writer = PdfWriter()
        writer.add_page(page)
        with page_pdf.open("wb") as handle:
            writer.write(handle)
        records.append(
            {
                "task_id": task_id,
                "source_type": "pdf",
                "source_path": as_posix(resolved),
                "page_number": page_number,
                "single_page_pdf_path": as_posix(page_pdf),
                "rendered_image_path": None,
            }
        )
    return records


def find_ghostscript() -> str:
    for executable in ("gswin64c", "gswin32c", "gs"):
        found = shutil.which(executable)
        if found:
            return found
    raise RuntimeError("Ghostscript executable not found: expected gswin64c, gswin32c, or gs")


def run_command(command: list[str], log_path: Path) -> None:
    result = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "COMMAND:\n"
        + json.dumps(command, ensure_ascii=False)
        + "\n\nSTDOUT:\n"
        + result.stdout
        + "\n\nSTDERR:\n"
        + result.stderr,
        encoding="utf-8",
    )
    if result.returncode != 0:
        tail = (result.stderr or result.stdout)[-1200:]
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {tail}")


def render_pdf_pages(records: list[dict[str, Any]], output_dir: Path, dpi: int) -> None:
    gs = find_ghostscript()
    png_dir = output_dir / "rendered_png"
    log_dir = output_dir / "logs" / "ghostscript"
    safe_reset_child_dir(png_dir, output_dir)
    for record in records:
        page_pdf = resolve_path(Path(record["single_page_pdf_path"]))
        png_path = png_dir / f"{record['task_id']}.png"
        command = [
            gs,
            "-dSAFER",
            "-dBATCH",
            "-dNOPAUSE",
            "-sDEVICE=png16m",
            f"-r{dpi}",
            "-dTextAlphaBits=4",
            "-dGraphicsAlphaBits=4",
            f"-sOutputFile={png_path}",
            str(page_pdf),
        ]
        run_command(command, log_dir / f"{record['task_id']}.log")
        record["rendered_image_path"] = as_posix(png_path)


def image_meta(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        width, height = image.size
    bytes_size = path.stat().st_size
    return {
        "input_image_path": as_posix(path),
        "input_image_format": "png",
        "original_width": width,
        "original_height": height,
        "prepared_width": width,
        "prepared_height": height,
        "bytes": bytes_size,
        "data_url_bytes": len(data_url_for(path, mime_type="image/png").encode("utf-8")),
    }


def build_png_requests(
    records: list[dict[str, Any]],
    models: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    requests: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    for record in records:
        image_path = resolve_path(Path(record["rendered_image_path"]))
        meta = image_meta(image_path)
        image_data_url = data_url_for(image_path, mime_type="image/png")
        for model in models:
            request = build_request(record, model, image_data_url)
            request["custom_id"] = f"{model}__{record['task_id']}"
            requests.append(
                {
                    "task_id": record["task_id"],
                    "page_number": record["page_number"],
                    "model": model,
                    "request": request,
                }
            )
            manifest_rows.append(
                {
                    **record,
                    **meta,
                    "provider_mode": "aliyun_openai_compatible",
                    "model": model,
                    "request_custom_id": request["custom_id"],
                    "no_resize": True,
                    "compressed": False,
                }
            )
    return requests, manifest_rows


def call_vlm_requests(
    request_rows: list[dict[str, Any]],
    env_file: Path,
    timeout_seconds: int,
    retries: int,
    retry_sleep_seconds: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    env_summary = load_env(env_file)
    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    base_url = os.environ.get("DASHSCOPE_BASE_URL", "")
    if not api_key:
        raise RuntimeError("Missing DASHSCOPE_API_KEY. Put it in .env/.env or the process environment.")
    if not base_url:
        raise RuntimeError("Missing DASHSCOPE_BASE_URL. Put it in .env/.env or the process environment.")
    endpoint = endpoint_from_base_url(base_url)
    raw_rows: list[dict[str, Any]] = []
    for request_row in request_rows:
        response = post_chat_completion(
            endpoint,
            api_key,
            request_row["request"]["body"],
            timeout_seconds,
            retries,
            retry_sleep_seconds,
        )
        raw_rows.append(
            {
                **request_row,
                "request": None,
                "request_custom_id": request_row["request"]["custom_id"],
                "endpoint": endpoint,
                **response,
            }
        )
    return raw_rows, env_summary


def public_raw_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_version": RECORD_VERSION,
        "task_id": row["task_id"],
        "page_number": row.get("page_number"),
        "model": row["model"],
        "request_custom_id": row["request_custom_id"],
        "provider_mode": "aliyun_openai_compatible",
        "endpoint": row.get("endpoint"),
        "ok": row.get("ok"),
        "http_status": row.get("http_status"),
        "attempt_count": row.get("attempt_count"),
        "error_type": row.get("error_type", ""),
        "error_message": row.get("error_message", ""),
        "response_json": row.get("response_json"),
        "response_text": row.get("response_text") if row.get("response_json") is None else "",
    }


def decision_by_task_model(decisions: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(row["task_id"], row["model"]): row for row in decisions}


def review_rows(records: list[dict[str, Any]], decisions: list[dict[str, Any]], models: list[str]) -> list[dict[str, Any]]:
    by_key = decision_by_task_model(decisions)
    rows: list[dict[str, Any]] = []
    index = 1
    for record in records:
        for model in models:
            decision = by_key.get((record["task_id"], model), {})
            position = decision.get("title_block_position", "")
            position_value = position if isinstance(position, str) else ""
            rows.append(
                {
                    "序号": index,
                    "页码": record["page_number"],
                    "样本编号": record["task_id"],
                    "模型": model,
                    "模型标题栏位置": POSITION_LABELS.get(position_value, position_value),
                    "模型标题栏位置代码": position_value,
                    "程序派生当前旋转角度": decision.get("derived_current_clockwise_degrees", ""),
                    "程序派生校正角度": decision.get("derived_correction_clockwise_degrees", ""),
                    "位置是否正确": "",
                    "正确标题栏位置": "",
                    "备注": "",
                }
            )
            index += 1
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
        '<col min="9" max="11" width="18" customWidth="1"/>'
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
        '<sheets><sheet name="VLM标题栏位置审核" sheetId="1" r:id="rId1"/></sheets></workbook>'
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


def archive_current_inbox(current_dir: Path) -> str | None:
    resolved = resolve_path(current_dir)
    if not resolved.exists():
        resolved.mkdir(parents=True, exist_ok=True)
        return None
    entries = [entry for entry in resolved.iterdir() if entry.name != ".gitkeep"]
    if not entries:
        return None
    archive_root = ROOT / "local_data" / "review_inbox" / "archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    archive_dir = archive_root / f"current_archived_before_js2207_real_vlm_{stamp}"
    if archive_dir.exists():
        raise FileExistsError(f"Archive directory already exists: {archive_dir}")
    shutil.move(str(resolved), str(archive_dir))
    resolved.mkdir(parents=True, exist_ok=True)
    return as_posix(archive_dir)


def publish_review_pack(
    output_dir: Path,
    current_dir: Path,
    records: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    review_rows_data: list[dict[str, Any]],
    models: list[str],
) -> dict[str, Any]:
    archived = archive_current_inbox(current_dir)
    review_dir = current_dir / "js2207_real_vlm_title_block_review"
    image_dir = review_dir / "images"
    review_dir.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)

    image_map: dict[str, str] = {}
    for record in records:
        source_image = resolve_path(Path(record["rendered_image_path"]))
        target_image = image_dir / source_image.name
        shutil.copy2(source_image, target_image)
        image_map[record["task_id"]] = rel_path(target_image, review_dir)

    fieldnames = [
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
    csv_path = review_dir / "vlm_title_block_review.csv"
    xlsx_path = review_dir / "vlm_title_block_review.xlsx"
    manifest_path = review_dir / "review_manifest.json"
    html_path = review_dir / "review_index.html"
    write_csv(csv_path, review_rows_data, fieldnames)
    write_xlsx(xlsx_path, review_rows_data, fieldnames)

    by_key = decision_by_task_model(decisions)
    cards = []
    for record in records:
        decision_lines = []
        for model in models:
            decision = by_key.get((record["task_id"], model), {})
            position = decision.get("title_block_position", "")
            position_value = position if isinstance(position, str) else ""
            reasons = "; ".join(decision.get("review_reasons") or [])
            decision_lines.append(
                "<tr>"
                f"<td>{html.escape(model)}</td>"
                f"<td>{html.escape(POSITION_LABELS.get(position_value, position_value))}</td>"
                f"<td>{html.escape(str(decision.get('derived_current_clockwise_degrees', '')))}</td>"
                f"<td>{html.escape(str(decision.get('derived_correction_clockwise_degrees', '')))}</td>"
                f"<td>{html.escape(str(decision.get('needs_review', '')))}</td>"
                f"<td>{html.escape(reasons)}</td>"
                "</tr>"
            )
        cards.append(
            f"""
    <article class="page-card" id="{html.escape(record['task_id'])}">
      <div class="page-head">
        <h2>第 {record['page_number']} 页</h2>
        <span>{html.escape(record['task_id'])}</span>
      </div>
      <img src="{html.escape(image_map[record['task_id']])}" alt="第 {record['page_number']} 页原向图纸">
      <table>
        <thead><tr><th>模型</th><th>标题栏位置</th><th>派生当前旋转</th><th>派生校正</th><th>需复核</th><th>原因</th></tr></thead>
        <tbody>{''.join(decision_lines)}</tbody>
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
  <title>JS2207 VLM 标题栏位置审核</title>
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
    <h1>JS2207 VLM 标题栏位置审核</h1>
    <div class="meta">
      <span>共 {len(records)} 页</span>
      <span>模型：{html.escape(', '.join(models))}</span>
      <span>填写：vlm_title_block_review.xlsx</span>
      <span>图片为原向 PNG，不旋转、不压缩</span>
    </div>
  </header>
  <main>
    <section class="guide">
      <strong>审核说明：</strong>
      只核对模型判断的标题栏当前位置是否正确。若错误，请在 Excel 中填写“位置是否正确”“正确标题栏位置”和备注。
    </section>
    {''.join(cards)}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )

    review_manifest = {
        "record_version": RECORD_VERSION,
        "task": "js2207_real_vlm_title_block_review",
        "page_count": len(records),
        "models": models,
        "archived_previous_current": archived,
        "html": rel_path(html_path, current_dir),
        "xlsx": rel_path(xlsx_path, current_dir),
        "csv": rel_path(csv_path, current_dir),
        "image_count": len(image_map),
        "source_output_dir": as_posix(output_dir),
        "comparisons": comparisons,
    }
    write_json(manifest_path, review_manifest)
    (current_dir / "README.md").write_text(
        "\n".join(
            [
                "# 当前待审核任务",
                "",
                "任务：JS2207 真实 PDF 原向 VLM 标题栏位置审核。",
                "",
                "请打开：",
                "",
                "- `js2207_real_vlm_title_block_review/review_index.html`",
                "- `js2207_real_vlm_title_block_review/vlm_title_block_review.xlsx`",
                "",
                "本轮只审核标题栏当前位置。图片为原向 PNG，不旋转、不压缩。",
                "",
                "请在 Excel 中填写 `位置是否正确`、必要时填写 `正确标题栏位置` 和 `备注`。",
                "",
                "本入口不会生成正式旋正 PDF，也不会重命名 PDF。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "review_dir": as_posix(review_dir),
        "review_html": as_posix(html_path),
        "review_xlsx": as_posix(xlsx_path),
        "review_csv": as_posix(csv_path),
        "review_manifest": as_posix(manifest_path),
        "archived_previous_current": archived,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    records = split_pdf(args.source_pdf, output_dir)
    render_pdf_pages(records, output_dir, args.render_dpi)
    models = parse_models(args.models)
    request_rows, manifest_rows = build_png_requests(records, models)

    requests_path = output_dir / "vlm_png_requests.jsonl"
    manifest_path = output_dir / "vlm_png_manifest.json"
    manifest_csv_path = output_dir / "vlm_png_manifest.csv"
    raw_path = output_dir / "vlm_raw_responses.jsonl"
    decisions_path = output_dir / "vlm_decisions.jsonl"
    decisions_csv_path = output_dir / "vlm_decisions.csv"
    comparison_path = output_dir / "dual_model_comparison.json"
    comparison_csv_path = output_dir / "dual_model_comparison.csv"
    summary_path = output_dir / "run_summary.json"

    write_jsonl(requests_path, [row["request"] for row in request_rows])
    write_json(manifest_path, manifest_rows)
    write_csv(
        manifest_csv_path,
        manifest_rows,
        [
            "task_id",
            "page_number",
            "source_path",
            "single_page_pdf_path",
            "rendered_image_path",
            "input_image_path",
            "input_image_format",
            "original_width",
            "original_height",
            "prepared_width",
            "prepared_height",
            "bytes",
            "data_url_bytes",
            "model",
            "compressed",
            "no_resize",
        ],
    )

    raw_rows, env_summary = call_vlm_requests(
        request_rows,
        args.env_file,
        args.timeout_seconds,
        args.retries,
        args.retry_sleep_seconds,
    )
    decisions = [build_decision_row(row) for row in raw_rows]
    comparisons = compare_decisions(decisions, models)
    review_rows_data = review_rows(records, decisions, models)

    write_jsonl(raw_path, [public_raw_row(row) for row in raw_rows])
    write_jsonl(decisions_path, decisions)
    write_csv(
        decisions_csv_path,
        [
            {
                **row,
                "drawing_number_candidates": json.dumps(row.get("drawing_number_candidates", []), ensure_ascii=False),
                "review_reasons": ";".join(row.get("review_reasons") or []),
            }
            for row in decisions
        ],
        [
            "task_id",
            "page_number",
            "model",
            "http_status",
            "api_ok",
            "parse_status",
            "schema_status",
            "title_block_position",
            "derived_current_clockwise_degrees",
            "derived_correction_clockwise_degrees",
            "orientation_confidence",
            "drawing_number_selected",
            "drawing_number_candidates",
            "drawing_number_confidence",
            "model_needs_human_review",
            "needs_review",
            "review_reasons",
            "error_type",
            "error_message",
        ],
    )
    write_json(comparison_path, comparisons)
    write_csv(
        comparison_csv_path,
        [
            {
                **row,
                "models": ",".join(row.get("models", [])),
                "title_block_position_by_model": json.dumps(row.get("title_block_position_by_model", {}), ensure_ascii=False),
                "derived_current_clockwise_degrees_by_model": json.dumps(
                    row.get("derived_current_clockwise_degrees_by_model", {}), ensure_ascii=False
                ),
                "derived_correction_clockwise_degrees_by_model": json.dumps(
                    row.get("derived_correction_clockwise_degrees_by_model", {}), ensure_ascii=False
                ),
                "drawing_number_selected_by_model": json.dumps(row.get("drawing_number_selected_by_model", {}), ensure_ascii=False),
                "needs_review_by_model": json.dumps(row.get("needs_review_by_model", {}), ensure_ascii=False),
                "review_reasons": ";".join(row.get("review_reasons") or []),
            }
            for row in comparisons
        ],
        [
            "task_id",
            "page_number",
            "models",
            "title_block_position_by_model",
            "derived_current_clockwise_degrees_by_model",
            "derived_correction_clockwise_degrees_by_model",
            "drawing_number_selected_by_model",
            "needs_review_by_model",
            "needs_review",
            "review_reasons",
        ],
    )

    review_summary = {}
    if not args.skip_review_publish:
        review_summary = publish_review_pack(
            output_dir,
            resolve_path(args.review_inbox),
            records,
            decisions,
            comparisons,
            review_rows_data,
            models,
        )
    summary = {
        "record_version": RECORD_VERSION,
        "source_pdf": as_posix(resolve_path(args.source_pdf)),
        "output_dir": as_posix(output_dir),
        "page_count": len(records),
        "model_count": len(models),
        "request_count": len(request_rows),
        "raw_response_count": len(raw_rows),
        "decision_count": len(decisions),
        "comparison_count": len(comparisons),
        "decision_needs_review_count": sum(1 for row in decisions if row.get("needs_review")),
        "comparison_needs_review_count": sum(1 for row in comparisons if row.get("needs_review")),
        "render_dpi": args.render_dpi,
        "image_format": "png",
        "compressed": False,
        "no_resize": True,
        "modified_pdf": False,
        "renamed_pdf": False,
        "env_status": env_summary,
        "outputs": {
            "requests": as_posix(requests_path),
            "manifest": as_posix(manifest_path),
            "manifest_csv": as_posix(manifest_csv_path),
            "raw_responses": as_posix(raw_path),
            "decisions": as_posix(decisions_path),
            "decisions_csv": as_posix(decisions_csv_path),
            "comparison": as_posix(comparison_path),
            "comparison_csv": as_posix(comparison_csv_path),
            "review": review_summary,
            "summary": as_posix(summary_path),
        },
    }
    write_json(summary_path, summary)
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build JS2207 real-PDF VLM title-block review pack.")
    parser.add_argument("--source-pdf", type=Path, default=DEFAULT_SOURCE_PDF)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--review-inbox", type=Path, default=DEFAULT_REVIEW_INBOX)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--models", default=DEFAULT_MODELS)
    parser.add_argument("--render-dpi", type=int, default=150)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--retries", type=int, default=0)
    parser.add_argument("--retry-sleep-seconds", type=float, default=2.0)
    parser.add_argument("--skip-review-publish", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
