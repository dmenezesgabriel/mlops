from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from ssg.domain.value_objects.alternate_link import AlternateLink
from ssg.domain.value_objects.author import Author
from ssg.domain.value_objects.language_link import LanguageLink
from ssg.domain.value_objects.pager_link import PagerLink
from ssg.domain.value_objects.site_navigation import SiteNavigation
from ssg.domain.value_objects.version_link import VersionLink

if TYPE_CHECKING:
    from ssg.domain.entities.article import Article
    from ssg.domain.entities.content_collection import ContentCollection
    from ssg.domain.entities.page import Page
    from ssg.domain.entities.site import Site


@dataclass(frozen=True)
class RenderedPage:
    site: "Site"
    collection: "ContentCollection"
    page: "Page"
    article: "Article"
    navigation: SiteNavigation
    previous_link: PagerLink | None
    next_link: PagerLink | None
    language_links: tuple[LanguageLink, ...] = ()
    version_links: tuple[VersionLink, ...] = ()
    alternate_links: tuple[AlternateLink, ...] = ()
    edit_url: str | None = None
    last_updated: date | None = None
    # Root-relative path of this page's generated og:image card (present
    # when a SocialCardRenderer plugin is installed); falls back to
    # site.image in head.html when unset.
    social_image: str | None = None
    authors: tuple[Author, ...] = ()
    readtime_minutes: int | None = None
