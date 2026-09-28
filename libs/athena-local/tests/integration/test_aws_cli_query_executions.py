"""The AWS CLI athena query-execution examples over the live stack.

The start/get/list/stop-query-execution + get-query-results doc chains,
driven the same way as ``test_aws_cli_consumer`` — the real ``aws`` binary
against the in-process emulator with compose moto as shared data plane.
"""

from __future__ import annotations

import time

import pytest
from tests.integration._cli_examples import load_example
from tests.integration._cli_harness import (
    CliStack,
    as_dict,
    as_list,
    as_str,
    cli_scope,
    parsed_json,
    substitute_tokens,
)
from tests.integration.conftest import LiveAthenaServer

SAMPLE_QE_ID = "a1b2c3d4-5678-90ab-cdef-EXAMPLE11111"
SAMPLE_QE_ID_2 = "a1b2c3d4-5678-90ab-cdef-EXAMPLE22222"


def _create_admin_workgroup(stack: CliStack) -> None:
    # The docs run queries under AthenaAdmin; give it the result location
    # the DML writes to (request → workgroup fallback, query_executions).
    created = stack.run(
        "athena",
        "create-work-group",
        "--name",
        "AthenaAdmin",
        "--configuration",
        f"ResultConfiguration={{OutputLocation={stack.harness.prefix}}}",
        "--description",
        "cli-example seed",
    )
    assert created.returncode == 0, created.stderr


def _run_ddl_database_example(stack: CliStack, db: str) -> str:
    # start-query-execution example 2: create database if not exists.
    result = stack.run(
        *substitute_tokens(
            load_example("start-query-execution")[1],
            fragments={"newdb": db},
        )
    )
    assert result.returncode == 0, result.stderr
    ddl_id = as_str(parsed_json(result)["QueryExecutionId"])
    execution = stack.wait_terminal(ddl_id)
    assert execution["Status"]["State"] == "SUCCEEDED"
    assert execution["StatementType"] == "DDL"
    location = as_str(
        as_dict(execution["ResultConfiguration"])["OutputLocation"]
    )
    assert location.endswith(f"{ddl_id}.txt")
    return ddl_id


def _seed_cloudfront_logs(stack: CliStack, bucket: str, db: str) -> str:
    # The doc SELECT needs a cloudfront_logs table; CTAS the seed data.
    # The WHERE clause references method even though it is not selected,
    # so the VALUES columns include it.
    seed_sql = (
        "CREATE TABLE cloudfront_logs WITH (external_location = "
        f"'s3://{bucket}/cloudfront_logs/', format = 'PARQUET') AS "
        "SELECT * FROM (VALUES "
        "('2023-01-01', 'SFO', 'GET', 'Chrome/1', '/index.html', '200'), "
        "('2023-01-02', 'JFK', 'POST', 'Safari/1', '/login', '403')) "
        "AS t(date, location, method, browser, uri, status)"
    )
    seeded = stack.run(
        "athena",
        "start-query-execution",
        "--query-string",
        seed_sql,
        "--work-group",
        "AthenaAdmin",
        "--query-execution-context",
        f"Database={db},Catalog=AwsDataCatalog",
    )
    assert seeded.returncode == 0, seeded.stderr
    seed_id = as_str(parsed_json(seeded)["QueryExecutionId"])
    assert stack.wait_terminal(seed_id)["Status"]["State"] == "SUCCEEDED"
    return seed_id


def _run_dml_select_example(stack: CliStack, bucket: str, db: str) -> str:
    # start-query-execution example 1: the documented SELECT, with the
    # sample database and the strict-engine status comparison swapped.
    example_one = substitute_tokens(
        load_example("start-query-execution")[0],
        exact={
            "Database=cflogsdatabase,Catalog=AwsDataCatalog": (
                f"Database={db},Catalog=AwsDataCatalog"
            )
        },
        fragments={"status = 200": "status = '200'"},
    )
    result = stack.run(*example_one)
    assert result.returncode == 0, result.stderr
    dml_id = as_str(parsed_json(result)["QueryExecutionId"])

    begun = time.monotonic()
    dml_execution = stack.wait_terminal(dml_id)
    # The measured DML turn-around feeds the close-out note only; no
    # latency bound is asserted (Trino timings vary by machine).
    latency_ms = int((time.monotonic() - begun) * 1000)
    assert latency_ms >= 0

    assert dml_execution["Status"]["State"] == "SUCCEEDED"
    assert dml_execution["StatementType"] == "DML"
    location = as_str(
        as_dict(dml_execution["ResultConfiguration"])["OutputLocation"]
    )
    assert location.endswith(f"{dml_id}.csv")
    stack.harness.s3.head_object(Bucket=bucket, Key=f"results/{dml_id}.csv")
    return dml_id


def _assert_doc_result_rows(stack: CliStack, dml_id: str) -> None:
    # get-query-results example: header row then the one SFO row.
    result = stack.run(
        *substitute_tokens(
            load_example("get-query-results")[0],
            exact={SAMPLE_QE_ID: dml_id},
        )
    )
    result_set = as_dict(parsed_json(result)["ResultSet"])
    rows = [
        as_list(as_dict(row)["Data"]) for row in as_list(result_set["Rows"])
    ]
    values = [
        [as_str(as_dict(cell)["VarCharValue"]) for cell in row] for row in rows
    ]
    assert values[0] == ["date", "location", "browser", "uri", "status"]
    assert values[1] == [
        "2023-01-01",
        "SFO",
        "Chrome/1",
        "/index.html",
        "200",
    ]


