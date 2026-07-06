from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:  # pragma: no cover
    from PyPDF2 import PdfReader, PdfWriter

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_INPUT_DIR = SCRIPT_DIR / "input"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output"
DEFAULT_WORK_DIR = SCRIPT_DIR / "work"
DEFAULT_ENV_FILE = REPO_ROOT / ".env" / ".env"
DEFAULT_MODEL = "qwen3.7-plus"
RECORD_VERSION = "pdf-rotation-mvp-v0.1"

TITLE_BLOCK_ONLY_PROMPT = """你是机械图纸标题栏定位助手。

请只根据当前图片中可见内容判断标题栏在图片屏幕坐标下的位置。

任务：
1. 定位真正的机械制图标题栏。
2. 输出标题栏在当前图片屏幕坐标下的位置。
3. 不要判断图纸旋转角度，旋转角度由程序根据标题栏位置推导。
4. 不要读取图号，不要解释图纸内容。

重要规则：
- 不要把图片想象旋转到正确阅读方向后再判断位置；图片顶部就是 top，底部就是 bottom，左侧就是 left，右侧就是 right。
- 标题栏在正确制图方向下应位于图纸下方、底边满宽区域或右下方。
- 有些机械图纸按纸张竖向绘制，标题栏位于当前图片下方，并横向占满或接近占满图纸宽度；这种情况必须返回 bottom_edge。
- 如果标题栏沿当前图片顶部、左侧或右侧边缘展开，分别返回 top_edge、left_edge、right_edge。
- 只有标题栏主体集中在角落时，才返回 bottom_right、bottom_left、top_right 或 top_left。
- 真正标题栏通常贴近或贴住图纸外框，并包含图号/图名/名称/材料/比例/设计/制图/校对/审核/批准/日期/单位等字段组合。
- 零件表格、明细表、技术要求表、局部说明表不是标题栏；即使它们靠近边缘或包含表格线，也不能当作标题栏。
- 如果找不到可确认标题栏，title_block_position 返回 no_title_block，并设置 needs_human_review=true。

只返回 JSON，不返回 Markdown，不返回额外说明。JSON 必须符合以下结构：

{
  "title_block_position": "bottom_edge",
  "confidence": 0.0,
  "evidence": [],
  "needs_human_review": true,
  "review_reasons": []
}

字段约束：
- title_block_position 只能使用 bottom_edge、top_edge、left_edge、right_edge、bottom_right、bottom_left、top_right、top_left、no_title_block、unknown。
- confidence 必须是 0 到 1 之间的数字。
- evidence 和 review_reasons 必须是字符串数组。
"""

