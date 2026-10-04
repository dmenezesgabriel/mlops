"""SceneSpec value objects — ComponentSpec, VisualObject, SceneSpec."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import (
    Field,
    ValidationInfo,
    field_validator,
)
from pydantic.dataclasses import dataclass

from videos.domain._base import PydanticModel, freeze_mapping, require_slug
from videos.domain.value_objects.layout import LayoutSpec
from videos.domain.value_objects.style import StyleSpec
from videos.domain.value_objects.timeline import TimelineSpec


@dataclass(frozen=True)
class ComponentSpec(PydanticModel):
    type: str
    region: str
    props: Mapping[str, object] = Field(
        default_factory=dict, validate_default=True
    )

    @field_validator("props")
    @classmethod
    def _props_immutable(cls, v: Mapping[str, object]) -> Mapping[str, object]:
        return freeze_mapping(v)


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
    def _scene_id_must_be_slug(cls, v: str) -> str:
        return require_slug(v, "scene_id")

    @field_validator("goal")
    @classmethod
    def _goal_must_not_be_empty(cls, v: str, info: ValidationInfo) -> str:
        if not v.strip():
            raise ValueError(
                f"goal must not be empty for scene "
                f"{info.data.get('scene_id')!r}"
            )
        return v

    @field_validator("duration_seconds")
    @classmethod
    def _duration_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(
                f"duration_seconds must be positive for scene, got {v}"
            )
        return v
