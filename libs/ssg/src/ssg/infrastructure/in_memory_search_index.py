import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from ssg.application.ports.search_index import SearchIndex
from ssg.domain import SearchIndexEntry


class InMemorySearchIndex(SearchIndex):
    def __init__(self) -> None:
        self._pages: dict[Path, dict[str, tuple[SearchIndexEntry, ...]]] = (
            defaultdict(dict)
        )

    def update_page(
        self,
        output_path: Path,
        location: str,
        entries: tuple[SearchIndexEntry, ...],
    ) -> None:
        # One entry set per page: an incremental rebuild replaces the set
        # wholesale so renamed or dropped headings leave no stale rows.
        self._pages[output_path][location] = entries

    def write(self, output_path: Path) -> None:
        entries = [
            entry
            for page_entries in self._pages.get(output_path, {}).values()
            for entry in page_entries
        ]
        index_path = output_path / "search-index.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps(
                {"docs": [asdict(entry) for entry in entries]},
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

    def clear(self) -> None:
        self._pages.clear()
