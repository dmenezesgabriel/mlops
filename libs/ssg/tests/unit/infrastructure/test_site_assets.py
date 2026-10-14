import pytest
from ssg.infrastructure.frontend.site_assets import (
    SITE_CSS,
    _read_frontend_asset,
)


def test_body_grid_decoration_does_not_overlay_content() -> None:
    assert "body::before" not in SITE_CSS
    assert "z-index: 30" not in SITE_CSS


def test_code_blocks_preserve_source_whitespace() -> None:
    assert "white-space: pre;" in SITE_CSS


def test_print_stylesheet_hides_navigation_chrome() -> None:
    print_block = SITE_CSS.split("@media print", 1)[1]
    for selector in (".sidebar", ".article-toc", ".pager", ".header-actions"):
        assert f"{selector}," in print_block or f"{selector} " in print_block
    assert "display: none" in print_block


def test_print_stylesheet_forces_light_readable_palette() -> None:
    print_block = SITE_CSS.split("@media print", 1)[1]
    # light-dark() resolves per-element color-scheme, so both the system
    # default (:root) and an explicit data-theme pick must be pinned light —
    # otherwise cream-on-dark gruvbox tokens print on white paper.
    assert "color-scheme: light" in print_block
    assert "body[data-theme]" in print_block
    assert ".highlight-token" in print_block
    assert "pre-wrap" in print_block


def test_read_frontend_asset_rejects_missing_file() -> None:
    # Arrange — a packaged asset that isn't shipped must fail loudly at import
    # time rather than embed an empty/None payload into rendered pages.
    with pytest.raises(FileNotFoundError, match="Missing frontend asset"):
        _read_frontend_asset("css/bogus.css")
