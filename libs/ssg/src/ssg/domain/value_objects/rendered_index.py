from dataclasses import dataclass
from typing import TYPE_CHECKING

from ssg.domain.value_objects.language_link import LanguageLink
from ssg.domain.value_objects.site_navigation import SiteNavigation

if TYPE_CHECKING:
    from ssg.domain.entities.content_collection import ContentCollection
    from ssg.domain.entities.site import Site


@dataclass(frozen=True)
class RenderedIndex:
    site: "Site"
    collections: "tuple[ContentCollection, ...]"
    navigation: SiteNavigation
    language_links: tuple[LanguageLink, ...] = ()
