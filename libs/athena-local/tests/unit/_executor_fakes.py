"""Shared named fakes for executor tests (ADR-0009).

``ScriptedStatementClient`` serves scripted Trino pages and records every
call; ``GatedStatementClient`` parks poll fetches inside a shared gate to
pin the semaphore/cancellation windows; ``RecordingWriter``/
``FailingWriter``/``GatedWriter``/``CancellingWriter`` cover the
artifact-writer port; ``RecordingSnapshotter``
records manifest captures and can assert capture-before-submit via a
``capture_client`` (F.I.R.S.T., no docker).
"""

from __future__ import annotations

import asyncio

from athena_local.executions import CANCELLED, QueryExecutionRecord
from athena_local.executor import ArtifactWriteError
from athena_local.output_targets import OutputSnapshot
from athena_local.trino_client import (
    TrinoColumn,
    TrinoPage,
    TrinoQueryError,
    TrinoTransportError,
)

QUERY_ID = "20260920_000000_00000_exec001"
URI_1 = f"http://trino:8080/v1/statement/{QUERY_ID}/1"
URI_2 = f"http://trino:8080/v1/statement/{QUERY_ID}/2"


def result_page(
    next_uri: str | None,
    data: list[list[object]] | None = None,
    columns: list[TrinoColumn] | None = None,
    error: TrinoQueryError | None = None,
    stats: dict[str, object] | None = None,
    update_type: str | None = None,
) -> TrinoPage:
    return TrinoPage(
        query_id=QUERY_ID,
        next_uri=next_uri,
        update_type=update_type,
        columns=columns if columns is not None else [],
        data=data if data is not None else [],
        stats=stats if stats is not None else {},
        error=error,
    )


class ScriptedStatementClient:
    """StatementClient fake serving scripted pages and recording every call."""

    def __init__(
        self,
        pages: list[TrinoPage],
        *,
        submit_delay_seconds: float = 0.0,
        fetch_delay_seconds: float = 0.0,
        submit_error: TrinoTransportError | None = None,
        fetch_error: TrinoTransportError | None = None,
        fetch_error_uri: str | None = None,
        cancel_error: TrinoTransportError | None = None,
    ) -> None:
        self._pages = list(pages)
        self._submit_delay = submit_delay_seconds
        self._fetch_delay = fetch_delay_seconds
        self._submit_error = submit_error
        self._fetch_error = fetch_error
        self._fetch_error_uri = fetch_error_uri
        self._cancel_error = cancel_error
        self.submissions: list[tuple[str, str, str, str]] = []
        self.session_properties_calls: list[dict[str, str] | None] = []
        self.fetches: list[str] = []
        self.cancellations: list[str] = []

    async def submit_statement(
        self,
        query: str,
        catalog: str,
        schema: str,
        user: str,
        session_properties: dict[str, str] | None = None,
    ) -> TrinoPage:
        self.submissions.append((query, catalog, schema, user))
        self.session_properties_calls.append(session_properties)
        await self._pause(self._submit_delay)
        if self._submit_error is not None:
            raise self._submit_error
        return self._pages.pop(0)

    async def fetch_next(self, next_uri: str) -> TrinoPage:
        self.fetches.append(next_uri)
        await self._pause(self._fetch_delay)
        # fetch_error_uri scopes a transport failure to one statement URI so
        # tests can keep the preflight fetch (URI_1) healthy and break a
        # later poll (the start preflight consumes the first fetch).
        if self._fetch_error is not None and (
            self._fetch_error_uri is None or next_uri == self._fetch_error_uri
        ):
            raise self._fetch_error
        return self._pages.pop(0)

    async def cancel(self, next_uri: str) -> None:
        self.cancellations.append(next_uri)
        if self._cancel_error is not None:
            raise self._cancel_error

    @staticmethod
    async def _pause(delay: float) -> None:
        if delay > 0:
            await asyncio.sleep(delay)


