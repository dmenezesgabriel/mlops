# Backward-compatible re-export — import from canonical location instead.
from videos.domain.value_objects.typography import (
    DEFAULT_TYPOGRAPHY,
    TypographyPreset,
)

__all__ = ["TypographyPreset", "DEFAULT_TYPOGRAPHY"]
