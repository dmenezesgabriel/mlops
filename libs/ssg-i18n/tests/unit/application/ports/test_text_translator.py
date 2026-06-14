from ssg_i18n.application.ports.text_translator import TextTranslator
from ssg_i18n.domain.value_objects.locale import Locale


class _StubTranslator:
    """Minimal TextTranslator implementation used for protocol conformance check."""

    def translate(self, source_text: str, target_locale: Locale) -> str:
        return source_text


class TestTextTranslatorProtocol:
    def test_stub_satisfies_protocol(self) -> None:
        # Runtime check that the protocol is satisfied structurally.
        assert isinstance(_StubTranslator(), TextTranslator)
