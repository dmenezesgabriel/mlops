from dataclasses import dataclass, field
from pathlib import Path

from ssg.domain.entities.page import Page


@dataclass(frozen=True)
class ContentCollection:
    name: str
    title: str
    source_root: Path
    output_slug: str
    pages: tuple[Page, ...]
    videos: dict[str, Path]
    images: dict[str, Path] = field(default_factory=dict)

    def source_file(self, relative_path: str) -> Path:
        resolved_path = (self.source_root / relative_path).resolve()
        resolved_source_root = self.source_root.resolve()
        if (
            resolved_path == resolved_source_root
            or resolved_source_root in resolved_path.parents
        ):
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

    def image_path(self, image_name: str) -> Path:
        if image_name in self.images:
            return self.images[image_name]

        raise ValueError(
            f"Unknown collection image {image_name}: expected one of {sorted(self.images)}",
        )

    def page_href(self, page_slug: str) -> str:
        if any(page.slug == page_slug for page in self.pages):
            return f"{page_slug}.html"

        expected_slugs = sorted(page.slug for page in self.pages)
        raise ValueError(
            f"Unknown collection page {page_slug}: expected one of {expected_slugs}"
        )

    def first_page(self) -> Page:
        if self.pages:
            return self.pages[0]

        raise ValueError(
            f"Empty collection {self.name}: expected at least one page"
        )

    def root_href(self) -> str:
        return f"{self.output_slug}/{self.first_page().file_name()}"

    def page_by_slug(self, page_slug: str) -> Page:
        for page in self.pages:
            if page.slug == page_slug:
                return page

        expected_slugs = sorted(page.slug for page in self.pages)
        raise ValueError(
            f"Unknown collection page {page_slug}: expected one of {expected_slugs}"
        )

    def previous_page(self, current_page: Page) -> Page | None:
        page_index = self._page_index(current_page)
        if page_index == 0:
            return None

        return self.pages[page_index - 1]

    def next_page(self, current_page: Page) -> Page | None:
        page_index = self._page_index(current_page)
        next_index = page_index + 1
        if next_index >= len(self.pages):
            return None

        return self.pages[next_index]

    def _page_index(self, current_page: Page) -> int:
        for index, page in enumerate(self.pages):
            if page.slug == current_page.slug:
                return index

        expected_slugs = sorted(page.slug for page in self.pages)
        raise ValueError(
            f"Unknown collection page {current_page.slug}: expected one of {expected_slugs}",
        )
