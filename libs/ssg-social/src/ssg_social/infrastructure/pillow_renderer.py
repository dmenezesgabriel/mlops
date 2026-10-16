"""Pillow rasterizer for generated per-page social cards.

Layout adapts mkdocs-material's default card (background, top chrome,
wrapped bold title, footer description — research_repos/mkdocs-material/
src/plugins/social/templates/default.yml) to this site's light theme.
"""

from collections.abc import Callable
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from ssg.domain import SocialCard

from ssg_social.application.card_text_layout import fit_font_size, wrap_lines

# Palette mirrors the site's light scheme (libs/ssg `site.css` :root):
# paper surface, ink type, muted secondary, taxi accent.
_PAPER = "#f3ead8"
_INK = "#15110d"
_MUTED = "#756852"
_TAXI = "#f2bd22"

_CARD_WIDTH = 1200
_CARD_HEIGHT = 630
_MARGIN = 64
_TEXT_WIDTH = _CARD_WIDTH - 2 * _MARGIN
_ACCENT_HEIGHT = 16

# Vendored variable fonts (OFL-1.1, fonts/OFL.txt), pinned upstream at
# google/fonts@0b58fb37 (IBM Plex Sans) and google/fonts@8b0a1d0f
# (Newsreader); set_variation_by_name picks the weight instance.
_PLEX_SANS = "IBMPlexSans-Variable.ttf"
_NEWSREADER = "Newsreader-Variable.ttf"


class PillowSocialCardRenderer:
    """``SocialCardRenderer`` adapter drawing cards with vendored fonts."""

    def __init__(self, fonts_dir: Path) -> None:
        self.fonts_dir = fonts_dir

    def render_social_card(self, card: SocialCard) -> bytes:
        image = Image.new("RGB", (_CARD_WIDTH, _CARD_HEIGHT), _PAPER)
        context = ImageDraw.Draw(image)
        context.rectangle(
            (0, _CARD_HEIGHT - _ACCENT_HEIGHT, _CARD_WIDTH, _CARD_HEIGHT),
            fill=_TAXI,
        )
        if card.eyebrow:
            self._draw_eyebrow(context, card.eyebrow)
        self._draw_title(context, card.title)
        self._draw_footer(context, card)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _draw_eyebrow(
        self, context: ImageDraw.ImageDraw, eyebrow: str
    ) -> None:
        font = self._font(_PLEX_SANS, "Medium", 32)
        lines = wrap_lines(
            eyebrow, self._measurer(context, font), _TEXT_WIDTH, max_lines=1
        )
        context.text((_MARGIN, 56), lines[0], font=font, fill=_MUTED)

    def _draw_title(self, context: ImageDraw.ImageDraw, title: str) -> None:
        size, spacing = fit_font_size(
            lambda px: self._font(_NEWSREADER, "ExtraBold", px).getmetrics(),
            box_height=330,
            max_lines=3,
            line_height=1.15,
        )
        font = self._font(_NEWSREADER, "ExtraBold", size)
        lines = wrap_lines(
            title, self._measurer(context, font), _TEXT_WIDTH, max_lines=3
        )
        context.multiline_text(
            (_MARGIN, 120),
            "\n".join(lines),
            font=font,
            fill=_INK,
            spacing=spacing,
        )

    def _draw_footer(
        self, context: ImageDraw.ImageDraw, card: SocialCard
    ) -> None:
        site_font = self._font(_PLEX_SANS, "SemiBold", 34)
        context.text(
            (_MARGIN, 486), card.site_title, font=site_font, fill=_INK
        )
        if not card.description:
            return
        description_font = self._font(_PLEX_SANS, "Regular", 30)
        lines = wrap_lines(
            card.description,
            self._measurer(context, description_font),
            _TEXT_WIDTH,
            max_lines=2,
        )
        context.multiline_text(
            (_MARGIN, 534),
            "\n".join(lines),
            font=description_font,
            fill=_MUTED,
            spacing=8,
        )

    def _font(
        self, family: str, variant: str, size: int
    ) -> ImageFont.FreeTypeFont:
        font = ImageFont.truetype(str(self.fonts_dir / family), size)
        font.set_variation_by_name(variant)
        return font

    @staticmethod
    def _measurer(
        context: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont
    ) -> Callable[[str], float]:
        return lambda text: context.textlength(text, font=font)