def _run_view_example(stack: CliStack, db: str) -> str:
    # start-query-execution example 3: CREATE OR REPLACE VIEW → DDL .txt.
    # The doc command names no workgroup, so it lands on the default
    # `primary` — real Athena's primary has a service-default output
    # bucket the emulator deliberately does not model, so the chain
    # configures one via update-work-group first.
    configured = stack.run(
        "athena",
        "update-work-group",
        "--work-group",
        "primary",
        "--configuration-updates",
        f"ResultConfigurationUpdates={{OutputLocation={stack.harness.prefix}}}",
    )
    assert configured.returncode == 0, configured.stderr

    example_three = substitute_tokens(
        load_example("start-query-execution")[2],
        exact={"Database=cflogsdatabase": f"Database={db}"},
    )
    result = stack.run(*example_three)
    assert result.returncode == 0, result.stderr
    view_id = as_str(parsed_json(result)["QueryExecutionId"])
    view_execution = stack.wait_terminal(view_id)
    assert view_execution["Status"]["State"] == "SUCCEEDED"
    location = as_str(
        as_dict(view_execution["ResultConfiguration"])["OutputLocation"]
    )
    assert location.endswith(f"{view_id}.txt")
    return view_id


def _assert_execution_listings(
    stack: CliStack, expected_ids: set[str], view_id: str
) -> None:
    # list-query-executions example (AthenaAdmin, max 10, paginated).
    result = stack.run(*load_example("list-query-executions")[0])
    listed = {
        as_str(entry)
        for entry in as_list(parsed_json(result)["QueryExecutionIds"])
    }
    assert expected_ids <= listed
    # The view ran under the default primary workgroup, and the list is
    # workgroup-scoped, so it appears on the primary listing instead.
    primary_list = stack.run(
        "athena", "list-query-executions", "--work-group", "primary"
    )
    assert view_id in {
        as_str(entry)
        for entry in as_list(parsed_json(primary_list)["QueryExecutionIds"])
    }


def _assert_batch_get_execution(stack: CliStack, dml_id: str) -> None:
    # batch-get-query-execution example: created + a doc sample ID.
    result = stack.run(
        *substitute_tokens(
            load_example("batch-get-query-execution")[0],
            exact={SAMPLE_QE_ID: dml_id},
        )
    )
    found = as_list(parsed_json(result)["QueryExecutions"])
    assert [as_dict(entry)["QueryExecutionId"] for entry in found] == [dml_id]
    unprocessed = {
        as_str(as_dict(entry)["QueryExecutionId"])
        for entry in as_list(
            parsed_json(result)["UnprocessedQueryExecutionIds"]
        )
    }
    assert unprocessed == {SAMPLE_QE_ID_2}


def _stop_slow_query_example(stack: CliStack) -> None:
    # stop-query-execution example: cancel a running query → CANCELLED.
    # Trino caps sequence() at 10000 entries (measured), so the long query
    # is three capped unnests cross-joined (~1e12 probes) — it cannot
    # finish within the CLI round-trip before the stop lands, and Trino
    # aborts it promptly once the DELETE cancel arrives.
    slow_sql = (
        "SELECT count(*) FROM unnest(sequence(1, 10000)) a "
        "CROSS JOIN unnest(sequence(1, 10000)) b "
        "CROSS JOIN unnest(sequence(1, 10000)) c"
    )
    result = stack.run(
        "athena",
        "start-query-execution",
        "--query-string",
        slow_sql,
        "--work-group",
        "AthenaAdmin",
    )
    assert result.returncode == 0, result.stderr
    slow_id = as_str(parsed_json(result)["QueryExecutionId"])

    stopped = stack.run(
        *substitute_tokens(
            load_example("stop-query-execution")[0],
            exact={SAMPLE_QE_ID: slow_id},
        )
    )
    assert stopped.returncode == 0, stopped.stderr
    cancelled = stack.wait_terminal(slow_id)
    assert cancelled["Status"]["State"] == "CANCELLED"


def test_cli_query_execution_examples(
    live_athena_server: LiveAthenaServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """start/get/results/list/batch-get/stop over real Trino + moto artifacts."""
    with cli_scope(live_athena_server, monkeypatch, "cs3query") as stack:
        bucket = stack.harness.bucket
        db = f"cflogsdatabase_{stack.harness.database.split('_', 1)[1]}"

        _create_admin_workgroup(stack)
        ddl_id = _run_ddl_database_example(stack, db)
        seed_id = _seed_cloudfront_logs(stack, bucket, db)
        dml_id = _run_dml_select_example(stack, bucket, db)
        _assert_doc_result_rows(stack, dml_id)
        view_id = _run_view_example(stack, db)
        _assert_execution_listings(stack, {ddl_id, seed_id, dml_id}, view_id)
        _assert_batch_get_execution(stack, dml_id)
        _stop_slow_query_example(stack)
