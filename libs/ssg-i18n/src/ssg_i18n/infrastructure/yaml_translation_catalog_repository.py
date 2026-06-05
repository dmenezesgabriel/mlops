from pathlib import Path

import yaml

from ssg_i18n.domain.translation_catalog import TranslationCatalog


class YamlTranslationCatalogRepository:
    def load(self, catalog_path: Path) -> TranslationCatalog:
        manifest = self._load_manifest(catalog_path)
        return TranslationCatalog(
            translations=self._read_string_mapping(manifest, "translations", catalog_path),
            glossary_terms=self._read_string_mapping(manifest, "glossary", catalog_path),
        )

    def _load_manifest(self, catalog_path: Path) -> dict[object, object]:
        parsed_yaml = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
        if isinstance(parsed_yaml, dict):
            return parsed_yaml

        raise ValueError(
            f"Invalid i18n catalog {catalog_path}: expected YAML mapping, "
            f"got {type(parsed_yaml).__name__}",
        )

    def _read_string_mapping(
        self, manifest: dict[object, object], key: str, catalog_path: Path
    ) -> dict[str, str]:
        value = manifest.get(key, {})
        if not isinstance(value, dict):
            raise ValueError(f"Invalid i18n catalog {catalog_path}: expected {key} mapping")

        return {
            str(source_text): str(translated_text) for source_text, translated_text in value.items()
        }
