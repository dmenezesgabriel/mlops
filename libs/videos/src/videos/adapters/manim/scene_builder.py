from __future__ import annotations

from typing import TYPE_CHECKING

from videos.components.registry import ComponentRegistry
from videos.core.domain.scene_spec import SceneSpec

if TYPE_CHECKING:
    from videos.core.domain.storyboard import Storyboard
    from videos.core.ports.layout_engine import LayoutEngine


class ManimSceneBuilder:
    def __init__(self, registry: ComponentRegistry | None = None) -> None:
        self._registry = registry or ComponentRegistry()

    def build(self, scene_spec: SceneSpec) -> object:
        from manim import Scene, Text, Write

        registry = self._registry

        class _DynamicScene(Scene):
            def construct(self) -> None:
                # Store mobjects for validation hooks if needed
                self._built_mobjects = []

                if scene_spec.components:
                    for spec in scene_spec.components:
                        mobj = registry.build(spec, self)
                        if mobj:
                            self._built_mobjects.append(mobj)
                else:
                    title = Text(scene_spec.title, font_size=40)
                    self._built_mobjects.append(title)
                    self.play(Write(title))

                self.wait(scene_spec.duration_seconds)

        return _DynamicScene()

    def build_storyboard(
        self, storyboard: Storyboard, layout_engine: LayoutEngine
    ) -> object:
        from manim import FadeOut, Scene, Text, Write

        registry = self._registry

        class _FullVideoScene(Scene):
            def construct(self) -> None:
                for scene_spec in storyboard.scenes:
                    positioned = layout_engine.apply(scene_spec)

                    # Store mobjects to clear them before next scene
                    scene_mobjects = []

                    if positioned.components:
                        for spec in positioned.components:
                            mobj = registry.build(spec, self)
                            if mobj:
                                scene_mobjects.append(mobj)
                    else:
                        title = Text(positioned.title, font_size=40)
                        scene_mobjects.append(title)
                        self.play(Write(title))

                    self.wait(positioned.duration_seconds)

                    # Clear scene for the next beat
                    if scene_mobjects:
                        self.play(*[FadeOut(m) for m in scene_mobjects])

        return _FullVideoScene()
