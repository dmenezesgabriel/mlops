from __future__ import annotations

from enum import StrEnum


class TransitionType(StrEnum):
    FADE = "fade"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    ZOOM = "zoom"
    CROSSFADE = "crossfade"
    NONE = "none"
