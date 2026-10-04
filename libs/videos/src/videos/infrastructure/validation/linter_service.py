from __future__ import annotations

from pathlib import Path

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
        density_analyzer: DensityAnalyzer | None = None,
    ) -> None:
        self._density_analyzer = density_analyzer or DensityAnalyzer()

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
