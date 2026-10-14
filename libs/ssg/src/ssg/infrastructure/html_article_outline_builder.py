import re
from html import escape, unescape

from ssg.application.ports.article_outline_builder import ArticleOutlineBuilder
from ssg.domain import Article, ArticleHeading


class HtmlArticleOutlineBuilder(ArticleOutlineBuilder):
    def build(self, title: str, body: str, permalink_label: str) -> Article:
        recorded: list[tuple[str, str, int]] = []
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
                attributes = (
                    f' id="{escape(heading_id, quote=True)}"{attributes}'
                )
            recorded.append((label, heading_id, level))
            permalink = (
                f'<a class="headerlink" '
                f'href="#{escape(heading_id, quote=True)}" '
                f'aria-label="{escape(permalink_label, quote=True)}">¶</a>'
            )
            return (
                f"<h{level}{attributes}>{heading_html}{permalink}</h{level}>"
            )

        outlined_body = _HEADING_PATTERN.sub(add_heading_id, body)
        headings = tuple(
            ArticleHeading(
                label=label,
                href=f"#{heading_id}",
                level=level,
                section_text=section_text,
            )
            for (label, heading_id, level), section_text in zip(
                recorded, _section_texts(body), strict=True
            )
        )
        return Article(
            title=title,
            body=outlined_body,
            headings=headings,
            plain_text=_plain_text(body),
        )


_HEADING_PATTERN = re.compile(
    r"<h(?P<level>[23])(?P<attributes>\s[^>]*)?>(?P<body>.*?)</h(?P=level)>",
    re.DOTALL,
)


def _section_texts(body: str) -> list[str]:
    # One plain-text section per labeled heading: the content between its
    # close tag and the next heading open tag. Unlabeled headings start no
    # section — their trailing text stays with the previous section.
    sections: list[list[str]] = []
    cursor = 0
    for match in _HEADING_PATTERN.finditer(body):
        if sections:
            sections[-1].append(body[cursor : match.start()])
        if _heading_label(match.group("body")):
            sections.append([])
        cursor = match.end()
    if sections:
        sections[-1].append(body[cursor:])

    return [_plain_text("".join(chunks)) for chunks in sections]


def _heading_label(heading_html: str) -> str:
    return _plain_text(heading_html)


_NON_CONTENT_BLOCK_PATTERN = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1\s*>",
    re.DOTALL | re.IGNORECASE,
)

_TAG_PATTERN = re.compile(r"<[^>]+>")


def _plain_text(html: str) -> str:
    without_blocks = _NON_CONTENT_BLOCK_PATTERN.sub(" ", html)
    text = _TAG_PATTERN.sub(" ", without_blocks)
    return " ".join(unescape(text).split())


_ATTRIBUTE_PATTERN = re.compile(
    r"(?P<name>[^\s=/>]+)"
    r"(?:\s*=\s*(?:\"(?P<double>[^\"]*)\"|'(?P<single>[^']*)'|(?P<bare>[^\s>]*)))?"
)


def _attribute_value(attributes: str, name: str) -> str | None:
    for match in _ATTRIBUTE_PATTERN.finditer(attributes):
        if match.group("name").lower() != name:
            continue
        value = (
            match.group("double")
            or match.group("single")
            or match.group("bare")
            or ""
        )
        return unescape(value)

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
