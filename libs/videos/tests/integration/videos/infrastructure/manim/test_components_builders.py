from __future__ import annotations

import pytest

pytest.importorskip("manim")
pytestmark = pytest.mark.docker

from videos.application.components import ComponentRegistry  # noqa: E402
from videos.domain.scene_spec import ComponentSpec  # noqa: E402
from videos.infrastructure.manim.components import (  # noqa: E402
    DiagramComponent,
    TextComponent,
    TitleComponent,
    register_default_components,
)


class TestTitleComponent:
    def test_build_returns_mobject(self) -> None:
        from manim import Scene

        comp = TitleComponent()
        spec = ComponentSpec(
            type="title", region="title", props={"content": "Hello"}
        )
        scene = Scene()
        result = comp.build(spec, scene)
        assert result is not None


class TestTextComponent:
    def test_build_returns_mobject(self) -> None:
        from manim import Scene

        comp = TextComponent()
        spec = ComponentSpec(
            type="text", region="body", props={"content": "Body text"}
        )
        scene = Scene()
        result = comp.build(spec, scene)
        assert result is not None


class TestDiagramComponent:
    def test_build_cycle(self) -> None:
        from manim import Scene

        comp = DiagramComponent()
        spec = ComponentSpec(
            type="diagram",
            region="diagram",
            props={
                "kind": "cycle",
                "labels": ["A", "B", "C"],
                "colors": ["red", "green", "blue"],
            },
        )
        scene = Scene()
        result = comp.build(spec, scene)
        assert result is not None

    def test_build_linear(self) -> None:
        from manim import Scene

        comp = DiagramComponent()
        spec = ComponentSpec(
            type="diagram",
            region="diagram",
            props={
                "kind": "linear",
                "labels": ["X", "Y"],
                "colors": ["red", "blue"],
            },
        )
        scene = Scene()
        result = comp.build(spec, scene)
        assert result is not None

    def test_build_target(self) -> None:
        from manim import Scene

        comp = DiagramComponent()
        spec = ComponentSpec(
            type="diagram",
            region="diagram",
            props={"kind": "target"},
        )
        scene = Scene()
        result = comp.build(spec, scene)
        assert result is not None

    def test_defaults_to_cycle(self) -> None:
        from manim import Scene

        comp = DiagramComponent()
        spec = ComponentSpec(
            type="diagram",
            region="diagram",
            props={"labels": ["A", "B"], "colors": ["red", "green"]},
        )
        scene = Scene()
        result = comp.build(spec, scene)
        assert result is not None


class TestRegisterDefaultComponents:
    def test_registers_three_types(self) -> None:
        from manim import Scene

        registry = ComponentRegistry()
        register_default_components(registry)
        specs = [
            ComponentSpec(
                type="title", region="title", props={"content": "Hello"}
            ),
            ComponentSpec(
                type="text", region="text", props={"content": "World"}
            ),
            ComponentSpec(
                type="diagram",
                region="diagram",
                props={"labels": ["A", "B"], "colors": ["red", "blue"]},
            ),
        ]
        for spec in specs:
            result = registry.build(spec, Scene())
            assert result is not None

    def test_rejects_non_registry(self) -> None:
        with pytest.raises(TypeError, match="ComponentRegistry"):
            register_default_components(object())
