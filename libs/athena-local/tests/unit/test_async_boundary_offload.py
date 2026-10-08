"""Blocking Glue/S3 boundary calls run off the event loop.

The emulator's Glue and S3 boundaries wrap synchronous boto3 clients. The async
query paths (manifest capture, artifact write, UNLOAD temp-table drop) must hand
those calls to a worker thread, or every moto roundtrip freezes the loop and
serializes concurrent executions. These tests pin that each blocking boundary
call executes on a thread other than the event loop's, and that the loop keeps
ticking while a blocking capture runs.
"""

from __future__ import annotations

import asyncio
import threading
import time

from athena_local.artifacts import ArtifactWriter
from athena_local.common_schemas import ResultConfiguration
from athena_local.executions import ExecutionStore, QueryExecutionRecord
from athena_local.executor import QueryExecutor
from athena_local.glue_proxy import GlueProxy
from athena_local.output_targets import OutputSnapshotter
from athena_local.s3_writer import S3Writer
from athena_local.statement_classification import StatementClassification
from athena_local.trino_client import TrinoPage
from tests.unit._executor_fakes import (
    URI_1,
    RecordingSnapshotter,
    RecordingWriter,
    ScriptedStatementClient,
    result_page,
)
from tests.unit._glue_fakes import FakeGlueClient
from tests.unit._s3_fakes import RecordingObjectStore

LATENCY_SECONDS = 0.05
RESULT_LOCATION = "s3://results-bucket/analytics/"
INSERT_QUERY = "INSERT INTO analytics.events SELECT * FROM src"
INSERT_TABLE: dict[str, object] = {
    "Name": "events",
    "TableType": "EXTERNAL_TABLE",
    "StorageDescriptor": {"Location": "s3://data-bucket/events/"},
}
UNLOAD_QUERY = (
    "UNLOAD (SELECT * FROM sales) TO 's3://unload-bucket/out/' "
    "WITH (format='PARQUET')"
)
UNLOAD_CLASSIFICATION = StatementClassification("DML", "UNLOAD")
PLACEHOLDER_PAGE = TrinoPage(
    query_id="20261008_120000_00001_a1b2c3",
    next_uri=None,
    update_type=None,
    columns=[],
    data=[],
    stats={},
    error=None,
)


class BlockingGlueClient(FakeGlueClient):
    """FakeGlueClient whose ``get_table`` blocks like a moto RTT.

    Records the calling thread so a test can prove the read ran off the event
    loop.
    """

    def __init__(
        self,
        tables: dict[str, list[dict[str, object]]] | None = None,
        *,
        latency: float = LATENCY_SECONDS,
    ) -> None:
        super().__init__(tables=tables)
        self._latency = latency
        self.get_table_threads: list[int] = []

    def get_table(  # noqa: N803 (mirrors the botocore keyword vocabulary)
        self,
        DatabaseName: str,  # noqa: N803
        Name: str,  # noqa: N803
    ) -> dict[str, object]:
        self.get_table_threads.append(threading.get_ident())
        time.sleep(self._latency)
        return super().get_table(DatabaseName, Name)


class BlockingObjectStore(RecordingObjectStore):
    """RecordingObjectStore whose calls block like moto RTTs.

    Records the calling thread for every S3 operation.
    """

    def __init__(self, *, latency: float = LATENCY_SECONDS) -> None:
        super().__init__()
        self._latency = latency
        self.call_threads: list[int] = []

    def put_object(  # noqa: N803 (mirrors the botocore keyword vocabulary)
        self,
        Bucket: str,  # noqa: N803
        Key: str,  # noqa: N803
        Body: bytes,  # noqa: N803
    ) -> dict[str, object]:
        self.call_threads.append(threading.get_ident())
        time.sleep(self._latency)
        return super().put_object(Bucket, Key, Body)

    def list_objects_v2(  # noqa: N803 (mirrors the botocore vocabulary)
        self,
        Bucket: str,  # noqa: N803
        Prefix: str = "",  # noqa: N803
        ContinuationToken: str | None = None,  # noqa: N803
    ) -> dict[str, object]:
        self.call_threads.append(threading.get_ident())
        time.sleep(self._latency)
        return super().list_objects_v2(Bucket, Prefix, ContinuationToken)


