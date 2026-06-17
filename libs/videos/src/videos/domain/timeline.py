# Backward-compatible re-export — import from canonical location instead.
from videos.domain.value_objects.timeline import TimelineEvent, TimelineSpec

__all__ = ["TimelineEvent", "TimelineSpec"]
