from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from videos.core.application.director import Director
from videos.core.ports.renderer import RenderResult
from videos.validation.linter_service import LinterError


class StubRenderer:
    def render(
        self, scene_job: object, output_path: Path, quality: str = "preview"
    ) -> RenderResult:
        # Create a dummy image that is mostly centered to trigger the visual linter
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (854, 480), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)
        # Small centered rectangle
        draw.rectangle([400, 200, 450, 250], fill=(255, 255, 255))
        img.save(output_path.with_suffix(".png"))
        return RenderResult(
            output_path=output_path, duration_ms=10.0, success=True
        )


class GoodRenderer:
    def render(
        self, scene_job: object, output_path: Path, quality: str = "preview"
    ) -> RenderResult:
        # Create a spread image (Title + Body)
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (854, 480), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)
        # Title at top
        draw.rectangle([300, 50, 500, 80], fill=(255, 255, 255))
        # Body at center
        draw.rectangle([200, 200, 600, 300], fill=(255, 255, 255))
        img.save(output_path.with_suffix(".png"))
        return RenderResult(
            output_path=output_path, duration_ms=10.0, success=True
        )


class TestLinterIntegration:
    @pytest.mark.parametrize("concept_id", ["test_e2e"])
    def test_director_fails_on_poor_layout(
        self, concept_id: str, tmp_path: Path
    ) -> None:
        # Arrange
        from videos.concepts import register_all

        test_defs = Path(__file__).parents[2] / "fixtures" / "concepts"
        register_all(definitions_dir=test_defs)

        renderer = StubRenderer()
        artifact_store = MagicMock()
        # Use temp dir for output paths to avoid permission issues and cleanup
        artifact_store.resolve_scene_preview_path.side_effect = (
            lambda cid, sid: tmp_path / f"{cid}_{sid}.mp4"
        )
        artifact_store.resolve_output_path.return_value = (
            tmp_path / "final.mp4"
        )

        director = Director(
            concept_id=concept_id,
            renderer=renderer,
            scene_builder=MagicMock(),
            layout_engine=MagicMock(),
            artifact_store=artifact_store,
            telemetry=MagicMock(),
        )

        # Act & Assert
        with pytest.raises(LinterError, match="Visual Linter failed"):
            director.produce()

    @pytest.mark.parametrize("concept_id", ["test_e2e"])
    def test_director_passes_on_good_layout(
        self, concept_id: str, tmp_path: Path
    ) -> None:
        # Arrange
        from videos.concepts import register_all

        test_defs = Path(__file__).parents[2] / "fixtures" / "concepts"
        register_all(definitions_dir=test_defs)

        renderer = GoodRenderer()
        artifact_store = MagicMock()
        artifact_store.resolve_scene_preview_path.side_effect = (
            lambda cid, sid: tmp_path / f"{cid}_{sid}.mp4"
        )
        artifact_store.resolve_output_path.return_value = (
            tmp_path / "final.mp4"
        )

        director = Director(
            concept_id=concept_id,
            renderer=renderer,
            scene_builder=MagicMock(),
            layout_engine=MagicMock(),
            artifact_store=artifact_store,
            telemetry=MagicMock(),
        )

        # Act
        director.produce()

        # Assert (No exception raised)
        assert True
