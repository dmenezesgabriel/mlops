from dataclasses import dataclass


@dataclass(frozen=True)
class VersionLink:
    label: str
    href: str
    # The target version's id — its output dir segment; the same-page
    # switcher script needs it to rewrite the current URL.
    version_id: str = ""
    current: bool = False
    alias: str | None = None
