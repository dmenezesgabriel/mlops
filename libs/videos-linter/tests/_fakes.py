"""Named fakes for the checker/analyzer seams (ADR-0005).

`LinterService` injects the concrete checker classes, so each recording fake
subclasses its real counterpart and records the calls it received rather
than standing in as an ad-hoc `MagicMock` attribute bag. `FakeVideoCapture`
scripts the `cv2.VideoCapture` boundary so frame stats — fps fallback, read
failures — are exercised deterministically.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from videos.domain.quality import RuleViolation
from videos_linter.linter_service import (
    BlurDetector,
    ContrastChecker,
    ImageOverlapDetector,
    VideoMotionAnalyzer,
)


class _RecordingImageChecker:
    def __init__(self, violations: list[RuleViolation] | None = None) -> None:
        self._violations = violations if violations is not None else []
        self.calls: list[tuple[Path, str]] = []

    def check_image(
        self, image_path: Path, scene_id: str = "unknown"
    ) -> list[RuleViolation]:
        self.calls.append((image_path, scene_id))
        return list(self._violations)


class RecordingContrastChecker(_RecordingImageChecker, ContrastChecker):
    pass


class RecordingBlurDetector(_RecordingImageChecker, BlurDetector):
    pass


class RecordingOverlapDetector(_RecordingImageChecker, ImageOverlapDetector):
    pass


class RecordingMotionAnalyzer(VideoMotionAnalyzer):
    def __init__(self, violations: list[RuleViolation] | None = None) -> None:
        self._violations = violations if violations is not None else []
        self.calls: list[tuple[Path, str]] = []

    def analyze_video(
        self, video_path: Path, scene_id: str = "unknown"
    ) -> list[RuleViolation]:
        self.calls.append((video_path, scene_id))
        return list(self._violations)


_REAL_CONVEXITY_DEFECTS = cv2.convexityDefects


def flat_convexity_defects(
    contour: np.ndarray, hull: np.ndarray
) -> np.ndarray | None:
    """cv2 5.x-shaped `convexityDefects`: flat (N, 4) rows vs 4.x (N, 1, 4).

    Wraps the real implementation and reshapes its output so tests exercise
    the flat-row contract under an installed 4.x cv2.
    """
    defects = _REAL_CONVEXITY_DEFECTS(contour, hull)
    if defects is None:
        return None
    return defects.reshape(-1, 4)


class FakeVideoCapture:
    """Scripted `cv2.VideoCapture`: `frames` are consumed one per `read()`,
    `fps` answers `get(CAP_PROP_FPS)`, `is_opened` controls `isOpened()`,
    and `released` records the teardown."""

    def __init__(
        self,
        frames: list[np.ndarray],
        fps: float = 30.0,
        is_opened: bool = True,
    ) -> None:
        self._frames = list(frames)
        self._fps = fps
        self._is_opened = is_opened
        self.released = False

    # The name mirrors cv2.VideoCapture's API — the SUT calls `isOpened()`.
    def isOpened(self) -> bool:  # noqa: N802
        return self._is_opened

    def get(self, prop: int) -> float:
        if prop == cv2.CAP_PROP_FPS:
            return self._fps
        return 0.0

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self._frames:
            return False, None
        return True, self._frames.pop(0)

    def release(self) -> None:
        self.released = True
