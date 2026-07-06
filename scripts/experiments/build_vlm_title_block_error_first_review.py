from __future__ import annotations

import argparse
import csv
import html
import json
import os
import shutil
import traceback
import time
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from PIL import Image

from scripts.common.obb_utils import ROOT, resolve_path
from scripts.experiments.build_vlm_title_block_blind_review import (
    POSITION_LABELS,
    archive_current_inbox,
    rel_path,
    safe_reset_child_dir,
    write_csv,
    write_xlsx,
)
from scripts.vlm.build_aliyun_vlm_mvp_requests import (
    PROMPT,
    RESPONSE_SCHEMA,
    data_url_for,
    write_json,
    write_jsonl,
)
from scripts.vlm.run_aliyun_vlm_mvp_smoke import (
    build_decision_row,
    compare_decisions,
    endpoint_from_base_url,
    load_env,
    post_chat_completion,
)


DEFAULT_PREVIOUS_REVIEW_XLSX = (
    ROOT
    / "local_data"
    / "review_inbox"
    / "current"
    / "ykj125_vlm_title_block_blind_review"
    / "vlm_title_block_blind_review.xlsx"
)
DEFAULT_PREVIOUS_OUTPUT_DIR = ROOT / "local_data" / "vlm_title_block_generalization_blind_ykj125"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "vlm_title_block_error_first_ykj125"
DEFAULT_REVIEW_INBOX = ROOT / "local_data" / "review_inbox" / "current"
DEFAULT_ENV_FILE = ROOT / ".env" / ".env"
DEFAULT_REVIEW_SLUG = "ykj125_vlm_title_block_error_first_review"
DEFAULT_REVIEW_TITLE = "YKJ125 VLM 标题栏错题集优先模型审核"
DEFAULT_PRIMARY_MODEL = "qwen3-vl-plus"
DEFAULT_MAX_PAGES = 20
RECORD_VERSION = "vlm-title-block-error-first-review-v0.1"

XLSX_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
POSITION_TO_ROTATION_GROUP: dict[str, int] = {
    "bottom_edge": 0,
    "bottom_right": 0,
    "bottom": 0,
    "bottom_left": 90,
    "left_edge": 90,
    "left": 90,
    "top_left": 180,
    "top_edge": 180,
    "top": 180,
    "top_right": 270,
    "right_edge": 270,
    "right": 270,
}
POSITION_LABEL_TO_CODE = {value: key for key, value in POSITION_LABELS.items()}


@dataclass(frozen=True)
class ModelVariant:
    variant_id: str
    display_name: str
    model: str
    enable_thinking: bool
    thinking_budget: int | None = None
    temperature: int = 0

    def extra_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {"enable_thinking": self.enable_thinking}
        if self.thinking_budget is not None:
            body["thinking_budget"] = self.thinking_budget
        return body


MODEL_VARIANTS = [
    ModelVariant(
        variant_id="qwen3_vl_plus_non_thinking",
        display_name="qwen3-vl-plus / 非思考",
        model="qwen3-vl-plus",
        enable_thinking=False,
    ),
    ModelVariant(
        variant_id="qwen3_vl_plus_thinking_512",
        display_name="qwen3-vl-plus / thinking_budget=512",
        model="qwen3-vl-plus",
        enable_thinking=True,
        thinking_budget=512,
    ),
    ModelVariant(
        variant_id="qwen3_7_plus_non_thinking",
        display_name="qwen3.7-plus / 非思考",
        model="qwen3.7-plus",
        enable_thinking=False,
    ),
    ModelVariant(
        variant_id="qwen3_7_max_2026_06_08_non_thinking",
        display_name="qwen3.7-max-2026-06-08 / 非思考",
        model="qwen3.7-max-2026-06-08",
        enable_thinking=False,
    ),
]


def as_posix(path: Path | str | None) -> str | None:
    if path is None:
        return None
    path_obj = Path(path)
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def read_xlsx_rows(path: Path) -> list[dict[str, str]]:
    resolved = resolve_path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"Previous review xlsx not found: {resolved}")

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


def xlsx_cell_col_index(cell_ref: str) -> int:
    letters = "".join(char for char in cell_ref if char.isalpha())
    value = 0
    for char in letters:
        value = value * 26 + (ord(char.upper()) - ord("A") + 1)
    return max(0, value - 1)


def is_correct_mark(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"正确", "对", "是", "ok", "yes", "true"}


