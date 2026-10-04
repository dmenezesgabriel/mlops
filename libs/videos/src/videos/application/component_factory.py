from __future__ import annotations

from collections.abc import Callable, Mapping

from videos.domain.value_objects.narrative import Beat
from videos.domain.value_objects.scene_spec import ComponentSpec


def _diagram_props(
    kind: str, params: Mapping[str, object], visual_key: str
) -> dict[str, object]:
    # `kind` is the dispatch result — a params copy silently re-dispatches
    # to a different component, so the reserved key is rejected instead.
    if "kind" in params:
        raise ValueError(
            f"Beat params must not contain 'kind' (dispatch sets it "
            f"from visual_key), got {visual_key!r} params "
            f"{dict(params)!r}"
        )
    return {"kind": kind, **params}


def _build_target_diagram(beat: Beat) -> ComponentSpec | None:
    return ComponentSpec(
        type="diagram",
        region="diagram",
        props=_diagram_props("target", beat.params, beat.visual_key),
    )


def _build_cycle_diagram(beat: Beat) -> ComponentSpec | None:
    return ComponentSpec(
        type="diagram",
        region="diagram",
        props=_diagram_props("cycle", beat.params, beat.visual_key),
    )


_DiagramRule = tuple[
    Callable[[str], bool], Callable[[Beat], ComponentSpec | None]
]

_DIAGRAM_RULES: tuple[_DiagramRule, ...] = (
    (lambda key: key == "target", _build_target_diagram),
    (
        lambda key: key == "cycle" or key.startswith("phase_"),
        _build_cycle_diagram,
    ),
)


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
        for matches, builder in _DIAGRAM_RULES:
            if matches(beat.visual_key):
                return builder(beat)
        return None
