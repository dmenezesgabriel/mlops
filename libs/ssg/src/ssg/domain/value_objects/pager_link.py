from dataclasses import dataclass


@dataclass(frozen=True)
class PagerLink:
    label: str
    href: str
    relation: str
