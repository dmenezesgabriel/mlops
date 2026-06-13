from ssg_i18n.application.document_translation import DocumentTranslator
from ssg_i18n.application.translation import InMemoryTextTranslator
from ssg_i18n.domain.locale import Locale

PT_BR = Locale("pt-BR")


def _make_translator(mappings: dict[str, str]) -> DocumentTranslator:
    """Build a DocumentTranslator backed by an in-memory lookup table."""
    return DocumentTranslator(InMemoryTextTranslator(mappings))


def test_translate_preserves_bold_in_nested_list_item() -> None:
    source = "  *   **Overestimating Demand (False Positives)**:\n"
    translator = _make_translator(
        {
            "**Overestimating Demand (False Positives)**:": (
                "**Superestimando a Demanda (Positivos Falsos)**:"
            ),
        }
    )
    result = translator.translate_markdown_source(source, PT_BR)
    assert result == "  *   **Superestimando a Demanda (Positivos Falsos)**:\n"


def test_translate_preserves_italic_inline_formatting() -> None:
    source = "By predicting demand *before* the ride requests occur.\n"
    translator = _make_translator(
        {
            "By predicting demand *before* the ride requests occur.": (
                "Ao prever a demanda *antes* que os pedidos de carona ocorram."
            ),
        }
    )
    result = translator.translate_markdown_source(source, PT_BR)
    assert (
        result
        == "Ao prever a demanda *antes* que os pedidos de carona ocorram.\n"
    )


def test_translate_passes_horizontal_rule_unchanged() -> None:
    source = "---\n"
    translator = _make_translator({"---": "SHOULD NOT BE CALLED"})
    result = translator.translate_markdown_source(source, PT_BR)
    assert result == "---\n"


def test_translate_preserves_italic_in_nested_list_item() -> None:
    source = "  *   *Operational Consequence*: Drivers are routed.\n"
    translator = _make_translator(
        {
            "*Operational Consequence*: Drivers are routed.": (
                "*Consequência Operacional*: Os motoristas são encaminhados."
            ),
        }
    )
    result = translator.translate_markdown_source(source, PT_BR)
    assert (
        result
        == "  *   *Consequência Operacional*: Os motoristas são encaminhados.\n"
    )


def test_translate_preserves_both_bold_and_italic_in_same_line() -> None:
    source = "Use **DuckDB** for *analytics*.\n"
    translator = _make_translator(
        {
            "Use **DuckDB** for *analytics*.": "Use **DuckDB** para *análise*.",
        }
    )
    result = translator.translate_markdown_source(source, PT_BR)
    assert result == "Use **DuckDB** para *análise*.\n"


def test_translate_preserves_bold_in_top_level_list_item() -> None:
    source = "*   **Target**: Predict the pickup count.\n"
    translator = _make_translator(
        {
            "**Target**: Predict the pickup count.": (
                "**Target**: Preveja a contagem de embarques."
            ),
        }
    )
    result = translator.translate_markdown_source(source, PT_BR)
    assert result == "*   **Target**: Preveja a contagem de embarques.\n"


def test_translate_falls_back_to_english_source_when_bold_marker_dropped() -> (
    None
):
    # If the MT model drops a glossary placeholder, fallback is triggered
    source = "Avoid **Feast** here.\n"
    translator = _make_translator(
        {
            # Feast is in glossary and becomes {99900}
            # MT drops the marker:
            "Avoid **{99900}** here.": "Evite aqui sem o marcador."
        }
    )
    # Mock catalog has Feast: Feast in glossary
    from ssg_i18n.application.translation import CatalogFirstTextTranslator
    from ssg_i18n.domain.translation_catalog import TranslationCatalog

    catalog = TranslationCatalog({}, {"Feast": "Feast"})
    doc_translator = DocumentTranslator(
        CatalogFirstTextTranslator(catalog, translator.text_translator)
    )
    result = doc_translator.translate_markdown_source(source, PT_BR)
    assert result == "Avoid **Feast** here.\n"
