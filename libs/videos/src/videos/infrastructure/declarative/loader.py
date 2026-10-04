from __future__ import annotations

from videos.infrastructure.declarative.extension import (
    DeclarativeConceptExtension,
)


def yaml_to_concept_extension(yaml_string: str) -> DeclarativeConceptExtension:
    try:
        import yaml
    except ImportError as e:
        raise ImportError(
            "The 'yaml' package is not installed. Please install it using: "
            "pip install videos[concepts]"
        ) from e
    data: object = yaml.safe_load(yaml_string)
    return DeclarativeConceptExtension(data)


def load_concept_from_yaml_file(path: str) -> DeclarativeConceptExtension:
    # Wrap every file-shape failure with the source path — in a definitions
    # dir of dozens, a parser/validation error naming no file is undebuggable.
    try:
        with open(path) as f:
            return yaml_to_concept_extension(f.read())
    except ImportError:
        raise
    except Exception as e:
        raise ValueError(f"{path}: {e}") from e
