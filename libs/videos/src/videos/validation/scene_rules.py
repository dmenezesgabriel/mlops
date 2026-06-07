from __future__ import annotations

from typing import Protocol

from videos.core.domain.quality import RuleViolation
from videos.core.domain.scene_spec import SceneSpec


class SceneRuleValidator(Protocol):
    def __call__(self, scene: SceneSpec) -> list[RuleViolation]: ...


class SceneRules:
    def __init__(self, rules: list[SceneRuleValidator] | None = None) -> None:
        self._rules = (
            rules
            if rules is not None
            else [
                self._check_has_title_or_explicit_style,
            ]
        )

    def validate(self, scene: SceneSpec) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        for rule in self._rules:
            violations.extend(rule(scene))
        return violations

    @staticmethod
    def _check_has_title_or_explicit_style(
        scene: SceneSpec,
    ) -> list[RuleViolation]:
        if not scene.title.strip() and scene.style is None:
            return [
                RuleViolation(
                    scene_id=scene.scene_id,
                    rule="scene_needs_title_or_style",
                    actual="no title and no style",
                    expected="title or a title-less style preset",
                    suggestion=(
                        f"Add a title or set an explicit title-less style "
                        f"for scene {scene.scene_id!r}."
                    ),
                )
            ]
        return []
