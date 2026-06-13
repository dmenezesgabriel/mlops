import sys
from types import ModuleType

from ssg_i18n.domain.locale import Locale
from ssg_i18n_machine_translation.transformers_text_translator import (
    TransformersTextTranslator,
)


class FakeTransformersModule(ModuleType):
    def __init__(self) -> None:
        super().__init__("transformers")
        self.pipeline_calls = 0

    def pipeline(self, task: str, model: str) -> "FakeTranslationPipeline":
        self.pipeline_calls += 1
        return FakeTranslationPipeline(task, model)


class FakeTranslationPipeline:
    def __init__(self, task: str, model: str) -> None:
        self.task = task
        self.model = model

    def __call__(
        self, source_text: str, **_generation_options: object
    ) -> list[dict[str, str]]:
        return [{"translation_text": f"pt-BR:{source_text}"}]


class RepeatingFakeTranslationPipeline:
    def __call__(
        self, _source_text: str, **_generation_options: object
    ) -> list[dict[str, str]]:
        return [{"translation_text": "translation " * 20}]


def test_translate_uses_transformers_pipeline_and_reuses_loaded_model() -> (
    None
):
    # Arrange
    previous_module = sys.modules.get("transformers")
    fake_module = FakeTransformersModule()
    sys.modules["transformers"] = fake_module
    translator = TransformersTextTranslator("fake-technical-model")

    try:
        # Act
        first_translation = translator.translate(
            "Feature store", Locale("pt-BR")
        )
        second_translation = translator.translate(
            "Model registry", Locale("pt-BR")
        )
    finally:
        if previous_module is None:
            del sys.modules["transformers"]
        else:
            sys.modules["transformers"] = previous_module

    # Assert
    assert first_translation == "pt-BR:Feature store"
    assert second_translation == "pt-BR:Model registry"
    assert fake_module.pipeline_calls == 1


def test_translate_falls_back_to_source_for_degenerate_repetition() -> None:
    # Arrange
    translator = TransformersTextTranslator("fake-technical-model")
    translator._translation_pipeline = RepeatingFakeTranslationPipeline()

    # Act
    translated_text = translator.translate(
        "Feature store for model registry", Locale("pt-BR")
    )

    # Assert
    assert translated_text == "Feature store for model registry"


class CaptureOptionsFakeTranslationPipeline:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def __call__(
        self, source_text: str, **generation_options: object
    ) -> list[dict[str, str]]:
        self.calls.append((source_text, generation_options))
        return [{"translation_text": f"translated:{source_text}"}]


def test_translate_passes_flores_language_codes_to_nllb_pipeline() -> None:
    # Arrange
    translator = TransformersTextTranslator("facebook/nllb-200-distilled-600M")
    pipeline_mock = CaptureOptionsFakeTranslationPipeline()
    translator._translation_pipeline = pipeline_mock

    # Act
    translator.translate("Hello world", Locale("pt-BR"))
    translator.translate("Machine learning", Locale("es"))

    # Assert
    assert len(pipeline_mock.calls) == 2
    assert pipeline_mock.calls[0] == (
        "Hello world",
        {
            "max_new_tokens": 16,
            "no_repeat_ngram_size": 3,
            "src_lang": "eng_Latn",
            "tgt_lang": "por_Latn",
        },
    )
    assert pipeline_mock.calls[1] == (
        "Machine learning",
        {
            "max_new_tokens": 16,
            "no_repeat_ngram_size": 3,
            "src_lang": "eng_Latn",
            "tgt_lang": "spa_Latn",
        },
    )
