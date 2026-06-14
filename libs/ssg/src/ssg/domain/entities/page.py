from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Page:
    slug: str
    title: str
    source_path: Path

    def file_name(self) -> str:
        return f"{self.slug}.html"
