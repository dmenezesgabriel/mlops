from __future__ import annotations

import pytest
from videos.domain.identifiers import ComponentType, QualityLevel, SceneId


class TestSceneId:
    def test_creates_from_non_empty_string(self) -> None:
        sid = SceneId("test_scene_1")
        assert sid.value == "test_scene_1"

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            SceneId("")

    def test_rejects_whitespace_only(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            SceneId("   ")

    def test_repr(self) -> None:
        sid = SceneId("abc")
        assert repr(sid) == "SceneId('abc')"


class TestQualityLevel:
    def test_preview_value(self) -> None:
        assert QualityLevel.PREVIEW.value == "preview"

    def test_final_value(self) -> None:
        assert QualityLevel.FINAL.value == "final"

    def test_accepts_valid_string(self) -> None:
        assert QualityLevel("preview") == QualityLevel.PREVIEW
        assert QualityLevel("final") == QualityLevel.FINAL

    def test_rejects_invalid_string(self) -> None:
        with pytest.raises(ValueError):
            QualityLevel("high")


class TestComponentType:
    def test_standard_types(self) -> None:
        assert ComponentType.TITLE.value == "title"
        assert ComponentType.TEXT.value == "text"
        assert ComponentType.DIAGRAM.value == "diagram"

    def test_diagram_variants(self) -> None:
        assert ComponentType.CYCLE.value == "cycle"
        assert ComponentType.TARGET.value == "target"
        assert ComponentType.LINEAR.value == "linear"

    def test_accepts_valid_string(self) -> None:
        assert ComponentType("title") == ComponentType.TITLE
