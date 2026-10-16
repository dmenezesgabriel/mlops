from dataclasses import dataclass, field


@dataclass(frozen=True)
class SiteVersion:
    """One declared site version: id is the path segment, title the
    switcher label, aliases extra browsable directories, hidden keeps the
    version out of the switcher."""

    id: str
    title: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    hidden: bool = False
