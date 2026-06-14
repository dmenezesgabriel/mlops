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
            "Overestimating Demand (False Positives)": "Superestimando a Demanda (Positivos Falsos)",
            "TR0:": "TR0:",
        }
    )
    result = translator.translate_markdown_source(source, PT_BR)
    assert result == "  *   **Superestimando a Demanda (Positivos Falsos)**:\n"


def test_translate_preserves_italic_inline_formatting() -> None:
    source = "By predicting demand *before* the ride requests occur.\n"
    translator = _make_translator(
        {
            "before": "antes",
            "By predicting demand TR0 the ride requests occur.": (
                "Ao prever a demanda TR0 que os pedidos de carona ocorram."
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
            "Operational Consequence": "Consequência Operacional",
            "TR0: Drivers are routed.": "TR0: Os motoristas são encaminhados.",
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
            "DuckDB": "DuckDB",
            "analytics": "análise",
            "Use TR0 for TR1.": "Use TR0 para TR1.",
        }
    )
    result = translator.translate_markdown_source(source, PT_BR)
    assert result == "Use **DuckDB** para *análise*.\n"


def test_translate_preserves_bold_in_top_level_list_item() -> None:
    source = "*   **Target**: Predict the pickup count.\n"
    translator = _make_translator(
        {
            "Target": "Target",
            "TR0: Predict the pickup count.": "TR0: Preveja a contagem de embarques.",
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
        {"Avoid TR0 here.": "Evite aqui sem o marcador."}
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


def test_translate_preserves_jinja_expressions_and_translates_surrounding_text() -> (
    None
):
    source = 'Below is the core implementation:\n{{ include_source("script.py") }}\n'
    translator = _make_translator(
        {
            "Below is the core implementation:TR0TR1": "Abaixo está a implementação principal:TR0TR1"
        }
    )
    result = translator.translate_markdown_source(source, PT_BR)
    assert (
        result
        == 'Abaixo está a implementação principal:\n{{ include_source("script.py") }}\n'
    )


def test_translate_preserves_math_expressions_with_underscores() -> None:
    source = "$$R^2 = 1 - \\frac{\\sum_{i=1}^n (y_i - \\hat{y}_i)^2}{\\sum_{i=1}^n (y_i - \\bar{y})^2}$$\n"
    translator = _make_translator({"TR0": "TR0"})
    result = translator.translate_markdown_source(source, PT_BR)
    assert (
        result
        == "$$R^2 = 1 - \\frac{\\sum_{i=1}^n (y_i - \\hat{y}_i)^2}{\\sum_{i=1}^n (y_i - \\bar{y})^2}$$\n"
    )


def test_translate_table_header_cells() -> None:
    source = "| Header A | Header B |\n| --- | --- |\n| Cell A | Cell B |\n"
    translator = _make_translator(
        {
            "Header A": "Cabeçalho A",
            "Header B": "Cabeçalho B",
            "Cell A": "Célula A",
            "Cell B": "Célula B",
        }
    )
    result = translator.translate_markdown_source(source, PT_BR)
    assert (
        result
        == "| Cabeçalho A | Cabeçalho B |\n| ----------- | ----------- |\n| Célula A    | Célula B    |\n"
    )
