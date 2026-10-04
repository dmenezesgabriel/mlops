"""Shared signature for scene-level validation rules.

One rule is a callable from a `SceneSpec` to the violations it finds; the
`*Rules` classes and `QualityGate(static_rules=…)` all take this shape.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from videos.domain.value_objects.quality import RuleViolation
from videos.domain.value_objects.scene_spec import SceneSpec

SceneRule: TypeAlias = Callable[[SceneSpec], list[RuleViolation]]
