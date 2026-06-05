from videos.production._render_profiles import BUILTIN_PROFILES, FINAL, PREVIEW


class TestRenderProfiles:
    def test_preview_has_low_quality(self) -> None:
        assert PREVIEW.quality == "low"
        assert PREVIEW.frame_rate == 15

    def test_final_has_high_quality(self) -> None:
        assert FINAL.quality == "high"
        assert FINAL.frame_rate == 30
        assert FINAL.resolution == (1920, 1080)

    def test_builtin_profiles_accessible(self) -> None:
        assert "preview" in BUILTIN_PROFILES
        assert "final" in BUILTIN_PROFILES
        assert len(BUILTIN_PROFILES) == 2
