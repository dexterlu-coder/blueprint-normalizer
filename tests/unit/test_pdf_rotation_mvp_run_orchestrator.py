from pathlib import Path
import tempfile
import unittest

from blueprint_normalizer.pdf_rotation_mvp.pipeline import build_run_disabled_report


class PdfRotationMvpRunOrchestratorTests(unittest.TestCase):
    def test_run_disabled_report_does_not_execute_side_effects(self) -> None:
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
                        "dry_run = false",
                    ]
                ),
                encoding="utf-8",
            )

            report = build_run_disabled_report(config_path)

            self.assertFalse(report["ok"])
            self.assertEqual(report["mode"], "pdf_rotation_mvp_run_disabled")
            self.assertFalse(report["run_enabled"])
            self.assertEqual(report["blockers"], ["run_not_enabled"])
            self.assertFalse(any(report["side_effects"].values()))
            self.assertEqual(report["config"]["status"], "ok")
            self.assertEqual(report["qwen"]["model"], "qwen-test")
            self.assertEqual(report["execution_plan"]["summary"]["step_count"], 11)
            self.assertIn("split_pdf_pages", [step["step_id"] for step in report["execution_plan"]["steps"]])
            self.assertIn("request_rotation_vlm", report["execution_plan"]["summary"]["side_effect_step_ids"])
            self.assertFalse((temp_path / "input").exists())
            self.assertFalse((temp_path / "output").exists())
            self.assertFalse((temp_path / "work").exists())
            self.assertFalse((temp_path / "logs").exists())

    def test_run_disabled_report_keeps_config_errors_visible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_config = Path(temp_dir) / "missing.toml"

            report = build_run_disabled_report(missing_config)

        self.assertFalse(report["ok"])
        self.assertEqual(report["mode"], "pdf_rotation_mvp_run_disabled")
        self.assertEqual(report["config"]["status"], "failed")
        self.assertIn("run_not_enabled", report["blockers"])
        self.assertIn("config_not_ok", report["blockers"])
        self.assertFalse(any(report["side_effects"].values()))


if __name__ == "__main__":
    unittest.main()
