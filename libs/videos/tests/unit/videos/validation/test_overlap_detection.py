from __future__ import annotations

import pytest
from videos.validation.geometry_rules import OverlapDetector


class MockMobject:
    def __init__(self, dl: list[float], ur: list[float]) -> None:
        self._dl = dl
        self._ur = ur

    def get_corner(self, direction: list[float]) -> list[float]:
        # Simple mock for DL (-1, -1, 0) and UR (1, 1, 0)
        if direction[0] < 0 and direction[1] < 0:
            return self._dl
        if direction[0] > 0 and direction[1] > 0:
            return self._ur
        return [0, 0, 0]


@pytest.fixture
def detector() -> OverlapDetector:
    return OverlapDetector()


class TestOverlapDetector:
    def test_detects_overlap(self, detector: OverlapDetector) -> None:
        # Arrange
        obj_a = MockMobject([0, 0, 0], [2, 2, 0])
        obj_b = MockMobject([1, 1, 0], [3, 3, 0])

        # Act
        result = detector.check_overlap(obj_a, obj_b)

        # Assert
        assert result is True

    def test_detects_no_overlap(self, detector: OverlapDetector) -> None:
        # Arrange
        obj_a = MockMobject([0, 0, 0], [1, 1, 0])
        obj_b = MockMobject([2, 2, 0], [3, 3, 0])

        # Act
        result = detector.check_overlap(obj_a, obj_b)

        # Assert
        assert result is False

    def test_detects_no_overlap_adjacent(
        self, detector: OverlapDetector
    ) -> None:
        # Arrange
        obj_a = MockMobject([0, 0, 0], [1, 1, 0])
        obj_b = MockMobject([1, 1, 0], [2, 2, 0])

        # Act
        result = detector.check_overlap(obj_a, obj_b)

        # Assert
        assert result is False
