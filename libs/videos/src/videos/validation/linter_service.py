from __future__ import annotations

from pathlib import Path
from typing import Any

from videos.core.domain.quality import RuleViolation
from videos.validation.geometry_rules import OverlapDetector
from videos.validation.visual_linter import DensityAnalyzer


class LinterError(RuntimeError):
    pass


class LinterService:
    def __init__(
        self,
        overlap_detector: OverlapDetector | None = None,
        density_analyzer: DensityAnalyzer | None = None,
    ) -> None:
        self._overlap_detector = overlap_detector or OverlapDetector()
        self._density_analyzer = density_analyzer or DensityAnalyzer()

    def verify_geometry(self, mobjects: list[Any], scene_id: str) -> list[RuleViolation]:
        violations = []
        # Check every pair of mobjects for overlap
        for i in range(len(mobjects)):
            for j in range(i + 1, len(mobjects)):
                if self._overlap_detector.check_overlap(mobjects[i], mobjects[j]):
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
        if result.is_centered_only:
            raise LinterError(
                f"Visual Linter failed for scene {scene_id!r}: "
                f"Content is concentrated in the center (spread={result.spread_ratio:.2f}). "
                "This usually indicates that the layout engine failed."
            )
