from collections.abc import Callable
from importlib import import_module
from typing import Protocol, runtime_checkable

from ssg_i18n.application.translation import TextTranslator
from ssg_i18n.domain.locale import Locale


@runtime_checkable
class TransformersModule(Protocol):
    def pipeline(self, task: str, model: str) -> Callable[..., object]:
        pass


class TransformersTextTranslator(TextTranslator):
    def __init__(
        self, model_name: str = "Helsinki-NLP/opus-mt-tc-big-en-pt"
    ) -> None:
        self._model_name = model_name
        self._translation_pipeline: Callable[..., object] | None = None

    def translate(self, source_text: str, target_locale: Locale) -> str:
        translation_pipeline = self._pipeline()
        generation_options: dict[str, object] = {
            "max_new_tokens": max(16, min(128, len(source_text.split()) * 4)),
            "no_repeat_ngram_size": 3,
        }
        if "nllb" in self._model_name.lower():
            generation_options["src_lang"] = "eng_Latn"
            generation_options["tgt_lang"] = self._flores_lang_code(
                target_locale
            )

        result = translation_pipeline(
            source_text,
            **generation_options,
        )
        translated_text = self._translation_text(
            result, source_text, target_locale
        )
        if self._looks_degenerate(translated_text):
            return source_text

        return translated_text

    def _flores_lang_code(self, locale: Locale) -> str:
        normalized = locale.tag.lower().replace("_", "-")
        prefix = normalized.split("-")[0]
        mapping = {
            "en": "eng_Latn",
            "pt": "por_Latn",
            "es": "spa_Latn",
            "fr": "fra_Latn",
            "de": "deu_Latn",
            "it": "ita_Latn",
            "ru": "rus_Cyrl",
            "zh": "zho_Hans",
            "ja": "jpn_Jpan",
            "ko": "kor_Hang",
        }
        if normalized in mapping:
            return mapping[normalized]
        if prefix in mapping:
            return mapping[prefix]
        return locale.tag

    def _pipeline(self) -> Callable[..., object]:
        if self._translation_pipeline is not None and callable(
            self._translation_pipeline
        ):
            return self._translation_pipeline

        transformers_module = import_module("transformers")
        if not isinstance(transformers_module, TransformersModule):
            raise RuntimeError(
                "Missing transformers.pipeline: expected transformers extra installed"
            )

        self._translation_pipeline = transformers_module.pipeline(
            "translation", model=self._model_name
        )
        return self._translation_pipeline

    def _translation_text(
        self, result: object, source_text: str, target_locale: Locale
    ) -> str:
        if not isinstance(result, list) or not result:
            raise RuntimeError(
                f"Invalid transformers result for locale {target_locale.tag}: "
                "expected non-empty list",
            )

        first_result = result[0]
        if isinstance(first_result, dict):
            translation_text = first_result.get("translation_text")
            if isinstance(translation_text, str):
                return translation_text

        raise RuntimeError(
            f"Invalid transformers result {result!r}: "
            f"expected translation_text for {source_text!r}",
        )

    def _looks_degenerate(self, translated_text: str) -> bool:
        normalized_words = translated_text.lower().split()
        if len(normalized_words) < 8:
            return False

        unique_word_ratio = len(set(normalized_words)) / len(normalized_words)
        return unique_word_ratio < 0.35
