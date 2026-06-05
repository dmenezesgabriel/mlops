from videos.production.typography import DEFAULT_TYPOGRAPHY, TypographyPreset


class TestTypographyPreset:
    def test_default_values(self) -> None:
        assert DEFAULT_TYPOGRAPHY.title_size == 40
        assert DEFAULT_TYPOGRAPHY.body_size == 24
        assert DEFAULT_TYPOGRAPHY.caption_size == 16

    def test_custom_preset(self) -> None:
        preset = TypographyPreset(title_size=48, body_size=18)
        assert preset.title_size == 48
        assert preset.body_size == 18
