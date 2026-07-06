from pathlib import Path
import tempfile
import unittest

from blueprint_normalizer.pdf_rotation_mvp.domain import RECORD_VERSION
from blueprint_normalizer.pdf_rotation_mvp.vlm_request import (
    build_request_body,
    data_url_for,
    endpoint_from_base_url,
    public_raw_row,
    redacted_request_row,
)
from blueprint_normalizer.pdf_rotation_mvp.workflow import ImageRecord


class PdfRotationMvpVlmRequestTests(unittest.TestCase):
    def test_endpoint_from_base_url_normalizes_dashscope_paths(self) -> None:
        cases = {
            "https://dashscope.aliyuncs.com/compatible-mode/v1": (
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
            ),
            "https://dashscope.aliyuncs.com/api/v1": (
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
            ),
            "https://example.com": "https://example.com/compatible-mode/v1/chat/completions",
            "https://example.com/custom/chat/completions": "https://example.com/custom/chat/completions",
        }

        for base_url, expected in cases.items():
            with self.subTest(base_url=base_url):
                self.assertEqual(endpoint_from_base_url(base_url), expected)

    def test_endpoint_from_base_url_rejects_empty_value(self) -> None:
        with self.assertRaises(ValueError):
            endpoint_from_base_url("  ")

    def test_data_url_for_encodes_temp_file_as_base64(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "page.png"
            image_path.write_bytes(b"png-bytes")

            self.assertEqual(data_url_for(image_path), "data:image/png;base64,cG5nLWJ5dGVz")
            self.assertEqual(data_url_for(image_path, "image/jpeg"), "data:image/jpeg;base64,cG5nLWJ5dGVz")

    def test_build_request_body_uses_openai_compatible_chat_structure(self) -> None:
        body = build_request_body("qwen-vl-plus", "data:image/png;base64,abc", "Return JSON.")

        self.assertEqual(body["model"], "qwen-vl-plus")
        self.assertEqual(body["temperature"], 0)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertFalse(body["enable_thinking"])
        content = body["messages"][0]["content"]
        self.assertEqual(content[0], {"type": "text", "text": "Return JSON."})
        self.assertEqual(content[1], {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}})

    def test_redacted_request_row_omits_image_data_url_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "work" / "page.png"
            image_path.parent.mkdir()
            image_path.write_bytes(b"secret-image-bytes")
            record = ImageRecord(
                source_pdf=root / "input" / "source.pdf",
                source_stem="source",
                page_number=1,
                task_id="source_page_001",
                image_path=image_path,
            )

            row = redacted_request_row(record, "qwen-vl-plus", "Prompt text", "orientation", root=root)

        self.assertEqual(row["custom_id"], "orientation__qwen-vl-plus__source_page_001")
        self.assertEqual(row["method"], "POST")
        self.assertEqual(row["url"], "/chat/completions")
        self.assertEqual(row["request_kind"], "orientation")
        body_text = repr(row["body"])
        self.assertIn("<omitted_png_data_url:work/page.png>", body_text)
        self.assertIn("Prompt text", body_text)
        self.assertNotIn("secret-image-bytes", body_text)
        self.assertNotIn("base64", body_text)

    def test_public_raw_row_suppresses_response_text_when_json_exists(self) -> None:
        row = public_raw_row(
            {
                "task_id": "source_page_001",
                "source_pdf": "input/source.pdf",
                "page_number": 1,
                "model": "qwen-vl-plus",
                "request_kind": "orientation",
                "endpoint": "https://example.com/chat/completions",
                "ok": True,
                "http_status": 200,
                "attempt_count": 1,
                "response_json": {"choices": []},
                "response_text": "raw body",
            }
        )

        self.assertEqual(row["record_version"], RECORD_VERSION)
        self.assertEqual(row["response_json"], {"choices": []})
        self.assertEqual(row["response_text"], "")

    def test_public_raw_row_keeps_response_text_without_json(self) -> None:
        row = public_raw_row(
            {
                "task_id": "source_page_001",
                "source_pdf": "input/source.pdf",
                "page_number": 1,
                "model": "qwen-vl-plus",
                "response_json": None,
                "response_text": "plain error body",
            }
        )

        self.assertEqual(row["request_kind"], "")
        self.assertEqual(row["error_type"], "")
        self.assertEqual(row["response_text"], "plain error body")


if __name__ == "__main__":
    unittest.main()
