from dataclasses import dataclass

from ssg.domain.value_objects.navigation_section import NavigationSection


@dataclass(frozen=True)
class SiteNavigation:
    home_href: str
    sections: tuple[NavigationSection, ...]
