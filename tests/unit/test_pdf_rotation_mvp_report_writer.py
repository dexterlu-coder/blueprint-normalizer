import csv
import json
from pathlib import Path
import tempfile
import unittest

from blueprint_normalizer.pdf_rotation_mvp.report_writer import write_csv, write_json, write_jsonl


class PdfRotationMvpReportWriterTests(unittest.TestCase):
    def test_write_json_uses_utf8_indent_and_trailing_newline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "nested" / "summary.json"

            write_json(path, {"图号": "JS2207-01", "ok": True})

            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.endswith("\n"))
            self.assertIn('"图号": "JS2207-01"', text)
            self.assertEqual(json.loads(text), {"图号": "JS2207-01", "ok": True})

    def test_write_jsonl_writes_one_json_object_per_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "logs" / "rows.jsonl"

            write_jsonl(path, [{"id": 1, "名称": "第一页"}, {"id": 2, "名称": "第二页"}])

            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0]), {"id": 1, "名称": "第一页"})
            self.assertEqual(json.loads(lines[1]), {"id": 2, "名称": "第二页"})

    def test_write_csv_uses_utf8_sig_and_ignores_extra_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "reports" / "report.csv"

            write_csv(
                path,
                [{"task_id": "p001", "drawing_number": "JS2207-01", "extra": "ignored"}],
                ["task_id", "drawing_number"],
            )

            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows, [{"task_id": "p001", "drawing_number": "JS2207-01"}])

    def test_write_csv_writes_header_for_empty_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "reports" / "empty.csv"

            write_csv(path, [], ["task_id", "status"])

            text = path.read_text(encoding="utf-8-sig")
            self.assertEqual(text, "task_id,status\n")


if __name__ == "__main__":
    unittest.main()
