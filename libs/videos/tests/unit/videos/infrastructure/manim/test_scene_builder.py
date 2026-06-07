from __future__ import annotations

from videos.application.components import ComponentRegistry
from videos.infrastructure.manim.scene_builder import ManimSceneBuilder


class TestManimSceneBuilder:
    def test_default_constructor_creates_empty_registry(self) -> None:
        builder = ManimSceneBuilder()
        assert isinstance(builder._registry, ComponentRegistry)

    def test_accepts_custom_registry(self) -> None:
        registry = ComponentRegistry()
        builder = ManimSceneBuilder(registry=registry)
        assert builder._registry is registry

    def test_without_components_uses_old_behavior(self) -> None:
        builder = ManimSceneBuilder()
        assert builder._registry is not None

    def test_build_uses_static_scene_class(self) -> None:
        from videos.domain.layout import LayoutRegion, LayoutSpec
        from videos.domain.scene_spec import SceneSpec

        builder = ManimSceneBuilder()
        spec = SceneSpec(
            scene_id="s1",
            title="Test",
            goal="Goal",
            duration_seconds=3.0,
            layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        )
        scene1 = builder.build(spec)
        scene2 = builder.build(spec)

        assert scene1.__class__.__name__ == "ConfigurableScene"
        assert scene1.__class__ is scene2.__class__

    def test_build_storyboard_uses_static_scene_class(self) -> None:
        from unittest.mock import MagicMock

        from videos.domain.layout import LayoutRegion, LayoutSpec
        from videos.domain.scene_spec import SceneSpec
        from videos.domain.storyboard import Storyboard

        builder = ManimSceneBuilder()
        spec = SceneSpec(
            scene_id="s1",
            title="Test",
            goal="Goal",
            duration_seconds=3.0,
            layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        )
        storyboard = Storyboard(scenes=[spec])
        layout_engine = MagicMock()

        scene1 = builder.build_storyboard(storyboard, layout_engine)
        scene2 = builder.build_storyboard(storyboard, layout_engine)

        assert scene1.__class__.__name__ == "StoryboardScene"
        assert scene1.__class__ is scene2.__class__
