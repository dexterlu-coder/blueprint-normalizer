from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import time
import traceback
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from scripts.common.obb_utils import ROOT, resolve_path
from scripts.experiments.build_vlm_title_block_blind_review import (
    archive_current_inbox,
    rel_path,
    render_pdf_pages,
    split_pdf,
    write_csv,
    write_xlsx,
)
from scripts.vlm.build_aliyun_vlm_mvp_requests import data_url_for, write_json, write_jsonl
from scripts.vlm.run_aliyun_vlm_mvp_smoke import endpoint_from_base_url, load_env, post_chat_completion


DEFAULT_SOURCE_DIR = ROOT / "local_data" / "source_pdfs"
DEFAULT_SPLIT_ROOT = ROOT / "local_data" / "split_source_pdfs"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "vlm_js2207_full_rotation_test"
DEFAULT_REVIEW_INBOX = ROOT / "local_data" / "review_inbox" / "current"
DEFAULT_ENV_FILE = ROOT / ".env" / ".env"
DEFAULT_REVIEW_SLUG = "js2207_vlm_full_rotation_review"
DEFAULT_REVIEW_TITLE = "JS2207 VLM 双模型全量方向审核"
RECORD_VERSION = "pdf-split-js2207-vlm-full-rotation-v0.1"

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

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["title_block_position", "confidence", "evidence", "needs_human_review", "review_reasons"],
    "properties": {
        "title_block_position": {
            "enum": [
                "bottom_edge",
                "top_edge",
                "left_edge",
                "right_edge",
                "bottom_right",
                "bottom_left",
                "top_right",
                "top_left",
                "no_title_block",
                "unknown",
            ]
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "needs_human_review": {"type": "boolean"},
        "review_reasons": {"type": "array", "items": {"type": "string"}},
    },
}

POSITION_LABELS = {
    "bottom_edge": "下方",
    "top_edge": "上方",
    "left_edge": "左侧",
    "right_edge": "右侧",
    "bottom_right": "右下方",
    "bottom_left": "左下方",
    "top_right": "右上方",
    "top_left": "左上方",
    "no_title_block": "无标题栏",
    "unknown": "未知",
}

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


@dataclass(frozen=True)
class SourcePdfSpec:
    source_pdf: Path
    slug: str
    sample_prefix: str
    display_name: str


@dataclass(frozen=True)
class ModelVariant:
    variant_id: str
    display_name: str
    model_id: str
    temperature: int = 0
    enable_thinking: bool = False

    def request_extra_body(self) -> dict[str, Any]:
        return {"enable_thinking": self.enable_thinking}


SOURCE_SPECS = [
    SourcePdfSpec(
        source_pdf=DEFAULT_SOURCE_DIR / "JS2207-00-00升降平台.pdf",
        slug="js2207_lifting_platform",
        sample_prefix="js2207_page",
        display_name="JS2207-00-00升降平台",
    ),
    SourcePdfSpec(
        source_pdf=DEFAULT_SOURCE_DIR / "YKJ125-00-00-2525铁屑压块机生产图（250911章）解密.pdf",
        slug="ykj125_briquetting_machine",
        sample_prefix="ykj125_page",
        display_name="YKJ125-00-00-2525铁屑压块机生产图",
    ),
]

MODEL_VARIANTS = [
    ModelVariant(
        variant_id="qwen3_7_plus_non_thinking",
        display_name="qwen3.7-plus / 非思考",
        model_id="qwen3.7-plus",
    ),
    ModelVariant(
        variant_id="qwen3_7_max_2026_06_08_non_thinking",
        display_name="qwen3.7-max-2026-06-08 / 非思考",
        model_id="qwen3.7-max-2026-06-08",
    ),
]


Image.MAX_IMAGE_PIXELS = None


