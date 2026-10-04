from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw
from videos_linter.linter_service import (
    Box,
    ImageOverlapDetector,
    _deepest_defect_depth,
    _DetectedBlob,
    _is_known_box,
    _overlap_violation,
)


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

    def test_passes_on_close_elements(self, temp_image_dir: Path) -> None:
        # Create an image with two rectangles placed very close (2 pixels apart)
        # representing characters in a word
        img = Image.new("RGB", (300, 300), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)
        # Draw a thick L-shape
        draw.rectangle([50, 65, 70, 70], fill=(255, 255, 255))
        draw.rectangle([50, 50, 55, 70], fill=(255, 255, 255))
        # Draw a thick vertical line inside the L-shape's bounding box, but not touching it
        draw.rectangle([62, 50, 67, 60], fill=(255, 255, 255))

        path = temp_image_dir / "close_elements.png"
        img.save(path)

        detector = ImageOverlapDetector()
        violations = detector.check_image(path)
        assert len(violations) == 0

    def test_flags_missing_image(self, temp_image_dir: Path) -> None:
        detector = ImageOverlapDetector()
        violations = detector.check_image(temp_image_dir / "missing.png")
        assert len(violations) == 1
        assert violations[0].rule == "unreadable_image"

    def test_fails_on_same_color_overlap(self, temp_image_dir: Path) -> None:
        # Two same-color overlapping elements fuse into one thresholded blob;
        # the collision must still surface instead of passing silently.
        img = Image.new("RGB", (300, 300), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)
        draw.rectangle([50, 50, 150, 150], fill=(255, 255, 255))
        draw.rectangle([120, 120, 220, 220], fill=(255, 255, 255))
        path = temp_image_dir / "same_color_overlap.png"
        img.save(path)

        detector = ImageOverlapDetector()
        violations = detector.check_image(path)
        assert len(violations) > 0
        assert "overlap" in violations[0].rule


class TestOverlapViolationBoundaries:
    """Pin the exact relational thresholds — a flipped operator must change
    the observable result."""

    def test_ignores_overlap_area_at_exactly_10px(self) -> None:
        # Overlap area of exactly 10 px is still the noise floor.
        box_a = (0, 0, 10, 10)
        box_b = (9, 0, 10, 10)  # overlap = 1 x 10 = 10
        assert _overlap_violation(box_a, box_b, "s", 0, 1) is None

    def test_flags_overlap_area_just_above_10px(self) -> None:
        box_a = (0, 0, 11, 11)
        box_b = (10, 0, 11, 11)  # overlap = 1 x 11 = 11
        assert _overlap_violation(box_a, box_b, "s", 0, 1) is not None

    def test_flags_overlap_at_exactly_70_percent_nesting(self) -> None:
        # area/min_area == 0.7 is NOT nested enough to skip — the skip
        # threshold for channel duplicates is strictly greater-than.
        box_a = (0, 0, 10, 10)
        box_b = (3, 0, 10, 10)  # overlap = 7 x 10 = 70; min_area = 100
        assert _overlap_violation(box_a, box_b, "s", 0, 1) is not None

    def test_ignores_fully_nested_boxes(self) -> None:
        # Identical boxes (channel duplicates) overlap at ratio 1.0.
        box_a = (0, 0, 10, 10)
        box_b = (0, 0, 10, 10)
        assert _overlap_violation(box_a, box_b, "s", 0, 1) is None


class TestIsKnownBoxBoundary:
    @pytest.mark.parametrize(
        "candidate",
        [
            (13, 10, 50, 50),  # x shifted by exactly 3
            (10, 13, 50, 50),  # y shifted by exactly 3
            (10, 10, 53, 50),  # w differs by exactly 3
            (10, 10, 50, 53),  # h differs by exactly 3
        ],
    )
    def test_diff_of_exactly_3_is_a_new_box(self, candidate: Box) -> None:
        # The cross-channel dedup window is strictly <3px per side; a 3px
        # difference in any coordinate means a distinct element.
        blobs = [_DetectedBlob(box=(10, 10, 50, 50), deepest_defect=0.0)]
        assert _is_known_box(candidate, blobs) is False

    def test_diff_under_3_is_the_same_box(self) -> None:
        blobs = [_DetectedBlob(box=(10, 10, 50, 50), deepest_defect=0.0)]
        assert _is_known_box((12, 10, 50, 50), blobs) is True


class TestDeepestDefectDepth:
    def test_returns_zero_for_under_three_points(self) -> None:
        contour = np.array([[[0, 0]], [[1, 1]]], dtype=np.int32)
        assert _deepest_defect_depth(contour) == 0.0

    def test_returns_zero_for_triangular_contour(self) -> None:
        # A 3-vertex contour's hull leaves no room for a concavity.
        contour = np.array([[[0, 0]], [[10, 0]], [[5, 10]]], dtype=np.int32)
        assert _deepest_defect_depth(contour) == 0.0
