from __future__ import annotations

import logging
from pathlib import Path

from mlops_videos.core._domain._narrative import Narrative
from mlops_videos.core.ports._renderer import VideoRenderer
from mlops_videos.core.ports._scene_builder import NarrativeProvider, SceneBuilder

logger = logging.getLogger(__name__)

_MIN_DURATION = 30.0
_MAX_DURATION = 120.0


class SceneDirector:
    def __init__(self, builder: SceneBuilder, renderer: VideoRenderer) -> None:
        self._builder = builder
        self._renderer = renderer

    def produce(self, provider: NarrativeProvider, output_path: Path) -> Path:
        narrative = provider.create_narrative()
        self._validate_duration(narrative)

        logger.info(
            "Producing video",
            extra={
                "concept": narrative.concept.id.value,
                "beats": len(narrative.beats),
                "duration": narrative.total_duration,
            },
        )

        plan = self._builder.plan(narrative)
        return self._renderer.render(plan, output_path)

    @staticmethod
    def _validate_duration(narrative: Narrative) -> None:
        total = narrative.total_duration
        if total < _MIN_DURATION or total > _MAX_DURATION:
            raise ValueError(
                f"Narrative total duration {total}s is outside "
                f"allowed range [{_MIN_DURATION}s, {_MAX_DURATION}s] "
                f"for concept {narrative.concept.id.value!r}"
            )
