from __future__ import annotations

from dataclasses import dataclass

from videos.core.domain.layout import LayoutSpec
from videos.core.domain.style import StyleSpec
from videos.core.domain.timeline import TimelineSpec


@dataclass(frozen=True)
class VisualObject:
    object_id: str
    region: str
    semantic_purpose: str


@dataclass(frozen=True)
class SceneSpec:
    scene_id: str
    title: str
    goal: str
    duration_seconds: float
    layout: LayoutSpec
    visual_objects: tuple[VisualObject, ...] = ()
    timeline: TimelineSpec | None = None
    style: StyleSpec | None = None

    def __post_init__(self) -> None:
        if not self.scene_id.strip():
            raise ValueError(f"scene_id must not be empty, got {self.scene_id!r}")
        if not self.goal.strip():
            raise ValueError(f"goal must not be empty for scene {self.scene_id!r}")
        if self.duration_seconds <= 0:
            raise ValueError(
                f"duration_seconds must be positive for scene {self.scene_id!r}, "
                f"got {self.duration_seconds}"
            )
