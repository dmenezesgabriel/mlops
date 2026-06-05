from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConceptId:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError(f"ConceptId must not be empty, got {self.value!r}")

    def __repr__(self) -> str:
        return f"ConceptId({self.value!r})"


@dataclass(frozen=True)
class ConceptTitle:
    short: str
    subtitle: str

    def __post_init__(self) -> None:
        if not self.short.strip():
            raise ValueError(f"ConceptTitle.short must not be empty, got {self.short!r}")


@dataclass(frozen=True)
class ConceptMetadata:
    title: ConceptTitle
    description: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class Concept:
    id: ConceptId
    metadata: ConceptMetadata
