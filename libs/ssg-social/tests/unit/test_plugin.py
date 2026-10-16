"""Unit tests for the social-card plugin entry-point factory."""

from ssg.application.ports import SocialCardRenderer
from ssg_social.infrastructure.pillow_renderer import PillowSocialCardRenderer
from ssg_social.infrastructure.plugin import create_social_card_renderer


def test_create_social_card_renderer() -> None:
    # Arrange & Act
    renderer = create_social_card_renderer()

    # Assert — public surface only: the entry-point contract is a
    # port-conforming renderer rooted at this package (where the vendored
    # fonts live).
    assert isinstance(renderer, SocialCardRenderer)
    assert isinstance(renderer, PillowSocialCardRenderer)
    assert renderer.fonts_dir.name == "fonts"
