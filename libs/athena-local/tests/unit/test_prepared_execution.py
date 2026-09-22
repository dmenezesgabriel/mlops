"""QE-7 unit tests: EXECUTE parse, bind, and resolve against the store.

Pure-logic coverage of ``prepared_execution``: parsing the ``EXECUTE``
statement shape, splicing values into the stored query, and resolving a
submitted query to the outcome real Athena reports — the bound statement for
success, a FAILED execution (never a 400) for a missing statement or a
``?``-count mismatch. No live Trino: the resolver's only dependency is the
in-memory ``PreparedStatementStore`` (ADR-0003).
"""

from __future__ import annotations

import pytest
from athena_local.errors import InvalidRequestException
from athena_local.prepared_execution import (
    ExecuteParts,
    ParameterCountError,
    bind_parameters,
    parse_execute_statement,
    resolve_execute_statement,
)
from athena_local.state import PreparedStatementStore
from athena_local.statement_classification import StatementClassification


@pytest.fixture()
def prepared_statements() -> PreparedStatementStore:
    return PreparedStatementStore()


def test_parse_bare_name() -> None:
    assert parse_execute_statement("EXECUTE flights_stmt") == ExecuteParts(
        name="flights_stmt", values=None
    )


def test_parse_quoted_name() -> None:
    assert parse_execute_statement('EXECUTE "my stmt"') == ExecuteParts(
        name="my stmt", values=None
    )


def test_parse_lowercase_keyword() -> None:
    assert parse_execute_statement("execute flights_stmt") == ExecuteParts(
        name="flights_stmt", values=None
    )


def test_parse_quoted_name_with_escaped_quote() -> None:
    assert parse_execute_statement('EXECUTE "it""s"') == ExecuteParts(
        name='it"s', values=None
    )


def test_parse_comment_prefix_is_stripped() -> None:
    assert parse_execute_statement(
        "-- run the flight report\nEXECUTE flights_stmt"
    ) == ExecuteParts(name="flights_stmt", values=None)


def test_parse_non_execute_statement_returns_none() -> None:
    assert parse_execute_statement("SELECT 1") is None
    assert parse_execute_statement("SELECT EXECUTE ?") is None


def test_parse_using_values_splits_at_top_level_commas() -> None:
    parts = parse_execute_statement("EXECUTE st USING 'Washington', 2012")
    assert parts == ExecuteParts(name="st", values=["'Washington'", "2012"])


def test_parse_using_cast_expression_travels_whole() -> None:
    parts = parse_execute_statement(
        "EXECUTE st USING CAST('2020-01-01' AS DATE)"
    )
    assert parts == ExecuteParts(
        name="st", values=["CAST('2020-01-01' AS DATE)"]
    )


def test_parse_using_comma_inside_string_literal_does_not_split() -> None:
    parts = parse_execute_statement("EXECUTE st USING 'a,b', 2")
    assert parts == ExecuteParts(name="st", values=["'a,b'", "2"])


def test_parse_missing_name_raises_shaped_error() -> None:
    with pytest.raises(InvalidRequestException, match="statement name"):
        parse_execute_statement("EXECUTE")


def test_parse_trailing_text_raises_shaped_error() -> None:
    with pytest.raises(InvalidRequestException, match="USING"):
        parse_execute_statement("EXECUTE st BOGUS")


def test_parse_empty_using_raises_shaped_error() -> None:
    with pytest.raises(InvalidRequestException, match="at least one value"):
        parse_execute_statement("EXECUTE st USING")


def test_parse_using_trailing_comma_raises_shaped_error() -> None:
    with pytest.raises(InvalidRequestException, match="must not be empty"):
        parse_execute_statement("EXECUTE st USING 1,")


def test_bind_single_parameter_splices_paren_wrapped() -> None:
    assert (
        bind_parameters(
            "SELECT * FROM flights WHERE origin = ?", ["'Washington'"]
        )
        == "SELECT * FROM flights WHERE origin = ('Washington')"
    )


def test_bind_multiple_parameters_in_order() -> None:
    assert (
        bind_parameters(
            "SELECT * FROM flights WHERE origin = ? AND year = ?",
            ["'Washington'", "2012"],
        )
        == "SELECT * FROM flights WHERE origin = ('Washington') AND year = (2012)"
    )


def test_bind_cast_expression_value() -> None:
    assert (
        bind_parameters(
            "SELECT * FROM orders WHERE order_date >= ?",
            ["CAST('2020-01-01' AS DATE)"],
        )
        == "SELECT * FROM orders WHERE order_date >= (CAST('2020-01-01' AS DATE))"
    )


def test_bind_no_placeholders_and_no_values() -> None:
    assert bind_parameters("SELECT 1", []) == "SELECT 1"


def test_bind_ignores_question_marker_inside_string_literal() -> None:
    assert bind_parameters("SELECT '?' AS q, ?", ["1"]) == (
        "SELECT '?' AS q, (1)"
    )


