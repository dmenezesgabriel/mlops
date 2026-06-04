from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Page:
    slug: str
    title: str
    source_path: Path


@dataclass(frozen=True)
class ContentCollection:
    name: str
    title: str
    source_root: Path
    output_slug: str
    pages: tuple[Page, ...]
    videos: dict[str, Path]

    def source_file(self, relative_path: str) -> Path:
        resolved_path = (self.source_root / relative_path).resolve()
        resolved_source_root = self.source_root.resolve()
        if resolved_path == resolved_source_root or resolved_source_root in resolved_path.parents:
            return resolved_path

        raise ValueError(
            f"Unsafe collection source path {relative_path}: "
            f"expected path under {self.source_root}",
        )

    def video_path(self, video_name: str) -> Path:
        if video_name in self.videos:
            return self.videos[video_name]

        raise ValueError(
            f"Unknown collection video {video_name}: expected one of {sorted(self.videos)}",
        )

    def page_href(self, page_slug: str) -> str:
        if any(page.slug == page_slug for page in self.pages):
            return f"{page_slug}.html"

        expected_slugs = sorted(page.slug for page in self.pages)
        raise ValueError(f"Unknown collection page {page_slug}: expected one of {expected_slugs}")


@dataclass(frozen=True)
class Site:
    title: str
    description: str
    collections: tuple[ContentCollection, ...]

    def selected_collections(self, collection_name: str | None) -> tuple[ContentCollection, ...]:
        if collection_name is None:
            return self.collections

        selected = tuple(
            collection for collection in self.collections if collection.name == collection_name
        )
        if selected:
            return selected

        expected_names = sorted(collection.name for collection in self.collections)
        raise ValueError(
            f"Unknown site collection {collection_name}: expected one of {expected_names}",
        )
