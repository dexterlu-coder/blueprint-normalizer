"""PDF output helpers for the PDF rotation MVP."""

from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path
from typing import Any

try:  # pragma: no cover - fallback depends on installed PDF package.
    from pypdf import PdfReader, PdfWriter
except ImportError:  # pragma: no cover
    from PyPDF2 import PdfReader, PdfWriter

from blueprint_normalizer.pdf_rotation_mvp.workflow import PageRecord, as_posix


def rotate_or_copy_pdf(
    record: PageRecord,
    decision: dict[str, Any],
    dry_run: bool,
    root: Path | None = None,
) -> dict[str, Any]:
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
        "source_pdf": as_posix(record.source_pdf, root),
        "page_number": record.page_number,
        "split_pdf_path": as_posix(record.split_pdf_path, root),
        "rendered_png_path": as_posix(record.rendered_png_path, root),
        "output_pdf_path": as_posix(record.output_pdf_path, root),
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
    root: Path | None = None,
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
                "source_pdf": as_posix(record.source_pdf, root),
                "page_number": record.page_number,
                "drawing_number": drawing.get("selected_drawing_number", "") if drawing else "",
                "final_filename_stem": filename_stem,
                "final_pdf_path": as_posix(target_path, root),
                "corrected_pdf_path": as_posix(source_pdf_path, root),
                "final_status": final_status,
                "needs_review": final_status != "published",
                "final_blockers": sorted(dict.fromkeys(final_blockers)),
            }
        )
    return final_rows
