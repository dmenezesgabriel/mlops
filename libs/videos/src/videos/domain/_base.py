from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Self, cast

from pydantic import TypeAdapter

_SLUG_PATTERN = re.compile(r"[a-z0-9_-]+")


def require_slug(value: str, field_name: str) -> str:
    # Ids land verbatim in artifact paths (`f"{id}_{id}.mp4"` joins), so
    # the identifier charset is bounded to characters safe in a filename.
    if not _SLUG_PATTERN.fullmatch(value):
        raise ValueError(
            f"Invalid {field_name} {value!r}: "
            f"expected slug matching {_SLUG_PATTERN.pattern}"
        )
    return value


def freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    # frozen=True blocks reassignment, not interior mutation — wrap a copy
    # so neither the VO nor the caller's dict can mutate post-construction.
    return MappingProxyType(dict(value))


class PydanticModel:
    _adapter: TypeAdapter[Any] | None = None

    @classmethod
    def _get_adapter(cls) -> TypeAdapter[Any]:
        if cls._adapter is None:
            cls._adapter = TypeAdapter(cls)
        return cls._adapter

    def to_dict(self) -> dict[str, Any]:
        return cast(
            dict[str, Any], self._get_adapter().dump_python(self, mode="json")
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cast(Self, cls._get_adapter().validate_python(data))
