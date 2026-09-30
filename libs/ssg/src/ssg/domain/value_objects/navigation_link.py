from dataclasses import dataclass


@dataclass(frozen=True)
class NavigationLink:
    label: str
    href: str
