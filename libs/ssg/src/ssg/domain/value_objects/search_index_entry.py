from dataclasses import dataclass


@dataclass(frozen=True)
class SearchIndexEntry:
    title: str
    text: str
    location: str
