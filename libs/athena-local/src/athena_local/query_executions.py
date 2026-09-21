"""Query-plane operations (QE-3): handlers bound into the dispatch registry.

Each handler parses its request payload, delegates lifecycle semantics to
``QueryExecutor`` (ADR-0009) and reads to ``ExecutionStore``, and returns the
operation's output object. Registration is explicit (composition root:
``main.py``) so handlers stay injectable and tests bind their own stores.
``StartQueryExecution`` and ``StopQueryExecution`` are coroutine handlers:
``dispatch`` awaits them so start can run the executor's Trino preflight
(QE-5) and stop can drive the Trino DELETE through the async executor.
Inline ``GetQueryResults``
answers from the page the executor stashed before the terminal transition
(ADR-0007, ADR-0009 #4); pagination, ``MaxResults``, and cell-type
serialization are owned by the artifact slices (AR-3/AR-4).
"""

from __future__ import annotations

from athena_local.common_schemas import (
    ResultConfiguration,
    parse_result_configuration,
)
from athena_local.dispatch import register_handler
from athena_local.errors import InvalidRequestException
from athena_local.executions import (
    ExecutionStore,
    QueryExecutionRecord,
)
from athena_local.executor import QueryExecutor
from athena_local.state import (
    PRIMARY_WORKGROUP_NAME,
    WorkGroupRecord,
    WorkGroupStore,
)
from athena_local.statement_classification import classify_statement


def _member(payload: dict[str, object] | None, member: str) -> object | None:
    if payload is None:
        return None
    return payload.get(member)


def _required_string(payload: dict[str, object] | None, member: str) -> str:
    raw = _member(payload, member)
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidRequestException(
            f"{member} is required and must be a non-empty string, got {raw!r}"
        )
    return raw


def _optional_string(payload: dict[str, object], member: str) -> str | None:
    raw = payload.get(member)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise InvalidRequestException(
            f"{member} must be a string, got {raw!r}"
        )
    return raw


def _required_string_list(
    payload: dict[str, object] | None, member: str
) -> list[str]:
    raw = _member(payload, member)
    if not isinstance(raw, list):
        raise InvalidRequestException(f"{member} must be a list, got {raw!r}")
    if not raw:
        raise InvalidRequestException(f"{member} must not be empty")
    for item in raw:
        if not isinstance(item, str):
            raise InvalidRequestException(
                f"{member} must contain only strings, got {item!r}"
            )
    return [item for item in raw if isinstance(item, str)]


def _optional_string_list(
    payload: dict[str, object] | None, member: str
) -> list[str] | None:
    raw = _member(payload, member)
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise InvalidRequestException(f"{member} must be a list, got {raw!r}")
    for item in raw:
        if not isinstance(item, str):
            raise InvalidRequestException(
                f"{member} must contain only strings, got {item!r}"
            )
    return [item for item in raw if isinstance(item, str)]


def _query_execution_context(
    payload: dict[str, object] | None,
) -> tuple[str | None, str | None]:
    raw = _member(payload, "QueryExecutionContext")
    if raw is None:
        return None, None
    if not isinstance(raw, dict):
        raise InvalidRequestException(
            f"QueryExecutionContext must be a JSON object, got {raw!r}"
        )
    return (
        _optional_string(raw, "Database"),
        _optional_string(raw, "Catalog"),
    )


def _workgroup_output_location(
    workgroup_record: WorkGroupRecord,
) -> str | None:
    if workgroup_record.configuration.result_configuration is None:
        return None
    return workgroup_record.configuration.result_configuration.output_location


def _effective_result_configuration(
    request_configuration: ResultConfiguration | None,
    workgroup_record: WorkGroupRecord,
) -> ResultConfiguration:
    """Apply the workgroup's OutputLocation per Athena's resolution order.

    Athena lets an enforced workgroup's ResultConfiguration override the
    request, and otherwise falls back request → workgroup; wrangler mirrors
    that order in ``_get_s3_output``
    (research_repos/aws-sdk-pandas/awswrangler/athena/_utils.py:49-66).
    """
    workgroup_location = _workgroup_output_location(workgroup_record)
    enforced = (
        workgroup_record.configuration.enforce_work_group_configuration is True
    )
    request_location = (
        request_configuration.output_location
        if request_configuration is not None
        else None
    )
    if enforced and workgroup_location is not None:
        output_location = workgroup_location
    else:
        output_location = request_location or workgroup_location
    if output_location is None:
        raise InvalidRequestException(
            "OutputLocation is required: pass ResultConfiguration."
            f"OutputLocation or configure one on workgroup "
            f"{workgroup_record.name}"
        )
    base = request_configuration or ResultConfiguration()
    return ResultConfiguration(
        output_location=output_location,
        encryption_configuration=base.encryption_configuration,
        expected_bucket_owner=base.expected_bucket_owner,
        acl_configuration=base.acl_configuration,
    )


