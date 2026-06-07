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
