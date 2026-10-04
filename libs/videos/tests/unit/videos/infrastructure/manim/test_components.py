"""Unit coverage for DiagramComponent prop validation.

Validation runs before the optional `manim` import inside `build`, so these
reject arms need no fake-manim fixture — the named ValueError fires first.
"""

from __future__ import annotations

import pytest
from videos.domain.value_objects.scene_spec import ComponentSpec
from videos.infrastructure.manim.components import DiagramComponent


def _diagram_spec(props: dict[str, object]) -> ComponentSpec:
    return ComponentSpec(type="diagram", region="diagram", props=props)


class TestDiagramComponentPropValidation:
    def test_rejects_str_labels(self) -> None:
        # "abc" iterated as 3 single-char labels — the G-160 measured harm
        with pytest.raises(ValueError, match="labels"):
            DiagramComponent().build(
                _diagram_spec({"labels": "abc"}), object()
            )

    def test_rejects_non_str_label_element(self) -> None:
        with pytest.raises(ValueError, match="labels"):
            DiagramComponent().build(
                _diagram_spec({"labels": ["a", 1]}), object()
            )

    @pytest.mark.parametrize("colors", [[], "red", [1, 2]])
    def test_rejects_bad_colors(self, colors: object) -> None:
        with pytest.raises(ValueError, match="colors"):
            DiagramComponent().build(
                _diagram_spec({"colors": colors}), object()
            )

    @pytest.mark.parametrize("kind", ["radial", 42])
    def test_rejects_unknown_kind(self, kind: object) -> None:
        # "radial" silently fell back to cycle before this fix
        with pytest.raises(ValueError, match="kind"):
            DiagramComponent().build(_diagram_spec({"kind": kind}), object())

    @pytest.mark.parametrize("rings", ["four", True])
    def test_rejects_bad_rings(self, rings: object) -> None:
        with pytest.raises(ValueError, match="rings"):
            DiagramComponent().build(
                _diagram_spec({"kind": "target", "rings": rings}), object()
            )

    def test_rejects_bad_max_radius(self) -> None:
        with pytest.raises(ValueError, match="max_radius"):
            DiagramComponent().build(
                _diagram_spec({"kind": "target", "max_radius": "big"}),
                object(),
            )
