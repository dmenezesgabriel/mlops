from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from videos.domain.value_objects.identifiers import require_quality

if TYPE_CHECKING:
    from videos.application.ports.renderer import RenderResult
    from videos.domain.entities.concept_extension import ConceptExtension
    from videos.domain.entities.narrative import Narrative
    from videos.domain.entities.storyboard import Storyboard
    from videos.domain.value_objects.quality import QualityReport


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

    def __post_init__(self) -> None:
        # Guard at the context boundary so both `produce` and a directly
        # constructed `execute(context)` reject a quality that would skip
        # the final-render branch and mislead at the artifact store.
        require_quality(self.quality)
        # The context owns the correlation id so every pipeline run —
        # including partial runs that never reach the narrative step —
        # carries one identifier end to end.
        if not self.correlation_id:
            self.correlation_id = f"{self.concept_id}_{uuid.uuid4().hex[:8]}"
