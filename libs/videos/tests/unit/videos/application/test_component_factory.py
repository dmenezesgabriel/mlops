import pytest
from videos.application.component_factory import ComponentFactory
from videos.domain.value_objects.narrative import (
    Beat,
    BeatKind,
    NarrationLine,
)


def _beat(visual_key: str, params: dict[str, object]) -> Beat:
    return Beat(
        kind=BeatKind.REVEAL,
        narration=NarrationLine("x", 3.0),
        visual_key=visual_key,
        params=params,
    )


class TestComponentFactory:
    @pytest.mark.parametrize(
        ("visual_key", "expected_kind"),
        [
            ("target", "target"),
            ("cycle", "cycle"),
            ("phase_collect", "cycle"),
        ],
    )
    def test_diagram_beats_produce_diagram_component(
        self, visual_key: str, expected_kind: str
    ) -> None:
        # Diagram-dispatched keys must reach a builder — a presence assert
        # pins the dispatch so a dropped rule can't render keyless beats.
        specs = ComponentFactory().create_components(_beat(visual_key, {}))
        diagram = next(s for s in specs if s.type == "diagram")
        assert diagram.props["kind"] == expected_kind

    def test_rejects_kind_override_in_params(self) -> None:
        beat = _beat("target", {"kind": "cycle"})
        with pytest.raises(ValueError, match="kind"):
            ComponentFactory().create_components(beat)

    def test_dispatched_kind_wins_over_params(self) -> None:
        beat = _beat("target", {"labels": ["a"]})
        specs = ComponentFactory().create_components(beat)
        diagram = next(s for s in specs if s.type == "diagram")
        assert diagram.props["kind"] == "target"

    def test_non_diagram_beat_with_kind_params_untouched(self) -> None:
        beat = _beat("plain_visual", {"kind": "cycle"})
        specs = ComponentFactory().create_components(beat)
        assert all(s.type != "diagram" for s in specs)
