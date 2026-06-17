"""Domain value objects — immutable data structures identified by value."""

from videos.domain.value_objects.brand import DEFAULT_BRAND, BrandColors
from videos.domain.value_objects.identifiers import (
    ComponentType,
    QualityLevel,
    SceneId,
)
from videos.domain.value_objects.layout import LayoutRegion, LayoutSpec
from videos.domain.value_objects.layouts import (
    BUILT_IN_LAYOUTS,
    COMPARISON,
    DIAGRAM_WITH_LABELS,
    FULL_FRAME,
    TITLE_AND_BODY,
    TITLE_ONLY,
    LayoutPreset,
)
from videos.domain.value_objects.narrative import Beat, BeatKind, NarrationLine
from videos.domain.value_objects.quality import QualityReport, RuleViolation
from videos.domain.value_objects.render_profiles import (
    BUILT_IN_PROFILES,
    FINAL,
    PREVIEW,
    RenderProfile,
)
from videos.domain.value_objects.scene_spec import (
    ComponentSpec,
    SceneSpec,
    VisualObject,
)
from videos.domain.value_objects.style import StyleSpec
from videos.domain.value_objects.timeline import TimelineEvent, TimelineSpec
from videos.domain.value_objects.transitions import TransitionType
from videos.domain.value_objects.typography import (
    DEFAULT_TYPOGRAPHY,
    TypographyPreset,
)

__all__ = [
    "BrandColors",
    "DEFAULT_BRAND",
    "ComponentType",
    "QualityLevel",
    "SceneId",
    "LayoutRegion",
    "LayoutSpec",
    "LayoutPreset",
    "BUILT_IN_LAYOUTS",
    "TITLE_ONLY",
    "TITLE_AND_BODY",
    "DIAGRAM_WITH_LABELS",
    "COMPARISON",
    "FULL_FRAME",
    "Beat",
    "BeatKind",
    "NarrationLine",
    "QualityReport",
    "RuleViolation",
    "RenderProfile",
    "BUILT_IN_PROFILES",
    "PREVIEW",
    "FINAL",
    "ComponentSpec",
    "SceneSpec",
    "VisualObject",
    "StyleSpec",
    "TimelineEvent",
    "TimelineSpec",
    "TransitionType",
    "TypographyPreset",
    "DEFAULT_TYPOGRAPHY",
]
