"""Shared wire-shape helpers for the boto3 boundaries (ADR-0005/0008).

``GlueProxy`` and ``S3Writer`` are the two designated botocore boundaries and
both re-anchor an untyped boto3 response to the JSON object shape the wire
parser produces: each reads an ``Error.Code`` off a ``ClientError`` and walks
dict entries and string members of a response. Those helpers live here so the
two boundaries cannot drift apart (G-289).
"""

from __future__ import annotations

from typing import cast

# botocore ships no type information (no py.typed marker) and the community
# stubs are deliberately not vendored — this module is part of the designated
# botocore boundary, so the rule is scoped off here rather than weakened
# project-wide.
# pyright: reportMissingTypeStubs=false
from botocore.exceptions import ClientError


def error_code(error: ClientError) -> str:
    """The ``Error.Code`` string of a boto3 failure; ``""`` when absent."""
    # ClientError.response is untyped upstream; re-anchor it to the JSON
    # object shape the wire parser actually produces.
    response: object = getattr(error, "response", None)
    if not isinstance(response, dict):
        return ""
    raw = cast(dict[str, object], response).get("Error")
    if not isinstance(raw, dict):
        return ""
    code = cast(dict[str, object], raw).get("Code")
    return code if isinstance(code, str) else ""


def object_entries(
    response: dict[str, object], key: str
) -> list[dict[str, object]]:
    """The dict entries of a list member, skipping non-dict elements."""
    raw = response.get(key)
    if not isinstance(raw, list):
        return []
    entries: list[object] = raw
    return [
        cast(dict[str, object], item)
        for item in entries
        if isinstance(item, dict)
    ]


def string_member(record: dict[str, object], key: str) -> str | None:
    """A string member of ``record``, or None when absent/not a string."""
    raw = record.get(key)
    return raw if isinstance(raw, str) else None
