from __future__ import annotations

from typing import Protocol

from videos.core.domain.layout import LayoutRegion
from videos.core.domain.quality import RuleViolation
from videos.core.domain.scene_spec import SceneSpec


class LayoutRuleValidator(Protocol):
    def __call__(self, scene: SceneSpec) -> list[RuleViolation]: ...


class LayoutRules:
    def __init__(self, rules: list[LayoutRuleValidator] | None = None) -> None:
        self._rules = (
            rules
            if rules is not None
            else [
                self._check_known_regions,
                self._check_objects_have_regions,
            ]
        )

    def validate(self, scene: SceneSpec) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        for rule in self._rules:
            violations.extend(rule(scene))
        return violations

    def _check_known_regions(self, scene: SceneSpec) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        known = LayoutRegion.all_region_names()
        for obj in scene.visual_objects:
            if obj.region not in known:
                violations.append(
                    RuleViolation(
                        scene_id=scene.scene_id,
                        object_id=obj.object_id,
                        rule="unknown_layout_region",
                        actual=obj.region,
                        expected=f"one of {sorted(known)}",
                        suggestion=(
                            f"Assign '{obj.object_id}' to a valid layout region."
                        ),
                    )
                )
        return violations

    def _check_objects_have_regions(
        self, scene: SceneSpec
    ) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        for obj in scene.visual_objects:
            if not obj.region.strip():
                violations.append(
                    RuleViolation(
                        scene_id=scene.scene_id,
                        object_id=obj.object_id,
                        rule="object_must_have_region",
                        actual="(empty region)",
                        expected="non-empty layout region name",
                        suggestion=(
                            f"Assign a layout region to '{obj.object_id}'."
                        ),
                    )
                )
        return violations
