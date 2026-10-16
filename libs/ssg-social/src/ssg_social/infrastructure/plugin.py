"""Entry-point factory for the social-card renderer plugin."""

from pathlib import Path

from ssg.application.ports import SocialCardRenderer

from ssg_social.infrastructure.pillow_renderer import PillowSocialCardRenderer


def create_social_card_renderer() -> SocialCardRenderer:
    """Instantiate the PillowSocialCardRenderer for the entry-point group."""
    fonts_dir = Path(__file__).parent.parent.resolve() / "fonts"
    return PillowSocialCardRenderer(fonts_dir)
