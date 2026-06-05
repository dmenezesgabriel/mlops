from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Page:
    slug: str
    title: str
    source_path: Path

    def file_name(self) -> str:
        return f"{self.slug}.html"


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

    def first_page(self) -> Page:
        if self.pages:
            return self.pages[0]

        raise ValueError(f"Empty collection {self.name}: expected at least one page")

    def root_href(self) -> str:
        return f"{self.output_slug}/{self.first_page().file_name()}"

    def page_by_slug(self, page_slug: str) -> Page:
        for page in self.pages:
            if page.slug == page_slug:
                return page

        expected_slugs = sorted(page.slug for page in self.pages)
        raise ValueError(f"Unknown collection page {page_slug}: expected one of {expected_slugs}")

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


@dataclass(frozen=True)
class Site:
    title: str
    description: str
    collections: tuple[ContentCollection, ...]
    extensions: dict[str, dict[str, str]] | None = None

    def extension_setting(self, extension_name: str, setting_name: str, default: str) -> str:
        extension_settings = (self.extensions or {}).get(extension_name, {})
        return extension_settings.get(setting_name, default)

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

    def navigation_for(
        self,
        current_collection: ContentCollection | None,
        current_page: Page | None,
    ) -> "SiteNavigation":
        collections = self.collections
        if current_collection is not None:
            collections = (current_collection,)

        return SiteNavigation(
            home_href=self._root_relative_href(current_collection, "index.html"),
            sections=tuple(
                self._navigation_section(collection, current_collection, current_page)
                for collection in collections
            ),
        )

    def _navigation_section(
        self,
        collection: ContentCollection,
        current_collection: ContentCollection | None,
        current_page: Page | None,
    ) -> "NavigationSection":
        collection_is_current = current_collection == collection
        links: tuple[NavigationLink, ...] = ()
        if collection_is_current:
            links = tuple(
                self._navigation_link(collection, page, current_collection, current_page)
                for page in collection.pages
            )

        return NavigationSection(
            title=collection.title,
            href=self._root_relative_href(current_collection, collection.root_href()),
            current=collection_is_current,
            links=links,
        )

    def _navigation_link(
        self,
        collection: ContentCollection,
        page: Page,
        current_collection: ContentCollection | None,
        current_page: Page | None,
    ) -> "NavigationLink":
        current = current_collection == collection and current_page == page
        return NavigationLink(
            label=page.title,
            href=self._root_relative_href(
                current_collection,
                f"{collection.output_slug}/{page.file_name()}",
            ),
            current=current,
        )

    def _root_relative_href(
        self,
        current_collection: ContentCollection | None,
        href: str,
    ) -> str:
        if current_collection is None:
            return href

        return f"../{href}"


@dataclass(frozen=True)
class NavigationLink:
    label: str
    href: str
    current: bool = False

    def aria_current(self) -> str:
        if self.current:
            return "page"

        return "false"


@dataclass(frozen=True)
class NavigationSection:
    title: str
    href: str
    links: tuple[NavigationLink, ...]
    current: bool = False


@dataclass(frozen=True)
class SiteNavigation:
    home_href: str
    sections: tuple[NavigationSection, ...]


@dataclass(frozen=True)
class ArticleHeading:
    label: str
    href: str
    level: int

    def depth_class(self) -> str:
        return f"article-toc__link--level-{self.level}"


@dataclass(frozen=True)
class Article:
    title: str
    body: str
    headings: tuple[ArticleHeading, ...] = ()

    def has_table_of_contents(self) -> bool:
        return bool(self.headings)


@dataclass(frozen=True)
class PagerLink:
    label: str
    href: str
    relation: str


@dataclass(frozen=True)
class RenderedPage:
    site: Site
    collection: ContentCollection
    page: Page
    article: Article
    navigation: SiteNavigation
    previous_link: PagerLink | None
    next_link: PagerLink | None


@dataclass(frozen=True)
class RenderedIndex:
    site: Site
    collections: tuple[ContentCollection, ...]
    navigation: SiteNavigation
