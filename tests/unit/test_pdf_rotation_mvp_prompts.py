import unittest

from blueprint_normalizer.pdf_rotation_mvp.prompts import PROMPT_FILENAMES, load_prompt


class PdfRotationMvpPromptTests(unittest.TestCase):
    def test_prompt_resources_are_readable(self) -> None:
        self.assertEqual(set(PROMPT_FILENAMES), {"title_block_only", "drawing_number"})

        title_prompt = load_prompt("title_block_only")
        drawing_prompt = load_prompt("drawing_number")

        self.assertIn("机械图纸标题栏定位助手", title_prompt)
        self.assertIn("title_block_position", title_prompt)
        self.assertIn("bottom_edge", title_prompt)
        self.assertIn("needs_human_review", title_prompt)

        self.assertIn("机械制图标题栏图号提取助手", drawing_prompt)
        self.assertIn("selected_drawing_number", drawing_prompt)
        self.assertIn("candidates", drawing_prompt)
        self.assertIn("不要臆造图号", drawing_prompt)

    def test_unknown_prompt_name_fails_explicitly(self) -> None:
        with self.assertRaises(ValueError):
            load_prompt("missing")


if __name__ == "__main__":
    unittest.main()
