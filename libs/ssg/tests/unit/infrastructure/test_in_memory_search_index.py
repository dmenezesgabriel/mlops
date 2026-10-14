import json
from pathlib import Path

from ssg.domain import SearchIndexEntry
from ssg.infrastructure.in_memory_search_index import InMemorySearchIndex


def make_entry(
    location: str, title: str = "Title", text: str = "Text"
) -> SearchIndexEntry:
    return SearchIndexEntry(title=title, text=text, location=location)


def read_search_index(output_path: Path) -> dict:
    index_path = output_path / "search-index.json"
    return json.loads(index_path.read_text(encoding="utf-8"))


def test_write_emits_docs_envelope_with_entry_schema(tmp_path: Path) -> None:
    # Arrange
    index = InMemorySearchIndex()
    index.update_page(
        tmp_path,
        "sample/overview.html",
        (
            make_entry("sample/overview.html", "Overview", "Page text"),
            make_entry("sample/overview.html#setup", "Setup", "Section text"),
        ),
    )

    # Act
    index.write(tmp_path)

    # Assert — FR-11 schema: {title,text,location} per page and per section.
    assert read_search_index(tmp_path) == {
        "docs": [
            {
                "title": "Overview",
                "text": "Page text",
                "location": "sample/overview.html",
            },
            {
                "title": "Setup",
                "text": "Section text",
                "location": "sample/overview.html#setup",
            },
        ]
    }


def test_update_page_replaces_previous_entries(tmp_path: Path) -> None:
    # Arrange — a re-rendered page's new headings must not leave its old
    # entries behind in the index.
    index = InMemorySearchIndex()
    index.update_page(tmp_path, "a/p.html", (make_entry("a/p.html", "Old"),))
    index.update_page(tmp_path, "a/p.html", (make_entry("a/p.html", "New"),))

    # Act
    index.write(tmp_path)

    # Assert
    assert [
        entry["title"] for entry in read_search_index(tmp_path)["docs"]
    ] == ["New"]


def test_write_isolates_entries_per_output_path(tmp_path: Path) -> None:
    # Arrange — one index file per site variant: the default locale writes
    # at the output root, other locales under their own directory.
    index = InMemorySearchIndex()
    english_path = tmp_path / "build"
    portuguese_path = tmp_path / "build" / "pt-BR"
    index.update_page(
        english_path, "a/p.html", (make_entry("a/p.html", "Overview"),)
    )
    index.update_page(
        portuguese_path, "a/p.html", (make_entry("a/p.html", "Visao"),)
    )

    # Act
    index.write(english_path)
    index.write(portuguese_path)

    # Assert
    assert [
        entry["title"] for entry in read_search_index(english_path)["docs"]
    ] == ["Overview"]
    assert [
        entry["title"] for entry in read_search_index(portuguese_path)["docs"]
    ] == ["Visao"]


def test_clear_drops_accumulated_entries(tmp_path: Path) -> None:
    # Arrange — a full rebuild starts from an empty index so pages removed
    # from the site config leave no stale entries behind.
    index = InMemorySearchIndex()
    index.update_page(tmp_path, "a/p.html", (make_entry("a/p.html"),))

    # Act
    index.clear()
    index.write(tmp_path)

    # Assert
    assert read_search_index(tmp_path) == {"docs": []}


def test_entries_keep_page_update_order(tmp_path: Path) -> None:
    # Arrange — entry order follows build order (collection, then page):
    # deterministic output keeps built-site diffs stable.
    index = InMemorySearchIndex()
    index.update_page(
        tmp_path, "a/first.html", (make_entry("a/first.html", "First"),)
    )
    index.update_page(
        tmp_path, "a/second.html", (make_entry("a/second.html", "Second"),)
    )

    # Act
    index.write(tmp_path)

    # Assert
    assert [
        entry["location"] for entry in read_search_index(tmp_path)["docs"]
    ] == ["a/first.html", "a/second.html"]
