from ssg.application.ports import PageRenderer
from ssg.domain import (
    ContentCollection,
    PrecacheManifest,
    RenderedIndex,
    RenderedNotFound,
    RenderedPage,
    Site,
)
from ssg.infrastructure.frontend.jinja_environment import (
    create_frontend_environment,
)
from ssg.infrastructure.frontend.site_assets import (
    SITE_CSS,
    SITE_FAVICON,
    SITE_INSTANT_JS,
    SITE_JS,
)


class JinjaPageRenderer(PageRenderer):
    def __init__(self) -> None:
        self._environment = create_frontend_environment()
        self._page_template = self._environment.get_template("page.html")
        self._index_template = self._environment.get_template("index.html")
        self._sitemap_template = self._environment.get_template("sitemap.xml")
        self._robots_txt_template = self._environment.get_template(
            "robots.txt"
        )
        self._not_found_template = self._environment.get_template("404.html")
        self._service_worker_template = self._environment.get_template("sw.js")

    def render_page(self, rendered_page: RenderedPage) -> str:
        return self._page_template.render(rendered_page=rendered_page)

    def render_index(self, rendered_index: RenderedIndex) -> str:
        return self._index_template.render(rendered_index=rendered_index)

    def render_sitemap(
        self, site: Site, collections: tuple[ContentCollection, ...]
    ) -> str:
        return self._sitemap_template.render(
            site=site, collections=collections
        )

    def render_robots_txt(self, site: Site) -> str:
        return self._robots_txt_template.render(site=site)

    def render_not_found(self, rendered_not_found: RenderedNotFound) -> str:
        return self._not_found_template.render(
            rendered_not_found=rendered_not_found
        )

    def render_service_worker(self, manifest: PrecacheManifest) -> str:
        return self._service_worker_template.render(manifest=manifest)

    def assets(self) -> dict[str, str]:
        return {
            "site.css": SITE_CSS,
            "site.js": SITE_JS,
            "instant.js": SITE_INSTANT_JS,
            "favicon.svg": SITE_FAVICON,
        }
