from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import shutil
import subprocess
import time
import traceback
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from xml.sax.saxutils import escape

from PIL import Image

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_INPUT_DIR = ROOT / "tools" / "pdf_rotation_mvp" / "output" / "JS2207-00-00升降平台"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "js2207_title_block_drawing_number_ocr_test"
DEFAULT_REVIEW_INBOX = ROOT / "local_data" / "review_inbox" / "current"
DEFAULT_ENV_FILE = ROOT / ".env" / ".env"
DEFAULT_REVIEW_SLUG = "js2207_title_block_drawing_number_ocr_review"
DEFAULT_REVIEW_TITLE = "JS2207 标题栏图号 OCR 四模型审核"
RECORD_VERSION = "js2207-title-block-drawing-number-ocr-v0.1"

PROMPT = """你是机械制图标题栏图号提取助手。

请只从图片中的机械图纸标题栏提取整张图纸的“图号”或“图样代号”。不要提取明细表中的零件号、序号、材料牌号、标准件号、技术要求编号、文件路径或日期。

标题栏判断规则：
- 真正标题栏通常位于图纸正确方向下的底部、底边满宽区域或右下角，并贴近图框外边。
- 标题栏通常同时包含字段组合：图号/图样代号、图名/名称、材料、比例、重量/表面积、单位、设计、制图、校对、审核、批准、日期。
- 图号通常是紧邻“图号”“图样代号”“代号”“Drawing No.”“DWG No.”等标签的工程编号；不要把“图名/名称”字段里的中文名称当图号。
- 常见图号可由字母、数字、连字符、点号组成，但格式只是辅助证据，必须以标题栏字段关系为准。
- 明细表、零件表、技术要求表、局部说明表不是标题栏；即使它们有表格线或出现材料、数量、备注等字段，也不能把其中编号当作图纸图号。
- 只看见明细表或没有可确认标题栏时，selected_drawing_number 必须为空字符串，并设置 needs_human_review=true。
- 看不清、被裁切或存在多个候选无法确定时，selected_drawing_number 必须为空字符串，并设置 needs_human_review=true。

输出要求：
- 只返回 JSON，不返回 Markdown，不返回额外说明。
- 不要臆造图号。
- 候选值请保持原始大小写和连字符格式，去除明显空格。

JSON 结构：
{
  "selected_drawing_number": "",
  "candidates": [],
  "confidence": 0.0,
  "evidence": [],
  "needs_human_review": true,
  "review_reasons": []
}
"""

DRAWING_NUMBER_PATTERN = re.compile(r"\b[A-Z]{1,8}[A-Z0-9]{0,8}(?:[-_][A-Z0-9]{1,16}){1,10}\b", re.IGNORECASE)
UNKNOWN_VALUES = {"", "unknown", "none", "null", "n/a", "无法确定", "不确定", "看不清", "无"}
KNOWN_RISK_PAGES = {
    3: "not_a_drawing_or_no_title_block_from_rotation_review",
    22: "known_rotation_error_from_manual_review",
}
KNOWN_RISK_LABELS = {
    "not_a_drawing_or_no_title_block_from_rotation_review": "上一轮标记为无标题栏/非图纸",
    "known_rotation_error_from_manual_review": "方向存在已知错误，本轮暂不修正",
}
MODEL_ORDER = {
    "qwen3.7-plus": 0,
    "qwen3.7-max-2026-06-08": 1,
    "qwen3.5-ocr": 2,
    "qwen-vl-ocr-latest": 3,
}
REQUEST_MODES = ("structured_json", "nonthinking_text", "minimal_text")


@dataclass(frozen=True)
class ModelVariant:
    variant_id: str
    display_name: str
    model_id: str
    is_ocr_model: bool


MODEL_VARIANTS = [
    ModelVariant("qwen3_7_plus", "qwen3.7-plus", "qwen3.7-plus", False),
    ModelVariant("qwen3_7_max_2026_06_08", "qwen3.7-max-2026-06-08", "qwen3.7-max-2026-06-08", False),
    ModelVariant("qwen3_5_ocr", "qwen3.5-ocr", "qwen3.5-ocr", True),
    ModelVariant("qwen_vl_ocr_latest", "qwen-vl-ocr-latest", "qwen-vl-ocr-latest", True),
]


