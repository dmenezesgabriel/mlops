from __future__ import annotations

from videos.adapters.manim.components import (
    DiagramComponent,
    TextComponent,
    TitleComponent,
    register_default_components,
)
from videos.components.registry import ComponentRegistry


class TestRegisterDefaultComponents:
    def test_registers_three_types(self) -> None:
        registry = ComponentRegistry()
        register_default_components(registry)

        for type_name in ("title", "text", "diagram"):
            assert type_name in registry._builders

    def test_title_builder_is_title_component(self) -> None:
        registry = ComponentRegistry()
        register_default_components(registry)
        assert isinstance(registry._builders["title"], TitleComponent)

    def test_text_builder_is_text_component(self) -> None:
        registry = ComponentRegistry()
        register_default_components(registry)
        assert isinstance(registry._builders["text"], TextComponent)

    def test_diagram_builder_is_diagram_component(self) -> None:
        registry = ComponentRegistry()
        register_default_components(registry)
        assert isinstance(registry._builders["diagram"], DiagramComponent)

    def test_rejects_non_registry(self) -> None:
        raised = False
        try:
            register_default_components(object())
        except TypeError:
            raised = True
        assert raised
