"""Declarative concept extension — builds a ConceptExtension from YAML.

Loads YAML concept definitions into domain objects for use by the registry
and director pipeline. Structure is validated eagerly so a malformed
document fails with the offending field named rather than an AttributeError
deeper in the pydantic adapters.
"""

from __future__ import annotations

from typing import Any, cast

from videos.domain.entities.concept import Concept
from videos.domain.entities.concept_extension import ConceptExtension
from videos.domain.entities.narrative import Narrative
from videos.domain.value_objects.narrative import Beat
from videos.domain.value_objects.scene_spec import SceneSpec


def _require_mapping(value: object, context: str) -> dict[str, Any]:
    """Return `value` as a mapping or name the context that was violated."""
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    raise ValueError(
        f"expected mapping at {context}, got {type(value).__name__}"
    )


def _require_list(value: object, context: str) -> list[object]:
    """Return `value` as a list or name the context that was violated."""
    if isinstance(value, list):
        return cast(list[object], value)
    raise ValueError(f"expected list at {context}, got {type(value).__name__}")


class DeclarativeConceptExtension(ConceptExtension):
    """ConceptExtension built from a loaded YAML document mapping."""

    def __init__(self, data: object) -> None:
        document = _require_mapping(data, "document root")
        self._concept: Concept = Concept.from_dict(self._raw_concept(document))
        self._narrative = Narrative(
            concept=self._concept, beats=self._read_beats(document)
        )
        self._scenes: tuple[SceneSpec, ...] | None = self._read_scenes(
            document
        )

    @staticmethod
    def _raw_concept(document: dict[str, Any]) -> dict[str, Any]:
        raw = _require_mapping(document.get("concept"), "concept")
        # Concept.from_dict needs the SceneId/ConceptId shape; declarative
        # files carry the string, so wrap it before pydantic sees it.
        if isinstance(raw.get("id"), str):
            return {**raw, "id": {"value": raw["id"]}}
        return raw

    def _read_beats(self, document: dict[str, Any]) -> tuple[Beat, ...]:
        raw_narrative = document.get("narrative")
        narrative: dict[str, Any] = (
            {}
            if raw_narrative is None
            else _require_mapping(raw_narrative, "narrative")
        )
        raw_beats = narrative.get("beats", [])
        if not raw_beats:
            raise ValueError(
                f"Narrative must have at least one beat for {self._concept.id.value!r}"
            )
        beats = _require_list(raw_beats, "narrative.beats")
        return tuple(
            Beat.from_dict(_require_mapping(beat, f"narrative.beats[{i}]"))
            for i, beat in enumerate(beats)
        )

    @staticmethod
    def _read_scenes(
        document: dict[str, Any],
    ) -> tuple[SceneSpec, ...] | None:
        raw_scenes = document.get("scenes")
        if raw_scenes is None:
            return None
        scenes = _require_list(raw_scenes, "scenes")
        return tuple(
            SceneSpec.from_dict(_require_mapping(scene, f"scenes[{i}]"))
            for i, scene in enumerate(scenes)
        )

    @property
    def concept(self) -> Concept:
        return self._concept

    @property
    def scenes(self) -> tuple[SceneSpec, ...] | None:
        return self._scenes

    def create_narrative(self) -> Narrative:
        return self._narrative
