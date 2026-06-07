from __future__ import annotations

from videos.application.pipeline_context import PipelineContext


class TestPipelineContext:
    def test_creates_with_concept_id(self) -> None:
        ctx = PipelineContext(concept_id="test")
        assert ctx.concept_id == "test"
        assert ctx.quality == "preview"

    def test_accepts_quality(self) -> None:
        ctx = PipelineContext(concept_id="test", quality="final")
        assert ctx.quality == "final"

    def test_default_state_is_none(self) -> None:
        ctx = PipelineContext(concept_id="test")
        assert ctx.narrative is None
        assert ctx.storyboard is None
        assert ctx.quality_report is None
