from typing import Protocol, runtime_checkable

from ssg.domain import Site


@runtime_checkable
class HtmlPostProcessor(Protocol):
    def process(self, rendered_html: str, site: Site) -> str: ...
