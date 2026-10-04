from __future__ import annotations

from videos.domain.validation.scene_rule import SceneRule
from videos.domain.value_objects.quality import RuleViolation
from videos.domain.value_objects.scene_spec import SceneSpec


class SceneRules:
    def __init__(self, rules: list[SceneRule] | None = None) -> None:
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