def as_posix(path: Path | str | None) -> str | None:
    if path is None:
        return None
    path_obj = Path(path)
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def image_meta(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        width, height = image.size
    data_url_bytes = len(data_url_for(path, mime_type="image/png").encode("utf-8"))
    return {
        "input_image_path": as_posix(path),
        "input_image_format": "png",
        "original_width": width,
        "original_height": height,
        "prepared_width": width,
        "prepared_height": height,
        "bytes": path.stat().st_size,
        "data_url_bytes": data_url_bytes,
        "no_resize": True,
        "compressed": False,
        "image_lossless": True,
    }


def split_and_render_source_pdfs(split_root: Path, render_dpi: int) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    split_root.mkdir(parents=True, exist_ok=True)
    records_by_slug: dict[str, list[dict[str, Any]]] = {}
    summary_rows: list[dict[str, Any]] = []
    for spec in SOURCE_SPECS:
        output_dir = split_root / spec.slug
        output_dir.mkdir(parents=True, exist_ok=True)
        records = split_pdf(spec.source_pdf, output_dir, spec.sample_prefix, limit_pages=None)
        render_pdf_pages(records, output_dir, render_dpi)
        manifest_path = output_dir / "split_render_manifest.json"
        write_json(
            manifest_path,
            {
                "record_version": RECORD_VERSION,
                "source_pdf": as_posix(resolve_path(spec.source_pdf)),
                "display_name": spec.display_name,
                "slug": spec.slug,
                "render_dpi": render_dpi,
                "page_count": len(records),
                "single_page_pdf_dir": "single_page_pdfs",
                "rendered_png_dir": "rendered_png",
                "records": records,
                "modified_pdf": False,
                "renamed_pdf": False,
            },
        )
        records_by_slug[spec.slug] = records
        summary_rows.append(
            {
                "slug": spec.slug,
                "display_name": spec.display_name,
                "source_pdf": as_posix(resolve_path(spec.source_pdf)),
                "page_count": len(records),
                "output_dir": as_posix(output_dir),
                "manifest": as_posix(manifest_path),
            }
        )
    return records_by_slug, summary_rows


def build_request_rows(records: list[dict[str, Any]], variants: list[ModelVariant]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    request_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    for record in records:
        image_path = resolve_path(Path(record["rendered_image_path"]))
        meta = image_meta(image_path)
        for variant in variants:
            request_custom_id = f"{variant.variant_id}__{record['task_id']}"
            row = {
                "task_id": record["task_id"],
                "page_number": record["page_number"],
                "model": variant.display_name,
                "model_id": variant.model_id,
                "model_variant": variant.variant_id,
                "request_custom_id": request_custom_id,
                "rendered_image_path": record["rendered_image_path"],
                "temperature": variant.temperature,
                "top_p": "",
                "enable_thinking": variant.enable_thinking,
            }
            request_rows.append(row)
            manifest_rows.append(
                {
                    **record,
                    **meta,
                    "provider_mode": "aliyun_openai_compatible",
                    **row,
                }
            )
    return request_rows, manifest_rows


def redacted_request_row(request_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "custom_id": request_row["request_custom_id"],
        "method": "POST",
        "url": "/chat/completions",
        "body": {
            "model": request_row["model_id"],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": TITLE_BLOCK_ONLY_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"<omitted_png_data_url:{request_row['rendered_image_path']}>"},
                        },
                    ],
                }
            ],
            "temperature": request_row["temperature"],
            "response_format": {"type": "json_object"},
            "enable_thinking": request_row["enable_thinking"],
        },
    }


def build_request_body(variant: ModelVariant, image_data_url: str) -> dict[str, Any]:
    return {
        "model": variant.model_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": TITLE_BLOCK_ONLY_PROMPT},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        ],
        "temperature": variant.temperature,
        "response_format": {"type": "json_object"},
        **variant.request_extra_body(),
    }


