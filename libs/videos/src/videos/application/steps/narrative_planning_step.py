from __future__ import annotations

import uuid

from videos.application.pipeline_context import PipelineContext
from videos.domain.concept import ConceptId
from videos.domain.concept_registry import ConceptRegistry


class NarrativePlanningStep:
    def __init__(self, registry: ConceptRegistry) -> None:
        self._registry = registry

    def execute(self, context: PipelineContext) -> PipelineContext:
        extension = self._registry.get(ConceptId(context.concept_id))
        narrative = extension.create_narrative()
        if narrative.concept.id.value != context.concept_id:
            raise RuntimeError(
                f"Narrative for concept {narrative.concept.id.value!r} does "
                f"not match requested concept {context.concept_id!r}"
            )
        context.concept_extension = extension
        context.narrative = narrative
        context.correlation_id = f"{context.concept_id}_{uuid.uuid4().hex[:8]}"
        return context
