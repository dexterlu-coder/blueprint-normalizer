from pathlib import Path
import tempfile
import unittest

from PIL import Image

from blueprint_normalizer.pdf_rotation_mvp.title_block_crop import crop_title_block_candidate


class PdfRotationMvpTitleBlockCropTests(unittest.TestCase):
    def test_crop_title_block_candidate_uses_bottom_thirty_percent_for_landscape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "rendered" / "landscape.png"
            crop_path = root / "crops" / "landscape_title_block_crop.png"
            self._write_image(image_path, width=200, height=100)

            row = crop_title_block_candidate(image_path, crop_path, root=root)
            crop_size = self._image_size(crop_path)

        self.assertEqual(row["crop_path"], "crops/landscape_title_block_crop.png")
        self.assertEqual(row["crop_strategy"], "bottom_full_width_after_rotation_correction")
        self.assertEqual(row["crop_ratio"], 0.30)
        self.assertEqual(row["crop_box"], [0, 70, 200, 100])
        self.assertEqual(row["rendered_width"], 200)
        self.assertEqual(row["rendered_height"], 100)
        self.assertEqual(crop_size, (200, 30))

    def test_crop_title_block_candidate_uses_bottom_thirty_five_percent_for_portrait(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "rendered" / "portrait.png"
            crop_path = root / "crops" / "portrait_title_block_crop.png"
            self._write_image(image_path, width=100, height=200)

            row = crop_title_block_candidate(image_path, crop_path, root=root)
            crop_size = self._image_size(crop_path)

        self.assertEqual(row["crop_path"], "crops/portrait_title_block_crop.png")
        self.assertEqual(row["crop_ratio"], 0.35)
        self.assertEqual(row["crop_box"], [0, 130, 100, 200])
        self.assertEqual(row["rendered_width"], 100)
        self.assertEqual(row["rendered_height"], 200)
        self.assertEqual(crop_size, (100, 70))

    def _write_image(self, path: Path, width: int, height: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (width, height), color=(255, 255, 255))
        image.save(path)

    def _image_size(self, path: Path) -> tuple[int, int]:
        with Image.open(path) as image:
            return image.size


if __name__ == "__main__":
    unittest.main()
