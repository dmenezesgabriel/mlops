"""ExecutionStore lookups: batch reads, request tokens, result reuse.

``batch_get`` splits found/unprocessed per the model's output shape;
``find_by_request_token`` backs the ClientRequestToken idempotent replay;
``same_request``/``find_reusable``/``reuse_results_from`` implement the
result-reuse contract — normalized statement text match, freshness window,
SUCCEEDED-only — that ``SubmissionPlanner`` consults at submit.
"""

from __future__ import annotations

from time import monotonic

import pytest
from athena_local.common_schemas import (
    ResultConfiguration,
    ResultReuseByAgeConfiguration,
)
from athena_local.executions import (
    RUNNING,
    ExecutionStore,
)
from athena_local.statement_classification import normalize_statement_text
from tests.unit._execution_fakes import succeeded_execution


@pytest.fixture()
def store() -> ExecutionStore:
    return ExecutionStore()


def test_batch_get_returns_found_records_and_unprocessed_ids(
    store: ExecutionStore,
) -> None:
    first = store.create(query="SELECT 1", workgroup="primary")
    second = store.create(query="SELECT 2", workgroup="primary")

    found, unprocessed = store.batch_get(
        [
            first.query_execution_id,
            "missing-1",
            second.query_execution_id,
            "missing-2",
        ]
    )

    assert found == [first, second]
    assert unprocessed == ["missing-1", "missing-2"]


def test_find_by_request_token_returns_the_tokened_execution(
    store: ExecutionStore,
) -> None:
    record = store.create(
        query="SELECT 1",
        workgroup="primary",
        client_request_token="token-1",
    )

    assert store.find_by_request_token("primary", "token-1") is record


def test_find_by_request_token_is_scoped_per_workgroup_and_token(
    store: ExecutionStore,
) -> None:
    store.create(
        query="SELECT 1", workgroup="primary", client_request_token="token-1"
    )

    assert store.find_by_request_token("analytics", "token-1") is None
    assert store.find_by_request_token("primary", "token-2") is None


def test_find_by_request_token_misses_tokenless_executions(
    store: ExecutionStore,
) -> None:
    store.create(query="SELECT 1", workgroup="primary")

    assert store.find_by_request_token("primary", "token-1") is None


def test_request_token_mapping_keeps_the_first_execution(
    store: ExecutionStore,
) -> None:
    # The executor's dedup check normally prevents a second create; the map
    # still keeps the first id so a raced duplicate replays the original
    # response (StartQueryExecution is idempotent — service-2.json).
    first = store.create(
        query="SELECT 1", workgroup="primary", client_request_token="token-1"
    )
    second = store.create(
        query="SELECT 1", workgroup="primary", client_request_token="token-1"
    )

    assert second is not first
    assert store.find_by_request_token("primary", "token-1") is first


def test_reset_drops_request_token_mappings(store: ExecutionStore) -> None:
    store.create(
        query="SELECT 1", workgroup="primary", client_request_token="token-1"
    )

    store.reset()

    assert store.by_id == {}
    assert store.find_by_request_token("primary", "token-1") is None


def test_same_request_matches_an_identical_submission(
    store: ExecutionStore,
) -> None:
    record = store.create(
        query="SELECT 1",
        workgroup="primary",
        database="analytics",
        catalog="AwsDataCatalog",
        result_configuration=ResultConfiguration(output_location="s3://b/"),
        execution_parameters=["1"],
    )

    assert record.same_request(
        query="SELECT 1",
        database="analytics",
        catalog="AwsDataCatalog",
        execution_parameters=["1"],
        result_configuration=ResultConfiguration(output_location="s3://b/"),
    )


def test_same_request_detects_each_changed_parameter(
    store: ExecutionStore,
) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")

    assert not record.same_request(
        query="SELECT 2",
        database=None,
        catalog=None,
        execution_parameters=None,
        result_configuration=None,
    )
    assert not record.same_request(
        query="SELECT 1",
        database="analytics",
        catalog=None,
        execution_parameters=None,
        result_configuration=None,
    )
    assert not record.same_request(
        query="SELECT 1",
        database=None,
        catalog="AwsDataCatalog",
        execution_parameters=None,
        result_configuration=None,
    )
    assert not record.same_request(
        query="SELECT 1",
        database=None,
        catalog=None,
        execution_parameters=["1"],
        result_configuration=None,
    )
    assert not record.same_request(
        query="SELECT 1",
        database=None,
        catalog=None,
        execution_parameters=None,
        result_configuration=ResultConfiguration(output_location="s3://b/"),
    )
    assert not record.same_request(
        query="SELECT 1",
        database=None,
        catalog=None,
        execution_parameters=None,
        result_configuration=None,
        result_reuse_configuration=ResultReuseByAgeConfiguration(enabled=True),
    )


