"""Shared boto3-boundary wire helpers (boundary_helpers.py) tests.

``error_code`` re-anchors the untyped ``ClientError.response`` to the JSON
object shape the wire parser produces, and ``object_entries`` walks a list
member tolerantly; these pins cover the malformed shapes that must answer
``""``/``[]`` rather than raise or invent a code or entry.
"""

from __future__ import annotations

import pytest
from athena_local.boundary_helpers import error_code, object_entries
from botocore.exceptions import ClientError


def _client_error(error_response: dict[str, object]) -> ClientError:
    return ClientError(error_response=error_response, operation_name="Probe")


def test_error_code_reads_the_wire_code() -> None:
    error = _client_error(
        {"Error": {"Code": "NoSuchBucket", "Message": "gone"}}
    )

    assert error_code(error) == "NoSuchBucket"


@pytest.mark.parametrize(
    "error_response",
    [
        {},
        {"Error": {"Code": 42}},
    ],
    ids=["no Error member", "non-str Code"],
)
def test_error_code_malformed_shape_answers_empty(
    error_response: dict[str, object],
) -> None:
    assert error_code(_client_error(error_response)) == ""


def test_error_code_non_object_error_member_answers_empty() -> None:
    # ``Error`` must be a JSON object; a scalar member is a broken response.
    error = _client_error({"Error": {"Code": "X"}})
    error.response = {"Error": "not-an-object"}

    assert error_code(error) == ""


def test_error_code_non_object_response_answers_empty() -> None:
    # botocore stores .response as a plain attribute; a non-dict shape
    # (e.g. a raw transport payload) is not the wire object at all.
    error = _client_error({"Error": {"Code": "X"}})
    error.response = "not-an-object"

    assert error_code(error) == ""


@pytest.mark.parametrize(
    "response",
    [
        {"Contents": "not-a-list"},
        {"Contents": None},
        {},
    ],
    ids=["non-list member", "null member", "absent member"],
)
def test_object_entries_non_list_member_answers_empty(
    response: dict[str, object],
) -> None:
    assert object_entries(response, "Contents") == []


def test_object_entries_skips_non_object_items() -> None:
    response: dict[str, object] = {"Contents": ["junk", {"Key": "a.csv"}, 42]}

    assert object_entries(response, "Contents") == [{"Key": "a.csv"}]
