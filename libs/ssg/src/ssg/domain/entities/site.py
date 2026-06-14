from dataclasses import dataclass

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

    def html_language(self) -> str:
        return self.locale

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
    ) -> SiteNavigation:
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
        if collection_is_current:
            links = tuple(
                self._navigation_link(
                    collection, page, current_collection, current_page
                )
                for page in collection.pages
            )

        return NavigationSection(
            title=collection.title,
            href=self._root_relative_href(
                current_collection, collection.root_href()
            ),
            current=collection_is_current,
            links=links,
        )

    def _navigation_link(
        self,
        collection: ContentCollection,
        page: Page,
        current_collection: ContentCollection | None,
        current_page: Page | None,
    ) -> NavigationLink:
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
