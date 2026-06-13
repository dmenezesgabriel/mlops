from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from videos_linter.linter_service import ContrastChecker


@pytest.fixture
def temp_image_dir(tmp_path: Path) -> Path:
    return tmp_path


def _create_test_image(
    dir_path: Path,
    filename: str,
    bg_color: tuple[int, int, int],
    element_color: tuple[int, int, int],
) -> Path:
    img = Image.new("RGB", (200, 200), color=bg_color)
    draw = ImageDraw.Draw(img)
    # Draw a 50x50 box in the center
    draw.rectangle([75, 75, 125, 125], fill=element_color)
    path = dir_path / filename
    img.save(path)
    return path


class TestContrastChecker:
    def test_passes_on_high_contrast(self, temp_image_dir: Path) -> None:
        # White element on a dark background (very high contrast)
        img_path = _create_test_image(
            temp_image_dir, "high_contrast.png", (30, 30, 30), (255, 255, 255)
        )
        checker = ContrastChecker(min_ratio=4.5)
        violations = checker.check_image(img_path)
        assert len(violations) == 0

    def test_fails_on_low_contrast(self, temp_image_dir: Path) -> None:
        # Dark gray element on a slightly darker background (low contrast)
        img_path = _create_test_image(
            temp_image_dir, "low_contrast.png", (30, 30, 30), (45, 45, 45)
        )
        checker = ContrastChecker(min_ratio=4.5)
        violations = checker.check_image(img_path)
        assert len(violations) > 0
        assert "contrast" in violations[0].rule
        assert float(violations[0].actual) < 4.5
