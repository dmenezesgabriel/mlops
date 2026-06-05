from __future__ import annotations

from videos.components.registry import ComponentRegistry
from videos.core.domain.scene_spec import SceneSpec


class ManimSceneBuilder:
    def __init__(self, registry: ComponentRegistry | None = None) -> None:
        self._registry = registry or ComponentRegistry()

    def build(self, scene_spec: SceneSpec) -> object:
        from manim import Scene, Text, Write

        registry = self._registry

        class _DynamicScene(Scene):
            def construct(self) -> None:
                if scene_spec.components:
                    for spec in scene_spec.components:
                        registry.build(spec, self)
                else:
                    title = Text(scene_spec.title, font_size=40)
                    self.play(Write(title))
                self.wait(scene_spec.duration_seconds)

        return _DynamicScene()