def test_find_reusable_returns_the_matching_succeeded_execution(
    store: ExecutionStore,
) -> None:
    """AWS re-answers a query when an identical recent execution exists in
    the same workgroup (UG "Reusing query results")."""
    source = succeeded_execution(
        store,
        query="SELECT 1",
        workgroup="primary",
        database="analytics",
        result_configuration=ResultConfiguration(output_location="s3://b/"),
        execution_parameters=["1"],
    )

    found = store.find_reusable(
        workgroup="primary",
        query="SELECT 1",
        database="analytics",
        catalog=None,
        execution_parameters=["1"],
        result_configuration=ResultConfiguration(output_location="s3://b/"),
        max_age_minutes=60,
    )

    assert found is source


def test_find_reusable_prefers_the_newest_matching_result(
    store: ExecutionStore,
) -> None:
    # AWS uses the latest result when several match (UG "Reusing query
    # results"), so iteration walks the store newest-first.
    succeeded_execution(store, query="SELECT 1", workgroup="primary")
    newest = succeeded_execution(store, query="SELECT 1", workgroup="primary")
    succeeded_execution(store, query="SELECT 2", workgroup="primary")

    found = store.find_reusable(
        workgroup="primary",
        query="SELECT 1",
        database=None,
        catalog=None,
        execution_parameters=None,
        result_configuration=None,
        max_age_minutes=60,
    )

    assert found is newest


def test_find_reusable_matches_ignoring_comments_and_whitespace(
    store: ExecutionStore,
) -> None:
    # Athena's match treats queries under 100 KB differing only in comments
    # and whitespace as identical (UG "Reusing query results").
    source = succeeded_execution(store, query="SELECT 1", workgroup="primary")

    found = store.find_reusable(
        workgroup="primary",
        query=" SELECT  1 -- trailing\n",
        database=None,
        catalog=None,
        execution_parameters=None,
        result_configuration=None,
        max_age_minutes=60,
    )

    assert found is source


def test_find_reusable_rejects_each_mismatched_field(
    store: ExecutionStore,
) -> None:
    succeeded_execution(
        store,
        query="SELECT 1",
        workgroup="primary",
        database="analytics",
        catalog="AwsDataCatalog",
        result_configuration=ResultConfiguration(output_location="s3://b/"),
        execution_parameters=["1"],
    )

    def lookup(**override: object):
        identity = {
            "workgroup": "primary",
            "query": "SELECT 1",
            "database": "analytics",
            "catalog": "AwsDataCatalog",
            "execution_parameters": ["1"],
            "result_configuration": ResultConfiguration(
                output_location="s3://b/"
            ),
            "max_age_minutes": 60,
        }
        return store.find_reusable(**(identity | override))

    assert lookup(workgroup="other") is None
    assert lookup(query="SELECT 2") is None
    assert lookup(database="default") is None
    assert lookup(catalog="other") is None
    assert lookup(execution_parameters=["2"]) is None
    assert (
        lookup(
            result_configuration=ResultConfiguration(output_location="s3://x/")
        )
        is None
    )


def test_find_reusable_rejects_expired_and_unfinished_results(
    store: ExecutionStore,
) -> None:
    expired = succeeded_execution(store, query="SELECT 1", workgroup="primary")
    assert expired.completion_time is not None
    expired.completion_time -= 120  # completed two minutes ago

    still_running = store.create(query="SELECT 1", workgroup="primary")
    still_running.transition_to(RUNNING)

    assert (
        store.find_reusable(
            workgroup="primary",
            query="SELECT 1",
            database=None,
            catalog=None,
            execution_parameters=None,
            result_configuration=None,
            max_age_minutes=1,
        )
        is None
    )
    # Widen the window: the expired source now qualifies, while the
    # RUNNING execution never produces reusable results.
    assert (
        store.find_reusable(
            workgroup="primary",
            query="SELECT 1",
            database=None,
            catalog=None,
            execution_parameters=None,
            result_configuration=None,
            max_age_minutes=60,
        )
        is expired
    )


def test_record_caches_normalized_query_at_create(
    store: ExecutionStore,
) -> None:
    record = store.create(
        query=" SELECT  1 -- trailing\n", workgroup="primary"
    )

    assert record.normalized_query == normalize_statement_text(
        " SELECT  1 -- trailing\n"
    )


