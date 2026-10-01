from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageLink:
    label: str
    href: str
    current: bool = False
