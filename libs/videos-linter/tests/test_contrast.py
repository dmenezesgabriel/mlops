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

    def test_flags_missing_image(self, temp_image_dir: Path) -> None:
        checker = ContrastChecker()
        violations = checker.check_image(temp_image_dir / "missing.png")
        assert len(violations) == 1
        assert violations[0].rule == "unreadable_image"

    def test_flags_undecodable_image(self, temp_image_dir: Path) -> None:
        corrupt_path = temp_image_dir / "corrupt.png"
        corrupt_path.write_text("this is not image data")
        checker = ContrastChecker()
        violations = checker.check_image(corrupt_path)
        assert len(violations) == 1
        assert violations[0].rule == "unreadable_image"

    def test_measures_real_background_when_element_fills_roi(
        self, temp_image_dir: Path
    ) -> None:
        # A bright element on a moderately bright background leaves no
        # sub-threshold pixels inside the contour's bounding box — the real
        # background must be measured from the image, not assumed dark.
        img_path = _create_test_image(
            temp_image_dir,
            "bright_background.png",
            (100, 100, 100),
            (200, 200, 200),
        )
        checker = ContrastChecker(min_ratio=4.5)
        violations = checker.check_image(img_path)
        assert len(violations) > 0
        assert "contrast" in violations[0].rule
        # WCAG 2.x: gray-200 on gray-100 is ratio 3.54 — the raw-sRGB dot
        # reported 1.89 (~2x too strict at mid-dark tones).
        assert float(violations[0].actual) == pytest.approx(3.54, abs=0.05)

    def test_passes_mid_gray_element_on_white(
        self, temp_image_dir: Path
    ) -> None:
        # Gray-100 on white is WCAG ratio 5.92 — the un-linearized metric
        # reported 2.37 and false-rejected conformant content.
        img_path = _create_test_image(
            temp_image_dir,
            "mid_gray_on_white.png",
            (255, 255, 255),
            (100, 100, 100),
        )
        checker = ContrastChecker(min_ratio=4.5)
        violations = checker.check_image(img_path)
        assert len(violations) == 0

    def test_reports_wcag_ratio_for_flagged_pair(
        self, temp_image_dir: Path
    ) -> None:
        # Gray-150 on white: true WCAG 2.96 (un-linearized metric: 1.65).
        img_path = _create_test_image(
            temp_image_dir,
            "flagged_pair.png",
            (255, 255, 255),
            (150, 150, 150),
        )
        checker = ContrastChecker(min_ratio=4.5)
        violations = checker.check_image(img_path)
        assert len(violations) > 0
        assert float(violations[0].actual) == pytest.approx(2.96, abs=0.05)

    def test_passes_wcag_aa_boundary_gray(self, temp_image_dir: Path) -> None:
        # Gray-118 (~#767676) on white is the classic WCAG AA boundary at
        # ratio ~4.54 — must pass un-linearized-metric-free.
        img_path = _create_test_image(
            temp_image_dir,
            "aa_boundary.png",
            (255, 255, 255),
            (118, 118, 118),
        )
        checker = ContrastChecker(min_ratio=4.5)
        violations = checker.check_image(img_path)
        assert len(violations) == 0

    def test_skips_thin_elements_below_5px(self, temp_image_dir: Path) -> None:
        # A 4px-wide low-contrast bar falls under the w<5 noise floor even
        # though it is 50px tall — the skip is `or`, not `and`.
        img = Image.new("RGB", (200, 200), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)
        draw.rectangle([10, 50, 13, 99], fill=(45, 45, 45))
        path = temp_image_dir / "thin.png"
        img.save(path)

        checker = ContrastChecker(min_ratio=4.5)
        assert checker.check_image(path) == []

    def test_measures_background_inside_bounding_box(
        self, temp_image_dir: Path
    ) -> None:
        # A hollow bright ring leaves dark pixels inside its bounding box —
        # the background percentile must come from the ROI, not the
        # whole-image fallback.
        img = Image.new("RGB", (200, 200), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)
        draw.rectangle([50, 50, 149, 149], outline=(255, 255, 255), width=8)
        path = temp_image_dir / "ring.png"
        img.save(path)

        checker = ContrastChecker(min_ratio=4.5)
        assert checker.check_image(path) == []