def as_posix(path: Path | str | None) -> str | None:
    if path is None:
        return None
    path_obj = Path(path)
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def safe_reset_child_dir(path: Path, allowed_root: Path) -> None:
    resolved = path.resolve()
    allowed = allowed_root.resolve()
    if resolved == allowed:
        raise ValueError(f"Refusing to reset root itself: {resolved}")
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise ValueError(f"Refusing to reset outside allowed root: {resolved}") from exc
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def xlsx_col_name(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def write_xlsx(path: Path, rows: list[dict[str, Any]], fieldnames: list[str], sheet_name: str) -> None:
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
        '<col min="1" max="1" width="10" customWidth="1"/>'
        '<col min="2" max="2" width="28" customWidth="1"/>'
        '<col min="3" max="6" width="22" customWidth="1"/>'
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
        f'<sheets><sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets></workbook>'
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


def render_pdf(pdf_path: Path, png_path: Path, dpi: int, log_path: Path) -> None:
    gs = find_ghostscript()
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
        str(pdf_path),
    ]
    run_command(command, log_path)


def page_number_from_name(path: Path) -> int:
    match = re.search(r"_page_(\d+)\.pdf$", path.name, re.IGNORECASE)
    if not match:
        raise ValueError(f"Cannot parse page number from {path.name}")
    return int(match.group(1))


def build_crop(image_path: Path, crop_path: Path, page_number: int) -> dict[str, Any]:
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        crop_ratio = 0.35 if height > width else 0.30
        y0 = int(height * (1.0 - crop_ratio))
        crop = rgb.crop((0, y0, width, height))
        crop_path.parent.mkdir(parents=True, exist_ok=True)
        crop.save(crop_path)
    return {
        "page_number": page_number,
        "rendered_image_path": as_posix(image_path),
        "crop_path": as_posix(crop_path),
        "crop_strategy": "bottom_full_width",
        "crop_ratio": crop_ratio,
        "original_width": width,
        "original_height": height,
        "crop_box": [0, y0, width, height],
        "known_risk": KNOWN_RISK_PAGES.get(page_number, ""),
    }


def collect_records(input_dir: Path, output_dir: Path, render_dpi: int) -> list[dict[str, Any]]:
    pdfs = sorted(resolve_path(input_dir).glob("*.pdf"), key=page_number_from_name)
    if not pdfs:
        raise FileNotFoundError(f"No PDF pages found in {input_dir}")
    render_dir = output_dir / "rendered_pages"
    crop_dir = output_dir / "title_block_crops"
    log_dir = output_dir / "logs" / "ghostscript"
    safe_reset_child_dir(render_dir, output_dir)
    safe_reset_child_dir(crop_dir, output_dir)
    records: list[dict[str, Any]] = []
    for pdf_path in pdfs:
        page_number = page_number_from_name(pdf_path)
        task_id = f"js2207_page_{page_number:03d}"
        image_path = render_dir / f"{task_id}.png"
        crop_path = crop_dir / f"{task_id}_title_block_crop.png"
        render_pdf(pdf_path, image_path, render_dpi, log_dir / f"{task_id}.log")
        crop_meta = build_crop(image_path, crop_path, page_number)
        records.append(
            {
                "record_version": RECORD_VERSION,
                "task_id": task_id,
                "page_number": page_number,
                "source_pdf_path": as_posix(pdf_path),
                **crop_meta,
            }
        )
    return records


def read_env_file(path: Path) -> dict[str, str]:
    resolved = resolve_path(path)
    if not resolved.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in resolved.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[name] = value
    return values


def load_env(path: Path) -> dict[str, Any]:
    file_values = read_env_file(path)
    for name, value in file_values.items():
        os.environ[name] = value
    names = ["DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL"]
    return {
        "env_file": as_posix(resolve_path(path)),
        "env_file_exists": resolve_path(path).exists(),
        "variables": {name: {"present": bool(os.environ.get(name))} for name in names},
    }


