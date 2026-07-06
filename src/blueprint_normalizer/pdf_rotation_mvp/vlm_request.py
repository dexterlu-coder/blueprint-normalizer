"""VLM request construction helpers for the PDF rotation MVP."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from blueprint_normalizer.pdf_rotation_mvp.domain import RECORD_VERSION
from blueprint_normalizer.pdf_rotation_mvp.workflow import ImageRecord, as_posix


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


def data_url_for(path: Path, mime_type: str = "image/png") -> str:
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


def redacted_request_row(
    record: ImageRecord,
    model: str,
    prompt: str,
    request_kind: str,
    root: Path | None = None,
) -> dict[str, Any]:
    return {
        "custom_id": f"{request_kind}__{model}__{record.task_id}",
        "method": "POST",
        "url": "/chat/completions",
        "request_kind": request_kind,
        "body": build_request_body(
            model,
            f"<omitted_png_data_url:{as_posix(record.image_path, root)}>",
            prompt,
        ),
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
