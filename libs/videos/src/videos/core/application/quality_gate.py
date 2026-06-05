from __future__ import annotations

from collections.abc import Sequence

from videos.core.domain.quality import QualityReport, RuleViolation
from videos.core.domain.scene_spec import SceneSpec
from videos.validation.layout_rules import LayoutRules
from videos.validation.scene_rules import SceneRules
from videos.validation.text_rules import TextRules
from videos.validation.timeline_rules import TimelineRules

_Validator = TextRules | LayoutRules | TimelineRules | SceneRules


class QualityGate:
    def __init__(self) -> None:
        self._validators: list[_Validator] = [
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
