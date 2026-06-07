from __future__ import annotations

from typing import TYPE_CHECKING

from videos.application.components import ComponentRegistry
from videos.domain.scene_spec import SceneSpec

if TYPE_CHECKING:
    from videos.application.ports.layout_engine import LayoutEngine
    from videos.domain.storyboard import Storyboard


try:
    from manim import Scene
except ImportError:
    # Fallback dummy for environments where manim is not installed
    class Scene:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass


class ConfigurableScene(Scene):
    def __init__(
        self,
        scene_spec: SceneSpec,
        registry: ComponentRegistry,
    ) -> None:
        self._scene_spec = scene_spec
        self._registry = registry
        self._built_mobjects: list[object] = []
        super().__init__()

    def construct(self) -> None:
        from manim import Text, Write

        if not self._scene_spec.components:
            title = Text(self._scene_spec.title, font_size=40)
            self._built_mobjects.append(title)
            self.play(Write(title))
            self.wait(self._scene_spec.duration_seconds)
            return

        for spec in self._scene_spec.components:
            mobj = self._registry.build(spec, self)
            if mobj:
                self._built_mobjects.append(mobj)

        self.wait(self._scene_spec.duration_seconds)


class StoryboardScene(Scene):
    def __init__(
        self,
        storyboard: Storyboard,
        layout_engine: LayoutEngine,
        registry: ComponentRegistry,
    ) -> None:
        self._storyboard = storyboard
        self._layout_engine = layout_engine
        self._registry = registry
        super().__init__()

    def construct(self) -> None:
        from manim import FadeOut, Text, Write

        for scene_spec in self._storyboard.scenes:
            positioned = self._layout_engine.apply(scene_spec)

            # Store mobjects to clear them before next scene
            scene_mobjects = []

            if not positioned.components:
                title = Text(positioned.title, font_size=40)
                scene_mobjects.append(title)
                self.play(Write(title))
                self.wait(positioned.duration_seconds)
                if scene_mobjects:
                    self.play(*[FadeOut(m) for m in scene_mobjects])
                continue

            for spec in positioned.components:
                mobj = self._registry.build(spec, self)
                if mobj:
                    scene_mobjects.append(mobj)

            self.wait(positioned.duration_seconds)

            # Clear scene for the next beat
            if scene_mobjects:
                self.play(*[FadeOut(m) for m in scene_mobjects])


class ManimSceneBuilder:
    def __init__(self, registry: ComponentRegistry | None = None) -> None:
        self._registry = registry or ComponentRegistry()

    def build(self, scene_spec: SceneSpec) -> object:
        return ConfigurableScene(scene_spec, self._registry)

    def build_storyboard(
        self, storyboard: Storyboard, layout_engine: LayoutEngine
    ) -> object:
        return StoryboardScene(storyboard, layout_engine, self._registry)
