from typing import Protocol

from ssg.domain import Article


class ArticleOutlineBuilder(Protocol):
    def build(self, title: str, body: str) -> Article: ...
