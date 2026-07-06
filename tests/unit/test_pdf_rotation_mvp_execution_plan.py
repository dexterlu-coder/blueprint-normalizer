from pathlib import Path
import tempfile
import unittest

from blueprint_normalizer.pdf_rotation_mvp.execution_plan import build_execution_plan
from blueprint_normalizer.pdf_rotation_mvp.pipeline import build_dry_run_report
from blueprint_normalizer.pdf_rotation_mvp.runtime_config import load_mvp_run_config


class PdfRotationMvpExecutionPlanTests(unittest.TestCase):
    def test_execution_plan_step_order_and_side_effect_markers(self) -> None:
        config_path = Path(__file__).resolve().parents[2] / "etc" / "blueprint-normalizer.example.toml"
        run_config = load_mvp_run_config(config_path)

        plan = build_execution_plan(run_config)

        self.assertEqual(
            [step.step_id for step in plan.steps],
            [
                "load_config",
                "collect_input_pdfs",
                "prepare_work_dirs",
                "split_pdf_pages",
                "render_pages_with_ghostscript",
                "request_rotation_vlm",
                "correct_or_copy_pdf",
                "crop_title_block",
                "request_drawing_number_vlm",
                "publish_final_pdfs",
                "write_reports",
            ],
        )

        by_id = {step.step_id: step for step in plan.steps}
        self.assertTrue(by_id["render_pages_with_ghostscript"].reads_pdf)
        self.assertTrue(by_id["render_pages_with_ghostscript"].writes_files)
        self.assertTrue(by_id["render_pages_with_ghostscript"].calls_external_command)
        self.assertTrue(by_id["request_rotation_vlm"].calls_model_endpoint)
        self.assertTrue(by_id["request_drawing_number_vlm"].calls_model_endpoint)
        self.assertTrue(by_id["publish_final_pdfs"].reads_pdf)
        self.assertTrue(by_id["publish_final_pdfs"].writes_files)
        self.assertFalse(by_id["load_config"].has_side_effects)
        self.assertTrue(by_id["load_config"].enabled_for_dry_run)

    def test_dry_run_report_includes_plan_without_executing_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "blueprint-normalizer.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[qwen]",
                        'api_key = "fake-secret-value"',
                        'base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"',
                        'model = "qwen-test"',
                        "temperature = 0",
                        "enable_thinking = false",
                        "",
                        "[paths]",
                        'input_dir = "input"',
                        'output_dir = "output"',
                        'work_dir = "work"',
                        'log_dir = "logs"',
                        "",
                        "[runtime]",
                        "keep_work_files = true",
                        "dry_run = true",
                    ]
                ),
                encoding="utf-8",
            )

            report = build_dry_run_report(config_path)

            self.assertTrue(report["ok"])
            self.assertFalse(any(report["side_effects"].values()))
            self.assertEqual(report["execution_plan"]["summary"]["step_count"], 11)
            self.assertTrue(report["execution_plan"]["summary"]["future_run_reads_pdf"])
            self.assertTrue(report["execution_plan"]["summary"]["future_run_writes_files"])
            self.assertTrue(report["execution_plan"]["summary"]["future_run_calls_external_command"])
            self.assertTrue(report["execution_plan"]["summary"]["future_run_calls_model_endpoint"])
            self.assertFalse(report["execution_plan"]["summary"]["future_run_touches_review_inbox"])
            self.assertIn("render_pages_with_ghostscript", report["execution_plan"]["summary"]["side_effect_step_ids"])
            self.assertIn("request_rotation_vlm", report["execution_plan"]["summary"]["side_effect_step_ids"])
            collect_step = report["execution_plan"]["steps"][1]
            prepare_step = report["execution_plan"]["steps"][2]
            self.assertIn(str((temp_path / "input").resolve()), collect_step["description"])
            self.assertIn(str((temp_path / "output").resolve()), prepare_step["description"])
            self.assertFalse((temp_path / "input").exists())
            self.assertFalse((temp_path / "output").exists())
            self.assertFalse((temp_path / "work").exists())
            self.assertFalse((temp_path / "logs").exists())


if __name__ == "__main__":
    unittest.main()
