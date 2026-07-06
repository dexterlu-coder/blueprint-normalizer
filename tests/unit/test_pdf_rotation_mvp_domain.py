import json
import unittest

from blueprint_normalizer.pdf_rotation_mvp.domain import (
    build_decision,
    build_drawing_number_decision,
    canonical_title_block_position,
    derive_rotation,
    drawing_number_filename_status,
    extract_message_content,
    normalize_drawing_number,
    parse_json_content,
    safe_name,
)


def _raw_row(content: str, *, ok: bool = True) -> dict[str, object]:
    return {
        "task_id": "page_001",
        "source_pdf": "input/source.pdf",
        "page_number": 1,
        "model": "qwen-test",
        "ok": ok,
        "http_status": 200 if ok else 500,
        "attempt_count": 1,
        "response_json": {"choices": [{"message": {"content": content}}]},
        "error_type": "" if ok else "http_error",
        "error_message": "",
    }


class PdfRotationMvpDomainTests(unittest.TestCase):
    def test_safe_name_replaces_unsafe_chars_and_falls_back(self) -> None:
        self.assertEqual(safe_name(" A/B:C.pdf "), "A_B_C.pdf")
        self.assertEqual(safe_name("..."), "pdf")

    def test_drawing_number_normalization_and_filename_blockers(self) -> None:
        self.assertEqual(normalize_drawing_number(" JS 2207 - 01 "), "JS2207-01")
        self.assertEqual(normalize_drawing_number("无法确定"), "")

        filename, blockers = drawing_number_filename_status("CON")
        self.assertIsNone(filename)
        self.assertIn("drawing_number_is_windows_reserved_name", blockers)

        filename, blockers = drawing_number_filename_status("JS/2207")
        self.assertIsNone(filename)
        self.assertIn("drawing_number_has_illegal_filename_chars", blockers)

    def test_position_alias_and_rotation_mapping(self) -> None:
        self.assertEqual(canonical_title_block_position("right"), "right_edge")
        self.assertEqual(derive_rotation("right_edge"), (270, 90, []))
        self.assertEqual(derive_rotation("no_title_block")[2], ["unknown_title_block_position_for_rotation"])

    def test_extract_and_parse_json_content(self) -> None:
        content, errors = extract_message_content({"choices": [{"message": {"content": [{"text": "a"}, {"text": "b"}]}}]})
        self.assertEqual(content, "a\nb")
        self.assertEqual(errors, [])

        parsed, parse_errors = parse_json_content('```json\n{"ok": true}\n```')
        self.assertEqual(parsed, {"ok": True})
        self.assertEqual(parse_errors, [])

    def test_build_orientation_decision_success(self) -> None:
        content = json.dumps(
            {
                "title_block_position": "right",
                "confidence": 0.91,
                "evidence": ["title block on right edge"],
                "needs_human_review": False,
                "review_reasons": [],
            },
            ensure_ascii=False,
        )

        decision = build_decision(_raw_row(content))

        self.assertEqual(decision["parse_status"], "ok")
        self.assertEqual(decision["schema_status"], "ok")
        self.assertEqual(decision["title_block_position"], "right_edge")
        self.assertEqual(decision["current_clockwise_degrees"], 270)
        self.assertEqual(decision["correction_clockwise_degrees"], 90)
        self.assertFalse(decision["needs_review"])

    def test_build_orientation_decision_flags_schema_errors(self) -> None:
        content = json.dumps(
            {
                "title_block_position": "sideways",
                "confidence": 2,
                "evidence": "not-a-list",
                "needs_human_review": "false",
                "review_reasons": [],
            },
            ensure_ascii=False,
        )

        decision = build_decision(_raw_row(content))

        self.assertEqual(decision["schema_status"], "error")
        self.assertTrue(decision["needs_review"])
        self.assertIn("invalid_title_block_position", decision["review_reasons"])
        self.assertIn("invalid_confidence", decision["review_reasons"])

    def test_build_drawing_number_decision_success(self) -> None:
        content = json.dumps(
            {
                "selected_drawing_number": " JS 2207-01 ",
                "candidates": [" JS 2207-01 ", "", None],
                "confidence": 0.88,
                "evidence": ["label 图号"],
                "needs_human_review": False,
                "review_reasons": [],
            },
            ensure_ascii=False,
        )

        decision = build_drawing_number_decision(_raw_row(content))

        self.assertEqual(decision["parse_status"], "ok")
        self.assertEqual(decision["schema_status"], "ok")
        self.assertEqual(decision["selected_drawing_number"], "JS2207-01")
        self.assertEqual(decision["final_filename_stem"], "JS2207-01")
        self.assertEqual(decision["candidates"], ["JS2207-01"])
        self.assertFalse(decision["needs_review"])

    def test_build_drawing_number_decision_requires_filename_safe_value(self) -> None:
        content = json.dumps(
            {
                "selected_drawing_number": "A/B",
                "candidates": ["A/B"],
                "confidence": 0.75,
                "evidence": [],
                "needs_human_review": False,
                "review_reasons": [],
            },
            ensure_ascii=False,
        )

        decision = build_drawing_number_decision(_raw_row(content))

        self.assertEqual(decision["final_filename_stem"], "")
        self.assertTrue(decision["needs_review"])
        self.assertIn("drawing_number_has_illegal_filename_chars", decision["review_reasons"])


if __name__ == "__main__":
    unittest.main()
