from videos.production._transitions import TransitionType


class TestTransitionType:
    def test_has_expected_members(self) -> None:
        values = {t.value for t in TransitionType}
        assert values == {"fade", "slide_left", "slide_right", "zoom", "crossfade", "none"}
