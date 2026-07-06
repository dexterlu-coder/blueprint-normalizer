from pathlib import Path
import unittest

from blueprint_normalizer.pdf_rotation_mvp.workflow import (
    PageRecord,
    build_report_rows,
    image_records_from_pages,
)


class PdfRotationMvpWorkflowTests(unittest.TestCase):
    def test_image_records_from_pages_preserves_task_fields(self) -> None:
        root = Path(__file__).resolve().parents[2]
        page = PageRecord(
            source_pdf=root / "tools" / "pdf_rotation_mvp" / "input" / "demo.pdf",
            source_stem="demo",
            page_number=2,
            page_count=5,
            task_id="demo_p002",
            split_pdf_path=root / "tools" / "pdf_rotation_mvp" / "work" / "demo_p002.pdf",
            rendered_png_path=root / "tools" / "pdf_rotation_mvp" / "work" / "demo_p002.png",
            output_pdf_path=root / "tools" / "pdf_rotation_mvp" / "output" / "demo_p002.pdf",
        )

        image_records = image_records_from_pages([page])

        self.assertEqual(len(image_records), 1)
        image = image_records[0]
        self.assertEqual(image.source_pdf, page.source_pdf)
        self.assertEqual(image.source_stem, "demo")
        self.assertEqual(image.page_number, 2)
        self.assertEqual(image.task_id, "demo_p002")
        self.assertEqual(image.image_path, page.rendered_png_path)

    def test_build_report_rows_merges_stage_results_by_task_id(self) -> None:
        root = Path(__file__).resolve().parents[2]
        page = PageRecord(
            source_pdf=root / "input" / "source.pdf",
            source_stem="source",
            page_number=1,
            page_count=1,
            task_id="source_p001",
            split_pdf_path=root / "work" / "source_p001.pdf",
            rendered_png_path=root / "work" / "source_p001.png",
            output_pdf_path=root / "output" / "source_p001.pdf",
        )

        rows = build_report_rows(
            [page],
            decisions=[
                {
                    "task_id": "source_p001",
                    "title_block_position": "right_edge",
                    "current_clockwise_degrees": 270,
                    "correction_clockwise_degrees": 90,
                    "confidence": 0.93,
                    "api_ok": True,
                    "parse_status": "ok",
                    "schema_status": "ok",
                    "review_reasons": ["model:clear_title_block"],
                }
            ],
            outputs=[
                {
                    "task_id": "source_p001",
                    "output_pdf_path": "output/source_p001.pdf",
                    "output_status": "corrected",
                    "output_blockers": [],
                }
            ],
            drawing_decisions=[
                {
                    "task_id": "source_p001",
                    "selected_drawing_number": "JS2207-01",
                    "api_ok": True,
                    "parse_status": "ok",
                    "schema_status": "ok",
                    "confidence": 0.88,
                    "review_reasons": [],
                }
            ],
            final_outputs=[
                {
                    "task_id": "source_p001",
                    "final_pdf_path": "output/source/JS2207-01.pdf",
                    "final_status": "published",
                    "final_filename_stem": "JS2207-01",
                    "needs_review": False,
                    "final_blockers": [],
                }
            ],
            root=root,
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["source_pdf"], "input/source.pdf")
        self.assertEqual(row["page_number"], 1)
        self.assertEqual(row["title_block_position"], "right_edge")
        self.assertEqual(row["correction_clockwise_degrees"], 90)
        self.assertEqual(row["drawing_number"], "JS2207-01")
        self.assertEqual(row["final_pdf_path"], "output/source/JS2207-01.pdf")
        self.assertEqual(row["final_status"], "published")
        self.assertFalse(row["needs_review"])
        self.assertEqual(row["review_reasons"], "model:clear_title_block")
        self.assertEqual(row["output_blockers"], "")

    def test_build_report_rows_uses_empty_values_for_missing_stage_results(self) -> None:
        root = Path(__file__).resolve().parents[2]
        page = PageRecord(
            source_pdf=root / "input" / "missing.pdf",
            source_stem="missing",
            page_number=1,
            page_count=1,
            task_id="missing_p001",
            split_pdf_path=root / "work" / "missing_p001.pdf",
            rendered_png_path=root / "work" / "missing_p001.png",
            output_pdf_path=root / "output" / "missing_p001.pdf",
        )

        row = build_report_rows([page], [], [], [], [], root=root)[0]

        self.assertEqual(row["source_pdf"], "input/missing.pdf")
        self.assertEqual(row["page_number"], 1)
        self.assertEqual(row["final_pdf_path"], "")
        self.assertEqual(row["drawing_number"], "")
        self.assertEqual(row["api_ok"], "")
        self.assertEqual(row["needs_review"], "")
        self.assertEqual(row["final_blockers"], "")


if __name__ == "__main__":
    unittest.main()
