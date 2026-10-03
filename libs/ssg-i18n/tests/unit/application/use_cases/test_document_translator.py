import json
import re
from pathlib import Path

import pytest
from ssg_i18n.application.use_cases.catalog_first_text_translator import (
    CatalogFirstTextTranslator,
)
from ssg_i18n.application.use_cases.document_translator import (
    DocumentTranslator,
)
from ssg_i18n.domain.value_objects.locale import Locale
from ssg_i18n.domain.value_objects.translation_catalog import (
    TranslationCatalog,
)
from ssg_i18n.infrastructure.in_memory_text_translator import (
    InMemoryTextTranslator,
)


class _GlossaryAwareStubTranslator:
    """Catalog-bearing translator fake that is not CatalogFirstTextTranslator."""

    def __init__(
        self, glossary_terms: dict[str, str], translations: dict[str, str]
    ) -> None:
        self._glossary_terms = glossary_terms
        self._translations = translations

    @property
    def glossary_terms(self) -> dict[str, str]:
        return self._glossary_terms

    def catalog_translation_for(self, source_text: str) -> str | None:
        return self._translations.get(source_text)

    def translate(self, source_text: str, target_locale: Locale) -> str:
        return self._translations.get(source_text, source_text)


class _EchoTranslator:
    """TextTranslator fake returning its input — exercises marker restore."""

    def translate(self, source_text: str, target_locale: Locale) -> str:
        return source_text


