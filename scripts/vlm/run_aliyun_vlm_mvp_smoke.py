from __future__ import annotations

import argparse
import csv
import json
import os
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path
from scripts.vlm.build_aliyun_vlm_mvp_requests import (
    DEFAULT_JPEG_QUALITY,
    DEFAULT_MAX_LONG_SIDE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SOURCE_PDF,
    RESPONSE_SCHEMA,
    as_posix,
    build_request,
    collect_png_inputs,
    data_url_for,
    prepare_input_image,
    render_pdf_pages,
    safe_reset_child_dir,
    split_pdf,
    write_json,
    write_jsonl,
)


DEFAULT_ENV_FILE = ROOT / ".env" / ".env"
DEFAULT_INPUT_IMAGE_DIR = ROOT / "local_data" / "js2207_generalization_test" / "rendered_png"
DEFAULT_DRY_RUN_OUTPUT_DIR = ROOT / "local_data" / "aliyun_vlm_mvp_dry_run"
DEFAULT_MODELS = "qwen3-vl-flash,qwen3-vl-plus"
RECORD_VERSION = "aliyun-vlm-dual-model-smoke-v0.2"
ALLOWED_POSITIONS = {
    "bottom_edge",
    "top_edge",
    "left_edge",
    "right_edge",
    "bottom_right",
    "top_right",
    "top_left",
    "bottom_left",
    "no_title_block",
    "right",
    "left",
    "top",
    "bottom",
    "unknown",
}
UNKNOWN_DRAWING_VALUES = {"", "unknown", "none", "null", "n/a", "无法确定", "不确定", "看不清"}

POSITION_ALIASES = {
    "bottom": "bottom_edge",
    "top": "top_edge",
    "left": "left_edge",
    "right": "right_edge",
}

