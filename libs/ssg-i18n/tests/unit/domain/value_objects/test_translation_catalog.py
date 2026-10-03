from typing import cast

import pytest
from ssg_i18n.domain.value_objects.translation_catalog import (
    EMPTY_TRANSLATION_CATALOG,
    TranslationCatalog,
)


class TestTranslationCatalog:
    def test_translation_for_returns_translation(self) -> None:
        catalog = TranslationCatalog(
            translations={"Hello": "Olá"},
            glossary_terms={},
        )
        assert catalog.translation_for("Hello") == "Olá"

    def test_translation_for_returns_none_when_missing(self) -> None:
        catalog = TranslationCatalog(translations={}, glossary_terms={})
        assert catalog.translation_for("unknown") is None

    def test_empty_catalog_constant(self) -> None:
        assert EMPTY_TRANSLATION_CATALOG.translation_for("any") is None
        assert EMPTY_TRANSLATION_CATALOG.glossary_terms == {}

    def test_empty_catalog_is_immutable(self) -> None:
        # cast past the Mapping contract to reach the runtime guard —
        # the shared singleton must refuse item assignment.
        translations = cast(
            dict[str, str], EMPTY_TRANSLATION_CATALOG.translations
        )
        with pytest.raises(TypeError):
            translations["X"] = "y"

        glossary_terms = cast(
            dict[str, str], EMPTY_TRANSLATION_CATALOG.glossary_terms
        )
        with pytest.raises(TypeError):
            glossary_terms["X"] = "y"
