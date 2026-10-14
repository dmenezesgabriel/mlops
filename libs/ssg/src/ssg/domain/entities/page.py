from dataclasses import dataclass
from pathlib import Path


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

    def file_name(self) -> str:
        return f"{self.slug}.html"