class BlockingSnapshotter(RecordingSnapshotter):
    """RecordingSnapshotter whose ``drop_table`` blocks and records its thread."""

    def __init__(self, snapshot: None = None) -> None:
        super().__init__(snapshot=snapshot)
        self.drop_threads: list[int] = []

    def drop_table(self, database: str, table: str) -> None:
        self.drop_threads.append(threading.get_ident())
        time.sleep(LATENCY_SECONDS)
        super().drop_table(database, table)


def test_capture_runs_blocking_boundary_reads_off_the_loop() -> None:
    glue = BlockingGlueClient(tables={"analytics": [INSERT_TABLE]})
    store = BlockingObjectStore()
    snapshotter = OutputSnapshotter(GlueProxy(glue), S3Writer(store))
    loop_thread = threading.get_ident()

    async def scenario() -> None:
        snapshot = await snapshotter.capture(
            INSERT_QUERY, "analytics", None, "INSERT"
        )
        assert snapshot is not None

    asyncio.run(scenario())

    assert glue.get_table_threads
    assert all(thread != loop_thread for thread in glue.get_table_threads)
    assert store.call_threads
    assert all(thread != loop_thread for thread in store.call_threads)


def test_capture_leaves_the_event_loop_free_to_tick() -> None:
    glue = BlockingGlueClient(tables={"analytics": [INSERT_TABLE]})
    store = BlockingObjectStore()
    snapshotter = OutputSnapshotter(GlueProxy(glue), S3Writer(store))

    async def scenario() -> int:
        ticks = 0
        running = True

        async def ticker() -> None:
            nonlocal ticks
            while running:
                await asyncio.sleep(0.001)
                ticks += 1

        ticker_task = asyncio.create_task(ticker())
        await snapshotter.capture(INSERT_QUERY, "analytics", None, "INSERT")
        running = False
        await ticker_task
        return ticks

    # Blocking boundary I/O inside the capture keeps the ticker at ~zero.
    assert asyncio.run(scenario()) >= 5


def test_artifact_write_runs_blocking_s3_puts_off_the_loop() -> None:
    store = BlockingObjectStore()
    writer = ArtifactWriter(S3Writer(store))
    loop_thread = threading.get_ident()

    asyncio.run(writer.write(_record_for_write(), PLACEHOLDER_PAGE))

    assert store.call_threads
    assert all(thread != loop_thread for thread in store.call_threads)


def test_unload_cleanup_drops_the_temp_table_off_the_loop() -> None:
    snapshotter = BlockingSnapshotter()
    loop_thread = threading.get_ident()

    async def scenario() -> QueryExecutionRecord:
        client = ScriptedStatementClient(
            [
                result_page(next_uri=URI_1, stats={"state": "RUNNING"}),
                result_page(
                    next_uri=None, update_type="CREATE TABLE AS SELECT"
                ),
            ]
        )
        executor = QueryExecutor(
            store=ExecutionStore(),
            client=client,
            writer=RecordingWriter(),
            snapshotter=snapshotter,
        )
        record = await executor.start(
            query=UNLOAD_QUERY,
            workgroup="primary",
            database="analytics",
            statement_classification=UNLOAD_CLASSIFICATION,
        )
        await executor._tasks[record.query_execution_id]
        return record

    record = asyncio.run(scenario())

    assert record.state == "SUCCEEDED"
    assert snapshotter.drop_threads
    assert all(thread != loop_thread for thread in snapshotter.drop_threads)


def _record_for_write() -> QueryExecutionRecord:
    record = ExecutionStore().create(
        query="SELECT a FROM analytics.t",
        workgroup="primary",
        database="analytics",
        result_configuration=ResultConfiguration(
            output_location=RESULT_LOCATION
        ),
        statement_type="DML",
        substatement_type="SELECT",
    )
    record.cache_result_page([("a", "integer")], [[1]])
    return record
