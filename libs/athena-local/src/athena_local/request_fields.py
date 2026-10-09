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

The ``*_PATTERN``/``*_MAX_LENGTH``/``*_MINIMUM`` constants mirror constraint
metadata on canonical ``service-2.json`` shapes. botocore validates
``min``/``max`` client-side but never ``pattern``, so pattern violations
reach the wire — the emulator enforces the declared bounds either way.
"""

from __future__ import annotations

import re
from typing import cast

from athena_local.errors import InvalidRequestException

# service-2.json shape constraints (verbatim patterns; matched in full).
WORKGROUP_NAME_PATTERN = r"[a-zA-Z0-9._-]{1,128}"
WORKGROUP_DESCRIPTION_MAX_LENGTH = 1024
BYTES_SCANNED_CUTOFF_MINIMUM = 10_000_000
NAME_STRING_MIN_LENGTH = 1
NAME_STRING_MAX_LENGTH = 128
ROLE_ARN_PATTERN = r"arn:aws[a-z\-]*:iam::\d{12}:role/?[a-zA-Z_0-9+=,.@\-_/]+"
ROLE_ARN_MAX_LENGTH = 2048
AWS_ACCOUNT_ID_PATTERN = r"[0-9]+"
AWS_ACCOUNT_ID_LENGTH = 12
KMS_KEY_MIN_LENGTH = 1
KMS_KEY_PATTERN = (
    r"arn:aws[a-z\-]*:kms:([a-z0-9\-]+):\d{12}:key/?[a-zA-Z_0-9+=,.@\-_/]+"
    r"|arn:aws[a-z\-]*:kms:([a-z0-9\-]+):\d{12}:alias/?[a-zA-Z_0-9+=,.@\-_/]+"
    r"|alias/[a-zA-Z0-9/_-]+"
    r"|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}"
)
KMS_KEY_MAX_LENGTH = 2048
TAG_KEY_MIN_LENGTH = 1
TAG_KEY_MAX_LENGTH = 128
TAG_VALUE_MAX_LENGTH = 256
ENCRYPTION_OPTIONS = ("SSE_S3", "SSE_KMS", "CSE_KMS")
S3_ACL_OPTIONS = ("BUCKET_OWNER_FULL_CONTROL",)


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
    return cast(dict[str, object], raw)


def check_string_constraints(
    value: str,
    name: str,
    *,
    min_length: int | None = None,
    max_length: int | None = None,
    pattern: str | None = None,
    allowed_values: tuple[str, ...] | None = None,
) -> None:
    if min_length is not None and len(value) < min_length:
        raise InvalidRequestException(
            f"{name} must be at least {min_length} characters, "
            f"got {len(value)}"
        )
    if max_length is not None and len(value) > max_length:
        raise InvalidRequestException(
            f"{name} must be at most {max_length} characters, got {len(value)}"
        )
    if pattern is not None and re.fullmatch(pattern, value) is None:
        raise InvalidRequestException(
            f"{name} must match pattern {pattern!r}, got {value!r}"
        )
    if allowed_values is not None and value not in allowed_values:
        raise InvalidRequestException(
            f"{name} must be one of {list(allowed_values)}, got {value!r}"
        )


def required_string(
    payload: dict[str, object] | None,
    name: str,
    *,
    min_length: int | None = None,
    max_length: int | None = None,
    pattern: str | None = None,
    allowed_values: tuple[str, ...] | None = None,
) -> str:
    raw = member(payload, name)
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidRequestException(
            f"{name} is required and must be a non-empty string, got {raw!r}"
        )
    check_string_constraints(
        raw,
        name,
        min_length=min_length,
        max_length=max_length,
        pattern=pattern,
        allowed_values=allowed_values,
    )
    return raw


def optional_string(
    payload: dict[str, object] | None,
    name: str,
    *,
    min_length: int | None = None,
    max_length: int | None = None,
    pattern: str | None = None,
    allowed_values: tuple[str, ...] | None = None,
) -> str | None:
    raw = member(payload, name)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise InvalidRequestException(f"{name} must be a string, got {raw!r}")
    check_string_constraints(
        raw,
        name,
        min_length=min_length,
        max_length=max_length,
        pattern=pattern,
        allowed_values=allowed_values,
    )
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


def optional_int(
    payload: dict[str, object] | None,
    name: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    raw = member(payload, name)
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise InvalidRequestException(
            f"{name} must be an integer, got {raw!r}"
        )
    if minimum is not None and raw < minimum:
        raise InvalidRequestException(
            f"{name} must be at least {minimum}, got {raw}"
        )
    if maximum is not None and raw > maximum:
        raise InvalidRequestException(
            f"{name} must be at most {maximum}, got {raw}"
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
    items: list[object] = raw
    for item in items:
        if not isinstance(item, str):
            raise InvalidRequestException(
                f"{name} must contain only strings, got {item!r}"
            )
    return [item for item in items if isinstance(item, str)]


def optional_string_list(
    payload: dict[str, object] | None, name: str
) -> list[str] | None:
    raw = member(payload, name)
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise InvalidRequestException(f"{name} must be a list, got {raw!r}")
    items: list[object] = raw
    for item in items:
        if not isinstance(item, str):
            raise InvalidRequestException(
                f"{name} must contain only strings, got {item!r}"
            )
    return [item for item in items if isinstance(item, str)]


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
    entries: dict[object, object] = raw
    for key, value in entries.items():
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
