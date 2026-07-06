from pathlib import Path
import tempfile
import unittest

from blueprint_normalizer.pdf_rotation_mvp.runtime_config import load_mvp_run_config


class PdfRotationMvpRuntimeConfigTests(unittest.TestCase):
    def test_explicit_config_builds_runtime_config_without_secret_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            config_path = base / "blueprint-normalizer.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[qwen]",
                        'api_key = "fake-secret-value"',
                        'base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"',
                        'model = "qwen-test"',
                        "temperature = 0",
                        "enable_thinking = false",
                        'top_p = ""',
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

            run_config = load_mvp_run_config(config_path)

            self.assertTrue(run_config.config_ok)
            self.assertEqual(run_config.config_source, "explicit")
            self.assertEqual(run_config.config_path, config_path.resolve())
            self.assertEqual(run_config.qwen.model, "qwen-test")
            self.assertTrue(run_config.qwen.api_key_present)
            self.assertEqual(run_config.redacted_config["qwen"]["api_key"], "<redacted>")
            self.assertNotIn("fake-secret-value", str(run_config.config_report()))
            self.assertEqual(run_config.paths["input_dir"].resolved, (base / "input").resolve())
            self.assertFalse((base / "input").exists())
            self.assertFalse((base / "output").exists())
            self.assertFalse((base / "work").exists())
            self.assertFalse((base / "logs").exists())

    def test_missing_default_config_reports_failure_without_creating_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path.cwd()
            try:
                import os

                os.chdir(temp_dir)
                run_config = load_mvp_run_config()
            finally:
                os.chdir(cwd)

            self.assertFalse(run_config.config_ok)
            self.assertEqual(run_config.config_source, "missing")
            self.assertIn("Config file does not exist.", run_config.errors)
            self.assertEqual(run_config.redacted_config, {})


if __name__ == "__main__":
    unittest.main()
