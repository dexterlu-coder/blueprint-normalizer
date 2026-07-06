from pathlib import Path
import unittest

from blueprint_normalizer.config import check_config, load_toml, redacted_copy


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_CONFIG = ROOT / "etc" / "blueprint-normalizer.example.toml"


class ConfigTests(unittest.TestCase):
    def test_example_config_loads(self) -> None:
        data = load_toml(EXAMPLE_CONFIG)

        self.assertIn("qwen", data)
        self.assertIn("paths", data)
        self.assertIn("runtime", data)

    def test_example_config_check_passes_without_real_key(self) -> None:
        result = check_config(EXAMPLE_CONFIG)

        self.assertTrue(result.ok)
        self.assertEqual(result.errors, ())
        self.assertTrue(any("credentials" in warning for warning in result.warnings))

    def test_redacted_copy_masks_secret_fields(self) -> None:
        data = {"qwen": {"api_key": "secret-value", "model": "model-name"}}

        redacted = redacted_copy(data)

        self.assertEqual(redacted["qwen"]["api_key"], "<redacted>")
        self.assertEqual(redacted["qwen"]["model"], "model-name")


if __name__ == "__main__":
    unittest.main()
