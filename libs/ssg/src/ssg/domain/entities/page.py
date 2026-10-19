from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ssg.domain.value_objects.author import Author


@dataclass(frozen=True)
class Page:
    slug: str
    title: str
    source_path: Path
    # Authored file this page renders from; differs from source_path when a
    # variant provider substitutes a generated intermediate (e.g. i18n writes
    # gitignored translations under site/.ssg/). Provenance for revision
    # lookups and edit links, which must never target generated output.
    original_source_path: Path | None = None
    date: datetime | None = None
    authors: tuple[Author, ...] = ()
    draft: bool = False
    pin: bool = False
    readtime_minutes: int | None = None

    def __post_init__(self) -> None:
        if self.date is not None and self.date.tzinfo is None:
            object.__setattr__(self, "date", self.date.replace(tzinfo=UTC))

    def file_name(self) -> str:
        return f"{self.slug}.html"

    def is_published(self, now: datetime) -> bool:
        """A page is published unless it is a draft or dated in the future."""
        if self.draft:
            return False
        return self.date is None or self.date <= now
