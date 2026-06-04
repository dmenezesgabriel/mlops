from jinja2 import Template

from ssg.application.ports import PageRenderer
from ssg.domain.site import ContentCollection


class JinjaPageRenderer(PageRenderer):
    def __init__(self) -> None:
        self._template = Template(
            """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>{{ title }} - {{ collection.title }}</title>
  </head>
  <body>
    <main>
      <h1>{{ collection.title }}</h1>
      <article data-page-slug="{{ page_slug }}">{{ body | safe }}</article>
    </main>
  </body>
</html>
""".strip(),
        )

    def render_page(
        self,
        collection: ContentCollection,
        page_slug: str,
        title: str,
        body: str,
    ) -> str:
        return self._template.render(
            collection=collection,
            page_slug=page_slug,
            title=title,
            body=body,
        )
