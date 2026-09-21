"""Trino → Athena error mapping (error_mapping.py) tests.

The submit-time vs execution-time split mirrors real Athena: syntactically
invalid SQL is rejected by StartQueryExecution with a 400 whose message
starts ``Exception parsing query`` (wrangler maps that and ``extraneous
input`` to InvalidCtasApproachQuery at _utils.py:888-898), while analysis
errors surface in the FAILED StateChangeReason instead (wrangler sniffs
``Column name ... specified more than once`` etc. at _read.py:820-832).
Only Trino's SYNTAX_ERROR name maps to the submit-time 400.
"""

from __future__ import annotations

from athena_local.error_mapping import (
    is_syntax_error,
    syntax_error_invalid_request,
)
from athena_local.errors import InvalidRequestException
from athena_local.trino_client import TrinoQueryError


def _user_error(message: str, error_name: str) -> TrinoQueryError:
    return TrinoQueryError(
        message=message,
        error_type="USER_ERROR",
        error_name=error_name,
    )


def test_syntax_error_is_detected_by_error_name() -> None:
    assert is_syntax_error(_user_error("mismatched input", "SYNTAX_ERROR"))


def test_analysis_errors_are_not_start_time_syntax_errors() -> None:
    for name in (
        "DUPLICATE_COLUMN_NAME",
        "MISSING_COLUMN_NAME",
        "COLUMN_NOT_FOUND",
        "SCHEMA_NOT_FOUND",
    ):
        assert not is_syntax_error(
            _user_error("line 1:1: some analysis failure", name)
        )


def test_none_error_is_not_a_syntax_error() -> None:
    assert not is_syntax_error(None)


def test_syntax_error_maps_to_invalid_request_with_wrangler_prefix() -> None:
    error = syntax_error_invalid_request(
        _user_error("line 1:10: extraneous input '1'", "SYNTAX_ERROR")
    )

    assert isinstance(error, InvalidRequestException)
    assert (
        str(error)
        == "Exception parsing query: line 1:10: extraneous input '1'"
    )
