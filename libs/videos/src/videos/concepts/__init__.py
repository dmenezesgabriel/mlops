from __future__ import annotations

from pathlib import Path

from videos.concepts.registry import ConceptRegistry
from videos.declarative.discovery import find_concept_yaml_files
from videos.declarative.loader import load_concept_from_yaml_file


def register_all(definitions_dir: str | Path | None = None) -> None:
    """
    Discover and register all concept definitions from the specified directory.
    If no directory is provided, no concepts are registered.
    """
    if definitions_dir is None:
        return

    root = Path(definitions_dir)
    for yaml_path in find_concept_yaml_files(root):
        ext = load_concept_from_yaml_file(str(yaml_path))
        ConceptRegistry.register(ext)
