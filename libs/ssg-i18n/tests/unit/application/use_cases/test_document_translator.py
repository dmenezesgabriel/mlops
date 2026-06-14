from pathlib import Path

from ssg_i18n.application.use_cases.document_translator import (
    DocumentTranslator,
)
from ssg_i18n.domain.value_objects.locale import Locale
from ssg_i18n.infrastructure.in_memory_text_translator import (
    InMemoryTextTranslator,
)


class TestDocumentTranslator:
    def test_translate_file_markdown(self, tmp_path: Path) -> None:
        source = tmp_path / "page.md"
        source.write_text("Hello world", encoding="utf-8")
        output = tmp_path / "out" / "page.md"

        translator = DocumentTranslator(
            text_translator=InMemoryTextTranslator(
                {"Hello world": "Olá mundo"}
            )
        )
        result = translator.translate_file(source, output, Locale("pt-BR"))

        assert result == output
        assert output.read_text(encoding="utf-8") == "Olá mundo"

    def test_translate_file_creates_parent_dirs(self, tmp_path: Path) -> None:
        source = tmp_path / "doc.md"
        source.write_text("text", encoding="utf-8")
        output = tmp_path / "deep" / "nested" / "doc.md"

        DocumentTranslator(
            text_translator=InMemoryTextTranslator({})
        ).translate_file(source, output, Locale("pt-BR"))

        assert output.exists()

    def test_translate_markdown_source_empty_string(self) -> None:
        translator = DocumentTranslator(
            text_translator=InMemoryTextTranslator({})
        )
        result = translator.translate_markdown_source("", Locale("pt-BR"))
        assert result == ""
