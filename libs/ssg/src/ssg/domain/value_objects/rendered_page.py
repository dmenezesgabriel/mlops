from dataclasses import dataclass
from typing import TYPE_CHECKING

from ssg.domain.value_objects.language_link import LanguageLink
from ssg.domain.value_objects.pager_link import PagerLink
from ssg.domain.value_objects.site_navigation import SiteNavigation

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
