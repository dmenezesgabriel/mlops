"""Finished-execution read ops: GetQueryResults and GetQueryRuntimeStatistics.

Inline ``GetQueryResults`` answers from the page the executor stashed before
the terminal transition (ADR-0007, ADR-0009 #4) and paginates it with
``MaxResults``/``NextToken`` per the model's GetQueryResultsInput — a
different contract than ``pagination.offset_page`` (the header row travels
on page zero, the token is a parsed offset, negatives are rejected), which
is why this module keeps its own slicing. Per-type cell serialization
stays a separate concern (``result_shapes`` shapes the cached page; the
VarCharValue rendering below only owns the wire Datum member).
"""

from __future__ import annotations

from athena_local.errors import InvalidRequestException
from athena_local.executions import (
    ExecutionStore,
    QueryExecutionRecord,
)
from athena_local.executor import QueryExecutor
from athena_local.request_fields import (
    member,
    optional_max_results,
    required_string,
)

# Athena's default inline page size; GetQueryResults.MaxResults is bounded by
# the model's MaxQueryResults shape (1..1000).
DEFAULT_MAX_RESULTS = 1000


def get_query_results(
    store: ExecutionStore,
    executor: QueryExecutor,
    payload: dict[str, object] | None,
) -> dict[str, object]:
    """Run GetQueryResults: paginated terminal rows, header on page zero.

    Non-terminal executions raise the exact 400 Athena sends; terminal ones
    answer from the cached final page regardless of the terminal flavor (moto
    never conditions on state at ``moto/athena/models.py:415``, and wrangler
    never reads inline results for a FAILED execution). Pages slice the
    cached rows with ``MaxResults`` (default 1000) and an opaque ``NextToken``
    naming the next data-row offset, so botocore's get_query_results paginator
    — the path wrangler's ``_fetch_api_result`` walks (awswrangler/athena/
    _read.py:335-384) — merges the pages back losslessly.
    """
    query_execution_id = required_string(payload, "QueryExecutionId")
    record = executor.ensure_query_finished(query_execution_id)
    offset = _next_token_offset(payload)
    max_results = _max_results(payload)
    result_set, next_token = _result_page(record, offset, max_results)
    output: dict[str, object] = {"ResultSet": result_set}
    if next_token is not None:
        output["NextToken"] = next_token
    return output


def get_query_runtime_statistics(
    store: ExecutionStore, payload: dict[str, object] | None
) -> dict[str, object]:
    return {
        "QueryRuntimeStatistics": _runtime_statistics_payload(
            store.get(required_string(payload, "QueryExecutionId"))
        )
    }


def _result_page(
    record: QueryExecutionRecord,
    offset: int,
    max_results: int,
) -> tuple[dict[str, object], str | None]:
    """Slice one GetQueryResults page out of the cached rows.

    The header row travels only on page zero (offset 0), matching wrangler's
    first-page strip (awswrangler/athena/_read.py:357,383), and the outgoing
    ``NextToken`` names the next data-row offset exactly when rows remain —
    the condition botocore's paginator keeps polling on. Returns the wire
    ResultSet and the token (None at the end).
    """
    rows = record.result_rows
    end_offset = min(offset + max_results, len(rows))
    next_token = str(end_offset) if end_offset < len(rows) else None
    return _result_set_payload(record, offset, rows[offset:end_offset]), (
        next_token
    )


def _max_results(payload: dict[str, object] | None) -> int:
    """MaxResults with the model's 1..1000 bounds (service-2.json MaxQueryResults).

    An absent MaxResults means Athena's default page of 1000 rows; values
    outside the modeled bounds are rejected with the shaped error so a client
    can never widen a page beyond what the wire declares.
    """
    raw = optional_max_results(payload, "MaxResults", DEFAULT_MAX_RESULTS)
    return DEFAULT_MAX_RESULTS if raw is None else raw


def _next_token_offset(payload: dict[str, object] | None) -> int:
    """Decode an opaque NextToken into the data-row offset it resumes at.

    Tokens are opaque on the wire (model Token); this server issues the next
    zero-based data-row offset as the token and rejects anything it cannot
    decode with the shaped error, mirroring the state store's list pagination.
    """
    raw = member(payload, "NextToken")
    if raw is None:
        return 0
    if not isinstance(raw, str):
        raise InvalidRequestException(
            f"NextToken must be a string, got {raw!r}"
        )
    try:
        offset = int(raw)
    except ValueError:
        raise InvalidRequestException(f"Invalid NextToken: {raw}") from None
    if offset < 0:
        raise InvalidRequestException(f"Invalid NextToken: {raw}")
    return offset


def _result_set_payload(
    record: QueryExecutionRecord,
    offset: int,
    page_rows: list[list[object]],
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    if offset == 0:
        rows.append(
            {
                "Data": [
                    {"VarCharValue": name}
                    for name, _type in record.result_columns
                ]
            }
        )
    for row in page_rows:
        rows.append(
            {
                "Data": [
                    {}
                    if value is None
                    else {"VarCharValue": _cell_value(value)}
                    for value in row
                ]
            }
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
    """The VarCharValue string a cell becomes on the Athena wire.

    Numbers, decimals, dates and timestamps arrive from Trino already shaped
    like Athena's output, so ``str()`` passes them through. Trino sends
    booleans as JSON booleans, which Python renders ``True``/``False`` but
    Athena emits lowercase; normalize the case. Nulls never reach this
    function — ``_result_set_payload`` drops the member instead (the service
    model marks ``Datum.VarCharValue`` optional).
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


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
