from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, ClassVar

from mlops_videos.concepts._registry import ConceptRegistry
from mlops_videos.core._domain._concept import ConceptId
from mlops_videos.core._domain._narrative import Beat

logger = logging.getLogger(__name__)

try:
    from manim import FadeOut as _FadeOut
    from manim import Scene as _ManimScene
except ImportError:

    class _ManimScene:  # type: ignore[no-redef]
        """Stub for environments where Manim is not installed (e.g. testing)."""

        def play(self, *args: object, **kwargs: object) -> None:
            pass

        def wait(self, duration: float = 1.0) -> None:
            pass

        def add(self, *args: object) -> None:
            pass

        def remove(self, *args: object) -> None:
            pass

    class _FadeOut:  # type: ignore[no-redef]
        """Stub for environments where Manim is not installed."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass


class ConceptScene(_ManimScene):
    """Base for Manim concept scenes.

    Subclasses set concept_id as a class variable and define
    ``_on_{beat_kind}_{visual_key}`` handler methods.  Each handler
    receives the current :class:`Beat` and is responsible for rendering
    the corresponding visual.

    Handler discovery happens at construction time via naming convention.
    """

    concept_id: ClassVar[str]
    _handlers: dict[str, Callable[[Beat], None]]
    _state: dict[str, Any]
    _beat_times: list[dict[str, Any]]

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._handlers = {}
        self._state = {}
        self._beat_times = []

    def construct(self) -> None:
        start = time.monotonic()
        logger.info("Constructing scene", extra={"concept": self.concept_id})

        extension = ConceptRegistry.get(ConceptId(self.concept_id))
        narrative = extension.create_narrative()

        self._register_handlers()

        for index, beat in enumerate(narrative.beats):
            beat_start = time.monotonic()
            logger.debug(
                "Render beat",
                extra={
                    "concept": self.concept_id,
                    "beat": index,
                    "kind": beat.kind.value,
                },
            )
            self._dispatch(beat)
            elapsed = time.monotonic() - beat_start
            self._beat_times.append({"index": index, "kind": beat.kind.value, "elapsed": elapsed})

        total = time.monotonic() - start
        logger.info(
            "Scene complete",
            extra={
                "concept": self.concept_id,
                "duration": total,
                "beats": len(narrative.beats),
            },
        )

    def _register_handlers(self) -> None:
        for attr_name in dir(self):
            if attr_name.startswith("_on_"):
                key = attr_name[len("_on_") :]
                self._handlers[key] = getattr(self, attr_name)

    def _dispatch(self, beat: Beat) -> None:
        handler_key = f"{beat.kind.value}_{beat.visual_key}"
        handler = self._handlers.get(handler_key)
        if handler is not None:
            handler(beat)
        else:
            self._default_beat(beat)

    def _default_beat(self, beat: Beat) -> None:
        self.wait(beat.narration.duration_seconds * 0.25)

    def _clear_state(self, *keys: str) -> None:
        """Fade out and remove specific tracked mobjects simultaneously.

        All animations in a single play() call with short run_time,
        avoiding sequential overlap between old and new content.

        Args:
            *keys: State keys to clear.
        """
        to_fade = [_FadeOut(self._state[k]) for k in keys if k in self._state]
        if to_fade:
            self.play(*to_fade, run_time=0.3)
        for k in keys:
            self._state.pop(k, None)

    def _transition_to(self, new_state: dict[str, Any]) -> None:
        """Fade out all tracked mobjects simultaneously and clear state.

        Call this at major boundaries *before* creating new content.
        The caller is responsible for animating and adding new mobjects.

        Args:
            new_state: New state dict to replace the old one.
        """
        if self._state:
            self.play(*[_FadeOut(m) for m in self._state.values()], run_time=0.3)
            self.remove(*self._state.values())
        self._state.clear()
        self._state.update(new_state)
