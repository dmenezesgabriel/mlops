from __future__ import annotations

import pytest
from videos.components.registry import ComponentRegistry
from videos.core.domain.scene_spec import ComponentSpec


class _StubBuilder:
    def __init__(self) -> None:
        self.calls: list[ComponentSpec] = []

    def build(self, spec: ComponentSpec, scene: object) -> object:
        self.calls.append(spec)
        return object()


class TestComponentRegistry:
    def test_register_and_build(self) -> None:
        registry = ComponentRegistry()
        builder = _StubBuilder()
        registry.register("title", builder)

        spec = ComponentSpec(type="title", region="title")
        result = registry.build(spec, object())
        assert result is not None
        assert len(builder.calls) == 1

    def test_build_unknown_type_raises(self) -> None:
        registry = ComponentRegistry()
        spec = ComponentSpec(type="nonexistent", region="title")
        with pytest.raises(LookupError, match="nonexistent"):
            registry.build(spec, object())

    def test_register_overwrites(self) -> None:
        registry = ComponentRegistry()
        b1 = _StubBuilder()
        b2 = _StubBuilder()
        registry.register("x", b1)
        registry.register("x", b2)
        spec = ComponentSpec(type="x", region="title")
        registry.build(spec, object())
        assert len(b1.calls) == 0
        assert len(b2.calls) == 1

    def test_build_passes_spec_and_scene(self) -> None:
        registry = ComponentRegistry()
        builder = _StubBuilder()
        registry.register("text", builder)

        spec = ComponentSpec(
            type="text", region="body", props={"content": "hello"}
        )
        scene = object()
        registry.build(spec, scene)
        assert builder.calls[0] is spec