class _RecordingFallbackTranslator:
    """TextTranslator fake recording translate() inputs; echoes the source."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def translate(self, source_text: str, target_locale: Locale) -> str:
        self.calls.append(source_text)
        return source_text


class _TrailingProseTranslator:
    """Echoes the sentence with a trailing 'TR 9' — ordinary MT prose."""

    def translate(self, source_text: str, target_locale: Locale) -> str:
        return source_text + " com TR 9"


class _MarkerDroppingTranslator:
    """Machine-translation fake that drops every protection marker."""

    def translate(self, source_text: str, target_locale: Locale) -> str:
        return "cauda traduzida"


def _fixed_marker_token() -> str:
    return "0123456789abcdef"


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

    def test_glossary_applies_to_any_catalog_aware_translator(self) -> None:
        # Any translator exposing glossary_terms gets glossary protection —
        # the contract is the port, not CatalogFirstTextTranslator.
        stub = _GlossaryAwareStubTranslator(
            glossary_terms={"Zebraterm": "Termozebra"},
            translations={
                "Use TR0X0123456789abcdef here.": "Use TR0X0123456789abcdef aqui."
            },
        )
        translator = DocumentTranslator(
            stub, marker_token_factory=_fixed_marker_token
        )
        result = translator.translate_markdown_source(
            "Use Zebraterm here.\n", Locale("pt-BR")
        )
        assert result == "Use Termozebra aqui.\n"

    def test_glossary_skipped_when_translator_not_catalog_aware(self) -> None:
        translator = DocumentTranslator(InMemoryTextTranslator({}))
        result = translator.translate_markdown_source(
            "Zebraterm the model.\n", Locale("pt-BR")
        )
        assert result == "Zebraterm the model.\n"

    def test_glossary_protects_longest_matching_term(self) -> None:
        catalog = TranslationCatalog(
            translations={},
            glossary_terms={
                "machine": "maquina",
                "machine learning": "aprendizado de maquina",
            },
        )
        fallback = InMemoryTextTranslator(
            {"TR0X0123456789abcdef works.": "TR0X0123456789abcdef funciona."}
        )
        translator = DocumentTranslator(
            CatalogFirstTextTranslator(catalog, fallback),
            marker_token_factory=_fixed_marker_token,
        )
        result = translator.translate_markdown_source(
            "Machine learning works.\n", Locale("pt-BR")
        )
        assert result == "aprendizado de maquina funciona.\n"

    def test_glossary_pattern_compiles_once_per_translator(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        terms = {f"glossterm{i}": f"GT{i}" for i in range(50)}
        catalog = TranslationCatalog(translations={}, glossary_terms=terms)
        glossary_compiles: list[str] = []
        real_compile = re.compile

        def recording_compile(
            pattern: object, flags: int = 0
        ) -> re.Pattern[str]:
            if "glossterm" in str(pattern):
                glossary_compiles.append(str(pattern))
            return real_compile(str(pattern), flags)  # type: ignore[call-overload]

        monkeypatch.setattr(re, "compile", recording_compile)
        translator = DocumentTranslator(
            CatalogFirstTextTranslator(catalog, InMemoryTextTranslator({}))
        )
        translator.translate_markdown_source(
            "glossterm1 and glossterm49.\n", Locale("pt-BR")
        )
        translator.translate_markdown_source(
            "glossterm2 and glossterm48.\n", Locale("pt-BR")
        )

        assert len(glossary_compiles) == 1

    def test_terminology_rules_do_not_leak_into_non_pt_br_output(
        self,
    ) -> None:
        # The pt-BR "Batch Noun -> Noun em Batch" rule must not fire for
        # other target locales.
        translator = DocumentTranslator(InMemoryTextTranslator({}))
        result = translator.translate_markdown_source(
            "Batch Skript laeuft.\n", Locale("de")
        )
        assert result == "Batch Skript laeuft.\n"

    def test_literal_marker_text_in_source_is_not_collided(self) -> None:
        # "TR0" can be a legitimate acronym — protection markers are
        # unguessable so authored literals survive restore untouched.
        translator = DocumentTranslator(text_translator=_EchoTranslator())
        result = translator.translate_markdown_source(
            "TR0 is a real acronym. Use `code` now.\n", Locale("pt-BR")
        )
        assert result == "TR0 is a real acronym. Use `code` now.\n"

    def test_literal_mathexpr_text_survives_math_protection(self) -> None:
        translator = DocumentTranslator(text_translator=_EchoTranslator())
        result = translator.translate_markdown_source(
            "The MATHEXPR0 label and $x<y$ math.\n", Locale("pt-BR")
        )
        assert result == "The MATHEXPR0 label and $x<y$ math.\n"

    def test_tr_n_prose_is_not_rewritten_by_marker_heal(self) -> None:
        # "TR 9" is ordinary prose, not a mangled marker — heal may only
        # normalize copies of markers this sentence actually placed.
        translator = DocumentTranslator(
            text_translator=_TrailingProseTranslator()
        )
        result = translator.translate_markdown_source(
            "Use `code` now.\n", Locale("pt-BR")
        )
        assert result == "Use `code` now. com TR 9\n"

    def test_dropped_marker_falls_back_without_prepend_duplicate(
        self,
    ) -> None:
        translator = DocumentTranslator(
            text_translator=_MarkerDroppingTranslator()
        )
        result = translator.translate_markdown_source(
            "**bold** tail\n", Locale("pt-BR")
        )
        assert result == "**cauda traduzida** tail\n"

    def test_catalog_lookup_uses_source_sentence_not_marker_text(
        self,
    ) -> None:
        catalog = TranslationCatalog(
            translations={
                "Use `MLflow` for tracking.": "Use MLflow para rastreamento."
            },
            glossary_terms={},
        )
        fallback = _RecordingFallbackTranslator()
        translator = DocumentTranslator(
            CatalogFirstTextTranslator(catalog, fallback)
        )
        result = translator.translate_markdown_source(
            "Use `MLflow` for tracking.\n", Locale("pt-BR")
        )
        assert result == "Use MLflow para rastreamento.\n"
        assert fallback.calls == []

    def test_catalog_hit_is_independent_of_protected_span_count(
        self,
    ) -> None:
        catalog = TranslationCatalog(
            translations={
                "Rely on `MLflow` and `DuckDB` here.": (
                    "Confie em MLflow e DuckDB aqui."
                )
            },
            glossary_terms={},
        )
        fallback = _RecordingFallbackTranslator()
        translator = DocumentTranslator(
            CatalogFirstTextTranslator(catalog, fallback)
        )
        result = translator.translate_markdown_source(
            "Rely on `MLflow` and `DuckDB` here.\n", Locale("pt-BR")
        )
        assert result == "Confie em MLflow e DuckDB aqui.\n"
        assert fallback.calls == []

    def test_catalog_lookup_restores_math_markers_in_source_key(
        self,
    ) -> None:
        catalog = TranslationCatalog(
            translations={
                "The score is $R^2$ today.": "O escore é $R^2$ hoje."
            },
            glossary_terms={},
        )
        fallback = _RecordingFallbackTranslator()
        translator = DocumentTranslator(
            CatalogFirstTextTranslator(catalog, fallback)
        )
        result = translator.translate_markdown_source(
            "The score is $R^2$ today.\n", Locale("pt-BR")
        )
        assert result == "O escore é $R^2$ hoje.\n"
        assert fallback.calls == []

    def test_link_label_is_translated_and_target_preserved(self) -> None:
        translator = DocumentTranslator(
            InMemoryTextTranslator(
                {
                    "the link text": "o texto do link",
                    "A TR0X0123456789abcdef here.": (
                        "Um TR0X0123456789abcdef aqui."
                    ),
                }
            ),
            marker_token_factory=_fixed_marker_token,
        )
        result = translator.translate_markdown_source(
            "A [the link text](http://x) here.\n", Locale("pt-BR")
        )
        assert result == "Um [o texto do link](http://x) aqui.\n"

    def test_image_syntax_is_protected_whole_not_sent_raw(self) -> None:
        recorder = _RecordingFallbackTranslator()
        result = DocumentTranslator(
            recorder, marker_token_factory=_fixed_marker_token
        ).translate_markdown_source(
            "See ![the alt text](img.png) here.\n", Locale("pt-BR")
        )
        assert recorder.calls == ["See TR0X0123456789abcdef here."]
        assert result == "See ![the alt text](img.png) here.\n"

    def test_inline_html_tags_are_protected_not_sent_raw(self) -> None:
        recorder = _RecordingFallbackTranslator()
        result = DocumentTranslator(
            recorder, marker_token_factory=_fixed_marker_token
        ).translate_markdown_source(
            "before <em>inline</em> after\n", Locale("pt-BR")
        )
        assert recorder.calls == [
            "before TR0X0123456789abcdefinlineTR1X0123456789abcdef after"
        ]
        assert result == "before <em>inline</em> after\n"

    def test_autolink_is_protected_whole_without_dangling_bracket(
        self,
    ) -> None:
        recorder = _RecordingFallbackTranslator()
        result = DocumentTranslator(
            recorder, marker_token_factory=_fixed_marker_token
        ).translate_markdown_source(
            "Autolink <http://example.com> done.\n", Locale("pt-BR")
        )
        assert recorder.calls == ["Autolink TR0X0123456789abcdef done."]
        assert result == "Autolink <http://example.com> done.\n"

    def test_strikethrough_children_are_translated(self) -> None:
        translator = DocumentTranslator(
            InMemoryTextTranslator(
                {
                    "struck": "riscado",
                    "Some TR0X0123456789abcdef text.": (
                        "Algum TR0X0123456789abcdef texto."
                    ),
                }
            ),
            marker_token_factory=_fixed_marker_token,
        )
        result = translator.translate_markdown_source(
            "Some ~~struck~~ text.\n", Locale("pt-BR")
        )
        assert result == "Algum ~~riscado~~ texto.\n"

    def test_escape_sequence_is_protected_not_sent_raw(self) -> None:
        recorder = _RecordingFallbackTranslator()
        result = DocumentTranslator(
            recorder, marker_token_factory=_fixed_marker_token
        ).translate_markdown_source("An \\* escaped star.\n", Locale("pt-BR"))
        assert recorder.calls == ["An TR0X0123456789abcdef escaped star."]
        assert result == "An \\* escaped star.\n"

    @pytest.mark.parametrize(
        "entity",
        ["&amp;copy;", "&amp;", "&#233;"],
    )
    def test_authored_entities_round_trip_verbatim(self, entity: str) -> None:
        recorder = _RecordingFallbackTranslator()
        result = DocumentTranslator(
            recorder, marker_token_factory=_fixed_marker_token
        ).translate_markdown_source(
            f"The entity {entity} is text.\n", Locale("pt-BR")
        )
        assert recorder.calls == [f"The entity {entity} is text."]
        assert result == f"The entity {entity} is text.\n"

    def test_catalog_key_uses_authored_entity_text(self) -> None:
        catalog = TranslationCatalog(
            translations={
                "The entity &amp;copy; is text.": "A entidade permanece."
            },
            glossary_terms={},
        )
        fallback = _RecordingFallbackTranslator()
        translator = DocumentTranslator(
            CatalogFirstTextTranslator(catalog, fallback)
        )
        result = translator.translate_markdown_source(
            "The entity &amp;copy; is text.\n", Locale("pt-BR")
        )
        assert result == "A entidade permanece.\n"
        assert fallback.calls == []

    def test_translate_file_rejects_non_object_notebook(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "list.ipynb"
        source.write_text(json.dumps([1, 2]), encoding="utf-8")

        with pytest.raises(ValueError, match="expected JSON object"):
            DocumentTranslator(
                text_translator=InMemoryTextTranslator({})
            ).translate_file(source, tmp_path / "out.ipynb", Locale("pt-BR"))

    @pytest.mark.parametrize(
        "cell",
        [
            pytest.param(
                {"cell_type": "markdown", "metadata": {}}, id="absent"
            ),
            pytest.param(
                {"cell_type": "markdown", "metadata": {}, "source": None},
                id="null",
            ),
            pytest.param(
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": {"a": 1},
                },
                id="dict",
            ),
            pytest.param(
                {"cell_type": "markdown", "metadata": {}, "source": 42},
                id="int",
            ),
            pytest.param(
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["ok", 5],
                },
                id="mixed-list",
            ),
        ],
    )
    def test_translate_notebook_rejects_malformed_markdown_source(
        self, tmp_path: Path, cell: dict[str, object]
    ) -> None:
        source = tmp_path / "bad.ipynb"
        source.write_text(
            json.dumps({"cells": [cell], "metadata": {}, "nbformat": 4}),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="expected.*source"):
            DocumentTranslator(
                text_translator=InMemoryTextTranslator({})
            ).translate_file(source, tmp_path / "out.ipynb", Locale("pt-BR"))

    def test_translate_notebook_string_list_source(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "ok.ipynb"
        source.write_text(
            json.dumps(
                {
                    "cells": [
                        {
                            "cell_type": "markdown",
                            "metadata": {},
                            "source": ["Hello notebook."],
                        }
                    ],
                    "metadata": {},
                    "nbformat": 4,
                }
            ),
            encoding="utf-8",
        )
        output = tmp_path / "out.ipynb"

        DocumentTranslator(
            text_translator=InMemoryTextTranslator(
                {"Hello notebook.": "Ola caderno."}
            )
        ).translate_file(source, output, Locale("pt-BR"))

        translated = json.loads(output.read_text(encoding="utf-8"))
        assert translated["cells"][0]["source"] == "Ola caderno."
