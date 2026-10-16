from typing import Protocol, runtime_checkable

from ssg.domain import SocialCard


@runtime_checkable
class SocialCardRenderer(Protocol):
    """Rasterizes one social-share card to PNG bytes.

    The contract fixes the og:image card spec: 1200x630 PNG. Crawlers read
    the dimensions from meta tags emitted beside the URL, so a renderer must
    honor exactly that canvas.
    """

    def render_social_card(self, card: SocialCard) -> bytes: ...