def call_vlm_requests(
    request_rows: list[dict[str, Any]],
    variants_by_display_name: dict[str, ModelVariant],
    env_file: Path,
    checkpoint_path: Path,
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
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    if checkpoint_path.exists():
        checkpoint_path.unlink()
    total = len(request_rows)
    for index, request_row in enumerate(request_rows, start=1):
        print(
            json.dumps(
                {
                    "event": "js2207_full_rotation_vlm_request",
                    "index": index,
                    "total": total,
                    "page_number": request_row["page_number"],
                    "task_id": request_row["task_id"],
                    "model": request_row["model"],
                    "model_id": request_row["model_id"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        variant = variants_by_display_name[request_row["model"]]
        image_path = resolve_path(Path(request_row["rendered_image_path"]))
        image_data_url = data_url_for(image_path, mime_type="image/png")
        request_body = build_request_body(variant, image_data_url)
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
            **request_row,
            "endpoint": endpoint,
            **response,
        }
        raw_rows.append(raw_row)
        with checkpoint_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(public_raw_row(raw_row), ensure_ascii=False) + "\n")
    return raw_rows, env_summary


def public_raw_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_version": RECORD_VERSION,
        "task_id": row["task_id"],
        "page_number": row["page_number"],
        "model": row["model"],
        "model_id": row["model_id"],
        "model_variant": row["model_variant"],
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


def load_reusable_raw_rows(path: Path, request_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resolved = resolve_path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"Reusable raw response file not found: {resolved}")
    metadata_by_custom_id = {row["request_custom_id"]: row for row in request_rows}
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(resolved.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        public_row = json.loads(line)
        custom_id = public_row.get("request_custom_id")
        metadata = metadata_by_custom_id.get(custom_id)
        if metadata is None:
            raise ValueError(f"Raw response row {line_number} has unknown request_custom_id: {custom_id}")
        rows.append({**metadata, **public_row})
    return rows


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


def value_at(parsed: Any, *path: str) -> Any:
    current = parsed
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def canonical_title_block_position(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return POSITION_ALIASES.get(normalized, normalized)


def normalize_parsed_response(parsed: Any) -> dict[str, Any]:
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
    normalized = normalize_parsed_response(parsed)
    if not normalized:
        return ["decision_not_object"]
    errors: list[str] = []
    position = canonical_title_block_position(normalized.get("title_block_position"))
    if position not in RESPONSE_SCHEMA["properties"]["title_block_position"]["enum"]:
        errors.append("invalid_title_block_position")
    confidence = normalized.get("confidence")
    if not isinstance(confidence, int | float) or isinstance(confidence, bool) or not 0 <= float(confidence) <= 1:
        errors.append("invalid_confidence")
    if not isinstance(normalized.get("evidence"), list):
        errors.append("evidence_not_list")
    needs_review = normalized.get("needs_human_review")
    if not isinstance(needs_review, bool):
        errors.append("needs_human_review_not_bool")
    reasons = normalized.get("review_reasons")
    if not isinstance(reasons, list):
        errors.append("review_reasons_not_list")
    return errors


def derive_rotation_from_position(position: Any) -> tuple[int | None, int | None, list[str]]:
    canonical = canonical_title_block_position(position)
    if canonical is None:
        return None, None, ["missing_title_block_position_for_rotation"]
    current, correction = POSITION_TO_ROTATION.get(canonical, (None, None))
    if current is None or correction is None:
        return None, None, ["unknown_title_block_position_for_rotation"]
    return current, correction, []


def build_decision_row(raw_row: dict[str, Any]) -> dict[str, Any]:
    content, content_errors = extract_message_content(raw_row.get("response_json"))
    parsed, parse_errors = parse_json_content(content) if not content_errors else (None, [])
    normalized = normalize_parsed_response(parsed)
    schema_errors = validate_decision(parsed) if parsed is not None else []
    position = canonical_title_block_position(normalized.get("title_block_position"))
    derived_current, derived_correction, rotation_errors = derive_rotation_from_position(position)

    review_reasons: list[str] = []
    if not raw_row.get("ok"):
        review_reasons.append(f"api_error:{raw_row.get('error_type') or raw_row.get('http_status')}")
    review_reasons.extend(content_errors)
    review_reasons.extend(parse_errors)
    review_reasons.extend(schema_errors)
    review_reasons.extend(rotation_errors)
    if normalized.get("needs_human_review") is True:
        review_reasons.append("model_marked_needs_human_review")
    model_reasons = normalized.get("review_reasons")
    if isinstance(model_reasons, list):
        for reason in model_reasons:
            if isinstance(reason, str) and reason:
                review_reasons.append(f"model:{reason}")

    return {
        "record_version": RECORD_VERSION,
        "task_id": raw_row["task_id"],
        "page_number": raw_row["page_number"],
        "model": raw_row["model"],
        "model_id": raw_row["model_id"],
        "model_variant": raw_row["model_variant"],
        "request_custom_id": raw_row["request_custom_id"],
        "temperature": raw_row["temperature"],
        "top_p": "",
        "enable_thinking": raw_row["enable_thinking"],
        "http_status": raw_row.get("http_status"),
        "api_ok": bool(raw_row.get("ok")),
        "attempt_count": raw_row.get("attempt_count"),
        "parse_status": "ok" if parsed is not None and not content_errors and not parse_errors else "error",
        "schema_status": "ok" if parsed is not None and not schema_errors else "error",
        "title_block_position": position,
        "title_block_position_label": POSITION_LABELS.get(position or "", position or ""),
        "derived_current_clockwise_degrees": derived_current,
        "derived_correction_clockwise_degrees": derived_correction,
        "orientation_confidence": normalized.get("confidence"),
        "model_needs_human_review": normalized.get("needs_human_review") if isinstance(normalized.get("needs_human_review"), bool) else "",
        "needs_review": bool(review_reasons),
        "review_reasons": sorted(dict.fromkeys(review_reasons)),
        "evidence": normalized.get("evidence") if isinstance(normalized.get("evidence"), list) else [],
        "error_type": raw_row.get("error_type", ""),
        "error_message": raw_row.get("error_message", ""),
        "parsed_response": parsed if isinstance(parsed, dict) else {},
    }


def decision_by_task_model(decisions: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(row["task_id"], row["model"]): row for row in decisions}


def build_review_rows(
    records: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    variants: list[ModelVariant],
) -> list[dict[str, Any]]:
    by_key = decision_by_task_model(decisions)
    rows: list[dict[str, Any]] = []
    for record in records:
        for variant in variants:
            decision = by_key.get((record["task_id"], variant.display_name), {})
            rows.append(
                {
                    "页码": record["page_number"],
                    "模型": variant.display_name,
                    "模型派生当前旋转角度": decision.get("derived_current_clockwise_degrees", ""),
                    "旋转角度是否正确": "",
                    "正确旋转角度": "",
                    "备注": "",
                }
            )
    return rows


def build_model_comparison(records: list[dict[str, Any]], decisions: list[dict[str, Any]], variants: list[ModelVariant]) -> list[dict[str, Any]]:
    by_key = decision_by_task_model(decisions)
    comparisons: list[dict[str, Any]] = []
    for record in records:
        rows = [by_key.get((record["task_id"], variant.display_name), {}) for variant in variants]
        reasons: list[str] = []
        rotations = [row.get("derived_current_clockwise_degrees") for row in rows if row]
        positions = [row.get("title_block_position") for row in rows if row]
        if len(rows) != len([row for row in rows if row]):
            reasons.append("missing_model_result")
        if any(row.get("needs_review") for row in rows if row):
            reasons.append("one_or_more_model_results_need_review")
        if len(set(rotations)) > 1:
            reasons.append("rotation_conflict")
        if len(set(positions)) > 1:
            reasons.append("title_block_position_conflict")
        comparisons.append(
            {
                "record_version": RECORD_VERSION,
                "task_id": record["task_id"],
                "page_number": record["page_number"],
                "models": [variant.display_name for variant in variants],
                "title_block_position_by_model": {
                    variant.display_name: by_key.get((record["task_id"], variant.display_name), {}).get("title_block_position")
                    for variant in variants
                },
                "derived_current_clockwise_degrees_by_model": {
                    variant.display_name: by_key.get((record["task_id"], variant.display_name), {}).get(
                        "derived_current_clockwise_degrees"
                    )
                    for variant in variants
                },
                "needs_review_by_model": {
                    variant.display_name: by_key.get((record["task_id"], variant.display_name), {}).get("needs_review")
                    for variant in variants
                },
                "needs_review": bool(reasons),
                "review_reasons": sorted(dict.fromkeys(reasons)),
            }
        )
    return comparisons


def write_decisions_csv(path: Path, decisions: list[dict[str, Any]]) -> None:
    write_csv(
        path,
        [
            {
                **row,
                "review_reasons": ";".join(row.get("review_reasons") or []),
                "evidence": ";".join(row.get("evidence") or []),
                "parsed_response": json.dumps(row.get("parsed_response", {}), ensure_ascii=False),
            }
            for row in decisions
        ],
        [
            "task_id",
            "page_number",
            "model",
            "model_id",
            "model_variant",
            "temperature",
            "top_p",
            "enable_thinking",
            "http_status",
            "api_ok",
            "attempt_count",
            "parse_status",
            "schema_status",
            "title_block_position",
            "title_block_position_label",
            "derived_current_clockwise_degrees",
            "derived_correction_clockwise_degrees",
            "orientation_confidence",
            "model_needs_human_review",
            "needs_review",
            "review_reasons",
            "evidence",
            "error_type",
            "error_message",
            "parsed_response",
        ],
    )


def write_comparison_csv(path: Path, comparisons: list[dict[str, Any]]) -> None:
    write_csv(
        path,
        [
            {
                **row,
                "models": ",".join(row.get("models", [])),
                "title_block_position_by_model": json.dumps(row.get("title_block_position_by_model", {}), ensure_ascii=False),
                "derived_current_clockwise_degrees_by_model": json.dumps(
                    row.get("derived_current_clockwise_degrees_by_model", {}), ensure_ascii=False
                ),
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
            "needs_review_by_model",
            "needs_review",
            "review_reasons",
        ],
    )


def publish_review_pack(
    output_dir: Path,
    current_dir: Path,
    review_slug: str,
    review_title: str,
    records: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    variants: list[ModelVariant],
    split_summary_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    archived = archive_current_inbox(current_dir, review_slug)
    review_dir = current_dir / review_slug
    image_dir = review_dir / "images"
    review_dir.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)

    image_map: dict[str, str] = {}
    for record in records:
        source_image = resolve_path(Path(record["rendered_image_path"]))
        target_image = image_dir / source_image.name
        shutil.copy2(source_image, target_image)
        image_map[record["task_id"]] = rel_path(target_image, review_dir)

    review_fieldnames = ["页码", "模型", "模型派生当前旋转角度", "旋转角度是否正确", "正确旋转角度", "备注"]
    xlsx_path = review_dir / "js2207_vlm_full_rotation_review.xlsx"
    html_path = review_dir / "review_index.html"
    manifest_path = review_dir / "review_manifest.json"
    write_xlsx(xlsx_path, review_rows, review_fieldnames, "JS2207方向审核")

    by_key = decision_by_task_model(decisions)
    cards = []
    for record in records:
        decision_lines = []
        for variant in variants:
            decision = by_key.get((record["task_id"], variant.display_name), {})
            rotation = decision.get("derived_current_clockwise_degrees", "")
            decision_lines.append(
                "<tr>"
                f"<td>{html.escape(variant.display_name)}</td>"
                f"<td>{html.escape(str(rotation))}</td>"
                "</tr>"
            )
        cards.append(
            f"""
    <article class="page-card" id="{html.escape(record['task_id'])}">
      <div class="page-head">
        <h2>第 {record['page_number']} 页</h2>
      </div>
      <a href="{html.escape(image_map[record['task_id']])}" target="_blank">
        <img src="{html.escape(image_map[record['task_id']])}" alt="第 {record['page_number']} 页原向图纸">
      </a>
      <table>
        <thead><tr><th>模型</th><th>模型派生当前旋转角度</th></tr></thead>
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
    img {{ display: block; width: 100%; max-height: 78vh; object-fit: contain; background: #f8fafc; border: 1px solid #e2e8f0; }}
    table {{ width: 100%; margin-top: 10px; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border: 1px solid #d8dee8; padding: 7px 8px; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f6; }}
    @media (max-width: 760px) {{ main {{ padding: 10px; }} img {{ max-height: none; }} table {{ font-size: 12px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(review_title)}</h1>
    <div class="meta">
      <span>共 {len(records)} 页</span>
      <span>结果 {len(review_rows)} 行</span>
      <span>填写：js2207_vlm_full_rotation_review.xlsx</span>
      <span>图片为原向 PNG，不旋转、不 resize、不做有损压缩</span>
    </div>
  </header>
  <main>
    <section class="guide">
      <strong>审核说明：</strong>
      只核对每个模型派生的当前旋转角度是否正确。若错误，请在 Excel 中填写“旋转角度是否正确”“正确旋转角度”和备注。
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
        "task": review_slug,
        "review_title": review_title,
        "source_output_dir": as_posix(output_dir),
        "page_count": len(records),
        "model_variants": [variant.__dict__ for variant in variants],
        "archived_previous_current": archived,
        "html": rel_path(html_path, current_dir),
        "xlsx": rel_path(xlsx_path, current_dir),
        "image_count": len(image_map),
        "human_review_fields": review_fieldnames,
        "split_summary": split_summary_rows,
        "machine_review_rows": [
            {
                "page_number": decision["page_number"],
                "task_id": decision["task_id"],
                "model": decision["model"],
                "title_block_position": decision.get("title_block_position"),
                "title_block_position_label": decision.get("title_block_position_label"),
                "derived_current_clockwise_degrees": decision.get("derived_current_clockwise_degrees"),
                "needs_review": decision.get("needs_review"),
                "review_reasons": decision.get("review_reasons"),
            }
            for decision in decisions
        ],
        "comparisons": comparisons,
        "modified_pdf": False,
        "renamed_pdf": False,
        "network_call_executed": True,
    }
    write_json(manifest_path, review_manifest)
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
                f"- `{review_slug}/js2207_vlm_full_rotation_review.xlsx`",
                "",
                "本轮只审核 JS2207 全部图纸的派生当前旋转角度。",
                "图片为原向 PNG，不旋转、不 resize、不做有损压缩。",
                "",
                "请在 Excel 中填写 `旋转角度是否正确`，必要时填写 `正确旋转角度` 和 `备注`。",
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
        "review_manifest": as_posix(manifest_path),
        "image_count": len(image_map),
        "archived_previous_current": archived,
    }


def summarize_decisions(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: dict[str, dict[str, Any]] = {}
    for model in sorted({row["model"] for row in decisions}):
        rows = [row for row in decisions if row["model"] == model]
        by_model[model] = {
            "decision_count": len(rows),
            "api_ok_count": sum(1 for row in rows if row.get("api_ok")),
            "parse_ok_count": sum(1 for row in rows if row.get("parse_status") == "ok"),
            "schema_ok_count": sum(1 for row in rows if row.get("schema_status") == "ok"),
            "needs_review_count": sum(1 for row in rows if row.get("needs_review")),
            "rotation_distribution": dict(Counter(str(row.get("derived_current_clockwise_degrees", "")) for row in rows)),
            "position_distribution": dict(Counter(row.get("title_block_position") or "" for row in rows)),
        }
    return by_model


def run(args: argparse.Namespace) -> dict[str, Any]:
    split_root = resolve_path(args.split_root)
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records_by_slug, split_summary_rows = split_and_render_source_pdfs(split_root, args.render_dpi)
    records = records_by_slug["js2207_lifting_platform"]
    variants = MODEL_VARIANTS
    variants_by_display_name = {variant.display_name: variant for variant in variants}
    request_rows, manifest_rows = build_request_rows(records, variants)

    prompt_path = output_dir / "title_block_only_prompt.md"
    schema_path = output_dir / "title_block_only_response_schema.json"
    split_summary_path = output_dir / "split_source_pdfs_summary.json"
    requests_path = output_dir / "vlm_js2207_full_rotation_requests.jsonl"
    manifest_path = output_dir / "vlm_js2207_full_rotation_manifest.json"
    manifest_csv_path = output_dir / "vlm_js2207_full_rotation_manifest.csv"
    raw_path = output_dir / "vlm_raw_responses.jsonl"
    raw_checkpoint_path = output_dir / "vlm_raw_responses.partial.jsonl"
    decisions_path = output_dir / "vlm_decisions.jsonl"
    decisions_csv_path = output_dir / "vlm_decisions.csv"
    comparison_path = output_dir / "model_rotation_comparison.json"
    comparison_csv_path = output_dir / "model_rotation_comparison.csv"
    summary_path = output_dir / "run_summary.json"

    prompt_path.write_text(TITLE_BLOCK_ONLY_PROMPT, encoding="utf-8")
    write_json(schema_path, RESPONSE_SCHEMA)
    write_json(split_summary_path, {"record_version": RECORD_VERSION, "sources": split_summary_rows})
    write_jsonl(requests_path, [redacted_request_row(row) for row in request_rows])
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
            "input_image_format",
            "original_width",
            "original_height",
            "prepared_width",
            "prepared_height",
            "bytes",
            "data_url_bytes",
            "model",
            "model_id",
            "model_variant",
            "temperature",
            "top_p",
            "enable_thinking",
            "compressed",
            "no_resize",
            "image_lossless",
        ],
    )

    if args.reuse_raw_responses:
        raw_rows = load_reusable_raw_rows(args.reuse_raw_responses, request_rows)
        env_summary = load_env(args.env_file)
    else:
        raw_rows, env_summary = call_vlm_requests(
            request_rows,
            variants_by_display_name,
            args.env_file,
            raw_checkpoint_path,
            args.timeout_seconds,
            args.retries,
            args.retry_sleep_seconds,
        )

    decisions = [build_decision_row(row) for row in raw_rows]
    api_ok_count = sum(1 for row in decisions if row.get("api_ok"))
    if not args.reuse_raw_responses and request_rows and api_ok_count == 0:
        raise RuntimeError(
            "All VLM requests failed before review publishing. "
            "Check network permissions and rerun; no user review pack was published for this run."
        )

    comparisons = build_model_comparison(records, decisions, variants)
    review_rows = build_review_rows(records, decisions, variants)

    write_jsonl(raw_path, [public_raw_row(row) for row in raw_rows])
    write_jsonl(decisions_path, decisions)
    write_decisions_csv(decisions_csv_path, decisions)
    write_json(comparison_path, comparisons)
    write_comparison_csv(comparison_csv_path, comparisons)

    review_summary = {}
    if not args.skip_review_publish:
        review_summary = publish_review_pack(
            output_dir,
            resolve_path(args.review_inbox),
            args.review_slug,
            args.review_title,
            records,
            decisions,
            comparisons,
            review_rows,
            variants,
            split_summary_rows,
        )

    summary = {
        "record_version": RECORD_VERSION,
        "split_root": as_posix(split_root),
        "output_dir": as_posix(output_dir),
        "split_summary": split_summary_rows,
        "js2207_page_count": len(records),
        "model_variant_count": len(variants),
        "request_count": len(request_rows),
        "raw_response_count": len(raw_rows),
        "decision_count": len(decisions),
        "api_ok_count": api_ok_count,
        "parse_ok_count": sum(1 for row in decisions if row.get("parse_status") == "ok"),
        "schema_ok_count": sum(1 for row in decisions if row.get("schema_status") == "ok"),
        "decision_needs_review_count": sum(1 for row in decisions if row.get("needs_review")),
        "comparison_count": len(comparisons),
        "comparison_needs_review_count": sum(1 for row in comparisons if row.get("needs_review")),
        "decision_summary_by_model": summarize_decisions(decisions),
        "render_dpi": args.render_dpi,
        "image_format": "png",
        "compressed": False,
        "no_resize": True,
        "image_lossless": True,
        "temperature": 0,
        "top_p": "not_set",
        "enable_thinking": False,
        "modified_pdf": False,
        "renamed_pdf": False,
        "network_call_executed": not bool(args.reuse_raw_responses),
        "env_status": env_summary,
        "outputs": {
            "prompt": as_posix(prompt_path),
            "schema": as_posix(schema_path),
            "split_summary": as_posix(split_summary_path),
            "requests": as_posix(requests_path),
            "manifest": as_posix(manifest_path),
            "manifest_csv": as_posix(manifest_csv_path),
            "raw_responses": as_posix(raw_path),
            "raw_responses_partial": as_posix(raw_checkpoint_path),
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
    parser = argparse.ArgumentParser(description="Split source PDFs and build JS2207 full VLM rotation review pack.")
    parser.add_argument("--split-root", type=Path, default=DEFAULT_SPLIT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--review-inbox", type=Path, default=DEFAULT_REVIEW_INBOX)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--review-slug", default=DEFAULT_REVIEW_SLUG)
    parser.add_argument("--review-title", default=DEFAULT_REVIEW_TITLE)
    parser.add_argument("--render-dpi", type=int, default=150)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--retry-sleep-seconds", type=float, default=3.0)
    parser.add_argument("--skip-review-publish", action="store_true")
    parser.add_argument("--reuse-raw-responses", type=Path, default=None)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
