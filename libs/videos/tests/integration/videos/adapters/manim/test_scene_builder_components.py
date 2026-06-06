from __future__ import annotations

import pytest

pytest.importorskip("manim")
pytestmark = pytest.mark.docker

from videos.adapters.manim.components import (  # noqa: E402
    register_default_components,
)
from videos.adapters.manim.scene_builder import ManimSceneBuilder  # noqa: E402
from videos.components.registry import ComponentRegistry  # noqa: E402
from videos.core.domain.layout import LayoutRegion, LayoutSpec  # noqa: E402
from videos.core.domain.scene_spec import (  # noqa: E402
    ComponentSpec,
    SceneSpec,
)


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
