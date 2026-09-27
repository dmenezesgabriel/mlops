"""Shared opaque-offset pagination tests (``athena_local.pagination``).

Every list op issues ``str(index)`` tokens: an undecodable token answers
``InvalidRequestException``, a token at or past the end answers an empty
page, and ``MaxResults`` bounds the page only when positive — some list
handlers pass the request's unbounded value straight through.
"""

from __future__ import annotations

import pytest
from athena_local.errors import InvalidRequestException
from athena_local.pagination import offset_page


def test_no_token_or_max_returns_whole_list() -> None:
    page, token = offset_page(["a", "b"], None, None)

    assert page == ["a", "b"]
    assert token is None


def test_pages_walk_the_whole_list_with_opaque_offsets() -> None:
    items = ["a", "b", "c"]

    first, token = offset_page(items, 1, None)
    second, next_token = offset_page(items, 1, token)
    third, last_token = offset_page(items, 1, next_token)

    assert first == ["a"]
    assert second == ["b"]
    assert third == ["c"]
    assert token == "1"
    assert next_token == "2"
    assert last_token is None


def test_max_results_landing_on_the_end_returns_no_token() -> None:
    page, token = offset_page(["a", "b"], 2, None)

    assert page == ["a", "b"]
    assert token is None


def test_undecodable_token_raises_invalid_request() -> None:
    with pytest.raises(InvalidRequestException, match="Invalid NextToken"):
        offset_page(["a"], None, "bogus")


def test_token_at_or_past_the_end_returns_empty_page() -> None:
    assert offset_page(["a"], None, "1") == ([], None)
    assert offset_page(["a"], None, "99") == ([], None)


def test_empty_list_answers_empty_page_without_token() -> None:
    assert offset_page([], 5, None) == ([], None)


def test_non_positive_max_results_means_no_limit() -> None:
    items = ["a", "b", "c"]

    assert offset_page(items, 0, None) == (items, None)
    assert offset_page(items, -2, None) == (items, None)


def test_pages_generic_over_item_type() -> None:
    items = [{"k": 1}, {"k": 2}]

    page, token = offset_page(items, 1, None)

    assert page == [{"k": 1}]
    assert token == "1"
