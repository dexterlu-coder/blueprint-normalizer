from pathlib import Path
import tempfile
import unittest

from blueprint_normalizer.pdf_rotation_mvp.domain import RECORD_VERSION
from blueprint_normalizer.pdf_rotation_mvp.run_summary import build_run_summary
from blueprint_normalizer.pdf_rotation_mvp.workflow import PageRecord


class PdfRotationMvpRunSummaryTests(unittest.TestCase):
    def test_build_run_summary_counts_stage_results_and_uses_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "input"
            output_dir = root / "output"
            work_dir = root / "work"
            source_pdfs = [input_dir / "a.pdf", input_dir / "b.pdf"]
            records = [
                PageRecord(
                    source_pdf=source_pdfs[0],
                    source_stem="a",
                    page_number=1,
                    page_count=2,
                    task_id="a_page_001",
                    split_pdf_path=work_dir / "split" / "a_page_001.pdf",
                    rendered_png_path=work_dir / "png" / "a_page_001.png",
                    output_pdf_path=output_dir / "a" / "a_page_001.pdf",
                ),
                PageRecord(
                    source_pdf=source_pdfs[0],
                    source_stem="a",
                    page_number=2,
                    page_count=2,
                    task_id="a_page_002",
                    split_pdf_path=work_dir / "split" / "a_page_002.pdf",
                    rendered_png_path=work_dir / "png" / "a_page_002.png",
                    output_pdf_path=output_dir / "a" / "a_page_002.pdf",
                ),
            ]

            summary = build_run_summary(
                input_dir=input_dir,
                output_dir=output_dir,
                work_dir=work_dir,
                model="qwen-vl-plus",
                dry_run=True,
                source_pdfs=source_pdfs,
                records=records,
                decisions=[
                    {"api_ok": True, "parse_status": "ok", "schema_status": "ok"},
                    {"api_ok": False, "parse_status": "error", "schema_status": "error"},
                ],
                outputs=[
                    {"output_status": "corrected"},
                    {"output_status": "copied_needs_review"},
                ],
                drawing_decisions=[
                    {"api_ok": True, "parse_status": "ok", "schema_status": "ok", "selected_drawing_number": "JS2207-01"},
                    {"api_ok": True, "parse_status": "ok", "schema_status": "error", "selected_drawing_number": ""},
                ],
                final_outputs=[
                    {"final_status": "published"},
                    {"final_status": "needs_review"},
                ],
                env_summary={"variables": {"DASHSCOPE_API_KEY": {"present": False}}},
                root=root,
            )

        self.assertEqual(summary["record_version"], RECORD_VERSION)
        self.assertEqual(summary["input_dir"], "input")
        self.assertEqual(summary["output_dir"], "output")
        self.assertEqual(summary["work_dir"], "work")
        self.assertEqual(summary["model"], "qwen-vl-plus")
        self.assertEqual(summary["temperature"], 0)
        self.assertFalse(summary["enable_thinking"])
        self.assertEqual(summary["top_p"], "not_set")
        self.assertTrue(summary["dry_run"])
        self.assertEqual(summary["source_pdf_count"], 2)
        self.assertEqual(summary["page_count"], 2)
        self.assertEqual(summary["orientation_api_ok_count"], 1)
        self.assertEqual(summary["orientation_parse_ok_count"], 1)
        self.assertEqual(summary["orientation_schema_ok_count"], 1)
        self.assertEqual(summary["drawing_number_api_ok_count"], 2)
        self.assertEqual(summary["drawing_number_parse_ok_count"], 2)
        self.assertEqual(summary["drawing_number_schema_ok_count"], 1)
        self.assertEqual(summary["drawing_number_non_empty_count"], 1)
        self.assertEqual(summary["corrected_count"], 1)
        self.assertEqual(summary["copied_needs_review_count"], 1)
        self.assertEqual(summary["published_count"], 1)
        self.assertEqual(summary["final_needs_review_count"], 1)
        self.assertEqual(summary["env_status"], {"variables": {"DASHSCOPE_API_KEY": {"present": False}}})
        self.assertEqual(summary["outputs"]["report_csv"], "output/report.csv")
        self.assertEqual(summary["outputs"]["needs_review_csv"], "output/needs_review.csv")
        self.assertEqual(summary["outputs"]["summary_json"], "output/summary.json")
        self.assertEqual(summary["outputs"]["orientation_raw_responses_jsonl"], "work/orientation_raw_responses.jsonl")
        self.assertEqual(summary["outputs"]["orientation_decisions_jsonl"], "work/orientation_decisions.jsonl")
        self.assertEqual(
            summary["outputs"]["drawing_number_raw_responses_jsonl"],
            "work/drawing_number_raw_responses.jsonl",
        )
        self.assertEqual(summary["outputs"]["drawing_number_decisions_jsonl"], "work/drawing_number_decisions.jsonl")
        self.assertEqual(summary["outputs"]["rotation_output_records_jsonl"], "work/rotation_output_records.jsonl")
        self.assertEqual(summary["outputs"]["final_output_records_jsonl"], "work/final_output_records.jsonl")

    def test_build_run_summary_treats_non_published_final_outputs_as_needing_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary = build_run_summary(
                input_dir=root / "input",
                output_dir=root / "output",
                work_dir=root / "work",
                model="qwen-vl-plus",
                dry_run=False,
                source_pdfs=[],
                records=[],
                decisions=[],
                outputs=[],
                drawing_decisions=[],
                final_outputs=[{"final_status": "blocked"}, {"final_status": ""}, {}],
                env_summary={},
                root=root,
            )

        self.assertFalse(summary["dry_run"])
        self.assertEqual(summary["published_count"], 0)
        self.assertEqual(summary["final_needs_review_count"], 3)


if __name__ == "__main__":
    unittest.main()
