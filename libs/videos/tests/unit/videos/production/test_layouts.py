from videos.production.layouts import (
    BUILT_IN_LAYOUTS,
    COMPARISON,
    DIAGRAM_WITH_LABELS,
    FULL_FRAME,
    TITLE_AND_BODY,
    TITLE_ONLY,
)


class TestLayoutPresets:
    def test_title_only_has_title_region(self) -> None:
        assert "title" in TITLE_ONLY.layout.region_names
        assert "body" not in TITLE_ONLY.layout.region_names

    def test_title_and_body_has_both(self) -> None:
        assert "title" in TITLE_AND_BODY.layout.region_names
        assert "body" in TITLE_AND_BODY.layout.region_names

    def test_diagram_with_labels_has_diagram(self) -> None:
        assert "diagram" in DIAGRAM_WITH_LABELS.layout.region_names

    def test_comparison_has_left_and_right_panels(self) -> None:
        assert "left_panel" in COMPARISON.layout.region_names
        assert "right_panel" in COMPARISON.layout.region_names

    def test_full_frame_has_all_regions(self) -> None:
        assert "equation" in FULL_FRAME.layout.region_names

    def test_builtin_layouts_are_accessible(self) -> None:
        assert "title_only" in BUILT_IN_LAYOUTS
        assert "full_frame" in BUILT_IN_LAYOUTS
        assert len(BUILT_IN_LAYOUTS) == 5
