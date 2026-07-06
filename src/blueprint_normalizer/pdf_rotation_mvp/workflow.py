"""Side-effect-free workflow records for the PDF rotation MVP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from blueprint_normalizer.paths import project_root


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


def as_posix(path: Path | str | None, root: Path | None = None) -> str | None:
    if path is None:
        return None
    path_obj = Path(path)
    base = (root or project_root()).resolve()
    try:
        return path_obj.resolve().relative_to(base).as_posix()
    except ValueError:
        return path_obj.as_posix()


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


def build_report_rows(
    records: list[PageRecord],
    decisions: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
    drawing_decisions: list[dict[str, Any]],
    final_outputs: list[dict[str, Any]],
    root: Path | None = None,
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
                "source_pdf": as_posix(record.source_pdf, root),
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
