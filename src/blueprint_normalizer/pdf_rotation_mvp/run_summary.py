"""Run summary aggregation for the PDF rotation MVP."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from blueprint_normalizer.pdf_rotation_mvp.domain import RECORD_VERSION
from blueprint_normalizer.pdf_rotation_mvp.workflow import PageRecord, as_posix


def _count(rows: Sequence[dict[str, Any]], key: str, value: Any) -> int:
    return sum(1 for row in rows if row.get(key) == value)


def build_run_summary(
    *,
    input_dir: Path,
    output_dir: Path,
    work_dir: Path,
    model: str,
    dry_run: bool,
    source_pdfs: Sequence[Path],
    records: Sequence[PageRecord],
    decisions: Sequence[dict[str, Any]],
    outputs: Sequence[dict[str, Any]],
    drawing_decisions: Sequence[dict[str, Any]],
    final_outputs: Sequence[dict[str, Any]],
    env_summary: dict[str, Any],
    root: Path | None = None,
) -> dict[str, Any]:
    return {
        "record_version": RECORD_VERSION,
        "input_dir": as_posix(input_dir, root),
        "output_dir": as_posix(output_dir, root),
        "work_dir": as_posix(work_dir, root),
        "model": model,
        "temperature": 0,
        "enable_thinking": False,
        "top_p": "not_set",
        "dry_run": bool(dry_run),
        "source_pdf_count": len(source_pdfs),
        "page_count": len(records),
        "orientation_api_ok_count": _count(decisions, "api_ok", True),
        "orientation_parse_ok_count": _count(decisions, "parse_status", "ok"),
        "orientation_schema_ok_count": _count(decisions, "schema_status", "ok"),
        "drawing_number_api_ok_count": _count(drawing_decisions, "api_ok", True),
        "drawing_number_parse_ok_count": _count(drawing_decisions, "parse_status", "ok"),
        "drawing_number_schema_ok_count": _count(drawing_decisions, "schema_status", "ok"),
        "drawing_number_non_empty_count": sum(1 for row in drawing_decisions if row.get("selected_drawing_number")),
        "corrected_count": _count(outputs, "output_status", "corrected"),
        "copied_needs_review_count": _count(outputs, "output_status", "copied_needs_review"),
        "published_count": _count(final_outputs, "final_status", "published"),
        "final_needs_review_count": sum(1 for row in final_outputs if row.get("final_status") != "published"),
        "env_status": env_summary,
        "outputs": {
            "report_csv": as_posix(output_dir / "report.csv", root),
            "needs_review_csv": as_posix(output_dir / "needs_review.csv", root),
            "summary_json": as_posix(output_dir / "summary.json", root),
            "orientation_raw_responses_jsonl": as_posix(work_dir / "orientation_raw_responses.jsonl", root),
            "orientation_decisions_jsonl": as_posix(work_dir / "orientation_decisions.jsonl", root),
            "drawing_number_raw_responses_jsonl": as_posix(work_dir / "drawing_number_raw_responses.jsonl", root),
            "drawing_number_decisions_jsonl": as_posix(work_dir / "drawing_number_decisions.jsonl", root),
            "rotation_output_records_jsonl": as_posix(work_dir / "rotation_output_records.jsonl", root),
            "final_output_records_jsonl": as_posix(work_dir / "final_output_records.jsonl", root),
        },
    }
