from pathlib import Path
import os
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]


class CliTests(unittest.TestCase):
    def test_module_help_returns_zero(self) -> None:
        result = self._run_module("--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("blueprint-normalizer", result.stdout)

    def test_config_check_does_not_print_secret_value(self) -> None:
        config_path = ROOT / "etc" / "blueprint-normalizer.example.toml"

        result = self._run_module("config", "check", "--config", str(config_path))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Status: OK", result.stdout)
        self.assertNotIn("api_key =", result.stdout)

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
