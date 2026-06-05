import re
from html import escape, unescape

from ssg.application.ports import ArticleOutlineBuilder
from ssg.domain.site import Article, ArticleHeading


def demote_top_level_headings(rendered_html: str) -> str:
    """Keep generated pages to one document h1 by demoting article body h1 tags.

    Example:
        demote_top_level_headings("<h1>Intro</h1>")
    """
    opening_tags_demoted = re.sub(r"<h1(\s[^>]*)?>", r"<h2\1>", rendered_html)
    return opening_tags_demoted.replace("</h1>", "</h2>")


class HtmlArticleOutlineBuilder(ArticleOutlineBuilder):
    def build(self, title: str, body: str) -> Article:
        headings: list[ArticleHeading] = []
        used_slugs: dict[str, int] = {}

        def add_heading_id(match: re.Match[str]) -> str:
            level = int(match.group("level"))
            attributes = match.group("attributes") or ""
            heading_html = match.group("body")
            label = _heading_label(heading_html)
            if not label:
                return match.group(0)

            heading_id = _attribute_value(attributes, "id")
            if heading_id is None:
                heading_id = _unique_slug(label, used_slugs)
                attributes = f' id="{escape(heading_id, quote=True)}"{attributes}'
            headings.append(ArticleHeading(label=label, href=f"#{heading_id}", level=level))
            return f"<h{level}{attributes}>{heading_html}</h{level}>"

        outlined_body = _HEADING_PATTERN.sub(add_heading_id, body)
        return Article(title=title, body=outlined_body, headings=tuple(headings))


_HEADING_PATTERN = re.compile(
    r"<h(?P<level>[23])(?P<attributes>\s[^>]*)?>(?P<body>.*?)</h(?P=level)>",
    re.DOTALL,
)


def _heading_label(heading_html: str) -> str:
    text = re.sub(r"<[^>]+>", "", heading_html)
    return " ".join(unescape(text).split())


def _attribute_value(attributes: str, name: str) -> str | None:
    match = re.search(rf'\s{name}="([^"]+)"', attributes)
    if match:
        return unescape(match.group(1))

    return None


def _unique_slug(label: str, used_slugs: dict[str, int]) -> str:
    slug = _slugify(label)
    count = used_slugs.get(slug, 0) + 1
    used_slugs[slug] = count
    if count == 1:
        return slug

    return f"{slug}-{count}"


def _slugify(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    if slug:
        return slug

    return "section"
