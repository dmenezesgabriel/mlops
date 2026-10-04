from __future__ import annotations

import logging
from typing import Any, Protocol

from videos.domain.scene_spec import ComponentSpec

logger = logging.getLogger(__name__)


class ComponentBuilder(Protocol):
    def build(self, spec: ComponentSpec, scene: object) -> Any: ...


class ComponentRegistry:
    def __init__(self) -> None:
        self._builders: dict[str, ComponentBuilder] = {}

    def register(self, type_name: str, builder: ComponentBuilder) -> None:
        if type_name in self._builders:
            logger.warning(
                "Overwriting component builder",
                extra={"type_name": type_name},
            )
        self._builders[type_name] = builder

    def build(self, spec: ComponentSpec, scene: object) -> Any:
        builder = self._builders.get(spec.type)
        if builder is None:
            available = ", ".join(sorted(self._builders))
            raise LookupError(
                f"Unknown component type {spec.type!r}. Available: {available}"
            )
        return builder.build(spec, scene)
