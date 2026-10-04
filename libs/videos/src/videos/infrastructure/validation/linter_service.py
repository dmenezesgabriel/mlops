from __future__ import annotations

from pathlib import Path
from typing import Any

from videos.domain.value_objects.quality import RuleViolation
from videos.infrastructure.validation.geometry_rules import OverlapDetector
from videos.infrastructure.validation.visual_linter import (
    DensityAnalyzer,
    VisualLinterResult,
)


class LinterError(RuntimeError):
    pass


def _density_detail(result: VisualLinterResult) -> str:
    if result.spread_ratio == 0.0:
        return "No visible content above the background (blank frame)"
    return (
        "Content is concentrated in the center "
        f"(spread={result.spread_ratio:.2f})"
    )


# Minimal decodability proof available without cv2/ffmpeg: every artifact the
# pipeline resolves is .mp4, and an mp4 is an ISO-BMFF file whose first box is
# `ftyp` — absent, empty, and junk-byte files fail here instead of passing.
def _video_file_problem(video_path: Path) -> str | None:
    if not video_path.exists():
        return f"missing video file '{video_path}'"
    with video_path.open("rb") as stream:
        header = stream.read(12)
    if len(header) < 8 or header[4:8] != b"ftyp":
        return (
            f"undecodable video '{video_path}' "
            "(expected an ISO-BMFF 'ftyp' box)"
        )
    return None


class LinterService:
    def __init__(
        self,
        overlap_detector: OverlapDetector | None = None,
        density_analyzer: DensityAnalyzer | None = None,
    ) -> None:
        self._overlap_detector = overlap_detector or OverlapDetector()
        self._density_analyzer = density_analyzer or DensityAnalyzer()

    def verify_geometry(
        self, mobjects: list[Any], scene_id: str
    ) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        # Check every pair of mobjects for overlap
        for i in range(len(mobjects)):
            for j in range(i + 1, len(mobjects)):
                if self._overlap_detector.check_overlap(
                    mobjects[i], mobjects[j]
                ):
                    violations.append(
                        RuleViolation(
                            scene_id=scene_id,
                            rule="geometric_overlap",
                            suggestion="Adjust layout coordinates to prevent overlapping elements.",
                            actual=f"Overlap between object {i} and {j}",
                        )
                    )
        return violations

    def verify_visuals(self, image_path: Path, scene_id: str) -> None:
        result = self._density_analyzer.analyze(image_path)
        if not result.is_centered_only:
            return
        raise LinterError(
            f"Visual Linter failed for scene {scene_id!r}: "
            f"{_density_detail(result)} "
            "This usually indicates that the layout engine failed."
        )

    def verify_video(self, video_path: Path, scene_id: str) -> None:
        problem = _video_file_problem(video_path)
        if problem is None:
            return
        raise LinterError(
            f"Video Linter failed for scene {scene_id!r}: {problem}"
        )
