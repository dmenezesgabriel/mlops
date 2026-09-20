"""Unit tests for the Trino statement client (QE-1, ADR-0001).

The client is the only module that touches the Trino statement protocol, so
these tests pin the wire contract against ``httpx.MockTransport`` with a
named fake handler (F.I.R.S.T., no docker): the initial POST body/headers,
``nextUri`` polling, ``DELETE`` cancellation, retry on 429/502/503/504 and
empty-200 bodies, a failed query's ``error`` carried in the page as data, and
transport failures raising ``TrinoTransportError``.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from athena_local.trino_client import (
    TRINO_MAX_ATTEMPTS,
    TrinoClient,
    TrinoColumn,
    TrinoTransportError,
    _retry_after_seconds,
)

BASE_URL = "http://trino:8080"
QUERY_ID = "20260920_000000_00000_a1b2c3"
FIRST_NEXT_URI = f"{BASE_URL}/v1/statement/{QUERY_ID}/1"


def query_results_document(  # noqa: PLR0913
    *,
    next_uri: str | None = FIRST_NEXT_URI,
    columns: list[dict[str, object]] | None = None,
    data: list[list[object]] | None = None,
    update_type: str | None = None,
    error: dict[str, object] | None = None,
) -> dict[str, object]:
    """A realistic ``QueryResults`` JSON document (id/stats/infoUri required)."""
    document: dict[str, object] = {
        "id": QUERY_ID,
        "infoUri": "http://trino:8080/ui/query.html",
        "stats": {"state": "RUNNING"},
    }
    if next_uri is not None:
        document["nextUri"] = next_uri
    if columns is not None:
        document["columns"] = columns
    if data is not None:
        document["data"] = data
    if update_type is not None:
        document["updateType"] = update_type
    if error is not None:
        document["error"] = error
    return document


class ScriptedTrinoHandler:
    """MockTransport handler serving a script of ``(status, body, headers)``."""

    def __init__(
        self, responses: list[tuple[int, str, dict[str, str] | None]]
    ) -> None:
        self._responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, body, headers = self._responses.pop(0)
        return httpx.Response(
            status, text=body, headers=headers, request=request
        )


class RefusingTrinoHandler:
    """MockTransport handler that simulates an unreachable coordinator."""

    def __call__(self, request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            f"connection refused for {request.url}", request=request
        )


def test_submit_statement_posts_query_with_session_headers() -> None:
    handler = ScriptedTrinoHandler(
        [(200, json.dumps(query_results_document()), None)]
    )
    client = TrinoClient(
        BASE_URL, httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    page = asyncio.run(
        client.submit_statement(
            "SELECT 1", catalog="hive", schema="analytics", user="alice"
        )
    )

    request = handler.requests[0]
    assert request.method == "POST"
    assert str(request.url).endswith("/v1/statement")
    assert request.content.decode() == "SELECT 1"
    assert request.headers["X-Trino-User"] == "alice"
    assert request.headers["X-Trino-Catalog"] == "hive"
    assert request.headers["X-Trino-Schema"] == "analytics"
    assert request.headers["content-type"].startswith(
        "text/plain; charset=utf-8"
    )
    assert page.query_id == QUERY_ID
    assert page.next_uri == FIRST_NEXT_URI
    assert page.finished is False
    assert page.stats == {"state": "RUNNING"}
    assert page.error is None


def test_page_carries_columns_data_and_update_type() -> None:
    handler = ScriptedTrinoHandler(
        [
            (
                200,
                json.dumps(
                    query_results_document(
                        next_uri=None,
                        columns=[{"name": "_col0", "type": "varchar"}],
                        data=[["alpha"], [None]],
                        update_type="CREATE TABLE",
                    )
                ),
                None,
            )
        ]
    )
    client = TrinoClient(
        BASE_URL, httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    page = asyncio.run(
        client.submit_statement(
            "CREATE TABLE", catalog="hive", schema="analytics", user="alice"
        )
    )

    assert page.finished is True
    assert page.columns == [TrinoColumn(name="_col0", column_type="varchar")]
    assert page.data == [["alpha"], [None]]
    assert page.update_type == "CREATE TABLE"


def test_fetch_next_gets_next_uri_until_finished() -> None:
    handler = ScriptedTrinoHandler(
        [
            (
                200,
                json.dumps(
                    query_results_document(next_uri=FIRST_NEXT_URI, data=[[1]])
                ),
                None,
            ),
            (
                200,
                json.dumps(query_results_document(next_uri=None, data=[[2]])),
                None,
            ),
        ]
    )
    client = TrinoClient(
        BASE_URL, httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    asyncio.run(
        client.submit_statement(
            "SELECT 1", catalog="hive", schema="analytics", user="alice"
        )
    )
    final_page = asyncio.run(client.fetch_next(FIRST_NEXT_URI))

    assert final_page.finished is True
    assert final_page.data == [[2]]
    request = handler.requests[1]
    assert request.method == "GET"
    assert str(request.url).endswith(FIRST_NEXT_URI)


def test_cancel_deletes_next_uri() -> None:
    handler = ScriptedTrinoHandler([(204, "", None)])
    client = TrinoClient(
        BASE_URL, httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    asyncio.run(client.cancel(FIRST_NEXT_URI))

    request = handler.requests[0]
    assert request.method == "DELETE"
    assert str(request.url).endswith(FIRST_NEXT_URI)


def test_cancel_non_204_raises_transport_error() -> None:
    handler = ScriptedTrinoHandler([(200, "", None), (200, "", None)])
    client = TrinoClient(
        BASE_URL, httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(TrinoTransportError, match="expected 204"):
        asyncio.run(client.cancel(FIRST_NEXT_URI))


def test_failed_query_error_is_carried_in_page() -> None:
    handler = ScriptedTrinoHandler(
        [
            (
                200,
                json.dumps(
                    query_results_document(
                        next_uri=None,
                        error={
                            "message": "Column 'missing' cannot be resolved",
                            "errorCode": 1,
                            "errorName": "COLUMN_NOT_FOUND",
                            "errorType": "USER_ERROR",
                        },
                    )
                ),
                None,
            )
        ]
    )
    client = TrinoClient(
        BASE_URL, httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    page = asyncio.run(
        client.submit_statement(
            "SELECT missing FROM t",
            catalog="hive",
            schema="analytics",
            user="alice",
        )
    )

    assert page.finished is True
    assert page.error is not None
    assert page.error.message == "Column 'missing' cannot be resolved"
    assert page.error.error_type == "USER_ERROR"
    assert page.error.error_name == "COLUMN_NOT_FOUND"


def test_non_retryable_status_raises_transport_error() -> None:
    handler = ScriptedTrinoHandler([(500, "boom", None)])
    client = TrinoClient(
        BASE_URL, httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(TrinoTransportError, match="500"):
        asyncio.run(
            client.submit_statement(
                "SELECT 1", catalog="hive", schema="analytics", user="alice"
            )
        )


def test_retries_intermittent_502_then_succeeds() -> None:
    handler = ScriptedTrinoHandler(
        [
            (502, "bad gateway", None),
            (200, json.dumps(query_results_document(next_uri=None)), None),
        ]
    )
    client = TrinoClient(
        BASE_URL, httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    page = asyncio.run(
        client.submit_statement(
            "SELECT 1", catalog="hive", schema="analytics", user="alice"
        )
    )

    assert len(handler.requests) == 2
    assert page.finished is True


def test_retry_exhausted_on_503_raises_transport_error() -> None:
    handler = ScriptedTrinoHandler(
        [(503, "service unavailable", None), (503, "still down", None)]
    )
    client = TrinoClient(
        BASE_URL, httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(TrinoTransportError, match="503"):
        asyncio.run(
            client.submit_statement(
                "SELECT 1", catalog="hive", schema="analytics", user="alice"
            )
        )

    assert len(handler.requests) == TRINO_MAX_ATTEMPTS


def test_retries_429_honoring_retry_after() -> None:
    handler = ScriptedTrinoHandler(
        [
            (429, "throttled", {"Retry-After": "0"}),
            (200, json.dumps(query_results_document(next_uri=None)), None),
        ]
    )
    client = TrinoClient(
        BASE_URL, httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    page = asyncio.run(
        client.submit_statement(
            "SELECT 1", catalog="hive", schema="analytics", user="alice"
        )
    )

    assert len(handler.requests) == 2
    assert page.finished is True


def test_empty_200_body_is_retried_then_transport_error() -> None:
    handler = ScriptedTrinoHandler([(200, "", None), (200, "", None)])
    client = TrinoClient(
        BASE_URL, httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(TrinoTransportError, match="empty body"):
        asyncio.run(
            client.submit_statement(
                "SELECT 1", catalog="hive", schema="analytics", user="alice"
            )
        )

    assert len(handler.requests) == TRINO_MAX_ATTEMPTS


def test_non_json_body_raises_transport_error() -> None:
    handler = ScriptedTrinoHandler([(200, "not-json", None)])
    client = TrinoClient(
        BASE_URL, httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(TrinoTransportError, match="non-JSON"):
        asyncio.run(
            client.submit_statement(
                "SELECT 1", catalog="hive", schema="analytics", user="alice"
            )
        )


def test_page_without_id_raises_transport_error() -> None:
    handler = ScriptedTrinoHandler([(200, json.dumps({"stats": {}}), None)])
    client = TrinoClient(
        BASE_URL, httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(TrinoTransportError, match="expected a string"):
        asyncio.run(
            client.submit_statement(
                "SELECT 1", catalog="hive", schema="analytics", user="alice"
            )
        )


def test_connection_failure_raises_transport_error() -> None:
    client = TrinoClient(
        BASE_URL,
        httpx.AsyncClient(
            transport=httpx.MockTransport(RefusingTrinoHandler())
        ),
    )

    with pytest.raises(TrinoTransportError, match="unreachable"):
        asyncio.run(
            client.submit_statement(
                "SELECT 1", catalog="hive", schema="analytics", user="alice"
            )
        )


def test_retry_after_seconds_capped() -> None:
    assert _retry_after_seconds("300") == 60.0
    assert _retry_after_seconds("2") == 2.0
    assert _retry_after_seconds(None) == 0.1
    assert _retry_after_seconds("soon") == 0.1
