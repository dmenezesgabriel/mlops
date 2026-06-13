from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from videos.domain.quality import RuleViolation
from videos_linter.linter_service import LinterError, LinterService


class TestLinterService:
    def test_verify_visuals_passes_when_no_violations(self) -> None:
        # Arrange
        contrast = MagicMock()
        contrast.check_image.return_value = []
        blur = MagicMock()
        blur.check_image.return_value = []
        overlap = MagicMock()
        overlap.check_image.return_value = []

        service = LinterService(
            contrast_checker=contrast,
            blur_detector=blur,
            overlap_detector=overlap,
        )

        # Act & Assert (should not raise)
        service.verify_visuals(Path("dummy.png"), "scene_a")
        contrast.check_image.assert_called_once_with(
            Path("dummy.png"), "scene_a"
        )
        blur.check_image.assert_called_once_with(Path("dummy.png"), "scene_a")
        overlap.check_image.assert_called_once_with(
            Path("dummy.png"), "scene_a"
        )

    def test_verify_visuals_raises_on_contrast_violation(self) -> None:
        # Arrange
        contrast = MagicMock()
        contrast.check_image.return_value = [
            RuleViolation(
                scene_id="scene_a", rule="contrast", suggestion="Low contrast"
            )
        ]
        blur = MagicMock()
        blur.check_image.return_value = []
        overlap = MagicMock()
        overlap.check_image.return_value = []

        service = LinterService(
            contrast_checker=contrast,
            blur_detector=blur,
            overlap_detector=overlap,
        )

        # Act & Assert
        with pytest.raises(LinterError, match="contrast issues"):
            service.verify_visuals(Path("dummy.png"), "scene_a")

    def test_verify_video_raises_on_motion_violation(self) -> None:
        # Arrange
        motion = MagicMock()
        motion.analyze_video.return_value = [
            RuleViolation(
                scene_id="scene_a", rule="frozen", suggestion="Frozen frame"
            )
        ]

        service = LinterService(motion_analyzer=motion)

        # Act & Assert
        with pytest.raises(LinterError, match="motion issues"):
            service.verify_video(Path("dummy.mp4"), "scene_a")
