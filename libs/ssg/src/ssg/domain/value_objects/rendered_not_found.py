from dataclasses import dataclass
from typing import TYPE_CHECKING

from ssg.domain.value_objects.alternate_link import AlternateLink
from ssg.domain.value_objects.language_link import LanguageLink
from ssg.domain.value_objects.site_navigation import SiteNavigation
from ssg.domain.value_objects.version_link import VersionLink

if TYPE_CHECKING:
    from ssg.domain.entities.site import Site


@dataclass(frozen=True)
class RenderedNotFound:
    site: "Site"
    navigation: SiteNavigation
    language_links: tuple[LanguageLink, ...] = ()
    version_links: tuple[VersionLink, ...] = ()
    alternate_links: tuple[AlternateLink, ...] = ()
    # Always None: 404 is never carded, so head.html falls back to
    # site.image. The field exists so the template reads one uniform name.
    social_image: str | None = None
