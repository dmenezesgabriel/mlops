from ssg_i18n.application.translation import TextTranslator
from ssg_i18n_machine_translation.infrastructure.plugin import (
    create_transformers_text_translator,
)
from ssg_i18n_machine_translation.infrastructure.transformers_text_translator import (
    TransformersTextTranslator,
)


def test_plugin_factory_returns_a_conforming_text_translator() -> None:
    # The ssg_i18n.text_translators entry-point contract: a zero-arg factory
    # returning an object the provider can drive through the port.
    translator = create_transformers_text_translator()

    assert isinstance(translator, TextTranslator)
    assert isinstance(translator, TransformersTextTranslator)
