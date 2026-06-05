from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuleViolation:
    scene_id: str
    object_id: str | None
    rule: str
    actual: object
    expected: str
    suggestion: str


@dataclass(frozen=True)
class QualityReport:
    passed: bool
    violations: tuple[RuleViolation, ...] = ()

    def __post_init__(self) -> None:
        if self.passed and self.violations:
            raise ValueError("QualityReport passed=True but has violations")
        if not self.passed and not self.violations:
            raise ValueError("QualityReport passed=False but has no violations")
