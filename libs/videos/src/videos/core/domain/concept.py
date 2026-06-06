from __future__ import annotations

from pydantic import field_validator
from pydantic.dataclasses import dataclass

from videos.core.domain._base import PydanticModel


@dataclass(frozen=True)
class ConceptId(PydanticModel):
    value: str

    @field_validator("value")
    @classmethod
    def _must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(f"ConceptId must not be empty, got {v!r}")
        return v

    def __repr__(self) -> str:
        return f"ConceptId({self.value!r})"


@dataclass(frozen=True)
class ConceptTitle(PydanticModel):
    short: str
    subtitle: str = ""

    @field_validator("short")
    @classmethod
    def _short_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                f"ConceptTitle.short must not be empty, got {v!r}"
            )
        return v


@dataclass(frozen=True)
class ConceptMetadata(PydanticModel):
    title: ConceptTitle
    description: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class Concept(PydanticModel):
    id: ConceptId
    metadata: ConceptMetadata
