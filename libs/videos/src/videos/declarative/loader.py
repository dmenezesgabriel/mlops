from __future__ import annotations

from typing import Any

import yaml

from videos.declarative.extension import DeclarativeConceptExtension


def yaml_to_concept_extension(yaml_string: str) -> DeclarativeConceptExtension:
    data: dict[str, Any] = yaml.safe_load(yaml_string)
    return DeclarativeConceptExtension(data)


def load_concept_from_yaml_file(path: str) -> DeclarativeConceptExtension:
    with open(path) as f:
        return yaml_to_concept_extension(f.read())
