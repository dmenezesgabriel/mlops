from ssg.infrastructure.frontend.style_content import (
    ARTICLE_STYLES,
    COLLECTION_STYLES,
    MEDIA_STYLES,
    MOTION_STYLES,
    RESPONSIVE_STYLES,
)
from ssg.infrastructure.frontend.style_foundation import (
    BASE_STYLES,
    DESIGN_TOKENS,
    FONT_IMPORTS,
    LAYOUT_STYLES,
    NAVIGATION_STYLES,
    RESET_STYLES,
    UTILITY_STYLES,
)

SITE_CSS = "\n\n".join(
    (
        FONT_IMPORTS,
        DESIGN_TOKENS,
        RESET_STYLES,
        BASE_STYLES,
        UTILITY_STYLES,
        LAYOUT_STYLES,
        NAVIGATION_STYLES,
        ARTICLE_STYLES,
        MEDIA_STYLES,
        COLLECTION_STYLES,
        RESPONSIVE_STYLES,
        MOTION_STYLES,
    )
)
