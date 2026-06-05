from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter


class PydanticModel:
    _adapter: TypeAdapter[Any] | None = None

    @classmethod
    def _get_adapter(cls) -> TypeAdapter[Any]:
        if cls._adapter is None:
            cls._adapter = TypeAdapter(cls)
        return cls._adapter

    def to_dict(self) -> dict[str, Any]:
        return self._get_adapter().dump_python(self, mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Any:
        return cls._get_adapter().validate_python(data)
