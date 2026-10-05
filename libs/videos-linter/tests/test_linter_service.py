from __future__ import annotations

from pathlib import Path

import pytest
import videos_linter
from PIL import Image, ImageDraw
from videos.application.ports.linter import Linter
from videos.domain.quality import RuleViolation
from videos_linter.linter_service import LinterError, LinterService

from tests._fakes import (
    RecordingBlurDetector,
    RecordingContrastChecker,
    RecordingMotionAnalyzer,
    RecordingOverlapDetector,
    flat_convexity_defects,
)


class TestLinterService:
    def test_verify_visuals_passes_when_no_violations(self) -> None:
        # Arrange
        contrast = RecordingContrastChecker()
        blur = RecordingBlurDetector()
        overlap = RecordingOverlapDetector()

        service = LinterService(
            contrast_checker=contrast,
            blur_detector=blur,
            overlap_detector=overlap,
        )

        # Act & Assert (should not raise)
        service.verify_visuals(Path("dummy.png"), "scene_a")
        assert contrast.calls == [(Path("dummy.png"), "scene_a")]
        assert blur.calls == [(Path("dummy.png"), "scene_a")]
        assert overlap.calls == [(Path("dummy.png"), "scene_a")]

    def test_verify_visuals_raises_on_contrast_violation(self) -> None:
        # Arrange
        contrast = RecordingContrastChecker(
            violations=[
                RuleViolation(
                    scene_id="scene_a",
                    rule="contrast",
                    suggestion="Low contrast",
                )
            ]
        )
        blur = RecordingBlurDetector()
        overlap = RecordingOverlapDetector()

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
        motion = RecordingMotionAnalyzer(
            violations=[
                RuleViolation(
                    scene_id="scene_a",
                    rule="frozen",
                    suggestion="Frozen frame",
                )
            ]
        )

        service = LinterService(motion_analyzer=motion)

        # Act & Assert
        with pytest.raises(LinterError, match="motion issues"):
            service.verify_video(Path("dummy.mp4"), "scene_a")

    def test_verify_visuals_raises_on_missing_image(
        self, tmp_path: Path
    ) -> None:
        service = LinterService()
        with pytest.raises(LinterError, match="Could not decode image"):
            service.verify_visuals(tmp_path / "missing.png", "scene_a")

    def test_verify_video_raises_on_missing_video(
        self, tmp_path: Path
    ) -> None:
        service = LinterService()
        with pytest.raises(LinterError, match="Could not analyze video"):
            service.verify_video(tmp_path / "missing.mp4", "scene_a")

    def test_linter_service_implements_linter_port(self) -> None:
        # The nominal base is what lets pyright verify signature
        # conformance in-repo; the port is not @runtime_checkable, so
        # issubclass() is unavailable and the MRO is asserted directly.
        assert Linter in LinterService.__mro__

    def test_package_ships_py_typed_marker(self) -> None:
        package_dir = Path(videos_linter.__file__).parent
        assert (package_dir / "py.typed").is_file()

    def test_verify_visuals_under_flat_cv2_defect_rows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # opencv 5.x returns convexityDefects as flat (N, 4) rows where 4.x
        # returns (N, 1, 4); (N, 1, 4)-only indexing IndexError'd every real
        # render's VisualValidationStep under the container's cv2 5.0.0.
        monkeypatch.setattr(
            "videos_linter.linter_service.cv2.convexityDefects",
            flat_convexity_defects,
        )
        img = Image.new("RGB", (300, 300), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)
        draw.rectangle([50, 50, 150, 150], fill=(255, 255, 255))
        draw.rectangle([120, 120, 220, 220], fill=(255, 255, 255))
        path = tmp_path / "fused.png"
        img.save(path)

        with pytest.raises(LinterError, match="overlapping elements"):
            LinterService().verify_visuals(path, "scene_a")

    def test_verify_visuals_reports_all_failing_checkers(self) -> None:
        # Arrange — all three checkers fail; the error must carry every
        # label and suggestion, not just the first failing checker's.
        contrast = RecordingContrastChecker(
            violations=[
                RuleViolation(
                    scene_id="scene_a",
                    rule="contrast",
                    suggestion="Low contrast",
                )
            ]
        )
        blur = RecordingBlurDetector(
            violations=[
                RuleViolation(
                    scene_id="scene_a", rule="blur", suggestion="Too blurry"
                )
            ]
        )
        overlap = RecordingOverlapDetector(
            violations=[
                RuleViolation(
                    scene_id="scene_a",
                    rule="overlap",
                    suggestion="Elements overlap",
                )
            ]
        )

        service = LinterService(
            contrast_checker=contrast,
            blur_detector=blur,
            overlap_detector=overlap,
        )

        # Act & Assert
        with pytest.raises(LinterError) as exc_info:
            service.verify_visuals(Path("dummy.png"), "scene_a")
        message = str(exc_info.value)
        assert "contrast issues" in message
        assert "blurriness" in message
        assert "overlapping elements" in message
        assert "Low contrast" in message
        assert "Too blurry" in message
        assert "Elements overlap" in message
