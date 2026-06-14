from typing import Protocol

from ssg.domain import Site


class HtmlPostProcessor(Protocol):
    def process(self, rendered_html: str, site: Site) -> str: ...
