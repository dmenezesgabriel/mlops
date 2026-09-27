"""Typed member validators for Athena JSON-1.1 request objects.

One family serves both layers that parse ``service-2.json`` member shapes:
the top-level request payload, which the dispatch layer may hand in as
``None``, and nested member objects, which are always ``dict`` — every
validator therefore accepts ``dict | None`` and treats ``None`` as "absent"
(``required_*`` raises, ``optional_*``/``member`` return ``None``).

Messages name the offending member and echo the received value so a wire
client can tell which field failed. Integer validators reject booleans:
JSON ``true`` decodes to Python ``True``, an int subtype, but botocore's
client-side model validation rejects it — the emulator answers the same
shaped error instead of silently reading the member as ``1``.
"""

from __future__ import annotations

from athena_local.errors import InvalidRequestException


def member(payload: dict[str, object] | None, name: str) -> object | None:
    """Return ``payload[name]``, or ``None`` when payload/member is absent."""
    if payload is None:
        return None
    return payload.get(name)


def as_object(raw: object, name: str) -> dict[str, object] | None:
    """Coerce a member to a JSON object; ``None``/absent parses to ``None``."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise InvalidRequestException(
            f"{name} must be a JSON object, got {raw!r}"
        )
    return raw


def required_string(payload: dict[str, object] | None, name: str) -> str:
    raw = member(payload, name)
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidRequestException(
            f"{name} is required and must be a non-empty string, got {raw!r}"
        )
    return raw


def optional_string(
    payload: dict[str, object] | None, name: str
) -> str | None:
    raw = member(payload, name)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise InvalidRequestException(f"{name} must be a string, got {raw!r}")
    return raw


def required_bool(payload: dict[str, object] | None, name: str) -> bool:
    raw = member(payload, name)
    if not isinstance(raw, bool):
        raise InvalidRequestException(
            f"{name} is required and must be a boolean, got {raw!r}"
        )
    return raw


def optional_bool(payload: dict[str, object] | None, name: str) -> bool | None:
    raw = member(payload, name)
    if raw is None:
        return None
    if not isinstance(raw, bool):
        raise InvalidRequestException(f"{name} must be a boolean, got {raw!r}")
    return raw


def required_int(payload: dict[str, object] | None, name: str) -> int:
    raw = member(payload, name)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise InvalidRequestException(
            f"{name} must be an integer, got {raw!r}"
        )
    return raw


def optional_int(payload: dict[str, object] | None, name: str) -> int | None:
    raw = member(payload, name)
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise InvalidRequestException(
            f"{name} must be an integer, got {raw!r}"
        )
    return raw


def required_string_list(
    payload: dict[str, object] | None, name: str
) -> list[str]:
    raw = member(payload, name)
    if not isinstance(raw, list):
        raise InvalidRequestException(f"{name} must be a list, got {raw!r}")
    if not raw:
        raise InvalidRequestException(f"{name} must not be empty")
    for item in raw:
        if not isinstance(item, str):
            raise InvalidRequestException(
                f"{name} must contain only strings, got {item!r}"
            )
    return [item for item in raw if isinstance(item, str)]


def optional_string_list(
    payload: dict[str, object] | None, name: str
) -> list[str] | None:
    raw = member(payload, name)
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise InvalidRequestException(f"{name} must be a list, got {raw!r}")
    for item in raw:
        if not isinstance(item, str):
            raise InvalidRequestException(
                f"{name} must contain only strings, got {item!r}"
            )
    return [item for item in raw if isinstance(item, str)]


def optional_string_map(
    payload: dict[str, object] | None, name: str
) -> dict[str, str] | None:
    raw = member(payload, name)
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise InvalidRequestException(
            f"{name} must be an object of string pairs, got {raw!r}"
        )
    pairs: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise InvalidRequestException(
                f"{name} entries must map string to string, "
                f"got {key!r}: {value!r}"
            )
        pairs[key] = value
    return pairs


def optional_max_results(
    payload: dict[str, object] | None, name: str, maximum: int
) -> int | None:
    raw = member(payload, name)
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise InvalidRequestException(
            f"{name} must be an integer, got {raw!r}"
        )
    if raw < 1 or raw > maximum:
        raise InvalidRequestException(
            f"{name} must be between 1 and {maximum}, got {raw}"
        )
    return raw
