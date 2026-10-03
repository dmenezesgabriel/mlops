import sys
from types import ModuleType

import pytest
from ssg_i18n.domain.locale import Locale
from ssg_i18n_machine_translation.infrastructure import (
    transformers_text_translator,
)
from ssg_i18n_machine_translation.infrastructure.transformers_text_translator import (
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


def test_translate_uses_transformers_pipeline_and_reuses_loaded_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    fake_module = FakeTransformersModule()
    monkeypatch.setitem(sys.modules, "transformers", fake_module)
    translator = TransformersTextTranslator("fake-technical-model")

    # Act
    first_translation = translator.translate("Feature store", Locale("pt-BR"))
    second_translation = translator.translate(
        "Model registry", Locale("pt-BR")
    )

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


@pytest.mark.parametrize("target_tag", ["fr", "de"])
def test_translate_rejects_target_locale_outside_the_model_pair(
    target_tag: str,
) -> None:
    # Arrange
    translator = TransformersTextTranslator()
    translator._translation_pipeline = CaptureOptionsFakeTranslationPipeline()

    # Act / Assert
    with pytest.raises(
        ValueError, match=f"cannot translate to locale '{target_tag}'"
    ):
        translator.translate("Hello world", Locale(target_tag))


def test_translate_rejects_unmapped_flores_locale_on_nllb() -> None:
    # Arrange
    translator = TransformersTextTranslator("facebook/nllb-200-distilled-600M")
    translator._translation_pipeline = CaptureOptionsFakeTranslationPipeline()

    # Act / Assert
    with pytest.raises(ValueError) as excinfo:
        translator.translate("Hello world", Locale("nl"))

    assert "'nl'" in str(excinfo.value)
    assert "expected one of" in str(excinfo.value)


def test_translate_serves_a_declared_target_language() -> None:
    # Arrange
    translator = TransformersTextTranslator(
        "Helsinki-NLP/opus-mt-en-fr", target_languages=("fr",)
    )
    pipeline_mock = CaptureOptionsFakeTranslationPipeline()
    translator._translation_pipeline = pipeline_mock

    # Act
    translated_text = translator.translate("Hello world", Locale("fr"))

    # Assert
    assert translated_text == "translated:Hello world"


def test_translate_accepts_region_full_declared_target_language() -> None:
    # Arrange
    translator = TransformersTextTranslator(target_languages=("pt-BR",))
    translator._translation_pipeline = CaptureOptionsFakeTranslationPipeline()

    # Act
    translated_text = translator.translate("Hello world", Locale("pt-BR"))

    # Assert
    assert translated_text == "translated:Hello world"


def test_translate_scales_max_new_tokens_with_input_length() -> None:
    # Arrange
    translator = TransformersTextTranslator()
    pipeline_mock = CaptureOptionsFakeTranslationPipeline()
    translator._translation_pipeline = pipeline_mock
    source_text = " ".join(["feature"] * 50)

    # Act
    translator.translate(source_text, Locale("pt-BR"))

    # Assert
    assert pipeline_mock.calls[0][1]["max_new_tokens"] == 200


@pytest.mark.parametrize(
    ("model_name", "expected_cap"),
    [
        ("Helsinki-NLP/opus-mt-tc-big-en-pt", 512),
        ("facebook/nllb-200-distilled-600M", 1024),
    ],
)
def test_translate_caps_max_new_tokens_at_model_positional_max(
    model_name: str, expected_cap: int
) -> None:
    # Arrange
    translator = TransformersTextTranslator(model_name)
    pipeline_mock = CaptureOptionsFakeTranslationPipeline()
    translator._translation_pipeline = pipeline_mock
    source_text = " ".join(["feature"] * 300)

    # Act
    translator.translate(source_text, Locale("pt-BR"))

    # Assert
    assert pipeline_mock.calls[0][1]["max_new_tokens"] == expected_cap


class MissingModuleImporter:
    def __init__(self, missing_name: str) -> None:
        self._missing_name = missing_name

    def __call__(self, _name: str) -> ModuleType:
        raise ModuleNotFoundError(
            f"No module named {self._missing_name!r}",
            name=self._missing_name,
        )


@pytest.mark.parametrize("missing_name", ["transformers", "torch"])
def test_translate_names_transformers_extra_when_module_missing(
    missing_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(
        transformers_text_translator,
        "import_module",
        MissingModuleImporter(missing_name),
    )
    translator = TransformersTextTranslator()

    # Act / Assert
    with pytest.raises(RuntimeError) as excinfo:
        translator.translate("Hello world", Locale("pt-BR"))

    assert f"'{missing_name}'" in str(excinfo.value)
    assert "ssg-i18n-machine-translation[transformers]" in str(excinfo.value)


def test_translate_rejects_module_without_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — a module that imports but lacks a conforming `pipeline` must
    # name the missing surface, not AttributeError on attribute access.
    monkeypatch.setattr(
        transformers_text_translator,
        "import_module",
        lambda _name: ModuleType("transformers"),
    )
    translator = TransformersTextTranslator()

    # Act / Assert
    with pytest.raises(RuntimeError, match="Missing transformers.pipeline"):
        translator.translate("Hello world", Locale("pt-BR"))


class StaticResultPipeline:
    def __init__(self, result: object) -> None:
        self._result = result

    def __call__(
        self, _source_text: str, **_generation_options: object
    ) -> object:
        return self._result


@pytest.mark.parametrize(
    "bad_result",
    [{}, [], None, "not-a-list"],
    ids=["dict", "empty-list", "none", "str"],
)
def test_translate_rejects_non_list_pipeline_result(
    bad_result: object,
) -> None:
    # Arrange — the HF contract is a non-empty list of dicts; anything else
    # must fail loudly instead of indexing into it.
    translator = TransformersTextTranslator()
    translator._translation_pipeline = StaticResultPipeline(bad_result)

    # Act / Assert
    with pytest.raises(RuntimeError, match="expected non-empty list"):
        translator.translate("Hello world", Locale("pt-BR"))


@pytest.mark.parametrize(
    "bad_result",
    [[42], [{"other": "x"}], [{"translation_text": 5}]],
    ids=["non-dict-item", "missing-key", "non-str-value"],
)
def test_translate_rejects_result_without_translation_text(
    bad_result: object,
) -> None:
    # Arrange — a list result whose first item lacks a string
    # `translation_text` is equally invalid.
    translator = TransformersTextTranslator()
    translator._translation_pipeline = StaticResultPipeline(bad_result)

    # Act / Assert
    with pytest.raises(RuntimeError, match="expected translation_text"):
        translator.translate("Hello world", Locale("pt-BR"))


class BoundaryRatioPipeline:
    """20 words, 7 unique → unique_word_ratio exactly 0.35 (the boundary)."""

    TEXT = " ".join(["repeat"] * 14 + [f"unique{i}" for i in range(6)])

    def __call__(
        self, _source_text: str, **_generation_options: object
    ) -> list[dict[str, str]]:
        return [{"translation_text": self.TEXT}]


def test_translate_keeps_text_at_degenerate_ratio_boundary() -> None:
    # Arrange — ratio == 0.35 is NOT degenerate (strict `<`): `<=` would
    # discard a legitimate translation as repetition.
    translator = TransformersTextTranslator()
    translator._translation_pipeline = BoundaryRatioPipeline()

    # Act
    translated = translator.translate(
        "Feature store for model registry", Locale("pt-BR")
    )

    # Assert
    assert translated == BoundaryRatioPipeline.TEXT


def test_translate_floors_max_new_tokens_for_empty_source() -> None:
    # Arrange — a zero-word input must still request the 16-token floor,
    # never zero or negative.
    translator = TransformersTextTranslator()
    pipeline_mock = CaptureOptionsFakeTranslationPipeline()
    translator._translation_pipeline = pipeline_mock

    # Act
    translator.translate("", Locale("pt-BR"))

    # Assert
    assert pipeline_mock.calls[0][1]["max_new_tokens"] == 16
