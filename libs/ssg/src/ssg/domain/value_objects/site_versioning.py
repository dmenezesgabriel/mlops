from dataclasses import dataclass

from ssg.domain.value_objects.site_version import SiteVersion


@dataclass(frozen=True)
class SiteVersioning:
    """Versioned output layout: `current` is the version this build emits,
    `default` the id-or-alias the site root redirects to, `versions` the
    switcher registry.

    Example: ``SiteVersioning(current="0.2", default="latest", versions)``.
    """

    current: str
    default: str
    versions: tuple[SiteVersion, ...]

    def build_segments(self) -> tuple[str, ...]:
        """Output dirs the builder renders — the current version only;
        aliases arrive as byte-copies of that tree."""
        return (self.current,)

    def output_segments(self) -> tuple[str, ...]:
        """Every output dir this build owns: the current version plus its
        aliases; sibling versions are untouched."""
        entry = self.entry_for(self.current)
        aliases = entry.aliases if entry else ()
        return (self.current, *aliases)

    def default_version_id(self) -> str:
        """Resolve `default` (id or alias) to the version id the site root
        redirects to."""
        entry = self.entry_for(self.default)
        if entry is None:
            return self.current
        return entry.id

    def entry_for(self, path_segment: str) -> SiteVersion | None:
        """Look up a version by id or alias — the same resolution material
        applies to the deployed path segment."""
        for version in self.versions:
            if version.id == path_segment or path_segment in version.aliases:
                return version
        return None
