from dataclasses import dataclass

from ssg.domain.value_objects.article_heading import ArticleHeading


@dataclass(frozen=True)
class Article:
    title: str
    body: str
    headings: tuple[ArticleHeading, ...] = ()

    def has_table_of_contents(self) -> bool:
        return bool(self.headings)
