from collections.abc import Mapping
from pathlib import Path

import yaml

from ssg.application.ports import SiteRepository
from ssg.domain.site import ContentCollection, Page, Site


class SiteConfigRepository(SiteRepository):
    def load(self, config_path: Path) -> Site:
        manifest = self._load_yaml_mapping(config_path)
        site_config = self._required_mapping(manifest, "site", config_path)
        collections = self._required_list(manifest, "collections", config_path)
        return Site(
            title=self._required_string(site_config, "title", config_path),
            description=str(site_config.get("description", "")),
            extensions=self._read_extensions(manifest, config_path),
            collections=tuple(
                self._read_collection(collection, config_path)
                for collection in collections
            ),
        )

    def _load_yaml_mapping(self, config_path: Path) -> dict[object, object]:
        parsed_yaml = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if isinstance(parsed_yaml, dict):
            return parsed_yaml

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

        source_root = self._path_from_config(
            config_path,
            self._required_string(collection, "source_root", config_path),
        )
        name = self._required_string(collection, "name", config_path)
        return ContentCollection(
            name=name,
            title=self._required_string(collection, "title", config_path),
            source_root=source_root,
            output_slug=str(
                collection.get("output_slug", name.replace("_", "-"))
            ),
            pages=tuple(
                self._read_page(page, source_root, config_path)
                for page in self._required_list(
                    collection, "pages", config_path
                )
            ),
            videos=self._read_videos(collection, config_path),
        )

    def _read_page(
        self, page: object, source_root: Path, config_path: Path
    ) -> Page:
        if not isinstance(page, dict):
            raise ValueError(
                f"Invalid page in {config_path}: expected mapping"
            )

        return Page(
            slug=self._required_string(page, "slug", config_path),
            title=self._required_string(page, "title", config_path),
            source_path=source_root
            / self._required_string(page, "source", config_path),
        )

    def _read_videos(
        self, collection: Mapping[object, object], config_path: Path
    ) -> dict[str, Path]:
        assets = collection.get("assets", {})
        if not isinstance(assets, dict):
            raise ValueError(
                f"Invalid assets in {config_path}: expected mapping"
            )

        videos = assets.get("videos", {})
        if not isinstance(videos, dict):
            raise ValueError(
                f"Invalid asset videos in {config_path}: expected mapping"
            )

        return {
            str(name): self._path_from_config(config_path, str(video_path))
            for name, video_path in videos.items()
        }

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

        return {
            str(extension_name): self._read_extension_settings(
                str(extension_name), extension_settings, config_path
            )
            for extension_name, extension_settings in extensions.items()
        }

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

        return {
            str(setting_name): self._extension_setting_string(
                extension_name, str(setting_name), setting_value, config_path
            )
            for setting_name, setting_value in extension_settings.items()
        }

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
        path = Path(configured_path)
        if path.is_absolute():
            return path

        return (config_path.parent / path).resolve()

    def _required_mapping(
        self,
        config: Mapping[object, object],
        key: str,
        config_path: Path,
    ) -> Mapping[object, object]:
        value = config.get(key)
        if isinstance(value, dict):
            return value

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
            return value

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
