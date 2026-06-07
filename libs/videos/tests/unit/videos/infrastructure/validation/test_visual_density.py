from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from videos.infrastructure.validation.visual_linter import DensityAnalyzer


@pytest.fixture
def analyzer() -> DensityAnalyzer:
    return DensityAnalyzer()


def _create_test_image(
    tmp_path: Path,
    filename: str,
    content_rects: list[tuple[int, int, int, int]],
) -> Path:
    img = Image.new(
        "RGB", (854, 480), color=(30, 30, 30)
    )  # Manim background color
    draw = ImageDraw.Draw(img)
    for rect in content_rects:
        draw.rectangle(rect, fill=(255, 255, 255))
    path = tmp_path / filename
    img.save(path)
    return path


class TestDensityAnalyzer:
    def test_detects_centered_only_content(
        self, analyzer: DensityAnalyzer, tmp_path: Path
    ) -> None:
        # Content only in the center (100x100)
        img_path = _create_test_image(
            tmp_path, "centered.png", [(377, 190, 477, 290)]
        )

        result = analyzer.analyze(img_path)
        assert result.is_centered_only is True
        assert result.spread_ratio < 0.25

    def test_detects_spread_content(
        self, analyzer: DensityAnalyzer, tmp_path: Path
    ) -> None:
        # Title at top, content at center
        img_path = _create_test_image(
            tmp_path,
            "spread.png",
            [
                (300, 50, 500, 100),  # Title
                (300, 200, 500, 300),  # Body
            ],
        )

        result = analyzer.analyze(img_path)
        assert result.is_centered_only is False
        assert result.spread_ratio > 0.3
