from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path
from scripts.experiments.build_vlm_title_block_blind_review import (
    DEFAULT_REVIEW_INBOX,
    DEFAULT_REVIEW_SLUG,
    DEFAULT_REVIEW_TITLE,
    POSITION_LABELS,
    as_posix,
    call_vlm_requests,
    publish_review_pack,
    review_rows,
    write_csv,
)
from scripts.vlm.run_aliyun_vlm_mvp_smoke import build_decision_row, compare_decisions, parse_models
from scripts.vlm.build_aliyun_vlm_mvp_requests import write_json, write_jsonl


DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "vlm_title_block_generalization_blind_ykj125"
DEFAULT_ENV_FILE = ROOT / ".env" / ".env"
DEFAULT_MODELS = "qwen3-vl-flash,qwen3-vl-plus"
RECORD_VERSION = "vlm-title-block-generalization-blind-retry-v0.1"


def load_json(path: Path) -> Any:
    return json.loads(resolve_path(path).read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in resolve_path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl_append(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with resolve_path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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


def raw_success(row: dict[str, Any]) -> bool:
    return bool(row.get("ok")) and bool(row.get("response_json"))


def find_failed_keys(decisions: list[dict[str, Any]]) -> list[tuple[str, str]]:
    failed: list[tuple[str, str]] = []
    for row in decisions:
        if row.get("api_ok") and row.get("parse_status") == "ok" and row.get("schema_status") == "ok":
            continue
        failed.append((str(row["task_id"]), str(row["model"])))
    return failed


def build_retry_rows(
    failed_keys: list[tuple[str, str]],
    manifest_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    manifest_by_key = {
        (str(row["task_id"]), str(row["model"])): row
        for row in manifest_rows
    }
    retry_rows: list[dict[str, Any]] = []
    for task_id, model in failed_keys:
        manifest = manifest_by_key.get((task_id, model))
        if not manifest:
            raise KeyError(f"Missing manifest row for {task_id} / {model}")
        retry_rows.append(
            {
                "task_id": task_id,
                "page_number": int(manifest["page_number"]),
                "model": model,
                "rendered_image_path": manifest["rendered_image_path"],
                "request_custom_id": manifest.get("request_custom_id") or f"{model}__{task_id}",
            }
        )
    return retry_rows


def replace_raw_rows(
    raw_rows: list[dict[str, Any]],
    retry_raw_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    replacements = {
        (str(row["task_id"]), str(row["model"])): row
        for row in retry_raw_rows
        if raw_success(row)
    }
    merged: list[dict[str, Any]] = []
    for row in raw_rows:
        key = (str(row["task_id"]), str(row["model"]))
        merged.append(replacements.get(key, row))
    return merged


def records_from_manifest(manifest_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_task: dict[str, dict[str, Any]] = {}
    for row in manifest_rows:
        task_id = str(row["task_id"])
        if task_id in by_task:
            continue
        by_task[task_id] = {
            "task_id": task_id,
            "page_number": int(row["page_number"]),
            "source_path": row.get("source_path"),
            "single_page_pdf_path": row.get("single_page_pdf_path"),
            "rendered_image_path": row.get("rendered_image_path"),
        }
    return [by_task[key] for key in sorted(by_task, key=lambda item: by_task[item]["page_number"])]


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


def summarize_positions(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    by_model: dict[str, dict[str, int]] = {}
    for row in decisions:
        position = str(row.get("title_block_position") or "")
        model = str(row.get("model") or "")
        counts[position] = counts.get(position, 0) + 1
        by_model.setdefault(model, {})
        by_model[model][position] = by_model[model].get(position, 0) + 1
    return {"position_counts": counts, "position_counts_by_model": by_model}


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir)
    manifest_rows = load_csv_rows(output_dir / "vlm_png_manifest.csv")
    raw_rows = load_jsonl(output_dir / "vlm_raw_responses.jsonl")
    decisions = load_jsonl(output_dir / "vlm_decisions.jsonl")
    failed_keys = find_failed_keys(decisions)
    if not failed_keys:
        return {
            "record_version": RECORD_VERSION,
            "output_dir": as_posix(output_dir),
            "failed_before_retry": 0,
            "retry_attempted": 0,
            "message": "No failed rows found.",
        }

    retry_rows = build_retry_rows(failed_keys, manifest_rows)
    retry_raw_rows, env_summary = call_vlm_requests(
        retry_rows,
        args.env_file,
        args.timeout_seconds,
        args.retries,
        args.retry_sleep_seconds,
    )
    retry_decisions = [build_decision_row(row) for row in retry_raw_rows]
    retry_success_keys = {
        (str(row["task_id"]), str(row["model"]))
        for row in retry_decisions
        if row.get("api_ok") and row.get("parse_status") == "ok" and row.get("schema_status") == "ok"
    }

    retry_dir = output_dir / "retry_failures"
    retry_dir.mkdir(parents=True, exist_ok=True)
    stamp = args.retry_label
    retry_raw_path = retry_dir / f"{stamp}_raw_responses.jsonl"
    retry_decisions_path = retry_dir / f"{stamp}_decisions.jsonl"
    write_jsonl(retry_raw_path, [public_raw_row(row) for row in retry_raw_rows])
    write_jsonl(retry_decisions_path, retry_decisions)

    merged_raw_rows = replace_raw_rows(raw_rows, retry_raw_rows)
    merged_decisions = [build_decision_row(row) for row in merged_raw_rows]
    models = parse_models(args.models)
    comparisons = compare_decisions(merged_decisions, models)
    records = records_from_manifest(manifest_rows)
    review_rows_data = review_rows(records, merged_decisions, models)

    raw_path = output_dir / "vlm_raw_responses.jsonl"
    decisions_path = output_dir / "vlm_decisions.jsonl"
    decisions_csv_path = output_dir / "vlm_decisions.csv"
    comparison_path = output_dir / "dual_model_comparison.json"
    comparison_csv_path = output_dir / "dual_model_comparison.csv"
    summary_path = output_dir / "run_summary.json"
    previous_summary = load_json(summary_path)

    write_jsonl(raw_path, [public_raw_row(row) for row in merged_raw_rows])
    write_jsonl(decisions_path, merged_decisions)
    write_decisions_csv(decisions_csv_path, merged_decisions)
    write_json(comparison_path, comparisons)
    write_comparison_csv(comparison_csv_path, comparisons)

    source_pdf_value = previous_summary.get("source_pdf") or records[0].get("source_path")
    review_summary = publish_review_pack(
        output_dir,
        resolve_path(args.review_inbox),
        args.review_slug,
        args.review_title,
        Path(str(source_pdf_value)),
        records,
        merged_decisions,
        comparisons,
        review_rows_data,
        models,
    )

    remaining_failed = find_failed_keys(merged_decisions)
    summary = {
        **previous_summary,
        "record_version": previous_summary.get("record_version"),
        "raw_response_count": len(merged_raw_rows),
        "decision_count": len(merged_decisions),
        "comparison_count": len(comparisons),
        "decision_needs_review_count": sum(1 for row in merged_decisions if row.get("needs_review")),
        "comparison_needs_review_count": sum(1 for row in comparisons if row.get("needs_review")),
        "retry": {
            "record_version": RECORD_VERSION,
            "failed_before_retry": len(failed_keys),
            "retry_attempted": len(retry_rows),
            "retry_success_count": len(retry_success_keys),
            "remaining_failed_count": len(remaining_failed),
            "remaining_failed_keys": [{"task_id": task_id, "model": model} for task_id, model in remaining_failed],
            "retry_raw_responses": as_posix(retry_raw_path),
            "retry_decisions": as_posix(retry_decisions_path),
            "env_status": env_summary,
        },
        "position_summary": summarize_positions(merged_decisions),
        "outputs": {
            **previous_summary.get("outputs", {}),
            "review": review_summary,
            "summary": as_posix(summary_path),
        },
    }
    write_json(summary_path, summary)
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Retry failed rows for VLM title-block blind review.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--review-inbox", type=Path, default=DEFAULT_REVIEW_INBOX)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--models", default=DEFAULT_MODELS)
    parser.add_argument("--review-slug", default=DEFAULT_REVIEW_SLUG)
    parser.add_argument("--review-title", default=DEFAULT_REVIEW_TITLE)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--retry-sleep-seconds", type=float, default=3.0)
    parser.add_argument("--retry-label", default="retry_001")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
