"""QualityGate use case — validates SceneSpecs against configured rules."""

from __future__ import annotations

from collections.abc import Sequence

from videos.application.ports.scene_validator import SceneValidator
from videos.domain.validation.layout_rules import LayoutRules
from videos.domain.validation.scene_rule import SceneRule
from videos.domain.validation.scene_rules import SceneRules
from videos.domain.validation.text_rules import TextRules
from videos.domain.validation.timeline_rules import TimelineRules
from videos.domain.value_objects.quality import QualityReport, RuleViolation
from videos.domain.value_objects.scene_spec import SceneSpec


class _RulesWrapper:
    def __init__(self, rules: list[SceneRule]) -> None:
        self._rules = rules

    def validate(self, scene: SceneSpec) -> list[RuleViolation]:
        all_violations: list[RuleViolation] = []
        for rule in self._rules:
            all_violations.extend(rule(scene))
        return all_violations


class QualityGate:
    """Runs a sequence of validators over a list of SceneSpecs.

    Example:
        gate = QualityGate(validators=[MyValidator()])
        report = gate.validate(scenes)
    """

    def __init__(
        self,
        validators: Sequence[SceneValidator] | None = None,
        static_rules: list[SceneRule] | None = None,
    ) -> None:
        if validators is not None and static_rules is not None:
            raise ValueError(
                "QualityGate accepts 'validators' or 'static_rules', not both"
            )
        if static_rules is not None:
            self._validators: list[SceneValidator] = [
                _RulesWrapper(rules=static_rules)
            ]
        elif validators is not None:
            self._validators = list(validators)
        else:
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
