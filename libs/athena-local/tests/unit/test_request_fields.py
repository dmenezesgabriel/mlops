"""Request-field validator tests for the shared member parsers.

Every validator accepts ``dict | None`` so the same family serves the
possibly-absent top-level request object and nested member objects. Error
messages name the offending member so a wire client sees which field failed.
"""

from __future__ import annotations

import pytest
from athena_local.errors import InvalidRequestException
from athena_local.request_fields import (
    as_object,
    member,
    optional_bool,
    optional_int,
    optional_max_results,
    optional_string,
    optional_string_list,
    optional_string_map,
    required_bool,
    required_int,
    required_string,
    required_string_list,
)


def test_member_returns_none_for_absent_payload_or_member() -> None:
    assert member(None, "Name") is None
    assert member({}, "Name") is None
    assert member({"Name": "wg"}, "Name") == "wg"


def test_required_string_rejects_absent_empty_and_non_string() -> None:
    with pytest.raises(InvalidRequestException, match="req_str"):
        required_string(None, "req_str")
    with pytest.raises(InvalidRequestException, match="req_str"):
        required_string({}, "req_str")
    with pytest.raises(InvalidRequestException, match="req_str"):
        required_string({"req_str": "  "}, "req_str")
    with pytest.raises(InvalidRequestException, match="req_str"):
        required_string({"req_str": 7}, "req_str")
    assert required_string({"req_str": "v"}, "req_str") == "v"


def test_optional_string_returns_none_unless_present() -> None:
    assert optional_string(None, "opt_str") is None
    assert optional_string({}, "opt_str") is None
    with pytest.raises(InvalidRequestException, match="opt_str"):
        optional_string({"opt_str": 123}, "opt_str")
    assert optional_string({"opt_str": "v"}, "opt_str") == "v"


def test_int_validators_reject_bool_and_non_int() -> None:
    # JSON true decodes to Python True — an int subtype that must not read
    # as 1, matching botocore's client-side integer rejection.
    with pytest.raises(InvalidRequestException, match="int_val"):
        required_int({"int_val": "not_an_int"}, "int_val")
    with pytest.raises(InvalidRequestException, match="int_val"):
        required_int({"int_val": True}, "int_val")
    with pytest.raises(InvalidRequestException, match="int_val"):
        required_int(None, "int_val")
    assert required_int({"int_val": 3}, "int_val") == 3

    assert optional_int(None, "int_val") is None
    assert optional_int({}, "int_val") is None
    with pytest.raises(InvalidRequestException, match="int_val"):
        optional_int({"int_val": True}, "int_val")
    assert optional_int({"int_val": 3}, "int_val") == 3


def test_bool_validators_enforce_wire_booleans() -> None:
    with pytest.raises(InvalidRequestException, match="req_bool"):
        required_bool({"req_bool": "true"}, "req_bool")
    with pytest.raises(InvalidRequestException, match="req_bool"):
        required_bool(None, "req_bool")
    assert required_bool({"req_bool": True}, "req_bool") is True

    assert optional_bool(None, "opt_bool") is None
    assert optional_bool({}, "opt_bool") is None
    with pytest.raises(InvalidRequestException, match="opt_bool"):
        optional_bool({"opt_bool": 1}, "opt_bool")
    assert optional_bool({"opt_bool": False}, "opt_bool") is False


def test_required_string_list_needs_a_nonempty_all_string_list() -> None:
    with pytest.raises(InvalidRequestException, match="ids"):
        required_string_list(None, "ids")
    with pytest.raises(InvalidRequestException, match="ids"):
        required_string_list({"ids": "x"}, "ids")
    with pytest.raises(InvalidRequestException, match="ids"):
        required_string_list({"ids": []}, "ids")
    with pytest.raises(InvalidRequestException, match="ids"):
        required_string_list({"ids": ["a", 2]}, "ids")
    assert required_string_list({"ids": ["a", "b"]}, "ids") == ["a", "b"]


def test_optional_string_list_returns_none_unless_present() -> None:
    assert optional_string_list(None, "params") is None
    assert optional_string_list({}, "params") is None
    with pytest.raises(InvalidRequestException, match="params"):
        optional_string_list({"params": ["a", 2]}, "params")
    assert optional_string_list({"params": []}, "params") == []


def test_optional_string_map_validates_string_pairs() -> None:
    assert optional_string_map(None, "Parameters") is None
    assert optional_string_map({}, "Parameters") is None
    with pytest.raises(InvalidRequestException, match="Parameters"):
        optional_string_map({"Parameters": ["k"]}, "Parameters")
    with pytest.raises(InvalidRequestException, match="Parameters"):
        optional_string_map({"Parameters": {"k": 1}}, "Parameters")
    assert optional_string_map({"Parameters": {"k": "v"}}, "Parameters") == {
        "k": "v"
    }


def test_optional_max_results_bounds_to_the_member_maximum() -> None:
    assert optional_max_results(None, "MaxResults", 50) is None
    assert optional_max_results({}, "MaxResults", 50) is None
    with pytest.raises(InvalidRequestException, match="MaxResults"):
        optional_max_results({"MaxResults": "50"}, "MaxResults", 50)
    with pytest.raises(InvalidRequestException, match="MaxResults"):
        optional_max_results({"MaxResults": True}, "MaxResults", 50)
    with pytest.raises(InvalidRequestException, match="MaxResults"):
        optional_max_results({"MaxResults": 0}, "MaxResults", 50)
    with pytest.raises(InvalidRequestException, match="MaxResults"):
        optional_max_results({"MaxResults": 51}, "MaxResults", 50)
    assert optional_max_results({"MaxResults": 50}, "MaxResults", 50) == 50


def test_as_object_returns_none_or_typed_dict() -> None:
    assert as_object(None, "Configuration") is None
    with pytest.raises(InvalidRequestException, match="Configuration"):
        as_object("not_a_dict", "Configuration")
    assert as_object({"k": 1}, "Configuration") == {"k": 1}
