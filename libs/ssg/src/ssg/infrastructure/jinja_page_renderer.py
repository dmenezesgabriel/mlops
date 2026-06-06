from ssg.application.ports import PageRenderer
from ssg.domain.site import RenderedIndex, RenderedPage
from ssg.infrastructure.frontend.jinja_environment import (
    create_frontend_environment,
)
from ssg.infrastructure.frontend.site_assets import SITE_CSS, SITE_JS


class JinjaPageRenderer(PageRenderer):
    def __init__(self) -> None:
        self._environment = create_frontend_environment()
        self._page_template = self._environment.get_template("page.html")
        self._index_template = self._environment.get_template("index.html")

    def render_page(self, rendered_page: RenderedPage) -> str:
        return self._page_template.render(rendered_page=rendered_page)

    def render_index(self, rendered_index: RenderedIndex) -> str:
        return self._index_template.render(rendered_index=rendered_index)

    def assets(self) -> dict[str, str]:
        return {"site.css": SITE_CSS, "site.js": SITE_JS}
