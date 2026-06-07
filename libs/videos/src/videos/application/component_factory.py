from __future__ import annotations

from collections.abc import Callable

from videos.domain.narrative import Beat
from videos.domain.scene_spec import ComponentSpec


class ComponentFactory:
    _diagram_rules: list[
        tuple[Callable[[str], bool], Callable[[Beat], ComponentSpec | None]]
    ] = []

    @classmethod
    def _init_diagram_rules(cls) -> None:
        if cls._diagram_rules:
            return
        cls._diagram_rules = [
            (lambda k: k == "target", cls._build_target_diagram),
            (
                lambda k: k == "cycle" or k.startswith("phase_"),
                cls._build_cycle_diagram,
            ),
        ]

    @staticmethod
    def _build_target_diagram(beat: Beat) -> ComponentSpec | None:
        return ComponentSpec(
            type="diagram",
            region="diagram",
            props={"kind": "target", **beat.params},
        )

    @staticmethod
    def _build_cycle_diagram(beat: Beat) -> ComponentSpec | None:
        return ComponentSpec(
            type="diagram",
            region="diagram",
            props={"kind": "cycle", **beat.params},
        )

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
        self._init_diagram_rules()
        for matches, builder in self._diagram_rules:
            if matches(beat.visual_key):
                return builder(beat)
        return None
