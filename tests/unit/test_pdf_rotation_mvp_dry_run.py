from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class PdfRotationMvpDryRunTests(unittest.TestCase):
    def test_cli_dry_run_uses_explicit_config_and_redacts_secret(self) -> None:
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

            result = self._run_module("pdf-rotation-mvp", "dry-run", "--config", str(config_path))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("fake-secret-value", result.stdout)
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"])
            self.assertEqual(report["config"]["source"], "explicit")
            self.assertEqual(report["config"]["path"], str(config_path.resolve()))
            self.assertEqual(report["qwen"]["model"], "qwen-test")
            self.assertTrue(report["qwen"]["api_key_present"])
            self.assertEqual(report["config"]["redacted"]["qwen"]["api_key"], "<redacted>")
            self.assertFalse((temp_path / "input").exists())
            self.assertFalse((temp_path / "output").exists())
            self.assertFalse((temp_path / "work").exists())
            self.assertFalse((temp_path / "logs").exists())

    def test_cli_dry_run_reports_side_effects_disabled(self) -> None:
        config_path = ROOT / "etc" / "blueprint-normalizer.example.toml"

        result = self._run_module("pdf-rotation-mvp", "dry-run", "--config", str(config_path))

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["mode"], "pdf_rotation_mvp_dry_run")
        self.assertFalse(any(report["side_effects"].values()))

    def _run_module(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "blueprint_normalizer", *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
