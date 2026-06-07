import pytest
from videos.domain.layout import LayoutRegion, LayoutSpec


class TestLayoutRegion:
    def test_has_expected_members(self) -> None:
        names = sorted(LayoutRegion.all_region_names())
        assert names == [
            "body",
            "callout",
            "diagram",
            "equation",
            "footer",
            "left_panel",
            "right_panel",
            "title",
        ]


class TestLayoutSpec:
    def test_rejects_duplicate_regions(self) -> None:
        with pytest.raises(ValueError, match="Duplicate region"):
            LayoutSpec(regions=(LayoutRegion.TITLE, LayoutRegion.TITLE))

    def test_accepts_unique_regions(self) -> None:
        spec = LayoutSpec(regions=(LayoutRegion.TITLE, LayoutRegion.BODY))
        assert spec.region_names == {"title", "body"}

    def test_empty_layout(self) -> None:
        spec = LayoutSpec()
        assert spec.region_names == frozenset()

    def test_region_names_returns_frozenset(self) -> None:
        spec = LayoutSpec(regions=(LayoutRegion.DIAGRAM,))
        assert isinstance(spec.region_names, frozenset)
