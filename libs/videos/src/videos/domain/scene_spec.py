# Backward-compatible re-export — import from canonical location instead.
from videos.domain.value_objects.scene_spec import (
    ComponentSpec,
    SceneSpec,
    VisualObject,
)

__all__ = ["ComponentSpec", "VisualObject", "SceneSpec"]