POSITION_TO_ROTATION: dict[str, tuple[int, int] | tuple[None, None]] = {
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


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def parse_models(raw: str) -> list[str]:
    models = [item.strip() for item in raw.split(",") if item.strip()]
    deduped: list[str] = []
    for model in models:
        if model not in deduped:
            deduped.append(model)
    if not deduped:
        raise ValueError("At least one model is required.")
    return deduped


def safe_id(value: str) -> str:
    chars = []
    for char in value.lower():
        if char.isalnum() or char in {"-", "_"}:
            chars.append(char)
        else:
            chars.append("_")
    return "".join(chars).strip("_") or "model"


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


def build_records(args: argparse.Namespace, output_dir: Path) -> list[dict[str, Any]]:
    if args.input_image_dir:
        return collect_png_inputs(args.input_image_dir, args.limit_pages)
    records = split_pdf(args.source_pdf, output_dir, args.limit_pages)
    render_pdf_pages(records, output_dir, args.render_dpi)
    return records


def prepare_requests(
    records: list[dict[str, Any]],
    models: list[str],
    output_dir: Path,
    max_long_side: int,
    jpeg_quality: int,
    image_format: str,
    no_resize: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    input_image_dir = output_dir / "vlm_input_images"
    safe_reset_child_dir(input_image_dir, output_dir)
    request_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    data_urls: dict[str, str] = {}
    image_meta_by_task: dict[str, dict[str, Any]] = {}

    for record in records:
        rendered_value = record.get("rendered_image_path")
        if not rendered_value:
            raise ValueError(f"Missing rendered image for task {record['task_id']}")
        rendered_path = resolve_path(Path(rendered_value))
        extension = "png" if image_format == "png" else "jpg"
        mime_type = "image/png" if image_format == "png" else "image/jpeg"
        prepared_path = input_image_dir / f"{record['task_id']}.{extension}"
        image_meta = prepare_input_image(
            rendered_path,
            prepared_path,
            max_long_side,
            jpeg_quality,
            image_format=image_format,
            no_resize=no_resize,
        )
        image_data_url = data_url_for(prepared_path, mime_type=mime_type)
        data_urls[record["task_id"]] = image_data_url
        image_meta_by_task[record["task_id"]] = image_meta

    for record in records:
        for model in models:
            request = build_request(record, model, data_urls[record["task_id"]])
            request["custom_id"] = f"{safe_id(model)}__{record['task_id']}"
            request_rows.append(
                {
                    "task_id": record["task_id"],
                    "page_number": record.get("page_number"),
                    "model": model,
                    "request": request,
                }
            )
            manifest_rows.append(
                {
                    **record,
                    **image_meta_by_task[record["task_id"]],
                    "provider_mode": "aliyun_openai_compatible",
                    "model": model,
                    "request_custom_id": request["custom_id"],
                    "data_url_bytes": len(data_urls[record["task_id"]].encode("utf-8")),
                    "response_schema_path": "local_data/aliyun_vlm_mvp/vlm_response_schema.json",
                }
            )
    return request_rows, manifest_rows


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
    errors: list[str] = []
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
        return content, errors
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        if parts:
            return "\n".join(parts), errors
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


def is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def validate_decision(parsed: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(parsed, dict):
        return ["decision_not_object"]

    for field in RESPONSE_SCHEMA["required"]:
        if field not in parsed:
            errors.append(f"missing_required:{field}")

    page_orientation = parsed.get("page_orientation")
    if not isinstance(page_orientation, dict):
        errors.append("page_orientation:not_object")
    else:
        for field in RESPONSE_SCHEMA["properties"]["page_orientation"]["required"]:
            if field not in page_orientation:
                errors.append(f"page_orientation:missing_required:{field}")
        if page_orientation.get("title_block_position") not in ALLOWED_POSITIONS:
            errors.append("page_orientation:invalid_title_block_position")
        confidence = page_orientation.get("confidence")
        if not is_number(confidence) or not 0 <= float(confidence) <= 1:
            errors.append("page_orientation:invalid_confidence")
        if not isinstance(page_orientation.get("evidence"), list):
            errors.append("page_orientation:evidence_not_list")

    drawing_number = parsed.get("drawing_number")
    if not isinstance(drawing_number, dict):
        errors.append("drawing_number:not_object")
    else:
        for field in RESPONSE_SCHEMA["properties"]["drawing_number"]["required"]:
            if field not in drawing_number:
                errors.append(f"drawing_number:missing_required:{field}")
        candidates = drawing_number.get("candidates")
        if not isinstance(candidates, list) or any(not isinstance(item, str) for item in candidates):
            errors.append("drawing_number:invalid_candidates")
        if not isinstance(drawing_number.get("selected"), str):
            errors.append("drawing_number:selected_not_string")
        confidence = drawing_number.get("confidence")
        if not is_number(confidence) or not 0 <= float(confidence) <= 1:
            errors.append("drawing_number:invalid_confidence")
        if not isinstance(drawing_number.get("evidence"), list):
            errors.append("drawing_number:evidence_not_list")

    quality_gate = parsed.get("quality_gate")
    if not isinstance(quality_gate, dict):
        errors.append("quality_gate:not_object")
    else:
        for field in RESPONSE_SCHEMA["properties"]["quality_gate"]["required"]:
            if field not in quality_gate:
                errors.append(f"quality_gate:missing_required:{field}")
        if not isinstance(quality_gate.get("needs_human_review"), bool):
            errors.append("quality_gate:needs_human_review_not_bool")
        reasons = quality_gate.get("review_reasons")
        if not isinstance(reasons, list) or any(not isinstance(item, str) for item in reasons):
            errors.append("quality_gate:invalid_review_reasons")
    return errors


def normalized_drawing_number(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = value.strip().lower().replace(" ", "")
    return normalized


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
    schema_errors = validate_decision(parsed) if parsed is not None else []

    review_reasons: list[str] = []
    if not raw_row.get("ok"):
        review_reasons.append(f"api_error:{raw_row.get('error_type') or raw_row.get('http_status')}")
    review_reasons.extend(content_errors)
    review_reasons.extend(parse_errors)
    review_reasons.extend(schema_errors)

    selected = value_at(parsed, "drawing_number", "selected")
    if normalized_drawing_number(selected) in UNKNOWN_DRAWING_VALUES:
        review_reasons.append("drawing_number_missing_or_unknown")

    model_needs_review = value_at(parsed, "quality_gate", "needs_human_review")
    if model_needs_review is True:
        review_reasons.append("model_marked_needs_human_review")

    model_review_reasons = value_at(parsed, "quality_gate", "review_reasons")
    if isinstance(model_review_reasons, list):
        for reason in model_review_reasons:
            if isinstance(reason, str) and reason:
                review_reasons.append(f"model:{reason}")

    review_reasons = sorted(dict.fromkeys(review_reasons))
    schema_status = "ok" if parsed is not None and not schema_errors else "error"
    parse_status = "ok" if parsed is not None and not content_errors and not parse_errors else "error"
    title_block_position = canonical_title_block_position(value_at(parsed, "page_orientation", "title_block_position"))
    derived_current, derived_correction, rotation_errors = derive_rotation_from_position(title_block_position)
    review_reasons = sorted(dict.fromkeys([*review_reasons, *rotation_errors]))

    return {
        "record_version": RECORD_VERSION,
        "task_id": raw_row["task_id"],
        "page_number": raw_row.get("page_number"),
        "model": raw_row["model"],
        "request_custom_id": raw_row["request_custom_id"],
        "http_status": raw_row.get("http_status"),
        "api_ok": bool(raw_row.get("ok")),
        "attempt_count": raw_row.get("attempt_count"),
        "parse_status": parse_status,
        "schema_status": schema_status,
        "title_block_position": title_block_position,
        "derived_current_clockwise_degrees": derived_current,
        "derived_correction_clockwise_degrees": derived_correction,
        "orientation_confidence": value_at(parsed, "page_orientation", "confidence"),
        "drawing_number_selected": selected if isinstance(selected, str) else "",
        "drawing_number_candidates": value_at(parsed, "drawing_number", "candidates") or [],
        "drawing_number_confidence": value_at(parsed, "drawing_number", "confidence"),
        "model_needs_human_review": model_needs_review if isinstance(model_needs_review, bool) else "",
        "needs_review": bool(review_reasons),
        "review_reasons": review_reasons,
        "error_type": raw_row.get("error_type", ""),
        "error_message": raw_row.get("error_message", ""),
        "parsed_response": parsed if isinstance(parsed, dict) else {},
    }


def compare_decisions(decisions: list[dict[str, Any]], models: list[str]) -> list[dict[str, Any]]:
    by_task: dict[str, list[dict[str, Any]]] = {}
    for decision in decisions:
        by_task.setdefault(decision["task_id"], []).append(decision)

    comparisons: list[dict[str, Any]] = []
    for task_id in sorted(by_task):
        rows = sorted(by_task[task_id], key=lambda item: models.index(item["model"]) if item["model"] in models else 999)
        by_model = {row["model"]: row for row in rows}
        reasons: list[str] = []
        for model in models:
            if model not in by_model:
                reasons.append(f"missing_model_result:{model}")
        if any(row.get("needs_review") for row in rows):
            reasons.append("one_or_more_model_results_need_review")

        complete_rows = [by_model[model] for model in models if model in by_model]
        if len(complete_rows) >= 2:
            position_values = {row.get("title_block_position") for row in complete_rows}
            drawing_values = {
                normalized_drawing_number(row.get("drawing_number_selected")) for row in complete_rows
            }
            if len(position_values) > 1:
                reasons.append("title_block_position_conflict")
            if "" in drawing_values:
                reasons.append("drawing_number_missing_in_one_model")
            elif len(drawing_values) > 1:
                reasons.append("drawing_number_conflict")

        page_number = rows[0].get("page_number") if rows else ""
        comparisons.append(
            {
                "record_version": RECORD_VERSION,
                "task_id": task_id,
                "page_number": page_number,
                "models": models,
                "title_block_position_by_model": {
                    model: by_model.get(model, {}).get("title_block_position") for model in models
                },
                "derived_current_clockwise_degrees_by_model": {
                    model: by_model.get(model, {}).get("derived_current_clockwise_degrees") for model in models
                },
                "derived_correction_clockwise_degrees_by_model": {
                    model: by_model.get(model, {}).get("derived_correction_clockwise_degrees") for model in models
                },
                "drawing_number_selected_by_model": {
                    model: by_model.get(model, {}).get("drawing_number_selected") for model in models
                },
                "needs_review_by_model": {
                    model: by_model.get(model, {}).get("needs_review") for model in models
                },
                "needs_review": bool(reasons),
                "review_reasons": sorted(dict.fromkeys(reasons)),
            }
        )
    return comparisons


def build_needs_review_rows(
    decisions: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for decision in decisions:
        if not decision.get("needs_review"):
            continue
        rows.append(
            {
                "scope": "model_result",
                "task_id": decision["task_id"],
                "page_number": decision.get("page_number"),
                "model": decision.get("model"),
                "title_block_position": decision.get("title_block_position"),
                "derived_current_clockwise_degrees": decision.get("derived_current_clockwise_degrees"),
                "derived_correction_clockwise_degrees": decision.get("derived_correction_clockwise_degrees"),
                "drawing_number_selected": decision.get("drawing_number_selected"),
                "review_reasons": ";".join(decision.get("review_reasons") or []),
            }
        )
    for comparison in comparisons:
        if not comparison.get("needs_review"):
            continue
        rows.append(
            {
                "scope": "dual_model_comparison",
                "task_id": comparison["task_id"],
                "page_number": comparison.get("page_number"),
                "model": "",
                "title_block_position": json.dumps(
                    comparison.get("title_block_position_by_model", {}), ensure_ascii=False
                ),
                "derived_current_clockwise_degrees": json.dumps(
                    comparison.get("derived_current_clockwise_degrees_by_model", {}), ensure_ascii=False
                ),
                "derived_correction_clockwise_degrees": json.dumps(
                    comparison.get("derived_correction_clockwise_degrees_by_model", {}), ensure_ascii=False
                ),
                "drawing_number_selected": json.dumps(
                    comparison.get("drawing_number_selected_by_model", {}), ensure_ascii=False
                ),
                "review_reasons": ";".join(comparison.get("review_reasons") or []),
            }
        )
    return rows


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


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir or (DEFAULT_DRY_RUN_OUTPUT_DIR if args.dry_run else DEFAULT_OUTPUT_DIR))
    output_dir.mkdir(parents=True, exist_ok=True)
    env_summary = load_env(args.env_file)
    models = parse_models(args.models)
    records = build_records(args, output_dir)
    request_rows, manifest_rows = prepare_requests(
        records,
        models,
        output_dir,
        args.max_image_long_side,
        args.jpeg_quality,
        args.image_format,
        args.no_resize,
    )

    requests_path = output_dir / "vlm_smoke_requests.jsonl"
    manifest_json_path = output_dir / "vlm_smoke_manifest.json"
    manifest_csv_path = output_dir / "vlm_smoke_manifest.csv"
    raw_responses_path = output_dir / "vlm_raw_responses.jsonl"
    decisions_jsonl_path = output_dir / "vlm_decisions.jsonl"
    decisions_csv_path = output_dir / "vlm_decisions.csv"
    needs_review_path = output_dir / "needs_review.csv"
    comparison_json_path = output_dir / "dual_model_comparison.json"
    comparison_csv_path = output_dir / "dual_model_comparison.csv"
    schema_path = output_dir / "vlm_response_schema.json"
    summary_path = output_dir / "vlm_call_summary.json"

    write_jsonl(requests_path, [row["request"] for row in request_rows])
    write_json(manifest_json_path, manifest_rows)
    write_json(schema_path, RESPONSE_SCHEMA)
    write_csv(
        manifest_csv_path,
        manifest_rows,
        [
            "task_id",
            "source_type",
            "source_path",
            "page_number",
            "single_page_pdf_path",
            "rendered_image_path",
            "input_image_path",
            "input_image_format",
            "no_resize",
            "original_width",
            "original_height",
            "prepared_width",
            "prepared_height",
            "jpeg_quality",
            "max_long_side",
            "bytes",
            "data_url_bytes",
            "provider_mode",
            "model",
            "request_custom_id",
            "response_schema_path",
        ],
    )

    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    base_url = os.environ.get("DASHSCOPE_BASE_URL", "")
    endpoint = endpoint_from_base_url(base_url) if base_url else ""

    raw_rows: list[dict[str, Any]] = []
    if not args.dry_run:
        if not api_key:
            raise RuntimeError("Missing DASHSCOPE_API_KEY. Put it in .env/.env or the process environment.")
        if not base_url:
            raise RuntimeError("Missing DASHSCOPE_BASE_URL. Put it in .env/.env or the process environment.")
        for request_row in request_rows:
            response = post_chat_completion(
                endpoint,
                api_key,
                request_row["request"]["body"],
                args.timeout_seconds,
                args.retries,
                args.retry_sleep_seconds,
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

    decisions = [build_decision_row(row) for row in raw_rows]
    comparisons = compare_decisions(decisions, models) if decisions else []
    needs_review_rows = build_needs_review_rows(decisions, comparisons)

    write_jsonl(raw_responses_path, [public_raw_row(row) for row in raw_rows])
    write_jsonl(decisions_jsonl_path, decisions)
    write_csv(
        decisions_csv_path,
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
    write_json(comparison_json_path, comparisons)
    write_csv(
        comparison_csv_path,
        [
            {
                **row,
                "models": ",".join(row.get("models", [])),
                "title_block_position_by_model": json.dumps(
                    row.get("title_block_position_by_model", {}), ensure_ascii=False
                ),
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
    write_csv(
        needs_review_path,
        needs_review_rows,
        [
            "scope",
            "task_id",
            "page_number",
            "model",
            "title_block_position",
            "derived_current_clockwise_degrees",
            "derived_correction_clockwise_degrees",
            "drawing_number_selected",
            "review_reasons",
        ],
    )

    summary = {
        "record_version": RECORD_VERSION,
        "provider_mode": "aliyun_openai_compatible",
        "dry_run": bool(args.dry_run),
        "network_call_executed": not args.dry_run,
        "modified_pdf": False,
        "renamed_pdf": False,
        "models": models,
        "task_count": len(records),
        "request_count": len(request_rows),
        "raw_response_count": len(raw_rows),
        "decision_count": len(decisions),
        "decision_needs_review_count": sum(1 for row in decisions if row.get("needs_review")),
        "comparison_count": len(comparisons),
        "comparison_needs_review_count": sum(1 for row in comparisons if row.get("needs_review")),
        "needs_review_row_count": len(needs_review_rows),
        "env_status": env_summary,
        "output_dir": as_posix(output_dir),
        "outputs": {
            "requests": as_posix(requests_path),
            "manifest_json": as_posix(manifest_json_path),
            "manifest_csv": as_posix(manifest_csv_path),
            "raw_responses": as_posix(raw_responses_path),
            "decisions_jsonl": as_posix(decisions_jsonl_path),
            "decisions_csv": as_posix(decisions_csv_path),
            "needs_review": as_posix(needs_review_path),
            "dual_model_comparison_json": as_posix(comparison_json_path),
            "dual_model_comparison_csv": as_posix(comparison_csv_path),
            "response_schema": as_posix(schema_path),
            "summary": as_posix(summary_path),
        },
    }
    write_json(summary_path, summary)
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Aliyun VLM dual-model smoke test.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--source-pdf", type=Path, default=DEFAULT_SOURCE_PDF)
    parser.add_argument("--input-image-dir", type=Path, default=DEFAULT_INPUT_IMAGE_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--limit-pages", type=int, default=3)
    parser.add_argument("--models", default=DEFAULT_MODELS)
    parser.add_argument("--render-dpi", type=int, default=150)
    parser.add_argument("--max-image-long-side", type=int, default=DEFAULT_MAX_LONG_SIDE)
    parser.add_argument("--jpeg-quality", type=int, default=DEFAULT_JPEG_QUALITY)
    parser.add_argument("--image-format", choices=["jpeg", "png"], default="jpeg")
    parser.add_argument("--no-resize", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--retry-sleep-seconds", type=float, default=2.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
