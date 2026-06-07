from __future__ import annotations

from typing import Protocol

from videos.core.domain.quality import RuleViolation
from videos.core.domain.scene_spec import SceneSpec


class TimelineRuleValidator(Protocol):
    def __call__(self, scene: SceneSpec) -> list[RuleViolation]: ...


class TimelineRules:
    def __init__(
        self, rules: list[TimelineRuleValidator] | None = None
    ) -> None:
        self._rules = (
            rules
            if rules is not None
            else [
                self._check_events_reference_existing_objects,
                self._check_times_within_duration,
            ]
        )

    def validate(self, scene: SceneSpec) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        for rule in self._rules:
            violations.extend(rule(scene))
        return violations

    def _check_events_reference_existing_objects(
        self, scene: SceneSpec
    ) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        if scene.timeline is None:
            return violations
        object_ids = {o.object_id for o in scene.visual_objects}
        for event in scene.timeline.events:
            if event.target_object_id not in object_ids:
                violations.append(
                    RuleViolation(
                        scene_id=scene.scene_id,
                        object_id=event.target_object_id,
                        rule="timeline_target_must_exist",
                        actual=f"no object with id {event.target_object_id!r}",
                        expected=f"one of {sorted(object_ids)}",
                        suggestion=(
                            f"Add a VisualObject with object_id "
                            f"{event.target_object_id!r} or fix the timeline event."
                        ),
                    )
                )
        return violations

    def _check_times_within_duration(
        self, scene: SceneSpec
    ) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        if scene.timeline is None:
            return violations
        for event in scene.timeline.events:
            if event.time_seconds > scene.duration_seconds:
                violations.append(
                    RuleViolation(
                        scene_id=scene.scene_id,
                        object_id=event.target_object_id,
                        rule="timeline_event_exceeds_duration",
                        actual=event.time_seconds,
                        expected=f"<= {scene.duration_seconds}",
                        suggestion=(
                            f"Timeline event at {event.time_seconds}s "
                            f"exceeds scene duration {scene.duration_seconds}s."
                        ),
                    )
                )
        return violations
