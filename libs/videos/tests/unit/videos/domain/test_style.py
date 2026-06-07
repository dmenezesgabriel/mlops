from videos.domain.style import StyleSpec


class TestStyleSpec:
    def test_uses_defaults(self) -> None:
        s = StyleSpec()
        assert s.typography_preset == "default"
        assert s.color_palette == "default"
        assert s.spacing_scale == "default"
        assert s.render_profile == "default"

    def test_stores_custom_values(self) -> None:
        s = StyleSpec(
            typography_preset="educational",
            color_palette="dark",
            spacing_scale="compact",
            render_profile="preview",
        )
        assert s.typography_preset == "educational"
        assert s.color_palette == "dark"
        assert s.render_profile == "preview"
