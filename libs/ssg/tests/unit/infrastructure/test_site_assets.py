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


def test_read_frontend_asset_rejects_missing_file() -> None:
    # Arrange — a packaged asset that isn't shipped must fail loudly at import
    # time rather than embed an empty/None payload into rendered pages.
    with pytest.raises(FileNotFoundError, match="Missing frontend asset"):
        _read_frontend_asset("css/bogus.css")
