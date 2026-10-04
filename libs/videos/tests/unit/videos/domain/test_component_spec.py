from __future__ import annotations

import pytest
from videos.domain.value_objects.scene_spec import ComponentSpec


class TestComponentSpec:
    def test_stores_type_and_region(self) -> None:
        c = ComponentSpec(type="title", region="title")
        assert c.type == "title"
        assert c.region == "title"

    def test_default_props_is_empty(self) -> None:
        c = ComponentSpec(type="text", region="body")
        assert c.props == {}

    def test_default_props_reject_interior_mutation(self) -> None:
        c = ComponentSpec(type="text", region="body")
        with pytest.raises(TypeError):
            c.props["injected"] = 1  # type: ignore[index]

    def test_props_reject_interior_mutation(self) -> None:
        c = ComponentSpec(type="title", region="title", props={"a": 1})
        with pytest.raises(TypeError):
            c.props["injected"] = 1  # type: ignore[index]

    def test_props_isolated_from_source_dict(self) -> None:
        source = {"a": 1}
        c = ComponentSpec(type="title", region="title", props=source)
        source["b"] = 2
        assert "b" not in c.props

    def test_stores_props(self) -> None:
        c = ComponentSpec(
            type="diagram", region="diagram", props={"kind": "cycle"}
        )
        assert c.props == {"kind": "cycle"}

    def test_to_dict_round_trip(self) -> None:
        c = ComponentSpec(
            type="title", region="title", props={"text": "Hello"}
        )
        data = c.to_dict()
        assert data == {
            "type": "title",
            "region": "title",
            "props": {"text": "Hello"},
        }
        restored = ComponentSpec.from_dict(data)
        assert restored == c

    def test_from_dict(self) -> None:
        data = {
            "type": "text",
            "region": "body",
            "props": {"content": "Hello world"},
        }
        c = ComponentSpec.from_dict(data)
        assert c.type == "text"
        assert c.region == "body"
        assert c.props == {"content": "Hello world"}
