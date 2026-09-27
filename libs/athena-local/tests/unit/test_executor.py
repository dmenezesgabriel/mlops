"""Query execution lifecycle (executor.py) per ADR-0009.

The executor drives a ``QueryExecutionRecord`` QUEUED → RUNNING → terminal with
a real ``TrinoClient``-shaped dependency injected as a named fake (F.I.R.S.T.,
no docker): scripted pages for the happy/error paths. The terminal transition
must only fire after the artifact writer persisted the results (ADR-0009 #4).
Cancel/semaphore windows live in ``test_executor_cancel``/``_completion``.
"""

from __future__ import annotations

import asyncio

import pytest
from athena_local.errors import (
    InvalidRequestException,
)
from athena_local.executions import (
    FAILED,
    SUCCEEDED,
    ExecutionStore,
)
from athena_local.executor import QueryExecutor
from athena_local.statement_classification import StatementClassification
from athena_local.submission import TRINO_CATALOG, TRINO_USER
from athena_local.trino_client import (
    TrinoColumn,
    TrinoQueryError,
    TrinoTransportError,
)
from tests.unit._executor_fakes import (
    URI_1,
    URI_2,
    FailingWriter,
    RecordingWriter,
    ScriptedStatementClient,
    result_page,
)


@pytest.fixture()
def store() -> ExecutionStore:
    return ExecutionStore()


def test_happy_path_polls_and_succeeds(store: ExecutionStore) -> None:
    writer = RecordingWriter()

    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(next_uri=URI_1, stats={"state": "RUNNING"}),
                result_page(next_uri=URI_2, stats={"state": "RUNNING"}),
                result_page(
                    next_uri=None,
                    columns=[TrinoColumn(name="_col0", column_type="integer")],
                    data=[[1]],
                    stats={
                        "state": "FINISHED",
                        "processedBytes": 512,
                        "wallTimeMillis": 4,
                    },
                ),
            ]
        )
        executor = QueryExecutor(store=store, client=client, writer=writer)
        record = await executor.start(query="SELECT 1", workgroup="primary")
        await executor._tasks[record.query_execution_id]

        assert client.submissions == [
            ("SELECT 1", TRINO_CATALOG, "", TRINO_USER)
        ]
        assert client.fetches == [URI_1, URI_2]
        assert record.state == SUCCEEDED
        assert record.data_scanned_bytes == 512
        assert record.engine_execution_time_ms == 4

    asyncio.run(scenario())
    assert writer.calls == [
        "write:RUNNING"
    ]  # writer saw RUNNING, before SUCCEEDED


def test_managed_execution_completes_without_writing_artifacts(
    store: ExecutionStore,
) -> None:
    """Managed-results executions succeed without an S3 writer call (ADR-0011)."""
    writer = RecordingWriter()

    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(next_uri=URI_1, stats={"state": "RUNNING"}),
                result_page(
                    next_uri=None,
                    columns=[TrinoColumn(name="_col0", column_type="integer")],
                    data=[[1]],
                    stats={"state": "FINISHED"},
                ),
            ]
        )
        executor = QueryExecutor(store=store, client=client, writer=writer)
        record = await executor.start(
            query="SELECT 1", workgroup="managed", managed_results=True
        )
        await executor._tasks[record.query_execution_id]

        assert record.state == SUCCEEDED
        assert record.result_configuration is None
        # Inline rows are cached exactly like a regular execution (ADR-0011),
        # so GetQueryResults serves them even though nothing reached S3.
        assert record.result_rows == [[1]]

    asyncio.run(scenario())
    assert writer.calls == []


def test_start_records_statement_classification(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        classification = StatementClassification(
            statement_type="DDL", substatement_type="CREATE_TABLE_AS_SELECT"
        )

        record = await executor.start(
            query="CREATE TABLE db.t WITH (format='PARQUET') AS SELECT 1",
            workgroup="primary",
            statement_classification=classification,
        )
        await executor._tasks[record.query_execution_id]

        assert record.statement_type == "DDL"
        assert record.substatement_type == "CREATE_TABLE_AS_SELECT"

    asyncio.run(scenario())


def test_happy_path_submits_with_database_schema(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = await executor.start(
            query="SELECT 1", workgroup="primary", database="analytics"
        )
        await executor._tasks[record.query_execution_id]

        assert client.submissions == [
            ("SELECT 1", TRINO_CATALOG, "analytics", TRINO_USER)
        ]

    asyncio.run(scenario())


def test_submit_transport_error_marks_failed(store: ExecutionStore) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [],
            submit_error=TrinoTransportError("connection refused"),
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = await executor.start(query="SELECT 1", workgroup="primary")

        assert record.state == FAILED
        assert "connection refused" in record.state_change_reason or ""
        # No background task exists: the preflight failure is already terminal.
        assert record.query_execution_id not in executor._tasks

    asyncio.run(scenario())


def test_fetch_transport_error_marks_failed(store: ExecutionStore) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [result_page(next_uri=URI_1)],
            fetch_delay_seconds=0.05,
            fetch_error=TrinoTransportError("read timeout"),
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = await executor.start(query="SELECT 1", workgroup="primary")

        assert record.state == FAILED
        assert "read timeout" in record.state_change_reason or ""
        assert record.query_execution_id not in executor._tasks

    asyncio.run(scenario())


def test_preflight_syntax_error_raises_400_before_any_execution(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(
                    next_uri=None,
                    error=TrinoQueryError(
                        message="line 1:1: mismatched input 'SELEC'",
                        error_type="USER_ERROR",
                        error_name="SYNTAX_ERROR",
                    ),
                )
            ]
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )

        with pytest.raises(InvalidRequestException) as error:
            await executor.start(query="SELEC", workgroup="primary")

        # wrangler sniffs the prefix (and "extraneous input" inside the
        # Trino text) to map the ClientError to InvalidCtasApproachQuery.
        assert (
            str(error.value)
            == "Exception parsing query: line 1:1: mismatched input 'SELEC'"
        )
        assert store.by_id == {}  # rejected before any execution existed
        assert client.submissions == [("SELEC", TRINO_CATALOG, "", TRINO_USER)]
        assert client.fetches == []

    asyncio.run(scenario())


def test_preflight_forwards_analysis_error_to_failed_reason(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(next_uri=URI_1),
                result_page(
                    next_uri=None,
                    error=TrinoQueryError(
                        message="line 1:8: Column 'nope' cannot be resolved",
                        error_type="USER_ERROR",
                        error_name="COLUMN_NOT_FOUND",
                    ),
                ),
            ]
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = await executor.start(query="SELECT nope", workgroup="primary")
        await executor._tasks[record.query_execution_id]

        # Analysis errors are real-Athena execution failures: the start
        # succeeds and the FAILED StateChangeReason carries the Trino text
        # verbatim (wrangler's QueryFailed sniffs match it, _read.py:820-832).
        assert record.state == FAILED
        assert (
            record.state_change_reason
            == "line 1:8: Column 'nope' cannot be resolved"
        )
        assert client.submissions == [
            ("SELECT nope", TRINO_CATALOG, "", TRINO_USER)
        ]
        assert client.fetches == [URI_1]  # the preflight's single fetch

    asyncio.run(scenario())


def test_writer_failure_marks_failed_not_succeeded(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        executor = QueryExecutor(
            store=store, client=client, writer=FailingWriter()
        )
        record = await executor.start(query="SELECT 1", workgroup="primary")
        await executor._tasks[record.query_execution_id]

        assert record.state == FAILED
        assert "moto S3 refused put_object" in (
            record.state_change_reason or ""
        )

    asyncio.run(scenario())
