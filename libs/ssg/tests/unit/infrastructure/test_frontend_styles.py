from ssg.infrastructure.frontend.site_assets import SITE_CSS


def test_body_grid_decoration_does_not_overlay_content() -> None:
    assert "body::before" not in SITE_CSS
    assert "z-index: 30" not in SITE_CSS


def test_code_blocks_preserve_source_whitespace() -> None:
    assert "white-space: pre;" in SITE_CSS
