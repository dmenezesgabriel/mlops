from pathlib import Path

import yaml


class YamlMappingLoader:
    """Load YAML configuration files that must contain a mapping.

    Example:
        YamlMappingLoader().load(Path("configs/project.yaml"))
    """

    def load(self, config_path: Path) -> dict[str, object]:
        parsed_yaml = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if isinstance(parsed_yaml, dict):
            return {str(key): value for key, value in parsed_yaml.items()}

        raise ValueError(
            f"Invalid YAML in {config_path}: expected YAML mapping, "
            f"got {type(parsed_yaml).__name__}",
        )
