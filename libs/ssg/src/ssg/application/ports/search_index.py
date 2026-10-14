from pathlib import Path
from typing import Protocol

from ssg.domain import SearchIndexEntry


class SearchIndex(Protocol):
    """Accumulates per-page search entries across builds and emits one
    `search-index.json` per site variant output path."""

    def update_page(
        self,
        output_path: Path,
        location: str,
        entries: tuple[SearchIndexEntry, ...],
    ) -> None: ...

    def write(self, output_path: Path) -> None: ...

    def clear(self) -> None: ...
