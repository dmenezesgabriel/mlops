from collections.abc import Callable
from importlib import import_module
from typing import Any, Protocol, cast, runtime_checkable

from ssg_i18n.application.translation import TextTranslator
from ssg_i18n.domain.locale import Locale


@runtime_checkable
class TransformersModule(Protocol):
    def pipeline(self, task: str, model: str) -> Callable[..., object]: ...


class TransformersTextTranslator(TextTranslator):
    def __init__(
        self,
        model_name: str = "Helsinki-NLP/opus-mt-tc-big-en-pt",
        target_languages: tuple[str, ...] = ("pt",),
    ) -> None:
        # target_languages declares what a fixed-pair model (the Helsinki
        # opus-mt-{src}-{tgt} convention) can produce — mirroring HF's
        # MarianTokenizer.target_lang / supported_language_codes metadata —
        # so a target_locale the model cannot serve fails loudly instead of
        # publishing the wrong language. nllb models ignore it: their served
        # set is the FLORES mapping in _flores_lang_code.
        self._model_name = model_name
        self._target_languages = tuple(
            language.lower().replace("_", "-") for language in target_languages
        )
        self._translation_pipeline: Callable[..., object] | None = None

    def translate(self, source_text: str, target_locale: Locale) -> str:
        # Refuse unservable locales before loading the model: the rejection
        # must not depend on the transformers extra being installed.
        target_lang_code = self._target_lang_code(target_locale)
        translation_pipeline = self._pipeline()
        generation_options: dict[str, object] = {
            "max_new_tokens": max(16, min(128, len(source_text.split()) * 4)),
            "no_repeat_ngram_size": 3,
        }
        if target_lang_code is not None:
            generation_options["src_lang"] = "eng_Latn"
            generation_options["tgt_lang"] = target_lang_code

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

    def _target_lang_code(self, target_locale: Locale) -> str | None:
        if "nllb" in self._model_name.lower():
            return self._flores_lang_code(target_locale)
        self._require_supported_target(target_locale)
        return None

    def _require_supported_target(self, target_locale: Locale) -> None:
        normalized = target_locale.tag.lower().replace("_", "-")
        prefix = normalized.split("-")[0]
        if (
            normalized in self._target_languages
            or prefix in self._target_languages
        ):
            return

        expected = ", ".join(
            repr(language) for language in sorted(self._target_languages)
        )
        raise ValueError(
            f"Model {self._model_name!r} cannot translate to locale "
            f"{target_locale.tag!r}: expected one of {expected} "
            "(the model's fixed target set — pass target_languages "
            "matching the model's language pair)"
        )

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
        raise ValueError(
            f"Model {self._model_name!r} has no FLORES code for locale "
            f"{locale.tag!r}: expected one of {', '.join(sorted(mapping))}"
        )

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

        first_result = cast(object, result[0])
        if isinstance(first_result, dict):
            result_map = cast(dict[str, Any], first_result)
            translation_text = result_map.get("translation_text")
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
