from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFilter
from videos_linter.linter_service import BlurDetector


@pytest.fixture
def temp_image_dir(tmp_path: Path) -> Path:
    return tmp_path


def _create_sharp_image(dir_path: Path, filename: str) -> Path:
    # A sharp black image with white lines/text
    img = Image.new("RGB", (300, 300), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Draw high contrast sharp stripes
    for i in range(10, 290, 20):
        draw.rectangle([i, 10, i + 5, 290], fill=(255, 255, 255))
    path = dir_path / filename
    img.save(path)
    return path


def _create_blurry_image(sharp_path: Path, filename: str) -> Path:
    # Blur the sharp image using PIL GaussianBlur
    with Image.open(sharp_path) as img:
        blurry_img = img.filter(ImageFilter.GaussianBlur(radius=8))
        path = sharp_path.parent / filename
        blurry_img.save(path)
        return path


class TestBlurDetector:
    def test_passes_on_sharp_image(self, temp_image_dir: Path) -> None:
        sharp_path = _create_sharp_image(temp_image_dir, "sharp.png")
        detector = BlurDetector(threshold=100.0)
        violations = detector.check_image(sharp_path)
        assert len(violations) == 0

    def test_fails_on_blurry_image(self, temp_image_dir: Path) -> None:
        sharp_path = _create_sharp_image(temp_image_dir, "sharp.png")
        blurry_path = _create_blurry_image(sharp_path, "blurry.png")
        detector = BlurDetector(threshold=100.0)
        violations = detector.check_image(blurry_path)
        assert len(violations) > 0
        assert "blurry" in violations[0].rule
