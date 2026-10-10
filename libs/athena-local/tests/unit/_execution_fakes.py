"""Shared record factories for ExecutionStore tests.

``started_execution`` registers a fresh QUEUED record; ``succeeded_execution``
builds a terminal record through the real transitions so retention and reuse
tests see a set ``completion_time``.
"""

from __future__ import annotations

from uuid import uuid4

from athena_local.executions import (
    RUNNING,
    SUCCEEDED,
    ExecutionStore,
    QueryExecutionRecord,
)


def started_execution(
    store: ExecutionStore, **kwargs: object
) -> QueryExecutionRecord:
    """A QUEUED record registered in ``store`` with a fresh execution id.

    Test convenience over ``ExecutionStore.create`` (AF-144): builds the
    record from the keyword fields tests used to pass to ``create`` and
    maps a submission's ``client_request_token`` onto ``request_token``.
    """
    fields = dict(kwargs)
    record = QueryExecutionRecord(
        query_execution_id=str(uuid4()),
        query=fields.pop("query"),
        workgroup=fields.pop("workgroup"),
        request_token=fields.pop("client_request_token", None),
        **fields,
    )
    return store.create(record)


def succeeded_execution(
    store: ExecutionStore, **kwargs: object
) -> QueryExecutionRecord:
    """A SUCCEEDED record in ``store`` with a set completion time."""
    record = started_execution(store, **kwargs)
    record.transition_to(RUNNING)
    record.transition_to(SUCCEEDED)
    return record