async def start_query_execution(
    executor: QueryExecutor,
    workgroup_store: WorkGroupStore,
    payload: dict[str, object] | None,
) -> dict[str, object]:
    """Run StartQueryExecution: validate, create a QUEUED execution, return its ID.

    The executor's preflight (ADR-0009 #2) is awaited here, so a syntactically
    invalid query answers the exact Athena 400 before any execution exists
    (error_mapping, QE-5) and the ID is otherwise returned without waiting
    for the query to complete.
    """
    workgroup = (
        _optional_string(payload, "WorkGroup")
        if isinstance(payload, dict)
        else None
    ) or PRIMARY_WORKGROUP_NAME
    workgroup_record = workgroup_store.get(workgroup)
    database, catalog = _query_execution_context(payload)
    query = _required_string(payload, "QueryString")
    record = await executor.start(
        query=query,
        workgroup=workgroup,
        database=database,
        catalog=catalog,
        result_configuration=_effective_result_configuration(
            parse_result_configuration(
                _member(payload, "ResultConfiguration")
            ),
            workgroup_record,
        ),
        execution_parameters=_optional_string_list(
            payload, "ExecutionParameters"
        ),
        # Classified at submit, like real Athena: StatementType and
        # SubstatementType are reported even when the query later fails.
        statement_classification=classify_statement(query),
    )
    return {"QueryExecutionId": record.query_execution_id}


def get_query_execution(
    store: ExecutionStore, payload: dict[str, object] | None
) -> dict[str, object]:
    return {
        "QueryExecution": store.get(
            _required_string(payload, "QueryExecutionId")
        ).to_payload()
    }


def batch_get_query_execution(
    store: ExecutionStore, payload: dict[str, object] | None
) -> dict[str, object]:
    query_ids = _required_string_list(payload, "QueryExecutionIds")
    found, unprocessed = store.batch_get(query_ids)
    output: dict[str, object] = {
        "QueryExecutions": [record.to_payload() for record in found]
    }
    if unprocessed:
        output["UnprocessedQueryExecutionIds"] = [
            {
                "QueryExecutionId": query_id,
                "ErrorCode": "InvalidRequestException",
                "ErrorMessage": f"QueryExecution {query_id} does not exist",
            }
            for query_id in unprocessed
        ]
    return output


async def stop_query_execution(
    executor: QueryExecutor, payload: dict[str, object] | None
) -> dict[str, object]:
    """Run StopQueryExecution: cancel the execution, answer with {}(model)."""
    await executor.cancel(_required_string(payload, "QueryExecutionId"))
    return {}


def get_query_results(
    store: ExecutionStore,
    executor: QueryExecutor,
    payload: dict[str, object] | None,
) -> dict[str, object]:
    """Run GetQueryResults: terminal-only rows with the header first (FR-03).

    Non-terminal executions raise the exact 400 Athena sends; terminal ones
    answer from the cached final page regardless of the terminal flavor (moto
    never conditions on state at ``moto/athena/models.py:415``, and wrangler
    never reads inline results for a FAILED execution).
    """
    query_execution_id = _required_string(payload, "QueryExecutionId")
    record = executor.ensure_query_finished(query_execution_id)
    return {"ResultSet": _result_set_payload(record)}


def get_query_runtime_statistics(
    store: ExecutionStore, payload: dict[str, object] | None
) -> dict[str, object]:
    return {
        "QueryRuntimeStatistics": _runtime_statistics_payload(
            store.get(_required_string(payload, "QueryExecutionId"))
        )
    }


def _result_set_payload(record: QueryExecutionRecord) -> dict[str, object]:
    header_row = {
        "Data": [
            {"VarCharValue": name} for name, _type in record.result_columns
        ]
    }
    rows = [header_row]
    for row in record.result_rows:
        rows.append(
            {"Data": [{"VarCharValue": _cell_value(value)} for value in row]}
        )
    return {
        "Rows": rows,
        "ResultSetMetadata": {
            "ColumnInfo": [
                {"Name": name, "Type": column_type}
                for name, column_type in record.result_columns
            ]
        },
    }


def _cell_value(value: object) -> str:
    # Per-type serialization (decimals, timestamps, booleans) and the
    # absent-key null contract are owned by the artifact slices (AR-4);
    # the plain string form is fixed here.
    return "" if value is None else str(value)


def _runtime_statistics_payload(
    record: QueryExecutionRecord,
) -> dict[str, object]:
    return {
        "Timeline": {
            "EngineExecutionTimeInMillis": (
                record.engine_execution_time_ms or 0
            )
        },
        "Rows": {"InputBytes": record.data_scanned_bytes or 0},
    }


def register_query_execution_handlers(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroup_store: WorkGroupStore,
) -> None:
    """Bind the six query-plane operations (explicit wiring in ``main.py``)."""
    register_handler(
        "StartQueryExecution",
        lambda payload: start_query_execution(
            executor, workgroup_store, payload
        ),
    )
    register_handler(
        "GetQueryExecution",
        lambda payload: get_query_execution(store, payload),
    )
    register_handler(
        "BatchGetQueryExecution",
        lambda payload: batch_get_query_execution(store, payload),
    )
    register_handler(
        "StopQueryExecution",
        lambda payload: stop_query_execution(executor, payload),
    )
    register_handler(
        "GetQueryResults",
        lambda payload: get_query_results(store, executor, payload),
    )
    register_handler(
        "GetQueryRuntimeStatistics",
        lambda payload: get_query_runtime_statistics(store, payload),
    )
