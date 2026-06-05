from videos.core.application._scene_compiler import SceneCompiler
from videos.core.domain._layout import LayoutRegion, LayoutSpec
from videos.core.domain._scene_spec import SceneSpec
from videos.core.domain._storyboard import Storyboard


def _specs() -> Storyboard:
    scenes = [
        SceneSpec(
            scene_id="s1",
            title="S1",
            goal="G1",
            duration_seconds=5.0,
            layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        ),
        SceneSpec(
            scene_id="s2",
            title="S2",
            goal="G2",
            duration_seconds=3.0,
            layout=LayoutSpec(regions=(LayoutRegion.BODY,)),
        ),
    ]
    return Storyboard(scenes=scenes)


class TestSceneCompiler:
    def test_compile_preserves_scenes(self) -> None:
        compiler = SceneCompiler()
        storyboard = _specs()
        scenes = compiler.compile(storyboard)
        assert len(scenes) == 2
        assert scenes[0].scene_id == "s1"
        assert scenes[1].scene_id == "s2"

    def test_compile_returns_all_scenes(self) -> None:
        compiler = SceneCompiler()
        storyboard = _specs()
        scenes = compiler.compile(storyboard)
        assert all(s is not None for s in scenes)
