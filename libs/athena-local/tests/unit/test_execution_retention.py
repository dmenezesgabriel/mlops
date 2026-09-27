"""ExecutionStore retention: 45-day history expiry and the count cap.

AWS keeps a query history for 45 days (ListQueryExecutions API doc); the
store additionally bounds retained records so a long-lived process stays
memory-flat. Expired or evicted executions read as absent everywhere —
``get`` 400s, ``batch_get`` reports unprocessed, lists skip them, request
tokens free for re-registration — while in-flight executions are exempt
from both bounds.
"""

from __future__ import annotations

from time import time

import pytest
from athena_local.errors import InvalidRequestException
from athena_local.executions import (
    QUERY_HISTORY_TTL_SECONDS,
    RUNNING,
    SUCCEEDED,
    ExecutionStore,
)
from tests.unit._execution_fakes import succeeded_execution


@pytest.fixture()
def store() -> ExecutionStore:
    return ExecutionStore()


def _expired(store: ExecutionStore, **kwargs: object):
    """A terminal record past the 45-day query-history window."""
    record = succeeded_execution(store, **kwargs)
    assert record.completion_time is not None
    record.completion_time = time() - QUERY_HISTORY_TTL_SECONDS - 60
    return record


def test_store_rejects_a_nonpositive_retention_cap() -> None:
    with pytest.raises(ValueError, match="max_retained_executions"):
        ExecutionStore(max_retained_executions=0)


def test_create_evicts_oldest_terminal_records_past_the_cap() -> None:
    store = ExecutionStore(max_retained_executions=3)
    records = [
        succeeded_execution(
            store, query=f"SELECT {index}", workgroup="primary"
        )
        for index in range(4)
    ]
    evicted, kept = records[0], records[1:]

    assert len(store.by_id) == 3
    assert evicted.query_execution_id not in store.by_id
    with pytest.raises(InvalidRequestException, match="does not exist"):
        store.get(evicted.query_execution_id)
    found, unprocessed = store.batch_get(
        [record.query_execution_id for record in records]
    )
    assert found == kept
    assert unprocessed == [evicted.query_execution_id]
    listed_ids, _ = store.list_execution_ids("primary")
    assert listed_ids == [
        record.query_execution_id for record in reversed(kept)
    ]


def test_in_flight_executions_are_never_evicted() -> None:
    # The executor's poll tasks and StopQueryExecution act on live records,
    # so the retention cap bounds history only: in-flight submissions sit
    # outside it and push the store past the cap until they terminate.
    store = ExecutionStore(max_retained_executions=2)
    queued = [
        store.create(query=f"SELECT {index}", workgroup="primary")
        for index in range(3)
    ]

    assert len(store.by_id) == 3
    assert all(record.query_execution_id in store.by_id for record in queued)


def test_eviction_frees_the_client_request_token() -> None:
    # An evicted execution must not wedge its token: StartQueryExecution
    # idempotency replays only while the original is retained, and a later
    # submission of the same token runs fresh and re-registers.
    store = ExecutionStore(max_retained_executions=2)
    first = succeeded_execution(
        store,
        query="SELECT 1",
        workgroup="primary",
        client_request_token="tok",
    )
    succeeded_execution(store, query="SELECT 2", workgroup="primary")
    succeeded_execution(store, query="SELECT 3", workgroup="primary")

    assert first.query_execution_id not in store.by_id
    assert store.find_by_request_token("primary", "tok") is None

    retry = store.create(
        query="SELECT 1", workgroup="primary", client_request_token="tok"
    )
    assert retry.query_execution_id != first.query_execution_id
    assert store.find_by_request_token("primary", "tok") is retry


def test_evicting_a_duplicate_token_keeps_the_original_mapping() -> None:
    # First-wins registration means the surviving record owns the token;
    # evicting the raced duplicate must not delete its mapping.
    store = ExecutionStore(max_retained_executions=2)
    original = store.create(
        query="SELECT 1", workgroup="primary", client_request_token="tok"
    )
    duplicate = store.create(
        query="SELECT 1", workgroup="primary", client_request_token="tok"
    )
    duplicate.transition_to(RUNNING)
    duplicate.transition_to(SUCCEEDED)

    succeeded_execution(store, query="SELECT 4", workgroup="primary")

    assert duplicate.query_execution_id not in store.by_id
    assert store.find_by_request_token("primary", "tok") is original

    # Evicting the record that owns the token frees the mapping.
    original.transition_to(RUNNING)
    original.transition_to(SUCCEEDED)
    succeeded_execution(store, query="SELECT 5", workgroup="primary")

    assert original.query_execution_id not in store.by_id
    assert store.find_by_request_token("primary", "tok") is None


def test_expired_executions_read_as_absent(store: ExecutionStore) -> None:
    # AWS drops executions from query history after 45 days
    # (ListQueryExecutions API doc); every read path answers the same
    # not-found/absent shape as for a never-known id.
    live = succeeded_execution(store, query="SELECT 1", workgroup="primary")
    stale = _expired(
        store,
        query="SELECT 2",
        workgroup="primary",
        client_request_token="tok",
    )

    with pytest.raises(InvalidRequestException, match="does not exist"):
        store.get(stale.query_execution_id)
    found, unprocessed = store.batch_get(
        [live.query_execution_id, stale.query_execution_id]
    )
    assert found == [live]
    assert unprocessed == [stale.query_execution_id]
    listed_ids, _ = store.list_execution_ids("primary")
    assert live.query_execution_id in listed_ids
    assert stale.query_execution_id not in listed_ids
    assert store.find_by_request_token("primary", "tok") is None

    # The expired token is free: a retry runs fresh and re-registers.
    retry = store.create(
        query="SELECT 2", workgroup="primary", client_request_token="tok"
    )
    assert store.find_by_request_token("primary", "tok") is retry


def test_running_executions_never_expire(store: ExecutionStore) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")
    record.transition_to(RUNNING)

    # completion_time is unset until a terminal transition, so in-flight
    # executions sit outside the 45-day history bound entirely.
    assert store.get(record.query_execution_id) is record


def test_find_reusable_skips_expired_sources(store: ExecutionStore) -> None:
    # The wire's MaxAgeInMinutes tops out at 7 days — under the 45-day
    # history bound — so this needs an out-of-model window to isolate the
    # TTL mask from the age-window rejection.
    _expired(store, query="SELECT 1", workgroup="primary")

    assert (
        store.find_reusable(
            workgroup="primary",
            query="SELECT 1",
            database=None,
            catalog=None,
            execution_parameters=None,
            result_configuration=None,
            max_age_minutes=60 * 24 * 60,
        )
        is None
    )
