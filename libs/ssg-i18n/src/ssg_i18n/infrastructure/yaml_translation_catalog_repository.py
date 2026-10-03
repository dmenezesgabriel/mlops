from pathlib import Path
from typing import cast

import yaml

from ssg_i18n.domain.value_objects.translation_catalog import (
    TranslationCatalog,
)


class YamlTranslationCatalogRepository:
    """Loads a TranslationCatalog from a YAML file.

    Example:
        YamlTranslationCatalogRepository().load(Path("i18n/pt-BR.yaml"))
    """

    def load(self, catalog_path: Path) -> TranslationCatalog:
        manifest = self._load_manifest(catalog_path)
        return TranslationCatalog(
            translations=self._read_string_mapping(
                manifest, "translations", catalog_path
            ),
            glossary_terms=self._read_string_mapping(
                manifest, "glossary", catalog_path
            ),
        )

    def _load_manifest(self, catalog_path: Path) -> dict[object, object]:
        parsed_yaml = cast(
            object, yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
        )
        if isinstance(parsed_yaml, dict):
            return cast(dict[object, object], parsed_yaml)

        raise ValueError(
            f"Invalid i18n catalog {catalog_path}: expected YAML mapping, "
            f"got {type(parsed_yaml).__name__}",
        )

    def _read_string_mapping(
        self, manifest: dict[object, object], key: str, catalog_path: Path
    ) -> dict[str, str]:
        value = manifest.get(key, {})
        if not isinstance(value, dict):
            raise ValueError(
                f"Invalid i18n catalog {catalog_path}: expected {key} mapping"
            )

        mapping = cast(dict[object, object], value)
        return {
            self._require_catalog_key(
                source_text, key, catalog_path
            ): self._require_catalog_value(
                translated_text, source_text, key, catalog_path
            )
            for source_text, translated_text in mapping.items()
        }

    def _require_catalog_key(
        self, key: object, section: str, catalog_path: Path
    ) -> str:
        if isinstance(key, str):
            return key

        raise ValueError(
            f"Invalid i18n catalog {catalog_path}: expected string key "
            f"in {section}, got {key!r} ({type(key).__name__})"
        )

    def _require_catalog_value(
        self, value: object, key: object, section: str, catalog_path: Path
    ) -> str:
        if isinstance(value, str):
            return value

        raise ValueError(
            f"Invalid i18n catalog {catalog_path}: expected string value "
            f"for {key!r} in {section}, got {value!r} "
            f"({type(value).__name__})"
        )
