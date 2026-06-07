from __future__ import annotations

from pydantic import model_validator
from pydantic.dataclasses import dataclass

from videos.domain._base import PydanticModel


@dataclass(frozen=True)
class RuleViolation(PydanticModel):
    scene_id: str
    rule: str
    suggestion: str
    object_id: str = ""
    actual: object = None
    expected: str = ""


@dataclass(frozen=True)
class QualityReport(PydanticModel):
    passed: bool
    violations: tuple[RuleViolation, ...] = ()

    @model_validator(mode="after")
    def _check_consistency(self) -> QualityReport:
        if self.passed and self.violations:
            raise ValueError("passed=True but has violations")
        if not self.passed and not self.violations:
            raise ValueError("passed=False but has no violations")
        return self
