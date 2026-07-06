from pathlib import Path
import unittest

from blueprint_normalizer.paths import APP_CONFIG_FILENAME, config_candidates, project_root


ROOT = Path(__file__).resolve().parents[2]


class PathTests(unittest.TestCase):
    def test_project_root_can_be_found_from_tests(self) -> None:
        self.assertEqual(project_root(ROOT / "tests"), ROOT)

    def test_config_candidates_default_to_project_config(self) -> None:
        candidates = config_candidates()

        self.assertIn(ROOT / APP_CONFIG_FILENAME, candidates)


if __name__ == "__main__":
    unittest.main()
