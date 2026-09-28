from pathlib import Path
from typing import cast

import yaml


class YamlMappingLoader:
    """Load YAML configuration files that must contain a mapping.

    Example:
        YamlMappingLoader().load(Path("configs/project.yaml"))
    """

    def load(self, config_path: Path) -> dict[str, object]:
        parsed_yaml = cast(
            object, yaml.safe_load(config_path.read_text(encoding="utf-8"))
        )
        if not isinstance(parsed_yaml, dict):
            raise ValueError(
                f"Invalid YAML in {config_path}: expected YAML mapping, "
                f"got {type(parsed_yaml).__name__}",
            )

        mapping = cast(dict[object, object], parsed_yaml)
        return {
            self._require_string_key(key, config_path): value
            for key, value in mapping.items()
        }

    def _require_string_key(self, key: object, config_path: Path) -> str:
        if isinstance(key, str):
            return key

        raise ValueError(
            f"Invalid YAML in {config_path}: expected string key, "
            f"got {key!r} ({type(key).__name__})"
        )
