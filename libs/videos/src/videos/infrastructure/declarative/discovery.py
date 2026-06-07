from __future__ import annotations

from pathlib import Path


def find_concept_yaml_files(directory: str | Path) -> list[Path]:
    root = Path(directory)
    if not root.is_dir():
        return []
    files = list(root.glob("*.yaml")) + list(root.glob("*.yml"))
    return sorted(set(files), key=lambda p: p.name)
