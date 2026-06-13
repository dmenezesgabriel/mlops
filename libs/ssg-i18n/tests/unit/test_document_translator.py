from ssg_i18n.application.document_translation import DocumentTranslator
from ssg_i18n.application.translation import InMemoryTextTranslator
from ssg_i18n.domain.locale import Locale

PT_BR = Locale("pt-BR")


def _make_translator(mappings: dict[str, str]) -> DocumentTranslator:
    """Build a DocumentTranslator backed by an in-memory lookup table."""
    return DocumentTranslator(InMemoryTextTranslator(mappings))


def test_translate_preserves_bold_in_nested_list_item() -> None:
    # The bold span content is pre-translated separately; the whole span becomes
    # a single-occurrence {99900} marker sent to MT together with ':'.
    source = "    *   **Overestimating Demand (False Positives)**:\n"
    translator = _make_translator(
        {
            # Pre-translation of span content:
            "Overestimating Demand (False Positives)": (
                "Superestimando a Demanda (Positivos Falsos)"
            ),
            # Main body after span extraction ({99900}: is left; MT keeps it):
            # No mapping needed — "{99900}:" has no mapping → returned unchanged
        }
    )
    result = translator.translate_markdown_source(source, PT_BR)
    assert (
        result == "    *   **Superestimando a Demanda (Positivos Falsos)**:\n"
    )


def test_translate_preserves_italic_inline_formatting() -> None:
    # The italic span content is pre-translated; main body gets context-aware MT.
    source = "By predicting demand *before* the ride requests occur.\n"
    translator = _make_translator(
        {
            # Pre-translation of span content:
            "before": "antes",
            # Main line body with single {99900} placeholder for the span:
            "By predicting demand {99900} the ride requests occur.": (
                "Ao prever a demanda {99900} que os pedidos de carona ocorram."
            ),
        }
    )
    result = translator.translate_markdown_source(source, PT_BR)
    assert (
        result
        == "Ao prever a demanda *antes* que os pedidos de carona ocorram.\n"
    )


def test_translate_passes_horizontal_rule_unchanged() -> None:
    # --- must never be sent to the translator (it duplicates the dashes).
    source = "---\n"
    translator = _make_translator({"---": "SHOULD NOT BE CALLED"})
    result = translator.translate_markdown_source(source, PT_BR)
    assert result == "---\n"


def test_translate_preserves_italic_in_nested_list_item() -> None:
    # Italic in nested list: indentation preserved via prefix strip, * via pre-translation.
    source = "    *   *Operational Consequence*: Drivers are routed.\n"
    translator = _make_translator(
        {
            "Operational Consequence": "Consequência Operacional",
            "{99900}: Drivers are routed.": "{99900}: Os motoristas são encaminhados.",
        }
    )
    result = translator.translate_markdown_source(source, PT_BR)
    assert (
        result
        == "    *   *Consequência Operacional*: Os motoristas são encaminhados.\n"
    )


def test_translate_preserves_both_bold_and_italic_in_same_line() -> None:
    # Bold processed first → {99900}; italic processed after bold → {99901}.
    source = "Use **DuckDB** for *analytics*.\n"
    translator = _make_translator(
        {
            # Bold span content (pre-translated first):
            "DuckDB": "DuckDB",  # proper noun stays unchanged
            # Italic span content (pre-translated after bold placeholder is in text):
            "analytics": "análise",
            # Main line with both placeholders:
            "Use {99900} for {99901}.": "Use {99900} para {99901}.",
        }
    )
    result = translator.translate_markdown_source(source, PT_BR)
    assert result == "Use **DuckDB** para *análise*.\n"


def test_translate_preserves_bold_in_top_level_list_item() -> None:
    # No indentation, bold term in a list item definition.
    source = "*   **Target**: Predict the pickup count.\n"
    translator = _make_translator(
        {
            "Target": "Alvo",
            "{99900}: Predict the pickup count.": (
                "{99900}: Preveja a contagem de embarques."
            ),
        }
    )
    result = translator.translate_markdown_source(source, PT_BR)
    assert result == "*   **Alvo**: Preveja a contagem de embarques.\n"


def test_translate_falls_back_to_english_source_when_bold_marker_dropped() -> (
    None
):
    # Use a non-leading bold marker so that leading-marker healing does not apply.
    # If MT drops the marker, the fallback kicks in and returns the original line.
    source = "Avoid **Overestimating Demand** here.\n"
    translator = _make_translator(
        {
            # MT drops the {99900} marker completely
            "Avoid {99900} here.": "Evite aqui sem o marcador."
        }
    )
    result = translator.translate_markdown_source(source, PT_BR)
    # Validation fails (marker dropped) -> fallback to protected_source -> restore -> original English
    assert result == "Avoid **Overestimating Demand** here.\n"