def endpoint_from_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError("DASHSCOPE_BASE_URL is empty.")
    parts = urlsplit(normalized)
    path = parts.path.rstrip("/")
    if path.endswith("/chat/completions"):
        return normalized
    if path.endswith("/compatible-mode/v1"):
        return f"{normalized}/chat/completions"
    if path.endswith("/api/v1"):
        compatible_path = f"{path[: -len('/api/v1')]}/compatible-mode/v1/chat/completions"
        return urlunsplit((parts.scheme, parts.netloc, compatible_path, parts.query, parts.fragment))
    if not path:
        compatible_path = "/compatible-mode/v1/chat/completions"
        return urlunsplit((parts.scheme, parts.netloc, compatible_path, parts.query, parts.fragment))
    return f"{normalized}/chat/completions"


def data_url_for(path: Path, mime_type: str = "image/png") -> str:
    import base64

    payload = base64.b64encode(resolve_path(path).read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{payload}"


def image_content_item(variant: ModelVariant, image_url: str) -> dict[str, Any]:
    item: dict[str, Any] = {"type": "image_url", "image_url": {"url": image_url}}
    if variant.is_ocr_model:
        item["min_pixels"] = 3072
        item["max_pixels"] = 8388608
    return item


def build_request_body(variant: ModelVariant, image_data_url: str, request_mode: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": variant.model_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    image_content_item(variant, image_data_url),
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
        "temperature": 0,
    }
    if request_mode == "structured_json":
        body["response_format"] = {"type": "json_object"}
        body["enable_thinking"] = False
    elif request_mode == "nonthinking_text":
        body["enable_thinking"] = False
    elif request_mode == "minimal_text":
        pass
    else:
        raise ValueError(f"Unknown request mode: {request_mode}")
    return body


def request_modes_for_variant(variant: ModelVariant) -> tuple[str, ...]:
    if variant.variant_id == "qwen3_5_ocr":
        return ("minimal_text", "nonthinking_text", "structured_json")
    return REQUEST_MODES


def post_chat_completion(endpoint: str, api_key: str, body: dict[str, Any], timeout_seconds: int, retries: int, retry_sleep_seconds: float) -> dict[str, Any]:
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    last_result: dict[str, Any] | None = None
    total_attempts = max(1, retries + 1)
    for attempt in range(1, total_attempts + 1):
        request = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                response_text = response.read().decode("utf-8", errors="replace")
                try:
                    response_json = json.loads(response_text)
                except json.JSONDecodeError:
                    response_json = None
                return {
                    "ok": 200 <= response.status < 300,
                    "http_status": response.status,
                    "attempt_count": attempt,
                    "response_text": response_text,
                    "response_json": response_json,
                    "error_type": "",
                    "error_message": "",
                }
        except urllib.error.HTTPError as exc:
            response_text = exc.read().decode("utf-8", errors="replace")
            try:
                response_json = json.loads(response_text)
            except json.JSONDecodeError:
                response_json = None
            last_result = {
                "ok": False,
                "http_status": exc.code,
                "attempt_count": attempt,
                "response_text": response_text,
                "response_json": response_json,
                "error_type": "http_error",
                "error_message": str(exc),
            }
            if exc.code not in {408, 429, 500, 502, 503, 504}:
                break
        except TimeoutError as exc:
            last_result = {
                "ok": False,
                "http_status": "",
                "attempt_count": attempt,
                "response_text": "",
                "response_json": None,
                "error_type": "timeout",
                "error_message": str(exc),
            }
        except urllib.error.URLError as exc:
            last_result = {
                "ok": False,
                "http_status": "",
                "attempt_count": attempt,
                "response_text": "",
                "response_json": None,
                "error_type": "url_error",
                "error_message": str(exc.reason),
            }
        if attempt < total_attempts:
            time.sleep(retry_sleep_seconds)
    return last_result or {
        "ok": False,
        "http_status": "",
        "attempt_count": 0,
        "response_text": "",
        "response_json": None,
        "error_type": "unknown_error",
        "error_message": "No request attempt was executed.",
    }


def redacted_request_row(record: dict[str, Any], variant: ModelVariant, request_mode: str) -> dict[str, Any]:
    body = build_request_body(variant, f"<omitted_png_data_url:{record['crop_path']}>", request_mode)
    return {
        "custom_id": f"{variant.variant_id}__{record['task_id']}__{request_mode}",
        "method": "POST",
        "url": "/chat/completions",
        "request_mode": request_mode,
        "body": body,
    }


def response_content_text(response: dict[str, Any]) -> str:
    response_json = response.get("response_json")
    if not isinstance(response_json, dict):
        return ""
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content if isinstance(part, dict) and isinstance(part.get("text"), str))
    return ""