def is_problem_mark(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return False
    return not is_correct_mark(normalized)


def parse_page_number(value: str) -> int:
    text = value.strip()
    if not text:
        raise ValueError("Missing page number")
    return int(float(text))


def select_error_first_rows(
    review_rows_data: list[dict[str, str]],
    primary_model: str,
    max_pages: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected_by_page: dict[int, dict[str, Any]] = {}
    primary_rows = [row for row in review_rows_data if row.get("模型", "").strip() == primary_model]
    for row in primary_rows:
        verdict = row.get("位置是否正确", "")
        if not is_problem_mark(verdict):
            continue
        page_number = parse_page_number(row.get("页码", ""))
        selected_by_page[page_number] = {
            "page_number": page_number,
            "task_id": row.get("样本编号", "").strip(),
            "previous_model": row.get("模型", "").strip(),
            "previous_model_position_label": row.get("模型标题栏位置", "").strip(),
            "previous_model_position_code": row.get("模型标题栏位置代码", "").strip(),
            "previous_review_verdict": verdict.strip(),
            "previous_correct_position": row.get("正确标题栏位置", "").strip(),
            "previous_remark": row.get("备注", "").strip(),
            "selection_reason": "primary_model_manual_non_correct",
        }

    selected = [selected_by_page[page] for page in sorted(selected_by_page)]
    if max_pages > 0:
        selected = selected[:max_pages]

    summary = {
        "primary_model": primary_model,
        "previous_primary_row_count": len(primary_rows),
        "selected_page_count": len(selected),
        "selected_pages": [row["page_number"] for row in selected],
        "previous_verdict_distribution": dict(Counter(row.get("位置是否正确", "") for row in primary_rows)),
        "previous_correct_position_distribution": dict(
            Counter(row["previous_correct_position"] for row in selected if row.get("previous_correct_position"))
        ),
    }
    return selected, summary


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
        "no_resize": True,
        "compressed": False,
        "image_lossless": True,
    }


def build_records(selected_rows: list[dict[str, Any]], previous_output_dir: Path) -> list[dict[str, Any]]:
    rendered_dir = resolve_path(previous_output_dir) / "rendered_png"
    records: list[dict[str, Any]] = []
    for row in selected_rows:
        task_id = row["task_id"]
        image_path = rendered_dir / f"{task_id}.png"
        if not image_path.exists():
            raise FileNotFoundError(f"Rendered PNG not found for {task_id}: {image_path}")
        records.append(
            {
                "record_version": RECORD_VERSION,
                "task_id": task_id,
                "page_number": row["page_number"],
                "rendered_image_path": as_posix(image_path),
                "previous_review": row,
                **image_meta(image_path),
            }
        )
    return records


def build_request_body(variant: ModelVariant, image_data_url: str) -> dict[str, Any]:
    return {
        "model": variant.model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        ],
        "temperature": variant.temperature,
        "response_format": {"type": "json_object"},
        **variant.extra_body(),
    }


