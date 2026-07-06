"""Pure domain logic for the PDF rotation MVP."""

from __future__ import annotations

import json
import re
from typing import Any


RECORD_VERSION = "pdf-rotation-mvp-v0.1"

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
