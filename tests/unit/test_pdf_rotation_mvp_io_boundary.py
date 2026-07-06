from pathlib import Path
import tempfile
import unittest

from blueprint_normalizer.pdf_rotation_mvp.io_boundary import (
    collect_input_pdfs,
    ensure_child_dir,
    ensure_path_under_root,
)


class PdfRotationMvpIoBoundaryTests(unittest.TestCase):
    def test_collect_input_pdfs_reports_missing_and_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)

            with self.assertRaises(FileNotFoundError):
                collect_input_pdfs(base / "missing")

            empty = base / "empty"
            empty.mkdir()
            with self.assertRaises(FileNotFoundError):
                collect_input_pdfs(empty)

    def test_collect_input_pdfs_filters_pdf_files_without_recursing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "input"
            nested = input_dir / "nested"
            nested.mkdir(parents=True)
            (input_dir / "b.PDF").write_text("not a real pdf", encoding="utf-8")
            (input_dir / "a.pdf").write_text("not a real pdf", encoding="utf-8")
            (input_dir / "notes.txt").write_text("ignore me", encoding="utf-8")
            (nested / "z.pdf").write_text("ignore nested", encoding="utf-8")

            pdfs = collect_input_pdfs(input_dir)

            self.assertEqual([path.name for path in pdfs], ["a.pdf", "b.PDF"])

    def test_ensure_path_under_root_rejects_root_and_outside_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir).resolve()
            child = base / "child"
            outside = base.parent / f"{base.name}_outside"

            self.assertEqual(ensure_path_under_root(child, base), child.resolve())
            with self.assertRaises(ValueError):
                ensure_path_under_root(base, base)
            with self.assertRaises(ValueError):
                ensure_path_under_root(outside, base)

    def test_ensure_child_dir_creates_only_controlled_child_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            target = base / "output" / "run"

            resolved = ensure_child_dir(target, base)

            self.assertEqual(resolved, target.resolve())
            self.assertTrue(target.is_dir())
            with self.assertRaises(ValueError):
                ensure_child_dir(base, base)


if __name__ == "__main__":
    unittest.main()
