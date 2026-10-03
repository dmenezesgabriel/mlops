import pytest
from ssg_i18n.domain.value_objects.locale import Locale
from ssg_i18n.infrastructure import plugin
from ssg_i18n.infrastructure.plugin import EntryPointTextTranslatorFactory


class FakeTextTranslator:
    """Conforming TextTranslator fake returned by the loaded factory."""

    def translate(self, source_text: str, target_locale: Locale) -> str:
        return source_text


class FakeTranslatorEntryPoint:
    name = "fake-translator"

    def load(self) -> type[FakeTextTranslator]:
        return FakeTextTranslator


class FailingEntryPoint:
    name = "bad-translator"

    def load(self) -> object:
        raise ImportError("cannot import name 'explode'")


class ExplodingFactoryEntryPoint:
    name = "exploding-translator"

    def load(self) -> object:
        def factory() -> object:
            raise RuntimeError("model weights missing")

        return factory


class NonConformingEntryPoint:
    name = "non-conforming-translator"

    def load(self) -> type[object]:
        return object


def test_create_returns_conforming_translator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    def fake_entry_points(group: str) -> tuple[FakeTranslatorEntryPoint, ...]:
        return (FakeTranslatorEntryPoint(),)

    monkeypatch.setattr(plugin, "entry_points", fake_entry_points)

    # Act
    translator = EntryPointTextTranslatorFactory().create()

    # Assert
    assert isinstance(translator, FakeTextTranslator)


def test_create_wraps_entry_point_load_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    def fake_entry_points(group: str) -> tuple[FailingEntryPoint, ...]:
        return (FailingEntryPoint(),)

    monkeypatch.setattr(plugin, "entry_points", fake_entry_points)

    # Act / Assert
    with pytest.raises(RuntimeError) as excinfo:
        EntryPointTextTranslatorFactory().create()
    assert "'bad-translator'" in str(excinfo.value)
    assert "ssg_i18n.text_translators" in str(excinfo.value)


def test_create_wraps_translator_factory_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — load() succeeds, the returned factory raises on call.
    def fake_entry_points(
        group: str,
    ) -> tuple[ExplodingFactoryEntryPoint, ...]:
        return (ExplodingFactoryEntryPoint(),)

    monkeypatch.setattr(plugin, "entry_points", fake_entry_points)

    # Act / Assert
    with pytest.raises(RuntimeError) as excinfo:
        EntryPointTextTranslatorFactory().create()
    assert "'exploding-translator'" in str(excinfo.value)
    assert "ssg_i18n.text_translators" in str(excinfo.value)


def test_create_rejects_non_conforming_translator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    def fake_entry_points(group: str) -> tuple[NonConformingEntryPoint, ...]:
        return (NonConformingEntryPoint(),)

    monkeypatch.setattr(plugin, "entry_points", fake_entry_points)

    # Act / Assert
    with pytest.raises(TypeError) as excinfo:
        EntryPointTextTranslatorFactory().create()
    assert "'non-conforming-translator'" in str(excinfo.value)
    assert "ssg_i18n.text_translators" in str(excinfo.value)
    assert "TextTranslator" in str(excinfo.value)
