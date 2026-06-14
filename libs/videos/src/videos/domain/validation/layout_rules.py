from __future__ import annotations

from typing import Protocol

from videos.domain.layout import LayoutRegion
from videos.domain.quality import RuleViolation
from videos.domain.scene_spec import SceneSpec


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
                self._check_diagram_labels,
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

    def _check_diagram_labels(self, scene: SceneSpec) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        for index, comp in enumerate(scene.components):
            if comp.type == "diagram":
                kind = comp.props.get("kind")
                if kind in ("cycle", "linear"):
                    labels = comp.props.get("labels")
                    if (
                        not labels
                        or not isinstance(labels, (list, tuple))
                        or len(labels) == 0
                    ):
                        violations.append(
                            RuleViolation(
                                scene_id=scene.scene_id,
                                object_id=f"component_{index}",
                                rule="diagram_requires_labels",
                                actual=f"labels={labels}",
                                expected="non-empty list of labels",
                                suggestion=(
                                    f"Add a 'labels' list parameter to the diagram component "
                                    f"in scene {scene.scene_id!r}."
                                ),
                            )
                        )
        return violations
