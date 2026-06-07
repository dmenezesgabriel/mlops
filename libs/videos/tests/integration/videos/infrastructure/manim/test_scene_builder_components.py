from __future__ import annotations

import pytest

pytest.importorskip("manim")
pytestmark = pytest.mark.docker

from videos.application.components import ComponentRegistry  # noqa: I001, E402
from videos.domain.layout import LayoutRegion, LayoutSpec  # noqa: I001, E402
from videos.domain.scene_spec import ComponentSpec, SceneSpec  # noqa: I001, E402
from videos.infrastructure.manim.components import register_default_components  # noqa: I001, E402
from videos.infrastructure.manim.scene_builder import ManimSceneBuilder  # noqa: I001, E402


def _scene_with_components(components: tuple[ComponentSpec, ...]) -> SceneSpec:
    return SceneSpec(
        scene_id="test_scene",
        title="Test",
        goal="Test goal",
        duration_seconds=1.0,
        layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        components=components,
    )


class TestManimSceneBuilder:
    def test_build_returns_scene_without_registry(self) -> None:
        builder = ManimSceneBuilder()
        spec = _scene_with_components(())
        scene = builder.build(spec)
        assert scene is not None

    def test_build_with_registry_renders_components(self) -> None:
        registry = ComponentRegistry()
        register_default_components(registry)
        builder = ManimSceneBuilder(registry=registry)
        spec = _scene_with_components(
            (
                ComponentSpec(
                    type="title", region="title", props={"content": "Hello"}
                ),
            )
        )
        scene = builder.build(spec)
        assert scene is not None

    def test_with_multiple_components(self) -> None:
        registry = ComponentRegistry()
        register_default_components(registry)
        builder = ManimSceneBuilder(registry=registry)
        spec = _scene_with_components(
            (
                ComponentSpec(
                    type="title", region="title", props={"content": "Title"}
                ),
                ComponentSpec(
                    type="text", region="body", props={"content": "Body"}
                ),
            )
        )
        scene = builder.build(spec)
        assert scene is not None
