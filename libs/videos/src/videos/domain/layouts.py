# Backward-compatible re-export — import from canonical location instead.
from videos.domain.value_objects.layouts import (
    BUILT_IN_LAYOUTS,
    COMPARISON,
    DIAGRAM_WITH_LABELS,
    FULL_FRAME,
    TITLE_AND_BODY,
    TITLE_ONLY,
    LayoutPreset,
)

__all__ = [
    "LayoutPreset",
    "TITLE_ONLY",
    "TITLE_AND_BODY",
    "DIAGRAM_WITH_LABELS",
    "COMPARISON",
    "FULL_FRAME",
    "BUILT_IN_LAYOUTS",
]
