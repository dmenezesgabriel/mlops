from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

from ssg.domain.entities.page import Page
from ssg.domain.value_objects.navigation_link import NavigationLink


@dataclass(frozen=True)
class ContentCollection:
    name: str
    title: str
    source_root: Path
    output_slug: str
    pages: tuple[Page, ...]
    videos: dict[str, Path]
    images: dict[str, Path] = field(default_factory=dict)
    kind: str = "default"
    _slug_to_index: dict[str, int] = field(
        init=False, repr=False, compare=False
    )
    navigation_links: tuple[NavigationLink, ...] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_slug_to_index",
            {page.slug: index for index, page in enumerate(self.pages)},
        )
        # Links are only rendered from inside the collection's output dir, so
        # they carry the "../" prefix Site._root_relative_href applies in page
        # context — built once here instead of once per page.
        object.__setattr__(
            self,
            "navigation_links",
            tuple(
                NavigationLink(
                    label=page.title,
                    href=f"../{self.output_slug}/{page.file_name()}",
                )
                for page in self.pages
            ),
        )

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
        return self.pages[self.page_index(page_slug)].file_name()

    def page_index(self, page_slug: str) -> int:
        if page_slug in self._slug_to_index:
            return self._slug_to_index[page_slug]

        expected_slugs = sorted(self._slug_to_index)
        raise ValueError(
            f"Unknown collection page {page_slug}: expected one of {expected_slugs}"
        )

    def first_page(self) -> Page:
        if self.pages:
            return self.pages[0]

        raise ValueError(
            f"Empty collection {self.name}: expected at least one page"
        )

    @property
    def is_dated_posts(self) -> bool:
        return self.kind in ("posts", "dated-posts")

    def published(self, now: datetime) -> "ContentCollection":
        """The emit-ready collection: drafts and future dates stay out.

        Only dated-posts collections gate on `draft`/`date`; a plain
        collection is returned unchanged so its pages keep building.
        """
        if not self.is_dated_posts:
            return self

        published_pages = tuple(
            page for page in self.pages if page.is_published(now)
        )
        if len(published_pages) == len(self.pages):
            return self

        return replace(self, pages=published_pages)

    def root_href(self) -> str:
        # A posts collection whose every entry is still a draft has no page
        # to point at; its index is the collection's public entry point.
        if not self.pages:
            return f"{self.output_slug}/index.html"
        return f"{self.output_slug}/{self.first_page().file_name()}"

    def previous_page(self, current_page: Page) -> Page | None:
        page_index = self.page_index(current_page.slug)
        if page_index == 0:
            return None

        return self.pages[page_index - 1]

    def next_page(self, current_page: Page) -> Page | None:
        page_index = self.page_index(current_page.slug)
        next_index = page_index + 1
        if next_index >= len(self.pages):
            return None

        return self.pages[next_index]
