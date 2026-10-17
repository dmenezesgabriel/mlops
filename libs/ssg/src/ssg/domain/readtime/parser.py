from html.parser import HTMLParser


class ReadtimeParser(HTMLParser):
    """Extracts visible text and image count from rendered HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_tags = frozenset(
            {"object", "script", "style", "svg", "head", "nav", "footer"}
        )
        self._context: list[str] = []
        self._text: list[str] = []
        self._images = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del attrs  # override signature; attributes are never inspected
        if tag == "img":
            self._images += 1

        if tag not in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            self._context.append(tag)

    def handle_data(self, data: str) -> None:
        if not self._skip_tags.intersection(self._context):
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._context and self._context[-1] == tag:
            self._context.pop()

    @property
    def text(self) -> str:
        return "".join(self._text)

    @property
    def images(self) -> int:
        return self._images