def test_find_reusable_normalizes_only_the_incoming_query(
    store: ExecutionStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The scan must not re-normalize each stored query: the record caches
    # its key at create, so one lookup pays one normalization total.
    for index in range(100):
        succeeded_execution(
            store, query=f"SELECT {index}", workgroup="primary"
        )

    calls = 0
    real_normalize = normalize_statement_text

    def counting(query: str) -> str:
        nonlocal calls
        calls += 1
        return real_normalize(query)

    monkeypatch.setattr(
        "athena_local.executions.normalize_statement_text", counting
    )

    assert (
        store.find_reusable(
            workgroup="primary",
            query="SELECT missing",
            database=None,
            catalog=None,
            execution_parameters=None,
            result_configuration=None,
            max_age_minutes=60,
        )
        is None
    )
    assert calls == 1


def test_find_reusable_miss_scan_scales() -> None:
    # A miss over a 20k-execution history was O(executions × query-len)
    # (~40 ms at ~180-char queries) because every candidate re-normalized
    # its stored query; with the cached key the scan is ~4 ms of attribute
    # checks. The bound is generous because `make coverage`'s line tracing
    # inflates the pure-Python loop ~10x (~39 ms observed); the precise
    # per-candidate-normalize guard is the counting test above. The store
    # is sized past the fixture count so retention never fires mid-test.
    store = ExecutionStore(max_retained_executions=25_000)
    for index in range(20_000):
        columns = ", ".join(f"c{index}_{number}" for number in range(25))
        succeeded_execution(
            store,
            query=f"SELECT {columns} FROM t_{index}",
            workgroup="primary",
        )

    started = monotonic()
    found = store.find_reusable(
        workgroup="primary",
        query="SELECT missing",
        database=None,
        catalog=None,
        execution_parameters=None,
        result_configuration=None,
        max_age_minutes=60,
    )
    elapsed_ms = (monotonic() - started) * 1000

    assert found is None
    assert elapsed_ms < 100


def test_reuse_results_from_copies_the_result_surface(
    store: ExecutionStore,
) -> None:
    source = succeeded_execution(
        store,
        query="SELECT 1",
        workgroup="primary",
        result_configuration=ResultConfiguration(output_location="s3://b/"),
    )
    source.cache_result_page([("col", "integer")], [[1]])
    record = store.create(
        query="SELECT 1",
        workgroup="primary",
        result_configuration=ResultConfiguration(output_location="s3://b/"),
    )

    record.reuse_results_from(source)

    # The reused execution points at the source's artifact path — Athena
    # writes no new file for a reused result (UG "Reusing query results").
    assert record.reused_previous_result is True
    assert record.result_columns == [("col", "integer")]
    assert record.result_rows == [[1]]
    assert record._result_output_location() == source._result_output_location()


def test_payload_reports_result_reuse_members(store: ExecutionStore) -> None:
    reuse = ResultReuseByAgeConfiguration(enabled=True, max_age_in_minutes=30)
    source = succeeded_execution(
        store,
        query="SELECT 1",
        workgroup="primary",
        result_configuration=ResultConfiguration(output_location="s3://b/"),
        result_reuse_configuration=reuse,
    )
    record = store.create(
        query="SELECT 1",
        workgroup="primary",
        result_configuration=ResultConfiguration(output_location="s3://b/"),
        result_reuse_configuration=reuse,
    )
    record.reuse_results_from(source)

    payload = record.to_payload()

    assert payload["ResultReuseConfiguration"] == {
        "ResultReuseByAgeConfiguration": {
            "Enabled": True,
            "MaxAgeInMinutes": 30,
        }
    }
    assert payload["Statistics"]["ResultReuseInformation"] == {
        "ReusedPreviousResult": True
    }
    # The echoed OutputLocation is the source's, not the new id's path.
    assert (
        payload["ResultConfiguration"]["OutputLocation"]
        == (source.to_payload()["ResultConfiguration"]["OutputLocation"])
    )


def test_payload_reports_reuse_not_taken(store: ExecutionStore) -> None:
    record = store.create(
        query="SELECT 1",
        workgroup="primary",
        result_reuse_configuration=ResultReuseByAgeConfiguration(enabled=True),
    )

    payload = record.to_payload()

    assert payload["Statistics"]["ResultReuseInformation"] == {
        "ReusedPreviousResult": False
    }


def test_payload_omits_reuse_members_when_not_requested(
    store: ExecutionStore,
) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")

    payload = record.to_payload()

    assert "ResultReuseConfiguration" not in payload
    assert "ResultReuseInformation" not in payload["Statistics"]
