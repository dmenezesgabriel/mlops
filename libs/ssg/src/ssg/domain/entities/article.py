from dataclasses import dataclass

from ssg.domain.value_objects.article_heading import ArticleHeading
from ssg.domain.value_objects.search_index_entry import SearchIndexEntry


@dataclass(frozen=True)
class Article:
    title: str
    body: str
    headings: tuple[ArticleHeading, ...] = ()
    plain_text: str = ""

    def has_table_of_contents(self) -> bool:
        return bool(self.headings)

    def search_entries(self, location: str) -> tuple[SearchIndexEntry, ...]:
        """Page-then-sections entry list for the site's search index.

        Example:
            article.search_entries("guide/overview.html")
        """
        return (
            SearchIndexEntry(
                title=self.title, text=self.plain_text, location=location
            ),
            *(
                SearchIndexEntry(
                    title=heading.label,
                    text=heading.section_text,
                    location=f"{location}{heading.href}",
                )
                for heading in self.headings
            ),
        )