def build_request_rows(records: list[dict[str, Any]], variants: list[ModelVariant]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    request_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    for record in records:
        for variant in variants:
            request_custom_id = f"{variant.variant_id}__{record['task_id']}"
            request_rows.append(
                {
                    "task_id": record["task_id"],
                    "page_number": record["page_number"],
                    "model": variant.display_name,
                    "model_id": variant.model,
                    "model_variant": variant.variant_id,
                    "request_custom_id": request_custom_id,
                    "rendered_image_path": record["rendered_image_path"],
                    "temperature": variant.temperature,
                    "enable_thinking": variant.enable_thinking,
                    "thinking_budget": variant.thinking_budget,
                }
            )
            manifest_rows.append(
                {
                    **record,
                    "provider_mode": "aliyun_openai_compatible",
                    "model": variant.display_name,
                    "model_id": variant.model,
                    "model_variant": variant.variant_id,
                    "request_custom_id": request_custom_id,
                    "temperature": variant.temperature,
                    "top_p": "",
                    "enable_thinking": variant.enable_thinking,
                    "thinking_budget": variant.thinking_budget,
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
                        {"type": "text", "text": PROMPT},
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
            "thinking_budget": request_row["thinking_budget"] or "",
        },
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
                    "event": "vlm_error_first_request",
                    "index": index,
                    "total": total,
                    "task_id": request_row["task_id"],
                    "page_number": request_row["page_number"],
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
        except Exception as exc:  # Keep a single provider disconnect from discarding the batch.
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


def build_decisions(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for row in raw_rows:
        decision = build_decision_row(row)
        decision["record_version"] = RECORD_VERSION
        decision["model_id"] = row["model_id"]
        decision["model_variant"] = row["model_variant"]
        decision["temperature"] = row["temperature"]
        decision["top_p"] = ""
        decision["enable_thinking"] = row["enable_thinking"]
        decision["thinking_budget"] = row["thinking_budget"]
        decisions.append(decision)
    return decisions


def decision_by_task_model(decisions: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(row["task_id"], row["model"]): row for row in decisions}


def review_rows(records: list[dict[str, Any]], decisions: list[dict[str, Any]], variants: list[ModelVariant]) -> list[dict[str, Any]]:
    by_key = decision_by_task_model(decisions)
    rows: list[dict[str, Any]] = []
    index = 1
    for record in records:
        previous = record["previous_review"]
        for variant in variants:
            decision = by_key.get((record["task_id"], variant.display_name), {})
            position = decision.get("title_block_position", "")
            position_value = position if isinstance(position, str) else ""
            previous_correct = previous.get("previous_correct_position", "")
            predicted_label = POSITION_LABELS.get(position_value, position_value)
            machine_matches_previous = label_matches(predicted_label, position_value, previous_correct)
            model_rotation = decision.get("derived_current_clockwise_degrees")
            expected_rotation = rotation_group_from_position_label(previous_correct)
            rotation_matches_previous = (
                isinstance(model_rotation, int) and expected_rotation is not None and model_rotation == expected_rotation
            )
            rows.append(
                {
                    "序号": index,
                    "页码": record["page_number"],
                    "样本编号": record["task_id"],
                    "模型": variant.display_name,
                    "模型标题栏位置": predicted_label,
                    "模型标题栏位置代码": position_value,
                    "模型派生当前旋转角度": model_rotation if model_rotation is not None else "",
                    "上一轮人工正确位置": previous_correct,
                    "上一轮人工正确旋转角度": expected_rotation if expected_rotation is not None else "",
                    "上一轮Plus误判位置": previous.get("previous_model_position_label", ""),
                    "旋转角度是否正确": "",
                    "正确旋转角度": "",
                    "备注": "",
                    "_machine_matches_previous_truth": machine_matches_previous,
                    "_rotation_matches_previous_truth": rotation_matches_previous,
                }
            )
            index += 1
    return rows


def label_matches(predicted_label: str, predicted_code: str, expected_label: str) -> bool:
    expected = expected_label.strip()
    if not expected:
        return False
    normalized_map = {value: key for key, value in POSITION_LABELS.items()}
    expected_code = normalized_map.get(expected)
    return expected in {predicted_label, predicted_code} or (expected_code is not None and expected_code == predicted_code)


def rotation_group_from_position_code(position_code: Any) -> int | None:
    if not isinstance(position_code, str):
        return None
    return POSITION_TO_ROTATION_GROUP.get(position_code.strip())


def rotation_group_from_position_label(position_label: Any) -> int | None:
    if not isinstance(position_label, str):
        return None
    text = position_label.strip()
    if not text:
        return None
    return rotation_group_from_position_code(POSITION_LABEL_TO_CODE.get(text, text))


def publish_review_pack(
    output_dir: Path,
    current_dir: Path,
    review_slug: str,
    review_title: str,
    records: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    review_rows_data: list[dict[str, Any]],
    variants: list[ModelVariant],
    selection_summary: dict[str, Any],
) -> dict[str, Any]:
    archived = archive_current_inbox(current_dir, review_slug)
    review_dir = current_dir / review_slug
    image_dir = review_dir / "images"
    review_dir.mkdir(parents=True, exist_ok=True)
    safe_reset_child_dir(image_dir, review_dir)

    image_map: dict[str, str] = {}
    for record in records:
        source_image = resolve_path(Path(record["rendered_image_path"]))
        target_image = image_dir / source_image.name
        shutil.copy2(source_image, target_image)
        image_map[record["task_id"]] = rel_path(target_image, review_dir)

    review_fieldnames = [
        "页码",
        "模型",
        "模型派生当前旋转角度",
        "旋转角度是否正确",
        "正确旋转角度",
        "备注",
    ]
    review_rows_minimal = [{field: row.get(field, "") for field in review_fieldnames} for row in review_rows_data]
    csv_path = review_dir / "vlm_error_first_review.csv"
    xlsx_path = review_dir / "vlm_error_first_review.xlsx"
    manifest_path = review_dir / "review_manifest.json"
    html_path = review_dir / "review_index.html"
    write_csv(csv_path, review_rows_minimal, review_fieldnames)
    write_xlsx(xlsx_path, review_rows_minimal, review_fieldnames, "错题集审核")

    by_key = decision_by_task_model(decisions)
    cards: list[str] = []
    for record in records:
        previous = record["previous_review"]
        decision_lines: list[str] = []
        for variant in variants:
            decision = by_key.get((record["task_id"], variant.display_name), {})
            position = decision.get("title_block_position", "")
            position_value = position if isinstance(position, str) else ""
            reasons = "; ".join(decision.get("review_reasons") or [])
            decision_lines.append(
                "<tr>"
                f"<td>{html.escape(variant.display_name)}</td>"
                f"<td>{html.escape(POSITION_LABELS.get(position_value, position_value))}</td>"
                f"<td>{html.escape(position_value)}</td>"
                f"<td>{html.escape(str(decision.get('derived_current_clockwise_degrees', '')))}</td>"
                f"<td>{html.escape(str(decision.get('parse_status', '')))}</td>"
                f"<td>{html.escape(str(decision.get('schema_status', '')))}</td>"
                f"<td>{html.escape(str(decision.get('orientation_confidence', '')))}</td>"
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
      <div class="previous">
        上一轮 Plus：{html.escape(previous.get('previous_model_position_label', ''))}
        <span>人工正确位置：{html.escape(previous.get('previous_correct_position', ''))}</span>
        <span>人工正确旋转：{html.escape(str(rotation_group_from_position_label(previous.get('previous_correct_position', ''))))} 度</span>
        <span>{html.escape(previous.get('previous_remark', ''))}</span>
      </div>
      <a href="{html.escape(image_map[record['task_id']])}" target="_blank">
        <img src="{html.escape(image_map[record['task_id']])}" alt="第 {record['page_number']} 页原向图纸">
      </a>
      <table>
        <thead><tr><th>模型</th><th>标题栏位置</th><th>位置代码</th><th>派生当前旋转</th><th>解析</th><th>Schema</th><th>置信度</th><th>需复核</th><th>原因</th></tr></thead>
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
    body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; color: #1c2733; background: #f5f6f8; }}
    header {{ position: sticky; top: 0; z-index: 2; padding: 14px 20px; background: #ffffff; border-bottom: 1px solid #d8dee8; }}
    h1 {{ margin: 0 0 6px; font-size: 20px; }}
    .meta {{ display: flex; gap: 14px; flex-wrap: wrap; color: #52606d; font-size: 13px; }}
    main {{ max-width: 1480px; margin: 0 auto; padding: 18px; }}
    .guide {{ margin-bottom: 16px; padding: 12px 14px; background: #ffffff; border: 1px solid #d8dee8; }}
    .page-card {{ margin-bottom: 18px; padding: 14px; background: #ffffff; border: 1px solid #d8dee8; }}
    .page-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 8px; }}
    .page-head h2 {{ margin: 0; font-size: 18px; }}
    .page-head span {{ color: #52606d; font-size: 13px; }}
    .previous {{ display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 10px; color: #334155; font-size: 13px; }}
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
      <span>错题页 {len(records)} 页</span>
      <span>结果 {len(review_rows_data)} 行</span>
      <span>填写：vlm_error_first_review.xlsx</span>
      <span>图片为原向 PNG，不旋转、不 resize、不做有损压缩</span>
    </div>
  </header>
  <main>
    <section class="guide">
      <strong>审核说明：</strong>
      只核对本轮模型派生的当前旋转角度是否正确。精确标题栏位置仅作参考；若旋转角度错误，请在 Excel 中填写“旋转角度是否正确”“正确旋转角度”和备注。
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
        "selection_summary": selection_summary,
        "page_count": len(records),
        "model_variants": [variant.__dict__ for variant in variants],
        "archived_previous_current": archived,
        "html": rel_path(html_path, current_dir),
        "xlsx": rel_path(xlsx_path, current_dir),
        "csv": rel_path(csv_path, current_dir),
        "image_count": len(image_map),
        "human_review_fields": review_fieldnames,
        "machine_review_rows": review_rows_data,
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
                f"- `{review_slug}/vlm_error_first_review.xlsx`",
                "",
                "本轮只审核上一轮 Plus 识别出错页的派生当前旋转角度。",
                "图片为原向 PNG，不旋转、不 resize、不做有损压缩。",
                "",
                "请在 Excel 中填写 `旋转角度是否正确`、必要时填写 `正确旋转角度` 和 `备注`。",
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
        "image_count": len(image_map),
        "archived_previous_current": archived,
    }


def write_decisions_csv(path: Path, decisions: list[dict[str, Any]]) -> None:
    write_csv(
        path,
        [
            {
                **row,
                "drawing_number_candidates": json.dumps(row.get("drawing_number_candidates", []), ensure_ascii=False),
                "review_reasons": ";".join(row.get("review_reasons") or []),
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
            "thinking_budget",
            "http_status",
            "api_ok",
            "attempt_count",
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
                "derived_correction_clockwise_degrees_by_model": json.dumps(
                    row.get("derived_correction_clockwise_degrees_by_model", {}), ensure_ascii=False
                ),
                "drawing_number_selected_by_model": json.dumps(
                    row.get("drawing_number_selected_by_model", {}), ensure_ascii=False
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
            "derived_correction_clockwise_degrees_by_model",
            "drawing_number_selected_by_model",
            "needs_review_by_model",
            "needs_review",
            "review_reasons",
        ],
    )


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
            "position_distribution": dict(Counter(row.get("title_block_position") or "" for row in rows)),
        }
    return by_model


def summarize_against_previous_truth(review_rows_data: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: dict[str, dict[str, int]] = {}
    for model in sorted({row["模型"] for row in review_rows_data}):
        rows = [row for row in review_rows_data if row["模型"] == model]
        by_model[model] = {
            "match_count": sum(1 for row in rows if row.get("_machine_matches_previous_truth")),
            "mismatch_count": sum(1 for row in rows if not row.get("_machine_matches_previous_truth")),
            "total": len(rows),
        }
    return {
        "total_match_count": sum(1 for row in review_rows_data if row.get("_machine_matches_previous_truth")),
        "total_mismatch_count": sum(1 for row in review_rows_data if not row.get("_machine_matches_previous_truth")),
        "by_model": by_model,
    }


def summarize_rotation_against_previous_truth(review_rows_data: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: dict[str, dict[str, int]] = {}
    for model in sorted({row["模型"] for row in review_rows_data}):
        rows = [row for row in review_rows_data if row["模型"] == model]
        api_like_rows = [row for row in rows if row.get("模型派生当前旋转角度") != ""]
        by_model[model] = {
            "rotation_match_count": sum(1 for row in rows if row.get("_rotation_matches_previous_truth")),
            "rotation_mismatch_count": sum(1 for row in rows if row.get("模型派生当前旋转角度") != "" and not row.get("_rotation_matches_previous_truth")),
            "missing_rotation_count": sum(1 for row in rows if row.get("模型派生当前旋转角度") == ""),
            "valid_rotation_total": len(api_like_rows),
            "total": len(rows),
        }
    return {
        "total_rotation_match_count": sum(1 for row in review_rows_data if row.get("_rotation_matches_previous_truth")),
        "total_valid_rotation_count": sum(1 for row in review_rows_data if row.get("模型派生当前旋转角度") != ""),
        "total_missing_rotation_count": sum(1 for row in review_rows_data if row.get("模型派生当前旋转角度") == ""),
        "by_model": by_model,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    previous_rows = read_xlsx_rows(args.previous_review_xlsx)
    selected_rows, selection_summary = select_error_first_rows(previous_rows, args.primary_model, args.max_pages)
    records = build_records(selected_rows, args.previous_output_dir)
    variants = MODEL_VARIANTS
    variants_by_display_name = {variant.display_name: variant for variant in variants}
    model_names = [variant.display_name for variant in variants]
    request_rows, manifest_rows = build_request_rows(records, variants)

    prompt_path = output_dir / "vlm_prompt.md"
    schema_path = output_dir / "vlm_response_schema.json"
    selection_path = output_dir / "selected_error_first_pages.json"
    selection_csv_path = output_dir / "selected_error_first_pages.csv"
    requests_path = output_dir / "vlm_error_first_requests.jsonl"
    manifest_path = output_dir / "vlm_error_first_manifest.json"
    manifest_csv_path = output_dir / "vlm_error_first_manifest.csv"
    raw_path = output_dir / "vlm_raw_responses.jsonl"
    raw_checkpoint_path = output_dir / "vlm_raw_responses.partial.jsonl"
    decisions_path = output_dir / "vlm_decisions.jsonl"
    decisions_csv_path = output_dir / "vlm_decisions.csv"
    comparison_path = output_dir / "model_variant_comparison.json"
    comparison_csv_path = output_dir / "model_variant_comparison.csv"
    summary_path = output_dir / "run_summary.json"

    prompt_path.write_text(PROMPT, encoding="utf-8")
    write_json(schema_path, RESPONSE_SCHEMA)
    write_json(selection_path, {"summary": selection_summary, "selected_rows": selected_rows})
    write_csv(
        selection_csv_path,
        selected_rows,
        [
            "page_number",
            "task_id",
            "previous_model",
            "previous_model_position_label",
            "previous_model_position_code",
            "previous_review_verdict",
            "previous_correct_position",
            "previous_remark",
            "selection_reason",
        ],
    )
    write_jsonl(requests_path, [redacted_request_row(row) for row in request_rows])
    write_json(manifest_path, manifest_rows)
    write_csv(
        manifest_csv_path,
        manifest_rows,
        [
            "task_id",
            "page_number",
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
            "thinking_budget",
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
    decisions = build_decisions(raw_rows)
    comparisons = compare_decisions(decisions, model_names)
    review_rows_data = review_rows(records, decisions, variants)
    review_output_rows = [
        {key: value for key, value in row.items() if not key.startswith("_")} for row in review_rows_data
    ]

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
            review_output_rows,
            variants,
            selection_summary,
        )

    summary = {
        "record_version": RECORD_VERSION,
        "previous_review_xlsx": as_posix(resolve_path(args.previous_review_xlsx)),
        "previous_output_dir": as_posix(resolve_path(args.previous_output_dir)),
        "output_dir": as_posix(output_dir),
        "selection_summary": selection_summary,
        "page_count": len(records),
        "model_variant_count": len(variants),
        "request_count": len(request_rows),
        "raw_response_count": len(raw_rows),
        "decision_count": len(decisions),
        "api_ok_count": sum(1 for row in decisions if row.get("api_ok")),
        "parse_ok_count": sum(1 for row in decisions if row.get("parse_status") == "ok"),
        "schema_ok_count": sum(1 for row in decisions if row.get("schema_status") == "ok"),
        "decision_needs_review_count": sum(1 for row in decisions if row.get("needs_review")),
        "comparison_count": len(comparisons),
        "comparison_needs_review_count": sum(1 for row in comparisons if row.get("needs_review")),
        "decision_summary_by_model": summarize_decisions(decisions),
        "machine_match_previous_truth_summary": summarize_against_previous_truth(review_rows_data),
        "rotation_group_match_previous_truth_summary": summarize_rotation_against_previous_truth(review_rows_data),
        "image_format": "png",
        "compressed": False,
        "no_resize": True,
        "image_lossless": True,
        "top_p": "not_set",
        "prompt_modified_by_this_run": False,
        "ocr_test_included": False,
        "modified_pdf": False,
        "renamed_pdf": False,
        "network_call_executed": not bool(args.reuse_raw_responses),
        "env_status": env_summary,
        "outputs": {
            "prompt": as_posix(prompt_path),
            "schema": as_posix(schema_path),
            "selection": as_posix(selection_path),
            "selection_csv": as_posix(selection_csv_path),
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
    parser = argparse.ArgumentParser(description="Build error-first VLM title-block model review pack.")
    parser.add_argument("--previous-review-xlsx", type=Path, default=DEFAULT_PREVIOUS_REVIEW_XLSX)
    parser.add_argument("--previous-output-dir", type=Path, default=DEFAULT_PREVIOUS_OUTPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--review-inbox", type=Path, default=DEFAULT_REVIEW_INBOX)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--review-slug", default=DEFAULT_REVIEW_SLUG)
    parser.add_argument("--review-title", default=DEFAULT_REVIEW_TITLE)
    parser.add_argument("--primary-model", default=DEFAULT_PRIMARY_MODEL)
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--timeout-seconds", type=int, default=120)
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
