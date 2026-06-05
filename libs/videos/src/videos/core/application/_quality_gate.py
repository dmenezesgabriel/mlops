from __future__ import annotations

from collections.abc import Sequence

from videos.core.domain._quality import QualityReport, RuleViolation
from videos.core.domain._scene_spec import SceneSpec
from videos.validation._layout_rules import LayoutRules
from videos.validation._scene_rules import SceneRules
from videos.validation._text_rules import TextRules
from videos.validation._timeline_rules import TimelineRules


class QualityGate:
    def __init__(self) -> None:
        self._validators = [
            TextRules(),
            LayoutRules(),
            TimelineRules(),
            SceneRules(),
        ]

    def validate(self, scenes: Sequence[SceneSpec]) -> QualityReport:
        all_violations: list[RuleViolation] = []
        for scene in scenes:
            for validator in self._validators:
                violations = validator.validate(scene)
                all_violations.extend(violations)

        if all_violations:
            return QualityReport(
                passed=False,
                violations=tuple(all_violations),
            )
        return QualityReport(passed=True)
