from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_CALL_PREP_DIR = ROOT / "local_data" / "mcp_vlm_teacher_call_prep"
DEFAULT_MANIFEST = DEFAULT_CALL_PREP_DIR / "teacher_call_manifest.json"
DEFAULT_PROMPT = DEFAULT_CALL_PREP_DIR / "teacher_prompt.md"
DEFAULT_SCHEMA = DEFAULT_CALL_PREP_DIR / "teacher_response_schema.json"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "mcp_vlm_teacher_provider"


def as_posix(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> Any:
    return json.loads(resolve_path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    resolved = resolve_path(path)
    if not resolved.exists():
        return rows
    with resolved.open("r", encoding="utf-8") as f:
        for line_number, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                rows.append(
                    {
                        "task_id": "",
                        "_line_number": line_number,
                        "_json_error": str(exc),
                    }
                )
                continue
            row["_line_number"] = line_number
            rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def request_rows(
    tasks: list[dict[str, Any]],
    prompt: str,
    schema_path: Path,
    provider_mode: str,
) -> list[dict[str, Any]]:
    rows = []
    for task in tasks:
        rows.append(
            {
                "task_id": task["task_id"],
                "provider_mode": provider_mode,
                "prompt": prompt,
                "question": task["question"],
                "expected_teacher_question": task["expected_teacher_question"],
                "task_type": task["task_type"],
                "assets": {
                    "source_image": task.get("source_image", ""),
                    "overlay_image": task.get("overlay_image", ""),
                    "candidate_crop": task.get("candidate_crop", ""),
                },
                "response_schema_path": as_posix(resolve_path(schema_path)),
                "expected_output": "json_only",
                "distillation": {
                    "distill_to_rule": task.get("distill_to_rule", ""),
                    "distill_to_data": task.get("distill_to_data", ""),
                    "distill_to_model": task.get("distill_to_model", ""),
                },
            }
        )
    return rows


def response_template_rows(tasks: list[dict[str, Any]], provider_mode: str) -> list[dict[str, Any]]:
    return [
        {
            "task_id": task["task_id"],
            "provider": provider_mode,
            "raw_response": {},
            "parsed_response": {},
            "parse_status": "pending",
            "notes": "fill parsed_response with provider JSON output",
        }
        for task in tasks
    ]


def validate_parsed_response(task_id: str, parsed: Any, schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(parsed, dict) or not parsed:
        return ["missing_or_empty_parsed_response"]

    for field in schema.get("required", []):
        if field not in parsed:
            errors.append(f"missing_required:{field}")

    if parsed.get("task_id") not in {task_id, None, ""}:
        errors.append("task_id_mismatch")

    position = parsed.get("title_block_position")
    allowed_positions = set(schema["properties"]["title_block_position"]["enum"])
    if position is not None and position not in allowed_positions:
        errors.append("invalid_title_block_position")

    rotation = parsed.get("rotation_degrees")
    allowed_rotations = set(schema["properties"]["rotation_degrees"]["enum"])
    if rotation not in allowed_rotations:
        errors.append("invalid_rotation_degrees")

    confidence = parsed.get("confidence")
    if not isinstance(confidence, int | float) or not 0.0 <= float(confidence) <= 1.0:
        errors.append("invalid_confidence")

    judgments = parsed.get("candidate_judgments")
    if not isinstance(judgments, list) or not judgments:
        errors.append("missing_candidate_judgments")
    else:
        required_judgment = set(
            schema["properties"]["candidate_judgments"]["items"]["required"]
        )
        for index, judgment in enumerate(judgments):
            if not isinstance(judgment, dict):
                errors.append(f"candidate_judgment_{index}:not_object")
                continue
            missing = sorted(required_judgment - set(judgment))
            for field in missing:
                errors.append(f"candidate_judgment_{index}:missing_required:{field}")

    return errors


def validate_responses(path: Path, schema: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = read_jsonl(path)
    validated = []
    errors = []
    for row in rows:
        task_id = row.get("task_id", "")
        row_errors = []
        if row.get("_json_error"):
            row_errors.append(f"json_error:{row['_json_error']}")
        if not task_id:
            row_errors.append("missing_task_id")
        if row.get("parse_status") in {"pending", "", None}:
            row_errors.append("pending_response")
        row_errors.extend(validate_parsed_response(task_id, row.get("parsed_response"), schema))
        status = "ok" if not row_errors else "error"
        validated.append(
            {
                "task_id": task_id,
                "provider": row.get("provider", ""),
                "status": status,
                "errors": row_errors,
                "parsed_response": row.get("parsed_response", {}),
                "raw_response": row.get("raw_response", {}),
            }
        )
        for error in row_errors:
            errors.append(
                {
                    "task_id": task_id,
                    "line_number": row.get("_line_number", ""),
                    "error": error,
                }
            )
    return validated, errors


def build(args: argparse.Namespace) -> dict[str, Any]:
    manifest = read_json(args.manifest)
    schema = read_json(args.schema)
    prompt = resolve_path(args.prompt).read_text(encoding="utf-8")
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = manifest.get("tasks", [])
    requests = request_rows(tasks, prompt, args.schema, args.provider_mode)
    templates = response_template_rows(tasks, args.provider_mode)

    requests_path = output_dir / "teacher_requests.jsonl"
    template_path = output_dir / "teacher_response_template.jsonl"
    summary_path = output_dir / "teacher_provider_summary.json"
    validated_path = output_dir / "validated_responses.json"
    errors_path = output_dir / "validation_errors.csv"

    write_jsonl(requests_path, requests)
    write_jsonl(template_path, templates)

    validation_source = args.validate_responses or template_path
    validated, errors = validate_responses(validation_source, schema)
    write_json(validated_path, validated)
    write_csv(errors_path, errors, ["task_id", "line_number", "error"])

    summary = {
        "provider_mode": args.provider_mode,
        "task_count": len(tasks),
        "request_count": len(requests),
        "response_template_count": len(templates),
        "validation_source": as_posix(resolve_path(validation_source)),
        "validated_response_count": len(validated),
        "validation_error_count": len(errors),
        "outputs": {
            "teacher_requests": as_posix(requests_path),
            "teacher_response_template": as_posix(template_path),
            "validated_responses": as_posix(validated_path),
            "validation_errors": as_posix(errors_path),
        },
    }
    write_json(summary_path, summary)
    return {
        "output_dir": str(output_dir),
        "teacher_requests": str(requests_path),
        "teacher_response_template": str(template_path),
        "teacher_provider_summary": str(summary_path),
        "validated_responses": str(validated_path),
        "validation_errors": str(errors_path),
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MCP/VLM teacher provider request package.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--provider-mode", choices=["manual", "mcp", "cloud_vlm", "local_vlm"], default="manual")
    parser.add_argument("--validate-responses", type=Path, default=None)
    args = parser.parse_args()

    print(json.dumps(build(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

