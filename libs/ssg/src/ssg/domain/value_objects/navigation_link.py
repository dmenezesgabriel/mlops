from dataclasses import dataclass


@dataclass(frozen=True)
class NavigationLink:
    label: str
    href: str
    current: bool = False

    def aria_current(self) -> str:
        if self.current:
            return "page"

        return "false"
