from __future__ import annotations

import re

import pytest
from videos.application.pipeline_context import PipelineContext


class TestPipelineContext:
    def test_creates_with_concept_id(self) -> None:
        ctx = PipelineContext(concept_id="test")
        assert ctx.concept_id == "test"
        assert ctx.quality == "preview"

    def test_generates_correlation_id_at_construction(self) -> None:
        ctx = PipelineContext(concept_id="test")
        assert re.fullmatch(r"test_[0-9a-f]{8}", ctx.correlation_id)

    def test_preserves_explicit_correlation_id(self) -> None:
        ctx = PipelineContext(concept_id="test", correlation_id="test_123")
        assert ctx.correlation_id == "test_123"

    def test_accepts_quality(self) -> None:
        ctx = PipelineContext(concept_id="test", quality="final")
        assert ctx.quality == "final"

    def test_rejects_unknown_quality(self) -> None:
        with pytest.raises(ValueError, match="quality"):
            PipelineContext(concept_id="test", quality="bogus")

    def test_default_state_is_none(self) -> None:
        ctx = PipelineContext(concept_id="test")
        assert ctx.narrative is None
        assert ctx.storyboard is None
        assert ctx.quality_report is None