class GatedStatementClient:
    """StatementClient fake that parks *poll* fetches inside a shared gate.

    Preflight (submit + the first nextUri fetch) completes immediately so
    ``start`` returns and the task reaches the semaphore; the second fetch
    parks until the gate opens, pinning RUNNING executions at the concurrency
    bound and holding siblings QUEUED (ADR-0009 semaphore).
    """

    def __init__(self, gate: asyncio.Event, query_id: str = QUERY_ID) -> None:
        self._gate = gate
        self._query_id = query_id
        self._active = 0
        self.peak_active = 0
        self.submission_count = 0
        self.cancellations: list[str] = []

    async def submit_statement(
        self,
        query: str,
        catalog: str,
        schema: str,
        user: str,
        session_properties: dict[str, str] | None = None,
    ) -> TrinoPage:
        self.submission_count += 1
        return result_page(next_uri=URI_1, stats={"state": "QUEUED"})

    async def fetch_next(self, next_uri: str) -> TrinoPage:
        if next_uri == URI_1:
            return result_page(
                next_uri=URI_2, stats={"state": "RUNNING"}
            )  # the preflight fetch, never gated
        self._active += 1
        self.peak_active = max(self.peak_active, self._active)
        try:
            await self._gate.wait()
            await asyncio.sleep(0.02)
            return result_page(
                next_uri=None, data=[[1]], stats={"state": "FINISHED"}
            )
        finally:
            self._active -= 1

    async def cancel(self, next_uri: str) -> None:
        # A QUEUED execution's statement is live coordinator-side — the
        # preflight submitted it — so cancelling one must land a DELETE here.
        self.cancellations.append(next_uri)


class RecordingWriter:
    """ResultArtifactWriter fake that records what the write observed."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.snapshots: list[OutputSnapshot | None] = []

    async def write(
        self, execution: QueryExecutionRecord, final_page: TrinoPage
    ) -> None:
        self.calls.append(f"write:{execution.state}")
        self.snapshots.append(execution.output_snapshot)


class FailingWriter:
    """ResultArtifactWriter fake that never manages to persist results."""

    async def write(
        self, execution: QueryExecutionRecord, final_page: TrinoPage
    ) -> None:
        raise ArtifactWriteError("moto S3 refused put_object")


class GatedWriter:
    """ResultArtifactWriter fake parking inside ``write`` until a gate opens.

    The artifact record lands only after the gate, so a cancel that aborts
    the parked write leaves ``calls`` empty — the "no artifacts for a
    CANCELLED record" assertion.
    """

    def __init__(
        self, gate: asyncio.Event, error: Exception | None = None
    ) -> None:
        self._gate = gate
        self._error = error
        self.calls: list[str] = []

    async def write(
        self, execution: QueryExecutionRecord, final_page: TrinoPage
    ) -> None:
        await self._gate.wait()
        if self._error is not None:
            raise self._error
        self.calls.append(f"write:{execution.state}")


class CancellingWriter:
    """ResultArtifactWriter fake whose write flips the record to CANCELLED.

    Models StopQueryExecution landing while an uninterruptible write is in
    flight — the write completes with the record already terminal, and the
    executor must not resurrect it with a trailing SUCCEEDED transition.
    """

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.calls: list[str] = []

    async def write(
        self, execution: QueryExecutionRecord, final_page: TrinoPage
    ) -> None:
        self.calls.append(f"write:{execution.state}")
        execution.transition_to(CANCELLED)
        if self._error is not None:
            raise self._error


class RecordingSnapshotter:
    """ManifestSnapshotSource fake recording captures.

    Pass its ``capture_client`` the scripted statement client: capture must
    run before the statement is submitted, so the fake asserts no
    submission has happened yet and records the call.
    """

    def __init__(
        self,
        snapshot: OutputSnapshot | None = None,
        outcome: OutputSnapshot | Exception | None = None,
        capture_client: ScriptedStatementClient | None = None,
        drop_error: Exception | None = None,
    ) -> None:
        self._snapshot = snapshot
        self._outcome = outcome
        self._capture_client = capture_client
        self._drop_error = drop_error
        self.calls: list[tuple[str, str | None]] = []
        self.drop_calls: list[tuple[str, str]] = []

    async def capture(
        self,
        query: str,
        database: str | None,
        catalog: str | None,
        substatement_type: str | None,
    ) -> OutputSnapshot | None:
        self.calls.append((query, substatement_type))
        if self._capture_client is not None:
            assert self._capture_client.submissions == [], (
                "capture ran after the statement was submitted"
            )
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._snapshot if self._outcome is None else self._outcome

    def drop_table(self, database: str, table: str) -> None:
        self.drop_calls.append((database, table))
        if self._drop_error is not None:
            raise self._drop_error
