from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from videos_linter.linter_service import ImageOverlapDetector


@pytest.fixture
def temp_image_dir(tmp_path: Path) -> Path:
    return tmp_path


def _create_non_overlapping_image(dir_path: Path, filename: str) -> Path:
    img = Image.new("RGB", (300, 300), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    # Box A
    draw.rectangle([20, 20, 100, 100], fill=(255, 255, 255))
    # Box B
    draw.rectangle([150, 150, 250, 250], fill=(255, 255, 255))
    path = dir_path / filename
    img.save(path)
    return path


def _create_overlapping_image(dir_path: Path, filename: str) -> Path:
    img = Image.new("RGB", (300, 300), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    # Box A (Green)
    draw.rectangle([50, 50, 150, 150], fill=(0, 255, 0))
    # Box B (Red, overlapping Box A)
    draw.rectangle([120, 120, 220, 220], fill=(255, 0, 0))
    path = dir_path / filename
    img.save(path)
    return path


class TestImageOverlapDetector:
    def test_passes_on_non_overlapping(self, temp_image_dir: Path) -> None:
        img_path = _create_non_overlapping_image(temp_image_dir, "clean.png")
        detector = ImageOverlapDetector()
        violations = detector.check_image(img_path)
        assert len(violations) == 0

    def test_fails_on_overlapping(self, temp_image_dir: Path) -> None:
        img_path = _create_overlapping_image(temp_image_dir, "overlap.png")
        detector = ImageOverlapDetector()
        violations = detector.check_image(img_path)
        assert len(violations) > 0
        assert "overlap" in violations[0].rule
