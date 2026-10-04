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
