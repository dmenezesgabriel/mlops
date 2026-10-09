"""Opaque integer-offset pagination shared by the list operations.

Athena's ``Token`` shape (service-2.json) is opaque to consumers: the
emulator issues the next zero-based start index rendered as ``str(offset)``
and rejects anything it cannot decode with ``InvalidRequestException``. One
helper pins that wire contract for every list store and the catalog-metadata
handlers, so the paginators clients walk — botocore's ``list_*`` paginators,
wrangler's cache probe — see identical semantics on every operation.
"""

from __future__ import annotations

import re
from typing import TypeVar

from athena_local.errors import InvalidRequestException

T = TypeVar("T")

# The emulator issues ``str(index)``; only this canonical non-negative decimal
# form is a valid token. ``int()`` also accepts "+2", " 1 ", "01" and negative
# values, which real Athena rejects with a 400 (G-248, G-280).
_TOKEN_PATTERN = re.compile(r"^(0|[1-9][0-9]*)$")


def decode_offset_token(next_token: str) -> int:
    """Decode a canonical opaque-offset token into its zero-based start index.

    The emulator emits ``str(index)``; signed, whitespace-padded, zero-padded
    and negative forms are rejected with ``InvalidRequestException`` naming the
    value, matching the 400 Athena sends.

    >>> decode_offset_token("2")
    2
    """
    if not _TOKEN_PATTERN.fullmatch(next_token):
        raise InvalidRequestException(f"Invalid NextToken: {next_token}")
    return int(next_token)


def offset_page(
    items: list[T],
    max_results: int | None,
    next_token: str | None,
) -> tuple[list[T], str | None]:
    """Slice one page from ``items`` per Athena's opaque-offset tokens.

    ``next_token`` decodes to the zero-based start index; an undecodable
    token raises ``InvalidRequestException`` and a token at or past the end
    answers ``([], None)``. ``max_results`` bounds the page only when
    positive: some list ops pass the request's ``MaxResults`` through
    unbounded, and a ``<= 0`` value there means "no limit".

    >>> offset_page(["a", "b", "c"], 2, None)
    (['a', 'b'], '2')
    >>> offset_page(["a", "b", "c"], 2, "2")
    (['c'], None)
    """
    start_index = _token_offset(next_token)
    # No early return for start_index >= len(items): the slice below clamps to
    # [] and the token stays None, so the deleted guard was behaviorally dead
    # (G-291).
    end_index = len(items)
    if max_results is not None and max_results > 0:
        end_index = min(start_index + max_results, len(items))
    page = items[start_index:end_index]
    return page, str(end_index) if end_index < len(items) else None


def _token_offset(next_token: str | None) -> int:
    if next_token is None:
        return 0
    return decode_offset_token(next_token)
