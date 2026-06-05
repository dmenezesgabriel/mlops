from ssg_i18n.application.translation import TextTranslator

from ssg_i18n_machine_translation.transformers_text_translator import TransformersTextTranslator


def create_transformers_text_translator() -> TextTranslator:
    return TransformersTextTranslator()
