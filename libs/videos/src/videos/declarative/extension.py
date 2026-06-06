from __future__ import annotations

from typing import Any

from videos.concepts.base import ConceptExtension
from videos.core.domain.concept import Concept
from videos.core.domain.narrative import Beat, Narrative
from videos.core.domain.scene_spec import SceneSpec


class DeclarativeConceptExtension(ConceptExtension):
    def __init__(self, data: dict[str, Any]) -> None:
        raw_concept = data["concept"]
        if isinstance(raw_concept["id"], str):
            raw_concept = {**raw_concept, "id": {"value": raw_concept["id"]}}
        self._concept: Concept = Concept.from_dict(raw_concept)

        raw_beats = data.get("narrative", {}).get("beats", [])
        if not raw_beats:
            raise ValueError(
                f"Narrative must have at least one beat for {self._concept.id.value!r}"
            )
        beats = tuple(Beat.from_dict(b) for b in raw_beats)
        self._narrative = Narrative(concept=self._concept, beats=beats)

        raw_scenes = data.get("scenes")
        self._scenes: tuple[SceneSpec, ...] | None
        if raw_scenes is not None:
            self._scenes = tuple(SceneSpec.from_dict(s) for s in raw_scenes)
        else:
            self._scenes = None

    @property
    def concept(self) -> Concept:
        return self._concept

    def create_narrative(self) -> Narrative:
        return self._narrative

    @property
    def scenes(self) -> tuple[SceneSpec, ...] | None:
        return self._scenes
