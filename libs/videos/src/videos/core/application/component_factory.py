from __future__ import annotations

from videos.core.domain.narrative import Beat
from videos.core.domain.scene_spec import ComponentSpec


class ComponentFactory:
    def create_components(self, beat: Beat) -> list[ComponentSpec]:
        components = [
            self._create_title_component(beat),
            self._create_body_component(beat),
        ]

        diagram = self._create_diagram_component(beat)
        if diagram:
            components.append(diagram)

        return components

    def _create_title_component(self, beat: Beat) -> ComponentSpec:
        return ComponentSpec(
            type="title",
            region="title",
            props={"content": beat.visual_key.replace("_", " ").title()},
        )

    def _create_body_component(self, beat: Beat) -> ComponentSpec:
        return ComponentSpec(
            type="text",
            region="body",
            props={"content": beat.narration.text},
        )

    def _create_diagram_component(self, beat: Beat) -> ComponentSpec | None:
        if beat.visual_key == "target":
            return ComponentSpec(
                type="diagram",
                region="diagram",
                props={"kind": "target", **beat.params},
            )
        if "phase_" in beat.visual_key or beat.visual_key == "cycle":
            return ComponentSpec(
                type="diagram",
                region="diagram",
                props={"kind": "cycle", **beat.params},
            )
        return None
