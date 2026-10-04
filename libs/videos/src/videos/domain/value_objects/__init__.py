"""Domain value objects — immutable data structures identified by value."""

from videos.domain.value_objects.identifiers import QualityLevel
from videos.domain.value_objects.layout import LayoutRegion, LayoutSpec
from videos.domain.value_objects.narrative import Beat, BeatKind, NarrationLine
from videos.domain.value_objects.quality import QualityReport, RuleViolation
from videos.domain.value_objects.scene_spec import (
    ComponentSpec,
    SceneSpec,
    VisualObject,
)
from videos.domain.value_objects.style import StyleSpec
from videos.domain.value_objects.timeline import TimelineEvent, TimelineSpec

__all__ = [
    "QualityLevel",
    "LayoutRegion",
    "LayoutSpec",
    "Beat",
    "BeatKind",
    "NarrationLine",
    "QualityReport",
    "RuleViolation",
    "ComponentSpec",
    "SceneSpec",
    "VisualObject",
    "StyleSpec",
    "TimelineEvent",
    "TimelineSpec",
]
