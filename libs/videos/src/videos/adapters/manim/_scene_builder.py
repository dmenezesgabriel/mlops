from __future__ import annotations

from videos.core.domain._scene_spec import SceneSpec


class ManimSceneBuilder:
    def build(self, scene_spec: SceneSpec) -> object:
        from manim import Scene, Text, Write

        class _DynamicScene(Scene):
            def construct(self) -> None:
                title = Text(scene_spec.title, font_size=40)
                self.play(Write(title))
                self.wait(scene_spec.duration_seconds)

        return _DynamicScene()
