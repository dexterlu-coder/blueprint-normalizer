from pathlib import Path
import tempfile
import unittest

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    from PyPDF2 import PdfReader, PdfWriter

from blueprint_normalizer.pdf_rotation_mvp.pdf_output import publish_final_pdfs, rotate_or_copy_pdf
from blueprint_normalizer.pdf_rotation_mvp.workflow import PageRecord


class PdfRotationMvpPdfOutputTests(unittest.TestCase):
    def test_rotate_or_copy_pdf_writes_corrected_pdf_for_valid_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            record = self._make_record(root, "valid_page_001")
            self._write_blank_pdf(record.split_pdf_path)

            row = rotate_or_copy_pdf(record, self._valid_decision(90), dry_run=False, root=root)

            reader = PdfReader(str(record.output_pdf_path))
            rotate_value = int(reader.pages[0].get("/Rotate", 0) or 0)

        self.assertEqual(row["task_id"], "valid_page_001")
        self.assertEqual(row["source_pdf"], "input/source.pdf")
        self.assertEqual(row["split_pdf_path"], "work/split/valid_page_001.pdf")
        self.assertEqual(row["rendered_png_path"], "work/png/valid_page_001.png")
        self.assertEqual(row["output_pdf_path"], "work/corrected/valid_page_001.pdf")
        self.assertEqual(row["output_status"], "corrected")
        self.assertEqual(row["original_pdf_rotate"], 0)
        self.assertEqual(row["applied_pdf_rotate_clockwise"], 90)
        self.assertFalse(row["needs_review"])
        self.assertEqual(row["output_blockers"], [])
        self.assertEqual(rotate_value, 90)

    def test_rotate_or_copy_pdf_copies_split_pdf_when_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            record = self._make_record(root, "dry_page_001")
            self._write_blank_pdf(record.split_pdf_path, rotate=180)

            row = rotate_or_copy_pdf(record, self._valid_decision(270), dry_run=True, root=root)

            output_reader = PdfReader(str(record.output_pdf_path))
            output_rotate = int(output_reader.pages[0].get("/Rotate", 0) or 0)

        self.assertEqual(row["output_status"], "copied_needs_review")
        self.assertEqual(row["original_pdf_rotate"], 180)
        self.assertEqual(row["applied_pdf_rotate_clockwise"], 0)
        self.assertTrue(row["needs_review"])
        self.assertEqual(row["output_blockers"], ["dry_run"])
        self.assertEqual(output_rotate, 180)

    def test_rotate_or_copy_pdf_copies_split_pdf_when_quality_gate_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            record = self._make_record(root, "blocked_page_001")
            self._write_blank_pdf(record.split_pdf_path)

            row = rotate_or_copy_pdf(
                record,
                {
                    "api_ok": False,
                    "parse_status": "error",
                    "schema_status": "error",
                    "correction_clockwise_degrees": "unknown",
                },
                dry_run=False,
                root=root,
            )
            output_exists = record.output_pdf_path.exists()

        self.assertEqual(row["output_status"], "copied_needs_review")
        self.assertTrue(row["needs_review"])
        self.assertEqual(
            row["output_blockers"],
            [
                "api_not_ok",
                "parse_not_ok",
                "schema_not_ok",
                "missing_or_invalid_correction_degrees",
            ],
        )
        self.assertTrue(output_exists)

    def test_rotate_or_copy_pdf_accepts_zero_degree_correction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            record = self._make_record(root, "upright_page_001")
            self._write_blank_pdf(record.split_pdf_path)

            row = rotate_or_copy_pdf(record, self._valid_decision(0), dry_run=False, root=root)

            reader = PdfReader(str(record.output_pdf_path))
            rotate_value = int(reader.pages[0].get("/Rotate", 0) or 0)

        self.assertEqual(row["output_status"], "corrected")
        self.assertEqual(row["applied_pdf_rotate_clockwise"], 0)
        self.assertEqual(rotate_value, 0)

    def test_publish_final_pdfs_writes_published_output_for_clean_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "output"
            record = self._make_record(root, "publish_page_001")
            self._write_blank_pdf(record.output_pdf_path)

            rows = publish_final_pdfs(
                [record],
                rotation_decisions=[{"task_id": record.task_id, "needs_review": False}],
                rotation_outputs=[{"task_id": record.task_id, "output_status": "corrected"}],
                drawing_number_decisions=[self._drawing_decision(record, "JS2207-01")],
                output_dir=output_dir,
                dry_run=False,
                root=root,
            )
            target_path = output_dir / "source" / "JS2207-01.pdf"
            target_exists = target_path.exists()

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["task_id"], "publish_page_001")
        self.assertEqual(row["source_pdf"], "input/source.pdf")
        self.assertEqual(row["drawing_number"], "JS2207-01")
        self.assertEqual(row["final_filename_stem"], "JS2207-01")
        self.assertEqual(row["final_pdf_path"], "output/source/JS2207-01.pdf")
        self.assertEqual(row["corrected_pdf_path"], "work/corrected/publish_page_001.pdf")
        self.assertEqual(row["final_status"], "published")
        self.assertFalse(row["needs_review"])
        self.assertEqual(row["final_blockers"], [])
        self.assertTrue(target_exists)

    def test_publish_final_pdfs_routes_to_needs_review_for_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "output"
            record = self._make_record(root, "dry_publish_page_001")
            self._write_blank_pdf(record.output_pdf_path)

            rows = publish_final_pdfs(
                [record],
                rotation_decisions=[{"task_id": record.task_id, "needs_review": False}],
                rotation_outputs=[{"task_id": record.task_id, "output_status": "corrected"}],
                drawing_number_decisions=[self._drawing_decision(record, "JS2207-01")],
                output_dir=output_dir,
                dry_run=True,
                root=root,
            )
            target_path = output_dir / "source" / "needs_review" / "dry_publish_page_001.pdf"
            target_exists = target_path.exists()

        self.assertEqual(rows[0]["final_status"], "needs_review")
        self.assertTrue(rows[0]["needs_review"])
        self.assertEqual(rows[0]["final_blockers"], ["dry_run"])
        self.assertEqual(rows[0]["final_pdf_path"], "output/source/needs_review/dry_publish_page_001.pdf")
        self.assertTrue(target_exists)

    def test_publish_final_pdfs_blocks_duplicate_drawing_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "output"
            first = self._make_record(root, "dup_page_001")
            second = self._make_record(root, "dup_page_002")
            self._write_blank_pdf(first.output_pdf_path)
            self._write_blank_pdf(second.output_pdf_path)

            rows = publish_final_pdfs(
                [first, second],
                rotation_decisions=[
                    {"task_id": first.task_id, "needs_review": False},
                    {"task_id": second.task_id, "needs_review": False},
                ],
                rotation_outputs=[
                    {"task_id": first.task_id, "output_status": "corrected"},
                    {"task_id": second.task_id, "output_status": "corrected"},
                ],
                drawing_number_decisions=[
                    self._drawing_decision(first, "JS2207-01"),
                    self._drawing_decision(second, "JS2207-01"),
                ],
                output_dir=output_dir,
                dry_run=False,
                root=root,
            )

        self.assertEqual([row["final_status"] for row in rows], ["needs_review", "needs_review"])
        self.assertEqual(rows[0]["final_blockers"], ["duplicate_drawing_number"])
        self.assertEqual(rows[1]["final_blockers"], ["duplicate_drawing_number"])

    def test_publish_final_pdfs_blocks_missing_drawing_number_and_failed_rotation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "output"
            record = self._make_record(root, "blocked_publish_page_001")
            self._write_blank_pdf(record.output_pdf_path)

            rows = publish_final_pdfs(
                [record],
                rotation_decisions=[{"task_id": record.task_id, "needs_review": True}],
                rotation_outputs=[{"task_id": record.task_id, "output_status": "copied_needs_review"}],
                drawing_number_decisions=[
                    {
                        "task_id": record.task_id,
                        "source_pdf": "input/source.pdf",
                        "selected_drawing_number": "",
                        "final_filename_stem": "",
                        "api_ok": False,
                        "parse_status": "error",
                        "schema_status": "error",
                        "needs_review": True,
                    }
                ],
                output_dir=output_dir,
                dry_run=False,
                root=root,
            )

        self.assertEqual(rows[0]["final_status"], "needs_review")
        self.assertEqual(
            rows[0]["final_blockers"],
            [
                "drawing_number_api_not_ok",
                "drawing_number_decision_needs_review",
                "drawing_number_parse_not_ok",
                "drawing_number_schema_not_ok",
                "missing_final_filename_stem",
                "rotation_decision_needs_review",
                "rotation_output_not_corrected",
            ],
        )

    def _make_record(self, root: Path, task_id: str) -> PageRecord:
        return PageRecord(
            source_pdf=root / "input" / "source.pdf",
            source_stem="source",
            page_number=1,
            page_count=1,
            task_id=task_id,
            split_pdf_path=root / "work" / "split" / f"{task_id}.pdf",
            rendered_png_path=root / "work" / "png" / f"{task_id}.png",
            output_pdf_path=root / "work" / "corrected" / f"{task_id}.pdf",
        )

    def _write_blank_pdf(self, path: Path, rotate: int = 0) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        if rotate:
            writer.pages[0].rotate(rotate)
        with path.open("wb") as handle:
            writer.write(handle)

    def _valid_decision(self, correction: int) -> dict[str, object]:
        return {
            "api_ok": True,
            "parse_status": "ok",
            "schema_status": "ok",
            "correction_clockwise_degrees": correction,
        }

    def _drawing_decision(self, record: PageRecord, drawing_number: str) -> dict[str, object]:
        return {
            "task_id": record.task_id,
            "source_pdf": "input/source.pdf",
            "selected_drawing_number": drawing_number,
            "final_filename_stem": drawing_number,
            "api_ok": True,
            "parse_status": "ok",
            "schema_status": "ok",
            "needs_review": False,
        }


if __name__ == "__main__":
    unittest.main()
