# Backward-compatible re-export — import from canonical location instead.
from videos.domain.entities.narrative import Narrative
from videos.domain.value_objects.narrative import Beat, BeatKind, NarrationLine

__all__ = ["BeatKind", "NarrationLine", "Beat", "Narrative"]
