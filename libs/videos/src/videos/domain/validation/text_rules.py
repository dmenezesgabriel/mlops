from __future__ import annotations

from typing import Protocol

from videos.domain.quality import RuleViolation
from videos.domain.scene_spec import SceneSpec


class TextRuleValidator(Protocol):
    def __call__(self, scene: SceneSpec) -> list[RuleViolation]: ...


class TextRules:
    MAX_WORDS_PER_TEXT = 14
    MAX_BULLETS_VISIBLE = 2

    def __init__(self, rules: list[TextRuleValidator] | None = None) -> None:
        self._rules = (
            rules
            if rules is not None
            else [
                self._check_max_words,
                self._check_no_paragraphs,
            ]
        )

    def validate(self, scene: SceneSpec) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        for rule in self._rules:
            violations.extend(rule(scene))
        return violations

    def _check_max_words(self, scene: SceneSpec) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        for obj in scene.visual_objects:
            word_count = len(obj.semantic_purpose.split())
            if word_count > self.MAX_WORDS_PER_TEXT:
                violations.append(
                    RuleViolation(
                        scene_id=scene.scene_id,
                        object_id=obj.object_id,
                        rule="max_words_per_text_block",
                        actual=word_count,
                        expected=f"<= {self.MAX_WORDS_PER_TEXT}",
                        suggestion=(
                            f"Split '{obj.object_id}' into shorter text blocks."
                        ),
                    )
                )
        return violations

    def _check_no_paragraphs(self, scene: SceneSpec) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        for obj in scene.visual_objects:
            sentences = [
                s for s in obj.semantic_purpose.split(".") if s.strip()
            ]
            if len(sentences) > 3:
                violations.append(
                    RuleViolation(
                        scene_id=scene.scene_id,
                        object_id=obj.object_id,
                        rule="no_dense_paragraphs",
                        actual=len(sentences),
                        expected="<= 3 sentences",
                        suggestion=(
                            "Split this explanation across multiple scenes or timeline events."
                        ),
                    )
                )
        return violations
