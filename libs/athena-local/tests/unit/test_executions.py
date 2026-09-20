"""Query execution registry semantics (executions.py) per ADR-0003/0009.

The wire transition contract pinned by ADR-0009: ``QUEUED → RUNNING →
SUCCEEDED|FAILED|CANCELLED``, terminal states immutable, and the runtime
counters Athena surfaces in ``GetQueryExecution`` Statistics are copied from
the Trino StatementStats JSON field names (``processedBytes``,
``wallTimeMillis`` — trino ``client/trino-client/.../StatementStats.java``).
"""

from __future__ import annotations

import pytest
from athena_local.common_schemas import ResultConfiguration
from athena_local.errors import InvalidRequestException
from athena_local.executions import (
    CANCELLED,
    FAILED,
    QUEUED,
    RUNNING,
    SUCCEEDED,
    ExecutionStore,
)


@pytest.fixture()
def store() -> ExecutionStore:
    return ExecutionStore()


def test_create_assigns_uuid_and_starts_queued(store: ExecutionStore) -> None:
    record = store.create(
        query="SELECT 1",
        workgroup="analytics",
        database="default",
        catalog="AwsDataCatalog",
    )

    assert record.state == QUEUED
    assert record.query == "SELECT 1"
    assert record.workgroup == "analytics"
    assert record.database == "default"
    assert record.catalog == "AwsDataCatalog"
    assert record.submission_time > 0
    assert len(record.query_execution_id) == 36
    assert store.get(record.query_execution_id) is record


def test_get_unknown_execution_raises(store: ExecutionStore) -> None:
    with pytest.raises(InvalidRequestException) as error:
        store.get("no-such-execution")

    assert "no-such-execution" in str(error.value)
    assert "does not exist" in str(error.value)


def test_transition_chain_pins_completion_time(store: ExecutionStore) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")

    record.transition_to(RUNNING, reason="dispatched")
    assert record.state == RUNNING
    assert record.completion_time is None

    record.transition_to(SUCCEEDED)
    assert record.state == SUCCEEDED
    assert record.completion_time is not None


def test_failed_transition_records_reason(store: ExecutionStore) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")

    record.transition_to(RUNNING)
    record.transition_to(FAILED, reason="query syntax error")

    assert record.state == FAILED
    assert record.state_change_reason == "query syntax error"


def test_terminal_states_are_immutable(store: ExecutionStore) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")
    record.transition_to(RUNNING)
    record.transition_to(SUCCEEDED)

    with pytest.raises(ValueError) as error:
        record.transition_to(RUNNING)

    assert "SUCCEEDED" in str(error.value)
    assert "RUNNING" in str(error.value)


def test_illegal_transition_is_rejected(store: ExecutionStore) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")

    with pytest.raises(ValueError):
        record.transition_to(
            SUCCEEDED
        )  # QUEUED may only reach RUNNING/CANCELLED


def test_cancelled_from_queued_is_valid(store: ExecutionStore) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")

    record.transition_to(CANCELLED)

    assert record.state == CANCELLED
    assert record.completion_time is not None


def test_apply_engine_statistics_copies_only_integers(
    store: ExecutionStore,
) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")

    record.apply_engine_statistics(
        {"processedBytes": 1024, "wallTimeMillis": 5, "processedRows": 9}
    )

    assert record.data_scanned_bytes == 1024
    assert record.engine_execution_time_ms == 5


def test_apply_engine_statistics_ignores_missing_fields(
    store: ExecutionStore,
) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")

    record.apply_engine_statistics({"state": "FINISHED"})

    assert record.data_scanned_bytes is None
    assert record.engine_execution_time_ms is None


def test_apply_engine_statistics_ignores_non_integer_values(
    store: ExecutionStore,
) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")

    record.apply_engine_statistics(
        {"processedBytes": "many", "wallTimeMillis": 7}
    )

    assert record.data_scanned_bytes is None
    assert record.engine_execution_time_ms == 7


def test_payload_shape_with_all_optional_members(
    store: ExecutionStore,
) -> None:
    record = store.create(
        query="SELECT 1",
        workgroup="analytics",
        database="default",
        catalog="AwsDataCatalog",
        result_configuration=ResultConfiguration(
            output_location="s3://bucket/q.csv"
        ),
        execution_parameters=["one", "two"],
    )
    record.transition_to(RUNNING, reason="dispatched")

    payload = record.to_payload()

    assert payload["QueryExecutionId"] == record.query_execution_id
    assert payload["Query"] == "SELECT 1"
    assert payload["WorkGroup"] == "analytics"
    assert payload["Status"] == {
        "State": RUNNING,
        "StateChangeReason": "dispatched",
        "SubmissionDateTime": record.submission_time,
    }
    assert payload["QueryExecutionContext"] == {
        "Database": "default",
        "Catalog": "AwsDataCatalog",
    }
    assert payload["ResultConfiguration"] == {
        "OutputLocation": "s3://bucket/q.csv"
    }
    assert payload["ExecutionParameters"] == ["one", "two"]


def test_terminal_payload_carries_completion_time(
    store: ExecutionStore,
) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")
    record.transition_to(RUNNING)
    record.transition_to(SUCCEEDED)

    payload = record.to_payload()

    assert payload["Status"]["State"] == SUCCEEDED
    assert payload["Status"]["CompletionDateTime"] == record.completion_time


def test_payload_always_carries_statistics_defaults(
    store: ExecutionStore,
) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")
    record.apply_engine_statistics(
        {"processedBytes": 2048, "wallTimeMillis": 3}
    )

    payload = record.to_payload()

    assert payload["Statistics"] == {
        "DataScannedInBytes": 2048,
        "EngineExecutionTimeInMillis": 3,
    }
    assert "QueryExecutionContext" not in payload
    assert "StatementType" not in payload


def test_payload_includes_statement_type_and_manifest_when_set(
    store: ExecutionStore,
) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")
    record.statement_type = "DML"
    record.data_manifest_location = "s3://bucket/q-manifest.csv"

    payload = record.to_payload()

    assert payload["StatementType"] == "DML"
    assert payload["Statistics"]["DataManifestLocation"] == (
        "s3://bucket/q-manifest.csv"
    )
