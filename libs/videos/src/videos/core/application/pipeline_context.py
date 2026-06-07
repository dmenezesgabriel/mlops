from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from videos.concepts.base import ConceptExtension
    from videos.core.domain.narrative import Narrative
    from videos.core.domain.quality import QualityReport
    from videos.core.domain.storyboard import Storyboard
    from videos.core.ports.renderer import RenderResult


@dataclass
class PipelineContext:
    concept_id: str
    quality: str = "preview"
    correlation_id: str = ""
    concept_extension: ConceptExtension | None = None
    narrative: Narrative | None = None
    storyboard: Storyboard | None = None
    quality_report: QualityReport | None = None
    scene_results: list[RenderResult] | None = None
    final_result: RenderResult | None = None
