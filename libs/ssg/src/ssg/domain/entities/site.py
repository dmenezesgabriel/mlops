from dataclasses import dataclass
from pathlib import Path

from ssg.domain.entities.content_collection import ContentCollection
from ssg.domain.entities.page import Page
from ssg.domain.value_objects.navigation_link import NavigationLink
from ssg.domain.value_objects.navigation_section import NavigationSection
from ssg.domain.value_objects.site_navigation import SiteNavigation


@dataclass(frozen=True)
class Site:
    title: str
    description: str
    collections: tuple[ContentCollection, ...]
    locale: str = "en"
    default_locale: str = "en"
    extensions: dict[str, dict[str, str]] | None = None
    url: str = ""
    repo_url: str = ""
    # Static social image: copied to each variant's assets/ and emitted as
    # absolute og:image/twitter:image (crawlers require absolute URLs, so
    # emission additionally gates on `url`).
    image: Path | None = None
    # edit_base_url joins the repo-relative source path into a "edit this
    # page" href (e.g. https://github.com/org/repo/edit/master); last_updated
    # opts pages into a git-derived "last updated" date.
    edit_base_url: str = ""
    last_updated: bool = False

    def html_language(self) -> str:
        return self.locale

    def absolute_url(self, path: str = "") -> str:
        """Absolute URL for a path inside this variant's locale root.

        Returns "" when no deployment `url` is configured. An empty `path`
        yields the locale root URL (index canonical).

        Example: ``site.absolute_url("guide/intro.html")`` ->
        ``https://example.com/docs/pt-BR/guide/intro.html`` on a pt-BR
        variant.
        """
        if not self.url:
            return ""
        prefix = (
            "" if self.locale == self.default_locale else f"{self.locale}/"
        )
        return f"{self.url.rstrip('/')}/{prefix}{path}"

    def extension_setting(
        self, extension_name: str, setting_name: str, default: str
    ) -> str:
        extension_settings = (self.extensions or {}).get(extension_name, {})
        return extension_settings.get(setting_name, default)

    def selected_collections(
        self, collection_name: str | None
    ) -> tuple[ContentCollection, ...]:
        if collection_name is None:
            return self.collections

        selected = tuple(
            collection
            for collection in self.collections
            if collection.name == collection_name
        )
        if selected:
            return selected

        expected_names = sorted(
            collection.name for collection in self.collections
        )
        raise ValueError(
            f"Unknown site collection {collection_name}: expected one of {expected_names}",
        )

    def navigation_for(
        self,
        current_collection: ContentCollection | None,
        current_page: Page | None,
        collections: tuple[ContentCollection, ...] | None = None,
    ) -> SiteNavigation:
        if collections is None:
            collections = self.collections
        if current_collection is not None:
            collections = (current_collection,)

        return SiteNavigation(
            home_href=self._root_relative_href(
                current_collection, "index.html"
            ),
            sections=tuple(
                self._navigation_section(
                    collection, current_collection, current_page
                )
                for collection in collections
            ),
        )

    def _navigation_section(
        self,
        collection: ContentCollection,
        current_collection: ContentCollection | None,
        current_page: Page | None,
    ) -> NavigationSection:
        collection_is_current = current_collection == collection
        links: tuple[NavigationLink, ...] = ()
        current_link_index: int | None = None
        if collection_is_current:
            links = collection.navigation_links
            if current_page is not None:
                current_link_index = collection.page_index(current_page.slug)

        return NavigationSection(
            title=collection.title,
            href=self._root_relative_href(
                current_collection, collection.root_href()
            ),
            current=collection_is_current,
            links=links,
            current_link_index=current_link_index,
        )

    def _root_relative_href(
        self,
        current_collection: ContentCollection | None,
        href: str,
    ) -> str:
        if current_collection is None:
            return href

        return f"../{href}"
