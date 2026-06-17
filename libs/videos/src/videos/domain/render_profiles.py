# Backward-compatible re-export — import from canonical location instead.
from videos.domain.value_objects.render_profiles import (
    BUILT_IN_PROFILES,
    FINAL,
    PREVIEW,
    RenderProfile,
)

__all__ = ["RenderProfile", "PREVIEW", "FINAL", "BUILT_IN_PROFILES"]
