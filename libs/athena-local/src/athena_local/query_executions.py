"""Query-plane operations: handlers bound into the dispatch registry.

Each handler parses its request payload, delegates lifecycle semantics to
``QueryExecutor`` (ADR-0009) and reads to ``ExecutionStore``, and returns the
operation's output object. Registration is explicit (composition root:
``main.py``) so handlers stay injectable and tests bind their own stores.
``StartQueryExecution`` and ``StopQueryExecution`` are coroutine handlers:
``dispatch`` awaits them so start can run the executor's Trino preflight
and stop can drive the Trino DELETE through the async executor.
Inline ``GetQueryResults``/``GetQueryRuntimeStatistics`` live in
``query_results`` — registration still happens here so ``main`` keeps one
call site for all seven query-plane ops.
"""

from __future__ import annotations

from athena_local.common_schemas import (
    ResultConfiguration,
    parse_result_configuration,
    parse_result_reuse_configuration,
)
from athena_local.data_catalog_state import (
    DataCatalogStore,
    ensure_executable_catalog,
)
from athena_local.dispatch import register_handler
from athena_local.errors import InvalidRequestException
from athena_local.executions import ExecutionStore
from athena_local.executor import QueryExecutor
from athena_local.prepared_execution import resolve_execute_statement
from athena_local.query_results import (
    get_query_results,
    get_query_runtime_statistics,
)
from athena_local.request_fields import (
    as_object,
    member,
    optional_max_results,
    optional_string,
    optional_string_list,
    required_string,
    required_string_list,
)
from athena_local.state import (
    PRIMARY_WORKGROUP_NAME,
    PreparedStatementStore,
    WorkGroupRecord,
    WorkGroupStore,
    ensure_workgroup_enabled,
)
from athena_local.statement_classification import classify_statement

# Canonical-model QueryString bound (service-2.json): real Athena rejects a
# longer statement at submit.
MAX_QUERY_STRING_LENGTH = 262144

# Model IdempotencyToken bound (service-2.json); an out-of-bounds token —
# including the empty string — 400s so it can never dedupe submissions.
MAX_CLIENT_REQUEST_TOKEN_LENGTH = 36


def _optional_client_request_token(
    payload: dict[str, object] | None,
) -> str | None:
    """ClientRequestToken under the model's IdempotencyToken 1..36 bound."""
    if payload is None:
        return None
    token = optional_string(payload, "ClientRequestToken")
    if token is None:
        return None
    if not 1 <= len(token) <= MAX_CLIENT_REQUEST_TOKEN_LENGTH:
        raise InvalidRequestException(
            f"ClientRequestToken must be between 1 and "
            f"{MAX_CLIENT_REQUEST_TOKEN_LENGTH} characters, "
            f"got {len(token)}"
        )
    return token


def _query_execution_context(
    payload: dict[str, object] | None,
) -> tuple[str | None, str | None]:
    raw = member(payload, "QueryExecutionContext")
    if raw is None:
        return None, None
    body = as_object(raw, "QueryExecutionContext")
    return (
        _unquoted_identifier(optional_string(body, "Database")),
        optional_string(body, "Catalog"),
    )


def _unquoted_identifier(value: str | None) -> str | None:
    """Strip Athena's identifier quoting from a wire name.

    awswrangler sends the Database context backticked
    (``awswrangler/athena/_utils.py:660-661``); the name is stored on the
    record and drives both Trino's session schema and Glue lookups, which
    expect the bare name.
    """
    if value is None or len(value) < 2:
        return value
    if (value[0], value[-1]) in {("`", "`"), ('"', '"')}:
        return value[1:-1]
    return value


