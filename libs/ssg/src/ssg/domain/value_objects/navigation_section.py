from dataclasses import dataclass

from ssg.domain.value_objects.navigation_link import NavigationLink


@dataclass(frozen=True)
class NavigationSection:
    title: str
    href: str
    links: tuple[NavigationLink, ...]
    current: bool = False