def should_try_next_request_mode(response: dict[str, Any]) -> bool:
    if response.get("ok"):
        return not response_content_text(response).strip()
    status = response.get("http_status")
    if status in {400, 404, 422}:
        return True
    text = str(response.get("response_text") or response.get("error_message") or "").lower()
    return any(keyword in text for keyword in ("response_format", "enable_thinking", "thinking", "parameter", "unsupported"))


def call_models(records: list[dict[str, Any]], variants: list[ModelVariant], env_file: Path, output_dir: Path, timeout_seconds: int, retries: int, retry_sleep_seconds: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    env_summary = load_env(env_file)
    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    base_url = os.environ.get("DASHSCOPE_BASE_URL", "")
    if not api_key:
        raise RuntimeError("Missing DASHSCOPE_API_KEY. Put it in .env/.env or the process environment.")
    if not base_url:
        raise RuntimeError("Missing DASHSCOPE_BASE_URL. Put it in .env/.env or the process environment.")
    endpoint = endpoint_from_base_url(base_url)
    request_rows: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    checkpoint = output_dir / "vlm_raw_responses.partial.jsonl"
    if checkpoint.exists():
        checkpoint.unlink()
    total = len(records) * len(variants)
    index = 0
    for record in records:
        for variant in variants:
            index += 1
            print(
                json.dumps(
                    {
                        "event": "js2207_drawing_number_ocr_request",
                        "index": index,
                        "total": total,
                        "page_number": record["page_number"],
                        "model": variant.display_name,
                        "model_id": variant.model_id,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            image_data_url = data_url_for(resolve_path(Path(record["crop_path"])))
            mode_results: list[dict[str, Any]] = []
            response: dict[str, Any] | None = None
            request_modes = request_modes_for_variant(variant)
            final_request_mode = request_modes[0]
            for request_mode in request_modes:
                final_request_mode = request_mode
                request_rows.append(redacted_request_row(record, variant, request_mode))
                body = build_request_body(variant, image_data_url, request_mode)
                try:
                    response = post_chat_completion(endpoint, api_key, body, timeout_seconds, retries, retry_sleep_seconds)
                except Exception as exc:
                    response = {
                        "ok": False,
                        "http_status": "",
                        "attempt_count": 0,
                        "response_text": "",
                        "response_json": None,
                        "error_type": exc.__class__.__name__,
                        "error_message": str(exc),
                        "exception_traceback": traceback.format_exc(limit=8),
                    }
                mode_results.append(
                    {
                        "request_mode": request_mode,
                        "ok": response.get("ok"),
                        "http_status": response.get("http_status"),
                        "error_type": response.get("error_type", ""),
                        "error_message": response.get("error_message", ""),
                    }
                )
                if response.get("ok") or not should_try_next_request_mode(response):
                    break
            raw_row = {
                "record_version": RECORD_VERSION,
                "task_id": record["task_id"],
                "page_number": record["page_number"],
                "crop_path": record["crop_path"],
                "known_risk": record.get("known_risk", ""),
                "model": variant.display_name,
                "model_id": variant.model_id,
                "model_variant": variant.variant_id,
                "is_ocr_model": variant.is_ocr_model,
                "endpoint": endpoint,
                "request_mode": final_request_mode,
                "fallback_used": len(mode_results) > 1,
                "request_mode_results": mode_results,
                **response,
            }
            raw_rows.append(raw_row)
            with checkpoint.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(public_raw_row(raw_row), ensure_ascii=False) + "\n")
    return raw_rows, request_rows, env_summary


def public_raw_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_version": RECORD_VERSION,
        "task_id": row["task_id"],
        "page_number": row["page_number"],
        "crop_path": row["crop_path"],
        "known_risk": row.get("known_risk", ""),
        "model": row["model"],
        "model_id": row["model_id"],
        "model_variant": row["model_variant"],
        "request_mode": row.get("request_mode", ""),
        "fallback_used": row.get("fallback_used", False),
        "request_mode_results": row.get("request_mode_results", []),
        "endpoint": row.get("endpoint"),
        "ok": row.get("ok"),
        "http_status": row.get("http_status"),
        "attempt_count": row.get("attempt_count"),
        "error_type": row.get("error_type", ""),
        "error_message": row.get("error_message", ""),
        "response_json": row.get("response_json"),
        "response_text": row.get("response_text") if row.get("response_json") is None else "",
    }


def extract_message_content(response_json: Any) -> tuple[str, list[str]]:
    if not isinstance(response_json, dict):
        return "", ["response_not_json_object"]
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        return "", ["missing_choices"]
    first = choices[0]
    if not isinstance(first, dict):
        return "", ["choice_not_object"]
    message = first.get("message")
    if not isinstance(message, dict):
        return "", ["missing_message"]
    content = message.get("content")
    if isinstance(content, str):
        return content, []
    if isinstance(content, list):
        parts = [part.get("text") for part in content if isinstance(part, dict) and isinstance(part.get("text"), str)]
        if parts:
            return "\n".join(parts), []
    return "", ["missing_message_content"]


def parse_json_content(content: str) -> tuple[Any, list[str]]:
    text = content.strip()
    if not text:
        return None, ["empty_message_content"]
    candidates = [text]
    if text.startswith("```"):
        stripped = text.strip("`").strip()
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
        candidates.append(stripped)
    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last > first:
        candidates.append(text[first : last + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate), []
        except json.JSONDecodeError:
            continue
    return None, ["content_json_parse_failed"]


def normalize_drawing_number(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if value.lower() in UNKNOWN_VALUES:
        return ""
    value = re.sub(r"\s+", "", value)
    value = value.replace("_", "-")
    return value


def fallback_candidates_from_text(text: str) -> list[str]:
    seen: list[str] = []
    for match in DRAWING_NUMBER_PATTERN.finditer(text):
        value = normalize_drawing_number(match.group(0))
        if value and value not in seen:
            seen.append(value)
    return seen[:8]


def build_decision(row: dict[str, Any]) -> dict[str, Any]:
    content, content_errors = extract_message_content(row.get("response_json"))
    parsed, parse_errors = parse_json_content(content) if not content_errors else (None, [])
    reasons: list[str] = []
    if not row.get("ok"):
        reasons.append(f"api_error:{row.get('error_type') or row.get('http_status')}")
    reasons.extend(content_errors)
    reasons.extend(parse_errors)

    selected = ""
    candidates: list[str] = []
    confidence: Any = ""
    evidence: list[str] = []
    model_needs_review: Any = ""
    model_reasons: list[str] = []
    schema_status = "error"
    if isinstance(parsed, dict):
        selected = normalize_drawing_number(parsed.get("selected_drawing_number"))
        raw_candidates = parsed.get("candidates")
        if isinstance(raw_candidates, list):
            candidates = [normalize_drawing_number(item) for item in raw_candidates if normalize_drawing_number(item)]
        confidence = parsed.get("confidence", "")
        raw_evidence = parsed.get("evidence")
        if isinstance(raw_evidence, list):
            evidence = [str(item) for item in raw_evidence if str(item)]
        model_needs_review = parsed.get("needs_human_review")
        raw_reasons = parsed.get("review_reasons")
        if isinstance(raw_reasons, list):
            model_reasons = [str(item) for item in raw_reasons if str(item)]
        required_ok = (
            isinstance(parsed.get("selected_drawing_number"), str)
            and isinstance(parsed.get("candidates"), list)
            and isinstance(parsed.get("evidence"), list)
            and isinstance(parsed.get("needs_human_review"), bool)
            and isinstance(parsed.get("review_reasons"), list)
            and isinstance(parsed.get("confidence"), int | float)
        )
        schema_status = "ok" if required_ok else "error"
        if not required_ok:
            reasons.append("schema_error")
    else:
        candidates = fallback_candidates_from_text(content)
        if candidates:
            reasons.append("fallback_regex_candidates_from_unstructured_text")

    if model_needs_review is True:
        reasons.append("model_marked_needs_human_review")
    for reason in model_reasons:
        reasons.append(f"model:{reason}")
    if not selected:
        reasons.append("drawing_number_missing")

    return {
        "record_version": RECORD_VERSION,
        "task_id": row["task_id"],
        "page_number": row["page_number"],
        "crop_path": row["crop_path"],
        "known_risk": row.get("known_risk", ""),
        "model": row["model"],
        "model_id": row["model_id"],
        "model_variant": row["model_variant"],
        "api_ok": bool(row.get("ok")),
        "http_status": row.get("http_status"),
        "attempt_count": row.get("attempt_count"),
        "parse_status": "ok" if parsed is not None and not content_errors and not parse_errors else "error",
        "schema_status": schema_status,
        "selected_drawing_number": selected,
        "candidates": candidates,
        "confidence": confidence,
        "model_needs_human_review": model_needs_review if isinstance(model_needs_review, bool) else "",
        "needs_review": bool(reasons),
        "review_reasons": sorted(dict.fromkeys(reasons)),
        "evidence": evidence,
        "error_type": row.get("error_type", ""),
        "error_message": row.get("error_message", ""),
        "parsed_response": parsed if isinstance(parsed, dict) else {},
        "raw_content_excerpt": content[:500],
    }


def build_review_rows(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for decision in sorted(decisions, key=lambda item: (item["page_number"], MODEL_ORDER.get(item["model"], 999), item["model"])):
        rows.append(
            {
                "页码": decision["page_number"],
                "模型": decision["model"],
                "模型提取图号": decision.get("selected_drawing_number", ""),
                "图号是否正确": "",
                "正确图号": "",
                "备注": "",
            }
        )
    return rows


def archive_current_inbox(current_dir: Path, archive_reason: str) -> str | None:
    resolved = resolve_path(current_dir)
    resolved.mkdir(parents=True, exist_ok=True)
    entries = [entry for entry in resolved.iterdir() if entry.name != ".gitkeep"]
    only_readme = len(entries) == 1 and entries[0].name == "README.md"
    readme_empty = False
    if only_readme:
        readme_empty = "当前没有待用户审核" in entries[0].read_text(encoding="utf-8", errors="replace")
    if not entries or readme_empty:
        return None
    archive_root = ROOT / "local_data" / "review_inbox" / "archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    archive_dir = archive_root / f"current_archived_before_{archive_reason}_{stamp}"
    shutil.move(str(resolved), str(archive_dir))
    resolved.mkdir(parents=True, exist_ok=True)
    return as_posix(archive_dir)


def publish_review_pack(
    output_dir: Path,
    current_dir: Path,
    review_slug: str,
    review_title: str,
    records: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, Any]:
    archived = archive_current_inbox(current_dir, review_slug)
    review_dir = current_dir / review_slug
    crop_dir = review_dir / "crops"
    page_dir = review_dir / "pages"
    reports_dir = review_dir / "reports"
    review_dir.mkdir(parents=True, exist_ok=True)
    crop_dir.mkdir(parents=True, exist_ok=True)
    page_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    crop_map: dict[int, str] = {}
    page_map: dict[int, str] = {}
    for record in records:
        src = resolve_path(Path(record["crop_path"]))
        target = crop_dir / src.name
        shutil.copy2(src, target)
        crop_map[int(record["page_number"])] = target.relative_to(review_dir).as_posix()
        page_src = resolve_path(Path(record["rendered_image_path"]))
        page_target = page_dir / page_src.name
        shutil.copy2(page_src, page_target)
        page_map[int(record["page_number"])] = page_target.relative_to(review_dir).as_posix()

    review_fields = ["页码", "模型", "模型提取图号", "图号是否正确", "正确图号", "备注"]
    xlsx_path = review_dir / "js2207_title_block_drawing_number_ocr_review.xlsx"
    html_path = review_dir / "review_index.html"
    manifest_path = review_dir / "review_manifest.json"
    write_xlsx(xlsx_path, review_rows, review_fields, "图号OCR审核")
    shutil.copy2(output_dir / "decisions.csv", reports_dir / "decisions.csv")
    shutil.copy2(output_dir / "run_summary.json", reports_dir / "run_summary.json")

    by_page: dict[int, list[dict[str, Any]]] = {}
    for decision in decisions:
        by_page.setdefault(int(decision["page_number"]), []).append(decision)
    cards = []
    for record in records:
        page = int(record["page_number"])
        rows_html = []
        for decision in sorted(by_page.get(page, []), key=lambda item: (MODEL_ORDER.get(item["model"], 999), item["model"])):
            rows_html.append(
                "<tr>"
                f"<td>{html.escape(decision['model'])}</td>"
                f"<td>{html.escape(str(decision.get('selected_drawing_number', '')))}</td>"
                f"</tr>"
            )
        risk_code = record.get("known_risk") or ""
        risk = KNOWN_RISK_LABELS.get(risk_code, risk_code)
        cards.append(
            f"""
    <article class="page-card" id="page-{page}">
      <div class="page-head"><h2>第 {page} 页</h2><span>{html.escape(risk)}</span></div>
      <a href="{html.escape(crop_map[page])}" target="_blank"><img src="{html.escape(crop_map[page])}" alt="第 {page} 页标题栏候选 crop"></a>
      <div class="page-link"><a href="{html.escape(page_map[page])}" target="_blank">打开整页图</a></div>
      <table><thead><tr><th>模型</th><th>模型提取图号</th></tr></thead><tbody>{''.join(rows_html)}</tbody></table>
    </article>
"""
        )
    html_path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(review_title)}</title>
  <style>
    body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; color: #1c2733; background: #f6f7f9; }}
    header {{ position: sticky; top: 0; z-index: 2; padding: 14px 20px; background: #ffffff; border-bottom: 1px solid #d8dee8; }}
    h1 {{ margin: 0 0 6px; font-size: 20px; }}
    .meta {{ display: flex; gap: 14px; flex-wrap: wrap; color: #52606d; font-size: 13px; }}
    main {{ max-width: 1480px; margin: 0 auto; padding: 18px; }}
    .guide {{ margin-bottom: 16px; padding: 12px 14px; background: #ffffff; border: 1px solid #d8dee8; }}
    .page-card {{ margin-bottom: 18px; padding: 14px; background: #ffffff; border: 1px solid #d8dee8; }}
    .page-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 8px; }}
    .page-head h2 {{ margin: 0; font-size: 18px; }}
    .page-head span {{ color: #8a1f1f; font-size: 13px; }}
    img {{ display: block; width: 100%; max-height: 52vh; object-fit: contain; background: #f8fafc; border: 1px solid #e2e8f0; }}
    .page-link {{ margin-top: 8px; font-size: 13px; }}
    .page-link a {{ color: #174ea6; }}
    table {{ width: 100%; margin-top: 10px; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border: 1px solid #d8dee8; padding: 7px 8px; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f6; }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(review_title)}</h1>
    <div class="meta">
      <span>页数：{summary['page_count']}</span>
      <span>模型：{len(MODEL_VARIANTS)}</span>
      <span>结果：{summary['decision_count']}</span>
      <span>填写：js2207_title_block_drawing_number_ocr_review.xlsx</span>
    </div>
  </header>
  <main>
    <section class="guide">
      请根据标题栏候选 crop 核对模型提取的图号。第 3 页无标题栏，第 22 页方向存在已知风险；如图号错误或缺失，请在 Excel 中填写正确图号和备注。
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
        "task": review_slug,
        "review_title": review_title,
        "source_output_dir": as_posix(output_dir),
        "page_count": len(records),
        "decision_count": len(decisions),
        "human_review_fields": review_fields,
        "archived_previous_current": archived,
        "html": html_path.relative_to(current_dir).as_posix(),
        "xlsx": xlsx_path.relative_to(current_dir).as_posix(),
        "crop_count": len(crop_map),
        "page_image_count": len(page_map),
    }
    write_json(manifest_path, manifest)
    (current_dir / "README.md").write_text(
        "\n".join(
            [
                "# 当前待审核任务",
                "",
                f"任务：{review_title}。",
                "",
                "请打开：",
                "",
                f"- `{review_slug}/review_index.html`",
                f"- `{review_slug}/js2207_title_block_drawing_number_ocr_review.xlsx`",
                f"- `{review_slug}/crops/`",
                f"- `{review_slug}/pages/`",
                "",
                "请审核模型提取图号是否正确，必要时填写正确图号和备注。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def write_decisions_csv(path: Path, decisions: list[dict[str, Any]]) -> None:
    write_csv(
        path,
        [
            {
                **row,
                "candidates": json.dumps(row.get("candidates", []), ensure_ascii=False),
                "evidence": ";".join(row.get("evidence", [])),
                "review_reasons": ";".join(row.get("review_reasons", [])),
                "parsed_response": json.dumps(row.get("parsed_response", {}), ensure_ascii=False),
            }
            for row in decisions
        ],
        [
            "task_id",
            "page_number",
            "crop_path",
            "known_risk",
            "model",
            "model_id",
            "model_variant",
            "request_mode",
            "fallback_used",
            "api_ok",
            "http_status",
            "attempt_count",
            "parse_status",
            "schema_status",
            "selected_drawing_number",
            "candidates",
            "confidence",
            "model_needs_human_review",
            "needs_review",
            "review_reasons",
            "evidence",
            "error_type",
            "error_message",
            "raw_content_excerpt",
            "parsed_response",
        ],
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    records = collect_records(args.input_dir, output_dir, args.render_dpi)
    variants = MODEL_VARIANTS
    raw_rows, request_rows, env_summary = call_models(
        records,
        variants,
        args.env_file,
        output_dir,
        args.timeout_seconds,
        args.retries,
        args.retry_sleep_seconds,
    )
    decisions = [build_decision(row) for row in raw_rows]
    if raw_rows and sum(1 for row in decisions if row.get("api_ok")) == 0:
        raise RuntimeError("All OCR model requests failed. Refusing to publish review pack.")

    prompt_path = output_dir / "prompt.md"
    records_path = output_dir / "records.json"
    requests_path = output_dir / "requests.jsonl"
    raw_path = output_dir / "vlm_raw_responses.jsonl"
    decisions_path = output_dir / "decisions.jsonl"
    decisions_csv_path = output_dir / "decisions.csv"
    review_rows = build_review_rows(decisions)

    prompt_path.write_text(PROMPT, encoding="utf-8")
    write_json(records_path, records)
    write_jsonl(requests_path, request_rows)
    write_jsonl(raw_path, [public_raw_row(row) for row in raw_rows])
    write_jsonl(decisions_path, decisions)
    write_decisions_csv(decisions_csv_path, decisions)

    summary = {
        "record_version": RECORD_VERSION,
        "input_dir": as_posix(resolve_path(args.input_dir)),
        "output_dir": as_posix(output_dir),
        "page_count": len(records),
        "model_count": len(variants),
        "request_count": len(records) * len(variants),
        "request_spec_count": len(request_rows),
        "raw_response_count": len(raw_rows),
        "decision_count": len(decisions),
        "api_ok_count": sum(1 for row in decisions if row.get("api_ok")),
        "parse_ok_count": sum(1 for row in decisions if row.get("parse_status") == "ok"),
        "schema_ok_count": sum(1 for row in decisions if row.get("schema_status") == "ok"),
        "selected_non_empty_count": sum(1 for row in decisions if row.get("selected_drawing_number")),
        "render_dpi": args.render_dpi,
        "temperature": 0,
        "top_p": "not_set",
        "request_modes": list(REQUEST_MODES),
        "model_request_modes": {variant.display_name: list(request_modes_for_variant(variant)) for variant in variants},
        "model_variants": [variant.__dict__ for variant in variants],
        "env_status": env_summary,
        "known_risk_pages": KNOWN_RISK_PAGES,
        "outputs": {
            "prompt": as_posix(prompt_path),
            "records": as_posix(records_path),
            "requests": as_posix(requests_path),
            "raw_responses": as_posix(raw_path),
            "decisions": as_posix(decisions_path),
            "decisions_csv": as_posix(decisions_csv_path),
        },
    }
    write_json(output_dir / "run_summary.json", summary)
    review_summary = publish_review_pack(
        output_dir,
        resolve_path(args.review_inbox),
        args.review_slug,
        args.review_title,
        records,
        decisions,
        review_rows,
        summary,
    )
    summary["outputs"]["review"] = review_summary
    write_json(output_dir / "run_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build JS2207 drawing-number OCR model review pack.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--review-inbox", type=Path, default=DEFAULT_REVIEW_INBOX)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--review-slug", default=DEFAULT_REVIEW_SLUG)
    parser.add_argument("--review-title", default=DEFAULT_REVIEW_TITLE)
    parser.add_argument("--render-dpi", type=int, default=180)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--retry-sleep-seconds", type=float, default=3.0)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
