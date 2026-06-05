import pytest

pytest.importorskip("manim")
pytestmark = pytest.mark.docker

from videos.adapters.manim.scene_builder import ManimSceneBuilder  # noqa: E402
from videos.core.domain.layout import LayoutRegion, LayoutSpec  # noqa: E402
from videos.core.domain.scene_spec import SceneSpec  # noqa: E402


class TestManimSceneBuilder:
    def test_build_returns_scene_object(self) -> None:
        builder = ManimSceneBuilder()
        spec = SceneSpec(
            scene_id="s1",
            title="Test",
            goal="Goal",
            duration_seconds=5.0,
            layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        )
        scene = builder.build(spec)
        assert scene is not None