def _is_managed_workgroup(workgroup_record: WorkGroupRecord) -> bool:
    """Whether the workgroup owns its query results in Athena-managed storage."""
    managed = (
        workgroup_record.configuration.managed_query_results_configuration
    )
    return managed is not None and managed.enabled is True


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
    A managed-results workgroup short-circuits both: the service model
    forbids an OutputLocation on it and wrangler's managed path
    (``_utils.py:105-109``) sends no ResultConfiguration at all, so the
    execution stores an empty configuration — the wire then reports a
    ResultConfiguration member without OutputLocation, and the executor
    skips S3 artifacts (ADR-0011).
    """
    if _is_managed_workgroup(workgroup_record):
        return ResultConfiguration()
    workgroup_location = _workgroup_output_location(workgroup_record)
    enforced = (
        workgroup_record.configuration.enforce_work_group_configuration is True
    )
    request_location = (
        request_configuration.output_location
        if request_configuration is not None
        else None
    )
    output_location = request_location or workgroup_location
    if enforced and workgroup_location is not None:
        output_location = workgroup_location
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
    prepared_statement_store: PreparedStatementStore | None = None,
    data_catalog_store: DataCatalogStore | None = None,
) -> dict[str, object]:
    """Run StartQueryExecution: validate, create a QUEUED execution, return its ID.

    The executor's preflight (ADR-0009 #2) is awaited here, so a syntactically
    invalid query answers the exact Athena 400 before any execution exists
    (error_mapping) and the ID is otherwise returned without waiting
    for the query to complete. An ``EXECUTE`` query is resolved against the
    workgroup's prepared statement store first: a missing statement or
    parameter-count mismatch starts the execution as a FAILED record instead
    of a 400, exactly like real Athena, while a successful resolution supplies
    both the SQL the executor submits and its classification.
    """
    workgroup = (
        optional_string(payload, "WorkGroup")
        if isinstance(payload, dict)
        else None
    ) or PRIMARY_WORKGROUP_NAME
    workgroup_record = workgroup_store.get(workgroup)
    ensure_workgroup_enabled(workgroup_store, workgroup)
    database, catalog = _query_execution_context(payload)
    if catalog is not None:
        # The model's context member names "the data catalog used in the
        # query execution" (service-2.json): an unregistered or non-GLUE
        # catalog is rejected at submit rather than silently executed on
        # the emulator's Glue-backed catalog.
        ensure_executable_catalog(
            data_catalog_store or DataCatalogStore(), catalog
        )
    query = required_string(payload, "QueryString")
    if len(query) > MAX_QUERY_STRING_LENGTH:
        raise InvalidRequestException(
            f"QueryString length {len(query)} exceeds the maximum "
            f"{MAX_QUERY_STRING_LENGTH} characters"
        )
    execution_parameters = optional_string_list(payload, "ExecutionParameters")
    client_request_token = _optional_client_request_token(payload)
    resolution = resolve_execute_statement(
        prepared_statement_store or PreparedStatementStore(),
        workgroup,
        query,
        execution_parameters,
    )
    record = await executor.start(
        query=query,
        workgroup=workgroup,
        database=database,
        catalog=catalog,
        result_configuration=_effective_result_configuration(
            parse_result_configuration(member(payload, "ResultConfiguration")),
            workgroup_record,
        ),
        managed_results=_is_managed_workgroup(workgroup_record),
        execution_parameters=execution_parameters,
        # A retried token replays the original execution instead of
        # re-running — the model marks the op idempotent (service-2.json);
        # the executor owns the lookup.
        client_request_token=client_request_token,
        # Classified at submit, like real Athena: StatementType and
        # SubstatementType are reported even when the query later fails. A
        # resolved EXECUTE reports its bound statement's classification — an
        # EXECUTE-of-SELECT answers DML/SELECT so the ``.csv`` artifact
        # naming wrangler gates on applies — while a failed resolution keeps
        # the submitted EXECUTE text's UTILITY classification.
        statement_classification=(
            resolution.statement_classification
            if resolution.failure_reason is None
            else classify_statement(query)
        ),
        resolved_statement=(
            resolution.statement
            if resolution.failure_reason is None
            and resolution.statement != query
            else None
        ),
        resolution_failure_reason=resolution.failure_reason,
        result_reuse_configuration=parse_result_reuse_configuration(
            member(payload, "ResultReuseConfiguration")
        ),
    )
    return {"QueryExecutionId": record.query_execution_id}


def get_query_execution(
    store: ExecutionStore, payload: dict[str, object] | None
) -> dict[str, object]:
    return {
        "QueryExecution": store.get(
            required_string(payload, "QueryExecutionId")
        ).to_payload()
    }


def batch_get_query_execution(
    store: ExecutionStore, payload: dict[str, object] | None
) -> dict[str, object]:
    query_ids = required_string_list(
        payload, "QueryExecutionIds", max_length=MAX_BATCH_QUERY_EXECUTIONS
    )
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


def list_query_executions(
    store: ExecutionStore, payload: dict[str, object] | None
) -> dict[str, object]:
    """Run ListQueryExecutions: IDs per workgroup, most recent first.

    wrangler's Athena cache probe paginates this op and batch_gets each ID
    (awswrangler/athena/_cache.py:113-129); WorkGroup defaults to ``primary``
    exactly as the model documents. The slice semantics mirror the named
    query store's list so botocore's paginator merges pages losslessly.
    Empty bodies answer the defaults rather than crashing, like every other
    list op (dispatch/parse_body returns None for empty requests).
    """
    body = payload or {}
    workgroup = optional_string(body, "WorkGroup") or "primary"
    max_results = optional_max_results(
        body, "MaxResults", MAX_LIST_EXECUTIONS, minimum=0
    )
    next_token = optional_string(body, "NextToken")
    execution_ids, next_token_out = store.list_execution_ids(
        workgroup=workgroup,
        max_results=max_results,
        next_token=next_token,
    )
    output: dict[str, object] = {"QueryExecutionIds": execution_ids}
    if next_token_out is not None:
        output["NextToken"] = next_token_out
    return output


async def stop_query_execution(
    executor: QueryExecutor, payload: dict[str, object] | None
) -> dict[str, object]:
    """Run StopQueryExecution: cancel the execution, answer with {}(model).

    The model marks the op idempotent: stopping a terminal execution is a
    200 no-op — the executor returns it unchanged rather than transitioning.
    """
    await executor.cancel(required_string(payload, "QueryExecutionId"))
    return {}


MAX_LIST_EXECUTIONS = 50  # model MaxQueryExecutionsCount (service-2.json)
MAX_BATCH_QUERY_EXECUTIONS = 50  # model QueryExecutionIdList max


def register_query_execution_handlers(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroup_store: WorkGroupStore,
    prepared_statement_store: PreparedStatementStore | None = None,
    data_catalog_store: DataCatalogStore | None = None,
) -> None:
    """Bind the seven query-plane operations (explicit wiring in ``main.py``).

    ``prepared_statement_store`` feeds EXECUTE resolution in
    ``StartQueryExecution``; a missing store means no statement exists
    in any workgroup, so every EXECUTE fails resolution as not-found.
    ``data_catalog_store`` validates ``QueryExecutionContext.Catalog`` at
    submit; a missing store still admits the seeded ``AwsDataCatalog``.
    """
    register_handler(
        "StartQueryExecution",
        lambda payload: start_query_execution(
            executor,
            workgroup_store,
            payload,
            prepared_statement_store=prepared_statement_store,
            data_catalog_store=data_catalog_store,
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
        "ListQueryExecutions",
        lambda payload: list_query_executions(store, payload),
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
