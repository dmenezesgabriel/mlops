"""Terminal-page handling of the query executor (ADR-0009 #4).

The poll task accumulates rows across intermediate statement pages (Trino's
final FINISHED document carries none), stashes the Athena-shaped page on the
record, bounds concurrency with a semaphore, and ``ensure_query_finished``
raises the exact pre-finish 400.
"""

from __future__ import annotations

import asyncio

import pytest
from athena_local.errors import (
    InvalidRequestException,
)
from athena_local.executions import (
    QUEUED,
    RUNNING,
    SUCCEEDED,
    ExecutionStore,
)
from athena_local.executor import QueryExecutor
from athena_local.statement_classification import StatementClassification
from athena_local.trino_client import (
    TrinoColumn,
)
from tests.unit._executor_fakes import (
    URI_1,
    URI_2,
    GatedStatementClient,
    RecordingWriter,
    ScriptedStatementClient,
    result_page,
)


@pytest.fixture()
def store() -> ExecutionStore:
    return ExecutionStore()


def test_completion_stashes_final_page_on_record(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(
                    next_uri=None,
                    columns=[
                        TrinoColumn(name="col_a", column_type="varchar"),
                        TrinoColumn(name="col_b", column_type="integer"),
                    ],
                    data=[["alpha", 1], ["beta", 2]],
                    stats={"state": "FINISHED"},
                )
            ]
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = await executor.start(query="SELECT 1", workgroup="primary")
        await executor._tasks[record.query_execution_id]

        assert record.state == SUCCEEDED
        assert record.result_columns == [
            ("col_a", "varchar"),
            ("col_b", "integer"),
        ]
        assert record.result_rows == [["alpha", 1], ["beta", 2]]

    asyncio.run(scenario())


def test_describe_result_is_cached_in_athena_shape(
    store: ExecutionStore,
) -> None:
    """The cached page carries Athena's col_name/data_type/comment shape.

    ``GetQueryResults`` ColumnInfo and the ``.txt`` artifact both read the
    cached page, so the reshape lands once here (result_shapes.py) and
    wrangler's ``_parse_describe_table`` names resolve
    (awswrangler/athena/_utils.py:224-239).
    """

    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(
                    next_uri=None,
                    columns=[
                        TrinoColumn(name="Column", column_type="varchar"),
                        TrinoColumn(name="Type", column_type="varchar"),
                        TrinoColumn(name="Extra", column_type="varchar"),
                        TrinoColumn(name="Comment", column_type="varchar"),
                    ],
                    data=[
                        ["quantity", "bigint", "", ""],
                        ["region", "varchar", "partition key", ""],
                    ],
                    stats={"state": "FINISHED"},
                )
            ]
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = await executor.start(
            query='DESCRIBE "sales"',
            workgroup="primary",
            statement_classification=StatementClassification(
                "UTILITY", "DESCRIBE"
            ),
        )
        await executor._tasks[record.query_execution_id]

        assert record.state == SUCCEEDED
        assert record.result_columns == [
            ("col_name", "varchar"),
            ("data_type", "varchar"),
            ("comment", "varchar"),
        ]
        assert record.result_rows == [
            ["quantity", "bigint", ""],
            ["region", "varchar", ""],
            ["# Partition Information", "", ""],
            ["# col_name", "data_type", "comment"],
            ["region", "varchar", ""],
        ]

    asyncio.run(scenario())


def test_rows_landing_on_intermediate_poll_pages_are_carried(
    store: ExecutionStore,
) -> None:
    """Trino streams data on pre-final pages; the final page carries none.

    Measured against the running coordinator: a 6-row VALUES SELECT arrived
    entirely on a RUNNING page and the FINISHED page carried
    ``data=None`` (statement protocol), so the last page alone would lose
    every row.
    """

    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(next_uri=URI_1, stats={"state": "QUEUED"}),
                result_page(
                    next_uri=URI_2,
                    columns=[TrinoColumn(name="x", column_type="integer")],
                    data=[[1], [2], [3]],
                    stats={"state": "RUNNING"},
                ),
                result_page(next_uri=None, stats={"state": "FINISHED"}),
            ]
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = await executor.start(query="SELECT 1", workgroup="primary")
        await executor._tasks[record.query_execution_id]

        assert record.state == SUCCEEDED
        assert record.result_rows == [[1], [2], [3]]

    asyncio.run(scenario())


def test_submit_page_rows_survive_the_preflight_fetch(
    store: ExecutionStore,
) -> None:
    """A fast query can carry rows on the POST response itself.

    The preflight folds the submit page's rows into the page it forwards to
    the poll task, so rows present on ``POST /v1/statement`` are not dropped
    at the one-fetch boundary (statement protocol: rows may arrive as early
    as the first document).
    """

    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(
                    next_uri=URI_1,
                    columns=[TrinoColumn(name="x", column_type="integer")],
                    data=[[1], [2]],
                    stats={"state": "RUNNING"},
                ),
                result_page(
                    next_uri=None,
                    data=[[3]],
                    stats={"state": "FINISHED"},
                ),
            ]
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = await executor.start(query="SELECT 1", workgroup="primary")
        await executor._tasks[record.query_execution_id]

        assert record.state == SUCCEEDED
        assert record.result_rows == [[1], [2], [3]]

    asyncio.run(scenario())


def test_semaphore_bounds_concurrency(store: ExecutionStore) -> None:
    async def scenario() -> None:
        gate = asyncio.Event()
        client = GatedStatementClient(gate)
        executor = QueryExecutor(
            store=store,
            client=client,
            writer=RecordingWriter(),
            max_concurrent_queries=2,
        )
        records = [
            await executor.start(query=f"SELECT {i}", workgroup="primary")
            for i in range(4)
        ]
        await asyncio.sleep(0.02)
        assert [record.state for record in records] == [
            RUNNING,
            RUNNING,
            QUEUED,
            QUEUED,
        ]

        gate.set()
        await asyncio.gather(
            *[executor._tasks[r.query_execution_id] for r in records]
        )

        assert client.peak_active <= 2
        assert all(record.state == SUCCEEDED for record in records)

    asyncio.run(scenario())


def test_ensure_query_finished_prefinish_400_parity(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        gate = asyncio.Event()
        client = GatedStatementClient(gate)
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        running = await executor.start(query="SELECT 1", workgroup="primary")
        await asyncio.sleep(0.02)
        assert running.state == RUNNING

        with pytest.raises(InvalidRequestException) as error:
            executor.ensure_query_finished(running.query_execution_id)
        assert (
            str(error.value)
            == "Query has not yet finished. Current state: RUNNING"
        )
        gate.set()
        await executor._tasks[running.query_execution_id]
        assert (
            executor.ensure_query_finished(running.query_execution_id)
            is running
        )

    asyncio.run(scenario())


def test_ensure_query_finished_unknown_execution_raises(
    store: ExecutionStore,
) -> None:
    executor = QueryExecutor(
        store=store,
        client=ScriptedStatementClient([]),
        writer=RecordingWriter(),
    )

    with pytest.raises(InvalidRequestException) as error:
        executor.ensure_query_finished("no-such-execution")

    assert "no-such-execution" in str(error.value)