def test_bind_ignores_question_marker_inside_comment() -> None:
    assert bind_parameters("SELECT ? -- ?", ["1"]) == "SELECT (1) -- ?"


def test_bind_count_mismatch_raises_naming_counts() -> None:
    with pytest.raises(ParameterCountError) as error:
        bind_parameters("SELECT ? AND ?", ["1"])
    assert "expected 2 but found 1" in str(error.value)


def test_bind_zero_values_for_placeholder_raises() -> None:
    with pytest.raises(ParameterCountError, match="expected 1 but found 0"):
        bind_parameters("SELECT ?", [])


def test_resolve_non_execute_passes_through(
    prepared_statements: PreparedStatementStore,
) -> None:
    resolution = resolve_execute_statement(
        prepared_statements, "primary", "SELECT 1", None
    )

    assert resolution.statement == "SELECT 1"
    assert resolution.failure_reason is None
    assert resolution.statement_classification == StatementClassification(
        "DML", "SELECT"
    )


def test_resolve_uses_inline_using_values(
    prepared_statements: PreparedStatementStore,
) -> None:
    prepared_statements.create(
        "st", "SELECT 1 WHERE origin = ?", "primary", None
    )

    resolution = resolve_execute_statement(
        prepared_statements,
        "primary",
        "EXECUTE \"st\" USING 'Washington'",
        None,
    )

    assert resolution.statement == "SELECT 1 WHERE origin = ('Washington')"
    assert resolution.failure_reason is None
    assert resolution.statement_classification == StatementClassification(
        "DML", "SELECT"
    )


def test_resolve_falls_back_to_execution_parameters_when_no_using(
    prepared_statements: PreparedStatementStore,
) -> None:
    prepared_statements.create(
        "st", "SELECT 1 WHERE origin = ?", "primary", None
    )

    resolution = resolve_execute_statement(
        prepared_statements, "primary", 'EXECUTE "st"', ["'Washington'"]
    )

    assert resolution.statement == "SELECT 1 WHERE origin = ('Washington')"


def test_resolve_inline_using_wins_over_execution_parameters(
    prepared_statements: PreparedStatementStore,
) -> None:
    prepared_statements.create(
        "st", "SELECT 1 WHERE origin = ?", "primary", None
    )

    resolution = resolve_execute_statement(
        prepared_statements,
        "primary",
        "EXECUTE st USING 'inline'",
        ["'parameter'"],
    )

    assert resolution.statement == "SELECT 1 WHERE origin = ('inline')"


def test_resolve_missing_statement_is_failed_execution(
    prepared_statements: PreparedStatementStore,
) -> None:
    resolution = resolve_execute_statement(
        prepared_statements, "primary", "EXECUTE nope", None
    )

    assert resolution.statement == "EXECUTE nope"
    assert resolution.failure_reason == (
        "PreparedStatement nope was not found in workGroup primary"
    )
    assert resolution.statement_classification.statement_type == "UTILITY"


def test_resolve_missing_statement_ignores_execution_parameters(
    prepared_statements: PreparedStatementStore,
) -> None:
    resolution = resolve_execute_statement(
        prepared_statements, "primary", "EXECUTE nope", ["'Washington'"]
    )

    assert resolution.failure_reason == (
        "PreparedStatement nope was not found in workGroup primary"
    )


def test_resolve_is_workgroup_scoped(
    prepared_statements: PreparedStatementStore,
) -> None:
    prepared_statements.create("st", "SELECT 1", "analytics", None)

    resolution = resolve_execute_statement(
        prepared_statements, "primary", "EXECUTE st", None
    )

    assert resolution.failure_reason == (
        "PreparedStatement st was not found in workGroup primary"
    )


def test_resolve_count_mismatch_is_failed_execution(
    prepared_statements: PreparedStatementStore,
) -> None:
    prepared_statements.create("st", "SELECT ? AND ?", "primary", None)

    resolution = resolve_execute_statement(
        prepared_statements, "primary", "EXECUTE st USING 1", None
    )

    assert resolution.statement == "EXECUTE st USING 1"
    assert (
        resolution.failure_reason
        == "Incorrect number of parameters: expected 2 but found 1"
    )
    assert resolution.statement_classification.statement_type == "UTILITY"


def test_resolve_bound_ctas_classifies_the_resolved_statement(
    prepared_statements: PreparedStatementStore,
) -> None:
    prepared_statements.create(
        "ctas",
        "CREATE TABLE db.t WITH (external_location = 's3://b/k') AS SELECT ?",
        "primary",
        None,
    )

    resolution = resolve_execute_statement(
        prepared_statements, "primary", "EXECUTE ctas USING 1", None
    )

    assert resolution.statement_classification == StatementClassification(
        "DDL", "CREATE_TABLE_AS_SELECT"
    )


def test_resolve_malformed_execute_is_shaped_400(
    prepared_statements: PreparedStatementStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="statement name"):
        resolve_execute_statement(
            prepared_statements, "primary", "EXECUTE", None
        )
