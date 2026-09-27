"""Opaque integer-offset pagination shared by the list operations.

Athena's ``Token`` shape (service-2.json) is opaque to consumers: the
emulator issues the next zero-based start index rendered as ``str(offset)``
and rejects anything it cannot decode with ``InvalidRequestException``. One
helper pins that wire contract for every list store and the catalog-metadata
handlers, so the paginators clients walk — botocore's ``list_*`` paginators,
wrangler's cache probe — see identical semantics on every operation.
"""

from __future__ import annotations

from typing import TypeVar

from athena_local.errors import InvalidRequestException

T = TypeVar("T")


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
    if start_index >= len(items):
        return [], None
    end_index = len(items)
    if max_results is not None and max_results > 0:
        end_index = min(start_index + max_results, len(items))
    page = items[start_index:end_index]
    return page, str(end_index) if end_index < len(items) else None


def _token_offset(next_token: str | None) -> int:
    if next_token is None:
        return 0
    try:
        return int(next_token)
    except ValueError:
        raise InvalidRequestException(
            f"Invalid NextToken: {next_token}"
        ) from None
