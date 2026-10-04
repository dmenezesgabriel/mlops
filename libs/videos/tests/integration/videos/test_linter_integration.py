from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from videos.application.director import Director
from videos.application.ports.renderer import RenderResult
from videos.infrastructure.validation.linter_service import (
    LinterError,
    LinterService,
)

from tests._fakes import (
    FakeSceneBuilder,
    PassthroughLayoutEngine,
    RecordingTelemetry,
    StubArtifactStore,
)

# Minimal ISO-BMFF header: verify_video rejects empty/undecodable mp4s, so a
# stub renderer's success=True must leave a header-valid file behind.
_FAKE_MP4_BYTES = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16


class StubRenderer:
    @contextlib.contextmanager
    def quality_context(self, quality: str) -> Iterator[None]:
        yield

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
        output_path.write_bytes(_FAKE_MP4_BYTES)
        return RenderResult(
            output_path=output_path, duration_ms=10.0, success=True
        )


class GoodRenderer:
    @contextlib.contextmanager
    def quality_context(self, quality: str) -> Iterator[None]:
        yield

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
        output_path.write_bytes(_FAKE_MP4_BYTES)
        return RenderResult(
            output_path=output_path, duration_ms=10.0, success=True
        )


class TestLinterIntegration:
    @pytest.mark.parametrize("concept_id", ["test_e2e"])
    def test_director_fails_on_poor_layout(
        self, concept_id: str, tmp_path: Path
    ) -> None:
        # Arrange
        from videos.domain.entities.concept_registry import ConceptRegistry
        from videos.infrastructure.declarative import register_all

        registry = ConceptRegistry()
        test_defs = Path(__file__).parents[2] / "fixtures" / "concepts"
        register_all(registry, definitions_dir=test_defs)

        renderer = StubRenderer()

        director = Director(
            concept_id=concept_id,
            renderer=renderer,
            scene_builder=FakeSceneBuilder(),
            layout_engine=PassthroughLayoutEngine(),
            artifact_store=StubArtifactStore(tmp_path),
            telemetry=RecordingTelemetry(),
            linter_service=LinterService(),
            concept_registry=registry,
        )

        # Act & Assert
        with pytest.raises(LinterError, match="Visual Linter failed"):
            director.produce()

    @pytest.mark.parametrize("concept_id", ["test_e2e"])
    def test_director_passes_on_good_layout(
        self, concept_id: str, tmp_path: Path
    ) -> None:
        # Arrange
        from videos.domain.entities.concept_registry import ConceptRegistry
        from videos.infrastructure.declarative import register_all

        registry = ConceptRegistry()
        test_defs = Path(__file__).parents[2] / "fixtures" / "concepts"
        register_all(registry, definitions_dir=test_defs)

        renderer = GoodRenderer()

        director = Director(
            concept_id=concept_id,
            renderer=renderer,
            scene_builder=FakeSceneBuilder(),
            layout_engine=PassthroughLayoutEngine(),
            artifact_store=StubArtifactStore(tmp_path),
            telemetry=RecordingTelemetry(),
            linter_service=LinterService(),
            concept_registry=registry,
        )

        # Act
        director.produce()

        # Assert (No exception raised)
        assert True
