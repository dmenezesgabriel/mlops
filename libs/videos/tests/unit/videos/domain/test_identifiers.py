from __future__ import annotations

import pytest
from videos.domain.value_objects.identifiers import QualityLevel


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
