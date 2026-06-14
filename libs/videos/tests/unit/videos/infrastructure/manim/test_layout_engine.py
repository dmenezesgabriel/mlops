from __future__ import annotations

import pytest
from videos.domain.layout import LayoutRegion, LayoutSpec
from videos.domain.scene_spec import ComponentSpec, SceneSpec
from videos.infrastructure.manim.layout_engine import ManimLayoutEngine


@pytest.fixture
def engine() -> ManimLayoutEngine:
    return ManimLayoutEngine()


def _minimal_scene(components: tuple[ComponentSpec, ...]) -> SceneSpec:
    return SceneSpec(
        scene_id="test",
        title="Test",
        goal="Test",
        duration_seconds=1.0,
        layout=LayoutSpec(regions=(LayoutRegion.TITLE, LayoutRegion.BODY)),
        components=components,
    )


class TestManimLayoutEngine:
    def test_apply_sets_title_position(
        self, engine: ManimLayoutEngine
    ) -> None:
        comp = ComponentSpec(type="title", region="title")
        scene = _minimal_scene((comp,))

        result = engine.apply(scene)

        title_comp = result.components[0]
        assert "position" in title_comp.props
        # Assuming TITLE maps to UP * 3 (or [0, 3, 0])
        assert title_comp.props["position"] == [0, 3, 0]

    def test_apply_sets_body_position(self, engine: ManimLayoutEngine) -> None:
        comp = ComponentSpec(type="text", region="body")
        scene = _minimal_scene((comp,))

        result = engine.apply(scene)

        body_comp = result.components[0]
        assert "position" in body_comp.props
        # Assuming BODY maps to [0, 0, 0] or similar
        assert body_comp.props["position"] == [0, 0, 0]

    def test_apply_sets_diagram_position(
        self, engine: ManimLayoutEngine
    ) -> None:
        comp = ComponentSpec(type="diagram", region="diagram")
        scene = _minimal_scene((comp,))

        result = engine.apply(scene)

        diag_comp = result.components[0]
        assert "position" in diag_comp.props
        # Assuming DIAGRAM maps to [0, -1, 0] or similar
        assert diag_comp.props["position"] == [0, -1, 0]

    def test_apply_stacks_multiple_components_in_same_region(
        self, engine: ManimLayoutEngine
    ) -> None:
        comp1 = ComponentSpec(type="text", region="body")
        comp2 = ComponentSpec(type="text", region="body")
        comp3 = ComponentSpec(type="text", region="body")
        scene = _minimal_scene((comp1, comp2, comp3))

        result = engine.apply(scene)

        assert len(result.components) == 3
        assert result.components[0].props["position"] == [0.0, 0.0, 0.0]
        assert result.components[1].props["position"] == [0.0, -0.8, 0.0]
        assert result.components[2].props["position"] == [0.0, -1.6, 0.0]
