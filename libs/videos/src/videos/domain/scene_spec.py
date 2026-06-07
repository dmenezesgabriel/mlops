from __future__ import annotations

from dataclasses import field

from pydantic import field_validator
from pydantic.dataclasses import dataclass

from videos.domain._base import PydanticModel
from videos.domain.layout import LayoutSpec
from videos.domain.style import StyleSpec
from videos.domain.timeline import TimelineSpec


@dataclass(frozen=True)
class ComponentSpec(PydanticModel):
    type: str
    region: str
    props: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class VisualObject(PydanticModel):
    object_id: str
    region: str
    semantic_purpose: str


@dataclass(frozen=True)
class SceneSpec(PydanticModel):
    scene_id: str
    title: str
    goal: str
    duration_seconds: float
    layout: LayoutSpec
    visual_objects: tuple[VisualObject, ...] = ()
    timeline: TimelineSpec | None = None
    style: StyleSpec | None = None
    components: tuple[ComponentSpec, ...] = ()

    @field_validator("scene_id")
    @classmethod
    def _scene_id_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(f"scene_id must not be empty, got {v!r}")
        return v

    @field_validator("goal")
    @classmethod
    def _goal_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(f"goal must not be empty for scene {v!r}")
        return v

    @field_validator("duration_seconds")
    @classmethod
    def _duration_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(
                f"duration_seconds must be positive for scene, got {v}"
            )
        return v