DRAWING_NUMBER_PROMPT = """你是机械制图标题栏图号提取助手。

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

POSITION_ALIASES = {
    "bottom": "bottom_edge",
    "top": "top_edge",
    "left": "left_edge",
    "right": "right_edge",
}

POSITION_TO_ROTATION: dict[str, tuple[int | None, int | None]] = {
    "bottom_edge": (0, 0),
    "bottom_right": (0, 0),
    "bottom_left": (90, 270),
    "left_edge": (90, 270),
    "top_left": (180, 180),
    "top_edge": (180, 180),
    "top_right": (270, 90),
    "right_edge": (270, 90),
    "no_title_block": (None, None),
    "unknown": (None, None),
}

ALLOWED_POSITIONS = set(POSITION_TO_ROTATION)
UNKNOWN_DRAWING_NUMBER_VALUES = {"", "unknown", "none", "null", "n/a", "无法确定", "不确定", "看不清", "无"}
WINDOWS_RESERVED_FILENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
ILLEGAL_FILENAME_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True)
class PageRecord:
    source_pdf: Path
    source_stem: str
    page_number: int
    page_count: int
    task_id: str
    split_pdf_path: Path
    rendered_png_path: Path
    output_pdf_path: Path


@dataclass(frozen=True)
class ImageRecord:
    source_pdf: Path
    source_stem: str
    page_number: int
    task_id: str
    image_path: Path


def safe_name(value: str) -> str:
    chars = []
    for char in value:
        if char.isalnum() or char in {"-", "_", "."}:
            chars.append(char)
        else:
            chars.append("_")
    return "".join(chars).strip("._") or "pdf"


def normalize_drawing_number(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if text.lower() in UNKNOWN_DRAWING_NUMBER_VALUES:
        return ""
    text = re.sub(r"\s+", "", text)
    return text


def drawing_number_filename_status(value: str) -> tuple[str | None, list[str]]:
    drawing_number = normalize_drawing_number(value)
    blockers: list[str] = []
    if not drawing_number:
        blockers.append("missing_drawing_number")
        return None, blockers
    if ILLEGAL_FILENAME_PATTERN.search(drawing_number):
        blockers.append("drawing_number_has_illegal_filename_chars")
    if drawing_number.endswith(".") or drawing_number.endswith(" "):
        blockers.append("drawing_number_has_invalid_trailing_char")
    if drawing_number.upper() in WINDOWS_RESERVED_FILENAMES:
        blockers.append("drawing_number_is_windows_reserved_name")
    if len(drawing_number) > 180:
        blockers.append("drawing_number_too_long")
    return (drawing_number if not blockers else None), blockers


def as_posix(path: Path | str | None) -> str | None:
    if path is None:
        return None
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def ensure_child_dir(path: Path, allowed_root: Path) -> Path:
    resolved = path.resolve()
    allowed = allowed_root.resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise ValueError(f"Refusing to use path outside allowed root: {resolved}") from exc
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def safe_reset_child_dir(path: Path, allowed_root: Path) -> Path:
    resolved = path.resolve()
    allowed = allowed_root.resolve()
    if resolved == allowed:
        raise ValueError(f"Refusing to reset root itself: {resolved}")
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise ValueError(f"Refusing to reset outside allowed root: {resolved}") from exc
    if resolved.exists():
        for child in resolved.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
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
    values = read_env_file(path)
    for name, value in values.items():
        os.environ[name] = value
    names = ["DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL"]
    return {
        "env_file": as_posix(path),
        "env_file_exists": path.exists(),
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
        return urlunsplit((parts.scheme, parts.netloc, "/compatible-mode/v1/chat/completions", parts.query, parts.fragment))
    return f"{normalized}/chat/completions"


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


def find_ghostscript() -> str:
    for executable in ("gswin64c", "gswin32c", "gs"):
        found = shutil.which(executable)
        if found:
            return found
    raise RuntimeError("Ghostscript executable not found: expected gswin64c, gswin32c, or gs")


def run_command(command: list[str], log_path: Path) -> None:
    result = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
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


def render_pdf_page(page_pdf: Path, png_path: Path, dpi: int, log_path: Path) -> None:
    gs = find_ghostscript()
    png_path.parent.mkdir(parents=True, exist_ok=True)
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
    run_command(command, log_path)


def crop_title_block_candidate(image_path: Path, crop_path: Path) -> dict[str, Any]:
    if Image is None:
        raise RuntimeError("Pillow is required for title-block crop generation. Install pillow.")
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        crop_ratio = 0.35 if height > width else 0.30
        y0 = int(height * (1.0 - crop_ratio))
        crop = rgb.crop((0, y0, width, height))
        crop_path.parent.mkdir(parents=True, exist_ok=True)
        crop.save(crop_path)
    return {
        "crop_path": as_posix(crop_path),
        "crop_strategy": "bottom_full_width_after_rotation_correction",
        "crop_ratio": crop_ratio,
        "crop_box": [0, y0, width, height],
        "rendered_width": width,
        "rendered_height": height,
    }


def collect_input_pdfs(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    pdfs = sorted([path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"])
    if not pdfs:
        raise FileNotFoundError(f"No PDF files found in input directory: {input_dir}")
    return pdfs


def split_and_render_pdfs(
    pdfs: list[Path],
    work_dir: Path,
    output_dir: Path,
    render_dpi: int,
    limit_pages: int | None,
) -> list[PageRecord]:
    records: list[PageRecord] = []
    split_root = work_dir / "split_pdfs"
    png_root = work_dir / "rendered_png"
    corrected_root = work_dir / "corrected_pdfs"
    log_root = work_dir / "logs" / "ghostscript"
    for pdf_path in pdfs:
        reader = PdfReader(str(pdf_path))
        page_count = len(reader.pages)
        selected_count = min(page_count, limit_pages) if limit_pages else page_count
        source_stem = safe_name(pdf_path.stem)
        for page_index in range(selected_count):
            page_number = page_index + 1
            task_id = f"{source_stem}_page_{page_number:03d}"
            split_pdf_path = split_root / source_stem / f"{task_id}.pdf"
            rendered_png_path = png_root / source_stem / f"{task_id}.png"
            output_pdf_path = corrected_root / source_stem / f"{task_id}.pdf"
            split_pdf_path.parent.mkdir(parents=True, exist_ok=True)
            writer = PdfWriter()
            writer.add_page(reader.pages[page_index])
            with split_pdf_path.open("wb") as handle:
                writer.write(handle)
            render_pdf_page(split_pdf_path, rendered_png_path, render_dpi, log_root / source_stem / f"{task_id}.log")
            records.append(
                PageRecord(
                    source_pdf=pdf_path,
                    source_stem=source_stem,
                    page_number=page_number,
                    page_count=page_count,
                    task_id=task_id,
                    split_pdf_path=split_pdf_path,
                    rendered_png_path=rendered_png_path,
                    output_pdf_path=output_pdf_path,
                )
            )
    return records


def data_url_for(path: Path, mime_type: str = "image/png") -> str:
    import base64

    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{payload}"


def build_request_body(model: str, image_data_url: str, prompt: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "enable_thinking": False,
    }


def post_chat_completion(
    endpoint: str,
    api_key: str,
    body: dict[str, Any],
    timeout_seconds: int,
    retries: int,
    retry_sleep_seconds: float,
) -> dict[str, Any]:
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


def canonical_title_block_position(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return POSITION_ALIASES.get(normalized, normalized)


def derive_rotation(position: str | None) -> tuple[int | None, int | None, list[str]]:
    if position is None:
        return None, None, ["missing_title_block_position_for_rotation"]
    current, correction = POSITION_TO_ROTATION.get(position, (None, None))
    if current is None or correction is None:
        return None, None, ["unknown_title_block_position_for_rotation"]
    return current, correction, []


def is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def normalize_decision(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        return {}
    if "page_orientation" in parsed and isinstance(parsed.get("page_orientation"), dict):
        page_orientation = parsed.get("page_orientation") or {}
        quality_gate = parsed.get("quality_gate") if isinstance(parsed.get("quality_gate"), dict) else {}
        return {
            "title_block_position": page_orientation.get("title_block_position"),
            "confidence": page_orientation.get("confidence"),
            "evidence": page_orientation.get("evidence"),
            "needs_human_review": quality_gate.get("needs_human_review"),
            "review_reasons": quality_gate.get("review_reasons"),
        }
    return parsed


def validate_decision(parsed: Any) -> list[str]:
    normalized = normalize_decision(parsed)
    if not normalized:
        return ["decision_not_object"]
    errors: list[str] = []
    position = canonical_title_block_position(normalized.get("title_block_position"))
    if position not in ALLOWED_POSITIONS:
        errors.append("invalid_title_block_position")
    confidence = normalized.get("confidence")
    if not is_number(confidence) or not 0 <= float(confidence) <= 1:
        errors.append("invalid_confidence")
    if not isinstance(normalized.get("evidence"), list):
        errors.append("evidence_not_list")
    if not isinstance(normalized.get("needs_human_review"), bool):
        errors.append("needs_human_review_not_bool")
    if not isinstance(normalized.get("review_reasons"), list):
        errors.append("review_reasons_not_list")
    return errors


def build_decision(raw_row: dict[str, Any]) -> dict[str, Any]:
    content, content_errors = extract_message_content(raw_row.get("response_json"))
    parsed, parse_errors = parse_json_content(content) if not content_errors else (None, [])
    normalized = normalize_decision(parsed)
    schema_errors = validate_decision(parsed) if parsed is not None else []
    position = canonical_title_block_position(normalized.get("title_block_position"))
    current, correction, rotation_errors = derive_rotation(position)

    reasons: list[str] = []
    if not raw_row.get("ok"):
        reasons.append(f"api_error:{raw_row.get('error_type') or raw_row.get('http_status')}")
    reasons.extend(content_errors)
    reasons.extend(parse_errors)
    reasons.extend(schema_errors)
    reasons.extend(rotation_errors)
    if normalized.get("needs_human_review") is True:
        reasons.append("model_marked_needs_human_review")
    model_reasons = normalized.get("review_reasons")
    if isinstance(model_reasons, list):
        for reason in model_reasons:
            if isinstance(reason, str) and reason:
                reasons.append(f"model:{reason}")

    return {
        "record_version": RECORD_VERSION,
        "task_id": raw_row["task_id"],
        "source_pdf": raw_row["source_pdf"],
        "page_number": raw_row["page_number"],
        "model": raw_row["model"],
        "api_ok": bool(raw_row.get("ok")),
        "http_status": raw_row.get("http_status"),
        "attempt_count": raw_row.get("attempt_count"),
        "parse_status": "ok" if parsed is not None and not content_errors and not parse_errors else "error",
        "schema_status": "ok" if parsed is not None and not schema_errors else "error",
        "title_block_position": position,
        "current_clockwise_degrees": current,
        "correction_clockwise_degrees": correction,
        "confidence": normalized.get("confidence"),
        "model_needs_human_review": normalized.get("needs_human_review") if isinstance(normalized.get("needs_human_review"), bool) else "",
        "needs_review": bool(reasons),
        "review_reasons": sorted(dict.fromkeys(reasons)),
        "evidence": normalized.get("evidence") if isinstance(normalized.get("evidence"), list) else [],
        "error_type": raw_row.get("error_type", ""),
        "error_message": raw_row.get("error_message", ""),
        "parsed_response": parsed if isinstance(parsed, dict) else {},
    }


def validate_drawing_number_response(parsed: Any) -> list[str]:
    if not isinstance(parsed, dict):
        return ["drawing_number_response_not_object"]
    errors: list[str] = []
    if not isinstance(parsed.get("selected_drawing_number"), str):
        errors.append("selected_drawing_number_not_string")
    if not isinstance(parsed.get("candidates"), list):
        errors.append("candidates_not_list")
    if not is_number(parsed.get("confidence")) or not 0 <= float(parsed.get("confidence")) <= 1:
        errors.append("invalid_drawing_number_confidence")
    if not isinstance(parsed.get("evidence"), list):
        errors.append("drawing_number_evidence_not_list")
    if not isinstance(parsed.get("needs_human_review"), bool):
        errors.append("drawing_number_needs_human_review_not_bool")
    if not isinstance(parsed.get("review_reasons"), list):
        errors.append("drawing_number_review_reasons_not_list")
    return errors


def build_drawing_number_decision(raw_row: dict[str, Any]) -> dict[str, Any]:
    content, content_errors = extract_message_content(raw_row.get("response_json"))
    parsed, parse_errors = parse_json_content(content) if not content_errors else (None, [])
    schema_errors = validate_drawing_number_response(parsed) if parsed is not None else []
    parsed_dict = parsed if isinstance(parsed, dict) else {}
    drawing_number = normalize_drawing_number(parsed_dict.get("selected_drawing_number"))
    filename_stem, filename_blockers = drawing_number_filename_status(drawing_number)
    candidates = parsed_dict.get("candidates")
    evidence = parsed_dict.get("evidence")
    model_reasons = parsed_dict.get("review_reasons")

    reasons: list[str] = []
    if not raw_row.get("ok"):
        reasons.append(f"drawing_number_api_error:{raw_row.get('error_type') or raw_row.get('http_status')}")
    reasons.extend(content_errors)
    reasons.extend(parse_errors)
    reasons.extend(schema_errors)
    reasons.extend(filename_blockers)
    if parsed_dict.get("needs_human_review") is True:
        reasons.append("drawing_number_model_marked_needs_human_review")
    if isinstance(model_reasons, list):
        for reason in model_reasons:
            if isinstance(reason, str) and reason:
                reasons.append(f"drawing_number_model:{reason}")

    return {
        "record_version": RECORD_VERSION,
        "task_id": raw_row["task_id"],
        "source_pdf": raw_row["source_pdf"],
        "page_number": raw_row["page_number"],
        "model": raw_row["model"],
        "api_ok": bool(raw_row.get("ok")),
        "http_status": raw_row.get("http_status"),
        "attempt_count": raw_row.get("attempt_count"),
        "parse_status": "ok" if parsed is not None and not content_errors and not parse_errors else "error",
        "schema_status": "ok" if parsed is not None and not schema_errors else "error",
        "selected_drawing_number": drawing_number,
        "final_filename_stem": filename_stem or "",
        "candidates": [normalize_drawing_number(item) for item in candidates if normalize_drawing_number(item)] if isinstance(candidates, list) else [],
        "confidence": parsed_dict.get("confidence"),
        "model_needs_human_review": parsed_dict.get("needs_human_review") if isinstance(parsed_dict.get("needs_human_review"), bool) else "",
        "needs_review": bool(reasons),
        "review_reasons": sorted(dict.fromkeys(reasons)),
        "evidence": evidence if isinstance(evidence, list) else [],
        "error_type": raw_row.get("error_type", ""),
        "error_message": raw_row.get("error_message", ""),
        "parsed_response": parsed if isinstance(parsed, dict) else {},
    }


def image_records_from_pages(records: list[PageRecord]) -> list[ImageRecord]:
    return [
        ImageRecord(
            source_pdf=record.source_pdf,
            source_stem=record.source_stem,
            page_number=record.page_number,
            task_id=record.task_id,
            image_path=record.rendered_png_path,
        )
        for record in records
    ]


def build_corrected_crop_records(records: list[PageRecord], outputs: list[dict[str, Any]], work_dir: Path, render_dpi: int) -> tuple[list[ImageRecord], list[dict[str, Any]]]:
    crop_records: list[ImageRecord] = []
    crop_meta_rows: list[dict[str, Any]] = []
    output_by_task = {row["task_id"]: row for row in outputs}
    rendered_root = work_dir / "corrected_rendered_png"
    crop_root = work_dir / "title_block_crops"
    log_root = work_dir / "logs" / "corrected_ghostscript"
    for record in records:
        output = output_by_task.get(record.task_id, {})
        corrected_pdf_path = record.output_pdf_path
        rendered_path = rendered_root / record.source_stem / f"{record.task_id}.png"
        crop_path = crop_root / record.source_stem / f"{record.task_id}_title_block_crop.png"
        meta: dict[str, Any] = {
            "task_id": record.task_id,
            "source_pdf": as_posix(record.source_pdf),
            "page_number": record.page_number,
            "corrected_pdf_path": as_posix(corrected_pdf_path),
            "corrected_rendered_png_path": as_posix(rendered_path),
            "title_block_crop_path": as_posix(crop_path),
            "rotation_output_status": output.get("output_status", ""),
        }
        if output.get("output_status") != "corrected":
            meta["crop_status"] = "skipped_rotation_not_corrected"
            crop_meta_rows.append(meta)
            continue
        if not corrected_pdf_path.exists():
            meta["crop_status"] = "skipped_missing_corrected_pdf"
            crop_meta_rows.append(meta)
            continue
        render_pdf_page(corrected_pdf_path, rendered_path, render_dpi, log_root / record.source_stem / f"{record.task_id}.log")
        crop_meta = crop_title_block_candidate(rendered_path, crop_path)
        meta.update(crop_meta)
        meta["crop_status"] = "ok"
        crop_meta_rows.append(meta)
        crop_records.append(
            ImageRecord(
                source_pdf=record.source_pdf,
                source_stem=record.source_stem,
                page_number=record.page_number,
                task_id=record.task_id,
                image_path=crop_path,
            )
        )
    return crop_records, crop_meta_rows


def call_vlm_for_records(
    records: list[ImageRecord],
    model: str,
    env_file: Path,
    work_dir: Path,
    prompt: str,
    request_kind: str,
    timeout_seconds: int,
    retries: int,
    retry_sleep_seconds: float,
    dry_run: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    env_summary = load_env(env_file)
    raw_rows: list[dict[str, Any]] = []
    request_rows: list[dict[str, Any]] = []
    if dry_run:
        for record in records:
            request_rows.append(redacted_request_row(record, model, prompt, request_kind))
            raw_rows.append(
                {
                    "task_id": record.task_id,
                    "source_pdf": as_posix(record.source_pdf),
                    "page_number": record.page_number,
                    "model": model,
                    "request_kind": request_kind,
                    "ok": False,
                    "http_status": "",
                    "attempt_count": 0,
                    "response_json": None,
                    "response_text": "",
                    "error_type": "dry_run",
                    "error_message": "VLM call skipped by --dry-run.",
                }
            )
        return raw_rows, request_rows, env_summary

    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    base_url = os.environ.get("DASHSCOPE_BASE_URL", "")
    if not api_key:
        raise RuntimeError("Missing DASHSCOPE_API_KEY. Put it in .env/.env or process environment.")
    if not base_url:
        raise RuntimeError("Missing DASHSCOPE_BASE_URL. Put it in .env/.env or process environment.")
    endpoint = endpoint_from_base_url(base_url)
    checkpoint_path = work_dir / f"{request_kind}_raw_responses.partial.jsonl"
    if checkpoint_path.exists():
        checkpoint_path.unlink()

    total = len(records)
    for index, record in enumerate(records, start=1):
        print(
            json.dumps(
                {
                    "event": "pdf_rotation_mvp_vlm_request",
                    "request_kind": request_kind,
                    "index": index,
                    "total": total,
                    "source_pdf": record.source_pdf.name,
                    "page_number": record.page_number,
                    "model": model,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        request_rows.append(redacted_request_row(record, model, prompt, request_kind))
        image_data_url = data_url_for(record.image_path)
        request_body = build_request_body(model, image_data_url, prompt)
        try:
            response = post_chat_completion(
                endpoint,
                api_key,
                request_body,
                timeout_seconds,
                retries,
                retry_sleep_seconds,
            )
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
        raw_row = {
            "task_id": record.task_id,
            "source_pdf": as_posix(record.source_pdf),
            "page_number": record.page_number,
            "model": model,
            "request_kind": request_kind,
            "endpoint": endpoint,
            **response,
        }
        raw_rows.append(raw_row)
        with checkpoint_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(public_raw_row(raw_row), ensure_ascii=False) + "\n")
    return raw_rows, request_rows, env_summary


def redacted_request_row(record: ImageRecord, model: str, prompt: str, request_kind: str) -> dict[str, Any]:
    return {
        "custom_id": f"{request_kind}__{model}__{record.task_id}",
        "method": "POST",
        "url": "/chat/completions",
        "request_kind": request_kind,
        "body": {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"<omitted_png_data_url:{as_posix(record.image_path)}>"}},
                    ],
                }
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "enable_thinking": False,
        },
    }


def public_raw_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_version": RECORD_VERSION,
        "task_id": row["task_id"],
        "source_pdf": row["source_pdf"],
        "page_number": row["page_number"],
        "model": row["model"],
        "request_kind": row.get("request_kind", ""),
        "endpoint": row.get("endpoint"),
        "ok": row.get("ok"),
        "http_status": row.get("http_status"),
        "attempt_count": row.get("attempt_count"),
        "error_type": row.get("error_type", ""),
        "error_message": row.get("error_message", ""),
        "response_json": row.get("response_json"),
        "response_text": row.get("response_text") if row.get("response_json") is None else "",
    }


def rotate_or_copy_pdf(record: PageRecord, decision: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    correction = decision.get("correction_clockwise_degrees")
    blockers: list[str] = []
    if dry_run:
        blockers.append("dry_run")
    if decision.get("api_ok") is not True:
        blockers.append("api_not_ok")
    if decision.get("parse_status") != "ok":
        blockers.append("parse_not_ok")
    if decision.get("schema_status") != "ok":
        blockers.append("schema_not_ok")
    if correction not in {0, 90, 180, 270}:
        blockers.append("missing_or_invalid_correction_degrees")

    record.output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    original_rotate: int | None = None
    output_status = "corrected"
    applied_rotation = correction

    if blockers:
        shutil.copy2(record.split_pdf_path, record.output_pdf_path)
        output_status = "copied_needs_review"
        applied_rotation = 0
        try:
            original_rotate = int(PdfReader(str(record.split_pdf_path)).pages[0].get("/Rotate", 0) or 0)
        except Exception:
            original_rotate = None
    else:
        reader = PdfReader(str(record.split_pdf_path))
        page = reader.pages[0]
        original_rotate = int(page.get("/Rotate", 0) or 0)
        if correction:
            page.rotate(int(correction))
        writer = PdfWriter()
        writer.add_page(page)
        with record.output_pdf_path.open("wb") as handle:
            writer.write(handle)

    return {
        "task_id": record.task_id,
        "source_pdf": as_posix(record.source_pdf),
        "page_number": record.page_number,
        "split_pdf_path": as_posix(record.split_pdf_path),
        "rendered_png_path": as_posix(record.rendered_png_path),
        "output_pdf_path": as_posix(record.output_pdf_path),
        "output_status": output_status,
        "original_pdf_rotate": original_rotate,
        "applied_pdf_rotate_clockwise": applied_rotation,
        "needs_review": output_status != "corrected",
        "output_blockers": blockers,
    }


def publish_final_pdfs(
    records: list[PageRecord],
    rotation_decisions: list[dict[str, Any]],
    rotation_outputs: list[dict[str, Any]],
    drawing_number_decisions: list[dict[str, Any]],
    output_dir: Path,
    dry_run: bool,
) -> list[dict[str, Any]]:
    rotation_decision_by_task = {row["task_id"]: row for row in rotation_decisions}
    rotation_output_by_task = {row["task_id"]: row for row in rotation_outputs}
    drawing_by_task = {row["task_id"]: row for row in drawing_number_decisions}
    filename_counts = Counter(
        (Path(str(row.get("source_pdf") or "")).stem, row.get("final_filename_stem", ""))
        for row in drawing_number_decisions
        if row.get("final_filename_stem")
    )
    final_rows: list[dict[str, Any]] = []
    for record in records:
        rotation_decision = rotation_decision_by_task.get(record.task_id, {})
        rotation_output = rotation_output_by_task.get(record.task_id, {})
        drawing = drawing_by_task.get(record.task_id, {})
        final_blockers: list[str] = []
        if dry_run:
            final_blockers.append("dry_run")
        if rotation_output.get("output_status") != "corrected":
            final_blockers.append("rotation_output_not_corrected")
        if rotation_decision.get("needs_review") is True:
            final_blockers.append("rotation_decision_needs_review")
        if not drawing:
            final_blockers.append("missing_drawing_number_decision")
        else:
            if drawing.get("api_ok") is not True:
                final_blockers.append("drawing_number_api_not_ok")
            if drawing.get("parse_status") != "ok":
                final_blockers.append("drawing_number_parse_not_ok")
            if drawing.get("schema_status") != "ok":
                final_blockers.append("drawing_number_schema_not_ok")
            if drawing.get("needs_review") is True:
                final_blockers.append("drawing_number_decision_needs_review")
        filename_stem = drawing.get("final_filename_stem", "") if drawing else ""
        if not filename_stem:
            final_blockers.append("missing_final_filename_stem")
        elif filename_counts[(record.source_pdf.stem, filename_stem)] > 1:
            final_blockers.append("duplicate_drawing_number")

        source_pdf_path = record.output_pdf_path
        if not source_pdf_path.exists():
            final_blockers.append("missing_corrected_pdf")
        if final_blockers:
            target_path = output_dir / record.source_stem / "needs_review" / f"{record.task_id}.pdf"
            final_status = "needs_review"
        else:
            target_path = output_dir / record.source_stem / f"{filename_stem}.pdf"
            final_status = "published"

        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source_pdf_path.exists():
            shutil.copy2(source_pdf_path, target_path)

        final_rows.append(
            {
                "task_id": record.task_id,
                "source_pdf": as_posix(record.source_pdf),
                "page_number": record.page_number,
                "drawing_number": drawing.get("selected_drawing_number", "") if drawing else "",
                "final_filename_stem": filename_stem,
                "final_pdf_path": as_posix(target_path),
                "corrected_pdf_path": as_posix(source_pdf_path),
                "final_status": final_status,
                "needs_review": final_status != "published",
                "final_blockers": sorted(dict.fromkeys(final_blockers)),
            }
        )
    return final_rows


def build_report_rows(
    records: list[PageRecord],
    decisions: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
    drawing_decisions: list[dict[str, Any]],
    final_outputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    decision_by_task = {row["task_id"]: row for row in decisions}
    output_by_task = {row["task_id"]: row for row in outputs}
    drawing_by_task = {row["task_id"]: row for row in drawing_decisions}
    final_by_task = {row["task_id"]: row for row in final_outputs}
    rows: list[dict[str, Any]] = []
    for record in records:
        decision = decision_by_task.get(record.task_id, {})
        output = output_by_task.get(record.task_id, {})
        drawing = drawing_by_task.get(record.task_id, {})
        final = final_by_task.get(record.task_id, {})
        rows.append(
            {
                "source_pdf": as_posix(record.source_pdf),
                "page_number": record.page_number,
                "final_pdf_path": final.get("final_pdf_path", ""),
                "final_status": final.get("final_status", ""),
                "drawing_number": drawing.get("selected_drawing_number", ""),
                "final_filename_stem": final.get("final_filename_stem", ""),
                "corrected_pdf_path": output.get("output_pdf_path", ""),
                "output_status": output.get("output_status", ""),
                "title_block_position": decision.get("title_block_position", ""),
                "current_clockwise_degrees": decision.get("current_clockwise_degrees", ""),
                "correction_clockwise_degrees": decision.get("correction_clockwise_degrees", ""),
                "confidence": decision.get("confidence", ""),
                "api_ok": decision.get("api_ok", ""),
                "parse_status": decision.get("parse_status", ""),
                "schema_status": decision.get("schema_status", ""),
                "drawing_number_api_ok": drawing.get("api_ok", ""),
                "drawing_number_parse_status": drawing.get("parse_status", ""),
                "drawing_number_schema_status": drawing.get("schema_status", ""),
                "drawing_number_confidence": drawing.get("confidence", ""),
                "needs_review": final.get("needs_review", ""),
                "review_reasons": ";".join(decision.get("review_reasons") or []),
                "drawing_number_review_reasons": ";".join(drawing.get("review_reasons") or []),
                "output_blockers": ";".join(output.get("output_blockers") or []),
                "final_blockers": ";".join(final.get("final_blockers") or []),
            }
        )
    return rows


def run(args: argparse.Namespace) -> dict[str, Any]:
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    work_dir = args.work_dir.resolve()
    ensure_child_dir(output_dir, SCRIPT_DIR)
    ensure_child_dir(work_dir, SCRIPT_DIR)

    pdfs = collect_input_pdfs(input_dir)
    for pdf_path in pdfs:
        safe_reset_child_dir(output_dir / safe_name(pdf_path.stem), output_dir)
    safe_reset_child_dir(work_dir, SCRIPT_DIR)
    (work_dir / "orientation_prompt.md").write_text(TITLE_BLOCK_ONLY_PROMPT, encoding="utf-8")
    (work_dir / "drawing_number_prompt.md").write_text(DRAWING_NUMBER_PROMPT, encoding="utf-8")

    records = split_and_render_pdfs(pdfs, work_dir, output_dir, args.render_dpi, args.limit_pages)
    orientation_image_records = image_records_from_pages(records)
    raw_rows, request_rows, env_summary = call_vlm_for_records(
        orientation_image_records,
        args.model,
        args.env_file.resolve(),
        work_dir,
        TITLE_BLOCK_ONLY_PROMPT,
        "orientation",
        args.timeout_seconds,
        args.retries,
        args.retry_sleep_seconds,
        args.dry_run,
    )
    decisions = [build_decision(row) for row in raw_rows]
    if not args.dry_run and records and sum(1 for row in decisions if row.get("api_ok")) == 0:
        raise RuntimeError("All VLM requests failed. Refusing to produce a successful-looking MVP output.")

    outputs = [rotate_or_copy_pdf(record, decision, args.dry_run) for record, decision in zip(records, decisions, strict=True)]
    crop_records, crop_meta_rows = build_corrected_crop_records(records, outputs, work_dir, args.render_dpi)
    drawing_raw_rows, drawing_request_rows, _ = call_vlm_for_records(
        crop_records,
        args.model,
        args.env_file.resolve(),
        work_dir,
        DRAWING_NUMBER_PROMPT,
        "drawing_number",
        args.timeout_seconds,
        args.retries,
        args.retry_sleep_seconds,
        args.dry_run,
    )
    drawing_decisions = [build_drawing_number_decision(row) for row in drawing_raw_rows]
    final_outputs = publish_final_pdfs(records, decisions, outputs, drawing_decisions, output_dir, args.dry_run)
    report_rows = build_report_rows(records, decisions, outputs, drawing_decisions, final_outputs)
    needs_review_rows = [row for row in report_rows if str(row.get("needs_review")).lower() == "true"]

    write_jsonl(work_dir / "orientation_requests.jsonl", request_rows)
    write_jsonl(work_dir / "orientation_raw_responses.jsonl", [public_raw_row(row) for row in raw_rows])
    write_jsonl(work_dir / "orientation_decisions.jsonl", decisions)
    write_jsonl(work_dir / "title_block_crop_records.jsonl", crop_meta_rows)
    write_jsonl(work_dir / "drawing_number_requests.jsonl", drawing_request_rows)
    write_jsonl(work_dir / "drawing_number_raw_responses.jsonl", [public_raw_row(row) for row in drawing_raw_rows])
    write_jsonl(work_dir / "drawing_number_decisions.jsonl", drawing_decisions)
    write_jsonl(work_dir / "rotation_output_records.jsonl", outputs)
    write_jsonl(work_dir / "final_output_records.jsonl", final_outputs)
    write_csv(output_dir / "report.csv", report_rows, list(report_rows[0].keys()) if report_rows else [])
    write_csv(output_dir / "needs_review.csv", needs_review_rows, list(report_rows[0].keys()) if report_rows else [])

    summary = {
        "record_version": RECORD_VERSION,
        "input_dir": as_posix(input_dir),
        "output_dir": as_posix(output_dir),
        "work_dir": as_posix(work_dir),
        "model": args.model,
        "temperature": 0,
        "enable_thinking": False,
        "top_p": "not_set",
        "dry_run": bool(args.dry_run),
        "source_pdf_count": len(pdfs),
        "page_count": len(records),
        "orientation_api_ok_count": sum(1 for row in decisions if row.get("api_ok")),
        "orientation_parse_ok_count": sum(1 for row in decisions if row.get("parse_status") == "ok"),
        "orientation_schema_ok_count": sum(1 for row in decisions if row.get("schema_status") == "ok"),
        "drawing_number_api_ok_count": sum(1 for row in drawing_decisions if row.get("api_ok")),
        "drawing_number_parse_ok_count": sum(1 for row in drawing_decisions if row.get("parse_status") == "ok"),
        "drawing_number_schema_ok_count": sum(1 for row in drawing_decisions if row.get("schema_status") == "ok"),
        "drawing_number_non_empty_count": sum(1 for row in drawing_decisions if row.get("selected_drawing_number")),
        "corrected_count": sum(1 for row in outputs if row.get("output_status") == "corrected"),
        "copied_needs_review_count": sum(1 for row in outputs if row.get("output_status") == "copied_needs_review"),
        "published_count": sum(1 for row in final_outputs if row.get("final_status") == "published"),
        "final_needs_review_count": sum(1 for row in final_outputs if row.get("final_status") != "published"),
        "env_status": env_summary,
        "outputs": {
            "report_csv": as_posix(output_dir / "report.csv"),
            "needs_review_csv": as_posix(output_dir / "needs_review.csv"),
            "summary_json": as_posix(output_dir / "summary.json"),
            "orientation_raw_responses_jsonl": as_posix(work_dir / "orientation_raw_responses.jsonl"),
            "orientation_decisions_jsonl": as_posix(work_dir / "orientation_decisions.jsonl"),
            "drawing_number_raw_responses_jsonl": as_posix(work_dir / "drawing_number_raw_responses.jsonl"),
            "drawing_number_decisions_jsonl": as_posix(work_dir / "drawing_number_decisions.jsonl"),
            "rotation_output_records_jsonl": as_posix(work_dir / "rotation_output_records.jsonl"),
            "final_output_records_jsonl": as_posix(work_dir / "final_output_records.jsonl"),
        },
    }
    write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MVP: split PDFs, detect drawing rotation by VLM, and output corrected single-page PDFs.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--render-dpi", type=int, default=150)
    parser.add_argument("--limit-pages", type=int, default=None)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--retry-sleep-seconds", type=float, default=3.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
