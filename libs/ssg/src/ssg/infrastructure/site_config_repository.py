import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import cast

import yaml

from ssg.application.ports import SiteRepository
from ssg.domain import ContentCollection, Page, Site

# Slugs land verbatim in output paths (`output_path / slug.html`) and hrefs,
# so path characters and case are both rejected — on case-insensitive
# filesystems `Foo`/`foo` would pass a caseful uniqueness check yet collide
# on the written file.
_SLUG_PATTERN = re.compile(r"[a-z0-9_-]+")


class SiteConfigRepository(SiteRepository):
    def load(self, config_path: Path) -> Site:
        manifest = self._load_yaml_mapping(config_path)
        site_config = self._required_mapping(manifest, "site", config_path)
        collection_entries = self._required_list(
            manifest, "collections", config_path
        )
        collections = tuple(
            self._read_collection(collection, config_path)
            for collection in collection_entries
        )
        self._reject_duplicate_collections(collections, config_path)
        return Site(
            title=self._required_string(site_config, "title", config_path),
            description=self._optional_string(
                site_config, "description", "", config_path
            ),
            extensions=self._read_extensions(manifest, config_path),
            collections=collections,
        )

    def _reject_duplicate_collections(
        self,
        collections: tuple[ContentCollection, ...],
        config_path: Path,
    ) -> None:
        fields: dict[str, Iterable[str]] = {
            "name": (collection.name for collection in collections),
            "output_slug": (
                collection.output_slug for collection in collections
            ),
        }
        for field, values in fields.items():
            duplicate = self._first_duplicate(values)
            if duplicate is None:
                continue
            raise ValueError(
                f"Invalid site config {config_path}: "
                f"duplicate collection {field} {duplicate!r}"
            )

    def _load_yaml_mapping(self, config_path: Path) -> dict[object, object]:
        parsed_yaml = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if isinstance(parsed_yaml, dict):
            return cast(dict[object, object], parsed_yaml)

        raise ValueError(
            f"Invalid site config {config_path}: expected YAML mapping, "
            f"got {type(parsed_yaml).__name__}",
        )

    def _read_collection(
        self, collection: object, config_path: Path
    ) -> ContentCollection:
        if not isinstance(collection, dict):
            raise ValueError(
                f"Invalid collection in {config_path}: expected mapping"
            )
        collection_map = cast(dict[object, object], collection)

        source_root = self._path_from_config(
            config_path,
            self._required_string(collection_map, "source_root", config_path),
        )
        name = self._required_string(collection_map, "name", config_path)
        page_entries = self._required_list(
            collection_map, "pages", config_path
        )
        if not page_entries:
            raise ValueError(
                f"Empty collection {name} in {config_path}: "
                "expected at least one page"
            )

        output_slug = self._optional_string(
            collection_map, "output_slug", name.replace("_", "-"), config_path
        )
        self._require_slug(output_slug, "collection output_slug", config_path)
        pages = tuple(
            self._read_page(page, source_root, config_path)
            for page in page_entries
        )
        self._reject_duplicate_page_slugs(pages, name, config_path)

        return ContentCollection(
            name=name,
            title=self._required_string(collection_map, "title", config_path),
            source_root=source_root,
            output_slug=output_slug,
            pages=pages,
            videos=self._read_asset_map(collection_map, "videos", config_path),
            images=self._read_asset_map(collection_map, "images", config_path),
        )

    def _reject_duplicate_page_slugs(
        self, pages: tuple[Page, ...], name: str, config_path: Path
    ) -> None:
        duplicate_slug = self._first_duplicate(page.slug for page in pages)
        if duplicate_slug is None:
            return

        raise ValueError(
            f"Invalid collection {name} in {config_path}: "
            f"duplicate page slug {duplicate_slug!r}"
        )

    def _read_page(
        self, page: object, source_root: Path, config_path: Path
    ) -> Page:
        if not isinstance(page, dict):
            raise ValueError(
                f"Invalid page in {config_path}: expected mapping"
            )
        page_map = cast(dict[object, object], page)

        slug = self._required_string(page_map, "slug", config_path)
        self._require_slug(slug, "page slug", config_path)
        return Page(
            slug=slug,
            title=self._required_string(page_map, "title", config_path),
            source_path=self._page_source_path(
                page_map, source_root, config_path
            ),
        )

    def _page_source_path(
        self,
        page_map: Mapping[object, object],
        source_root: Path,
        config_path: Path,
    ) -> Path:
        source = self._required_string(page_map, "source", config_path)
        resolved_source_root = source_root.resolve()
        source_path = (resolved_source_root / source).resolve()
        if source_path.is_relative_to(resolved_source_root):
            return source_path

        raise ValueError(
            f"Invalid page source {source!r} in {config_path}: "
            f"expected path under {resolved_source_root}"
        )

    def _require_slug(self, slug: str, field: str, config_path: Path) -> None:
        if _SLUG_PATTERN.fullmatch(slug):
            return

        raise ValueError(
            f"Invalid {field} {slug!r} in {config_path}: "
            f"expected slug matching {_SLUG_PATTERN.pattern}"
        )

    def _first_duplicate(self, values: Iterable[str]) -> str | None:
        seen: set[str] = set()
        for value in values:
            if value in seen:
                return value
            seen.add(value)

        return None

    def _read_asset_map(
        self, collection: Mapping[object, object], key: str, config_path: Path
    ) -> dict[str, Path]:
        assets = collection.get("assets", {})
        if not isinstance(assets, dict):
            raise ValueError(
                f"Invalid assets in {config_path}: expected mapping"
            )
        asset_entries = cast(dict[object, object], assets).get(key, {})
        if not isinstance(asset_entries, dict):
            raise ValueError(
                f"Invalid asset {key} in {config_path}: expected mapping"
            )

        asset_paths: dict[str, Path] = {}
        for name, asset_path in cast(
            dict[object, object], asset_entries
        ).items():
            asset_name = self._require_string_key(name, config_path)
            asset_paths[asset_name] = self._path_from_config(
                config_path,
                self._asset_path_string(
                    key, asset_name, asset_path, config_path
                ),
            )

        return asset_paths

    def _asset_path_string(
        self, key: str, name: str, value: object, config_path: Path
    ) -> str:
        if isinstance(value, str):
            return value

        raise ValueError(
            f"Invalid asset {key} in {config_path}: "
            f"expected {name} path string, got {value!r}"
        )

    def _read_extensions(
        self,
        manifest: Mapping[object, object],
        config_path: Path,
    ) -> dict[str, dict[str, str]]:
        extensions = manifest.get("extensions", {})
        if not isinstance(extensions, dict):
            raise ValueError(
                f"Invalid extensions in {config_path}: expected mapping"
            )
        settings_by_name: dict[str, dict[str, str]] = {}
        for extension_name, extension_settings in cast(
            dict[object, object], extensions
        ).items():
            name = self._require_string_key(extension_name, config_path)
            settings_by_name[name] = self._read_extension_settings(
                name, extension_settings, config_path
            )

        return settings_by_name

    def _read_extension_settings(
        self,
        extension_name: str,
        extension_settings: object,
        config_path: Path,
    ) -> dict[str, str]:
        if not isinstance(extension_settings, dict):
            raise ValueError(
                f"Invalid extension {extension_name} in {config_path}: expected mapping"
            )
        settings: dict[str, str] = {}
        for setting_name, setting_value in cast(
            dict[object, object], extension_settings
        ).items():
            name = self._require_string_key(setting_name, config_path)
            settings[name] = self._extension_setting_string(
                extension_name, name, setting_value, config_path
            )

        return settings

    def _extension_setting_string(
        self,
        extension_name: str,
        setting_name: str,
        setting_value: object,
        config_path: Path,
    ) -> str:
        if isinstance(setting_value, str):
            return setting_value

        raise ValueError(
            f"Invalid extensions in {config_path}: expected extension setting "
            f"{extension_name}.{setting_name} string"
        )

    def _path_from_config(
        self, config_path: Path, configured_path: str
    ) -> Path:
        # An absolute right operand replaces the left side of the join, so one
        # resolved join covers both configured-path shapes.
        return (config_path.parent / configured_path).resolve()

    def _required_mapping(
        self,
        config: Mapping[object, object],
        key: str,
        config_path: Path,
    ) -> Mapping[object, object]:
        value = config.get(key)
        if isinstance(value, dict):
            return cast(dict[object, object], value)

        raise ValueError(
            f"Invalid site config {config_path}: expected {key} mapping"
        )

    def _required_list(
        self,
        config: Mapping[object, object],
        key: str,
        config_path: Path,
    ) -> list[object]:
        value = config.get(key)
        if isinstance(value, list):
            return cast(list[object], value)

        raise ValueError(
            f"Invalid site config {config_path}: expected {key} list"
        )

    def _required_string(
        self,
        config: Mapping[object, object],
        key: str,
        config_path: Path,
    ) -> str:
        value = config.get(key)
        if isinstance(value, str):
            return value

        raise ValueError(
            f"Invalid site config {config_path}: expected {key} string"
        )

    def _optional_string(
        self,
        config: Mapping[object, object],
        key: str,
        default: str,
        config_path: Path,
    ) -> str:
        value = config.get(key, default)
        if isinstance(value, str):
            return value

        raise ValueError(
            f"Invalid site config {config_path}: expected {key} string"
        )

    def _require_string_key(self, key: object, config_path: Path) -> str:
        if isinstance(key, str):
            return key

        raise ValueError(
            f"Invalid site config {config_path}: expected string key, "
            f"got {key!r} ({type(key).__name__})"
        )
