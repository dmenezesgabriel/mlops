from __future__ import annotations

import uuid

from videos.concepts.registry import ConceptRegistry
from videos.core.application.pipeline_context import PipelineContext
from videos.core.domain.concept import ConceptId


class NarrativePlanningStep:
    def execute(self, context: PipelineContext) -> PipelineContext:
        extension = ConceptRegistry.get(ConceptId(context.concept_id))
        narrative = extension.create_narrative()
        context.concept_extension = extension
        context.narrative = narrative
        context.correlation_id = f"{context.concept_id}_{uuid.uuid4().hex[:8]}"
        return context
