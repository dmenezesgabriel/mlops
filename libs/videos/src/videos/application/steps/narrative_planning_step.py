from __future__ import annotations

from videos.application.pipeline_context import PipelineContext
from videos.domain.entities.concept import ConceptId
from videos.domain.entities.concept_registry import ConceptRegistry


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
        return context
