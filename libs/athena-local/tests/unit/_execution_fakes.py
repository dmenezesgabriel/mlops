"""Shared record factories for ExecutionStore tests.

``succeeded_execution`` builds a terminal record through the real
transitions so retention and reuse tests see a set ``completion_time``.
"""

from __future__ import annotations

from athena_local.executions import (
    RUNNING,
    SUCCEEDED,
    ExecutionStore,
    QueryExecutionRecord,
)


def succeeded_execution(
    store: ExecutionStore, **kwargs: object
) -> QueryExecutionRecord:
    """A SUCCEEDED record in ``store`` with a set completion time."""
    record = store.create(**kwargs)
    record.transition_to(RUNNING)
    record.transition_to(SUCCEEDED)
    return record
