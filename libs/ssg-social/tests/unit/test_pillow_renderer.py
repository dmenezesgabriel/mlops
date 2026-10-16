"""Tests for the Pillow social-card renderer against the real dependency.

The card is raster output: asserting on the returned PNG (magic bytes,
canvas size, differing pixels per input) exercises the true contract —
faking Pillow would test nothing but itself.
"""

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from ssg.domain import SocialCard
from ssg_social.infrastructure.pillow_renderer import (
    PillowSocialCardRenderer,
)

_FONTS_DIR = (
    Path(__file__).parent.parent.parent / "src" / "ssg_social" / "fonts"
)


@pytest.fixture
def renderer() -> PillowSocialCardRenderer:
    return PillowSocialCardRenderer(_FONTS_DIR)


def _card(**overrides: str) -> SocialCard:
    values = {
        "site_title": "Learning Site",
        "eyebrow": "Sample Collection",
        "title": "Feature Engineering",
        "description": "Rendered content collections.",
        "locale": "en",
    }
    values.update(overrides)
    return SocialCard(**values)  # type: ignore[arg-type]


def test_render_social_card_returns_1200x630_png(
    renderer: PillowSocialCardRenderer,
) -> None:
    png = renderer.render_social_card(_card())

    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    image = Image.open(BytesIO(png))
    assert image.size == (1200, 630)
    assert image.format == "PNG"


def test_render_social_card_draws_title_pixels(
    renderer: PillowSocialCardRenderer,
) -> None:
    image = Image.open(BytesIO(renderer.render_social_card(_card())))

    # The title band sits mid-card on a paper background; ink text must
    # land inside it.
    assert image.getpixel((64, 64))[:3] == (243, 234, 216)
    title_band = image.crop((64, 120, 1136, 470))
    extrema = title_band.convert("L").getextrema()
    assert extrema[0] < 64, "expected dark title pixels in the title band"


def test_render_social_card_differs_per_page_title(
    renderer: PillowSocialCardRenderer,
) -> None:
    first = renderer.render_social_card(_card(title="Overview"))
    second = renderer.render_social_card(_card(title="Deploy"))

    assert first != second


def test_render_social_card_ellipsizes_very_long_titles(
    renderer: PillowSocialCardRenderer,
) -> None:
    png = renderer.render_social_card(
        _card(title="Hyperparameter Optimization " * 20)
    )

    image = Image.open(BytesIO(png))
    assert image.size == (1200, 630)


def test_render_social_card_handles_pt_br_diacritics(
    renderer: PillowSocialCardRenderer,
) -> None:
    png = renderer.render_social_card(
        _card(
            eyebrow="Coleção",
            title="Avaliação do Modelo",
            description="Coleções de conteúdo renderizadas.",
            locale="pt-BR",
        )
    )

    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_social_card_without_eyebrow_or_description(
    renderer: PillowSocialCardRenderer,
) -> None:
    png = renderer.render_social_card(_card(eyebrow="", description=""))

    assert Image.open(BytesIO(png)).size == (1200, 630)
