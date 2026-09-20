"""Thin typed client over the Trino statement protocol (ADR-0001).

Stateless REST API (trino.io ``develop/client-protocol.html``): ``POST
/v1/statement`` runs the SQL in the request body and returns a
``QueryResults`` document; the client then ``GET``s each ``nextUri`` until a
document carries none, and ``DELETE``s the ``nextUri`` to cancel. The emulator
executor (ADR-0009) drives queries through this client, so handlers never see
Trino types (architecture §8.5). A failed statement arrives as a 200 document
whose ``error`` field is populated — that is carried in :class:`TrinoPage` as
data for the error mapper; only transport-level failures raise
:class:`TrinoTransportError`.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

import httpx

TRINO_STATEMENT_PATH = "/v1/statement"
TRINO_CONTENT_TYPE = "text/plain; charset=utf-8"
TRINO_TIMEOUT_SECONDS = 300.0
TRINO_MAX_ATTEMPTS = 2
TRINO_RETRYABLE_STATUSES = frozenset({429, 502, 503, 504})
TRINO_RETRY_DELAY_SECONDS = 0.1
TRINO_RETRY_AFTER_CAP_SECONDS = 60.0


class TrinoTransportError(Exception):
    """Trino is unreachable or answered outside the statement protocol."""


@dataclass(frozen=True)
class TrinoColumn:
    """A ``QueryResults`` columns entry (name + type tag)."""

    name: str
    column_type: str


@dataclass(frozen=True)
class TrinoQueryError:
    """A failed statement's ``QueryError`` record — data, not an exception."""

    message: str
    error_type: str
    error_name: str


@dataclass(frozen=True)
class TrinoPage:
    """One ``QueryResults`` document from the statement protocol."""

    query_id: str
    next_uri: str | None
    update_type: str | None
    columns: list[TrinoColumn]
    data: list[list[object]]
    stats: dict[str, object]
    error: TrinoQueryError | None

    @property
    def finished(self) -> bool:
        return self.next_uri is None


def create_trino_client(base_url: str) -> TrinoClient:
    """A production client with the statement-protocol request timeout."""
    return TrinoClient(
        base_url, httpx.AsyncClient(timeout=TRINO_TIMEOUT_SECONDS)
    )


class TrinoClient:
    """Issue statements against a Trino coordinator over the statement protocol.

    Headers to Trino are session-scoped (X-Trino-Catalog/-Schema/-User) and only
    required on the initial POST, per the client-protocol docs.
    """

    def __init__(self, base_url: str, http_client: httpx.AsyncClient) -> None:
        self._statement_url = f"{base_url.rstrip('/')}{TRINO_STATEMENT_PATH}"
        self._http_client = http_client

    async def submit_statement(
        self, query: str, catalog: str, schema: str, user: str
    ) -> TrinoPage:
        """POST ``query`` to ``/v1/statement`` and return the first page."""
        headers = {
            "X-Trino-User": user,
            "X-Trino-Catalog": catalog,
            "X-Trino-Schema": schema,
            "Content-Type": TRINO_CONTENT_TYPE,
        }
        response = await self._request(
            "POST", self._statement_url, content=query, headers=headers
        )
        return _parse_page(response)

    async def fetch_next(self, next_uri: str) -> TrinoPage:
        """GET ``next_uri`` and return the next page of the same statement."""
        response = await self._request("GET", next_uri)
        return _parse_page(response)

    async def cancel(self, next_uri: str) -> None:
        """DELETE ``next_uri`` to cancel the running statement (204 = success)."""
        response = await self._request("DELETE", next_uri)
        if response.status_code != 204:
            raise TrinoTransportError(
                f"Trino DELETE {next_uri} answered {response.status_code}, "
                "expected 204"
            )

    async def _request(
        self,
        method: str,
        url: str,
        content: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        attempt = 0
        while True:
            attempt += 1
            response = await self._send(method, url, content, headers)
            if attempt >= TRINO_MAX_ATTEMPTS or not _should_retry(response):
                return response
            await asyncio.sleep(_retry_delay(response))

    async def _send(
        self,
        method: str,
        url: str,
        content: str | None,
        headers: dict[str, str] | None,
    ) -> httpx.Response:
        try:
            return await self._http_client.request(
                method, url, content=content, headers=headers
            )
        except httpx.TransportError as error:
            raise TrinoTransportError(
                f"Trino unreachable via {method} {url}: {error}"
            ) from error


def _should_retry(response: httpx.Response) -> bool:
    if response.status_code in TRINO_RETRYABLE_STATUSES:
        return True
    return response.status_code == 200 and not response.text.strip()


def _retry_delay(response: httpx.Response) -> float:
    if response.status_code == 429:
        return _retry_after_seconds(response.headers.get("Retry-After"))
    return TRINO_RETRY_DELAY_SECONDS


def _retry_after_seconds(header_value: str | None) -> float:
    if header_value is not None and header_value.strip().isdigit():
        return min(float(header_value), TRINO_RETRY_AFTER_CAP_SECONDS)
    return TRINO_RETRY_DELAY_SECONDS


def _parse_page(response: httpx.Response) -> TrinoPage:
    if response.status_code != 200:
        raise TrinoTransportError(
            f"Trino answered {response.status_code} for {response.url}: "
            f"{response.text[:200]}"
        )
    if not response.text.strip():
        raise TrinoTransportError(
            f"Trino answered 200 with an empty body for {response.url}"
        )
    try:
        payload = json.loads(response.text)
    except json.JSONDecodeError as error:
        raise TrinoTransportError(
            f"Trino answered a non-JSON body for {response.url}: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise TrinoTransportError(
            f"Trino answered {type(payload).__name__} for {response.url}, "
            "expected a JSON object"
        )
    query_id = payload.get("id")
    if not isinstance(query_id, str):
        raise TrinoTransportError(
            f"Trino answered a QueryResults with id {query_id!r}, "
            "expected a string"
        )
    return TrinoPage(
        query_id=query_id,
        next_uri=_optional_string(payload, "nextUri"),
        update_type=_optional_string(payload, "updateType"),
        columns=_parse_columns(payload.get("columns")),
        data=_parse_rows(payload.get("data")),
        stats=_parse_stats(payload.get("stats")),
        error=_parse_error(payload.get("error")),
    )


def _optional_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) else None


def _parse_columns(raw_columns: object) -> list[TrinoColumn]:
    if not isinstance(raw_columns, list):
        return []
    columns: list[TrinoColumn] = []
    for column in raw_columns:
        if isinstance(column, dict):
            columns.append(
                TrinoColumn(
                    name=str(column.get("name", "")),
                    column_type=str(column.get("type", "")),
                )
            )
    return columns


def _parse_rows(raw_rows: object) -> list[list[object]]:
    if not isinstance(raw_rows, list):
        return []
    rows: list[list[object]] = []
    for row in raw_rows:
        if isinstance(row, list):
            rows.append(row)
    return rows


def _parse_stats(raw_stats: object) -> dict[str, object]:
    if not isinstance(raw_stats, dict):
        return {}
    return dict(raw_stats)


def _parse_error(raw_error: object) -> TrinoQueryError | None:
    if not isinstance(raw_error, dict):
        return None
    return TrinoQueryError(
        message=_error_field(raw_error, "message"),
        error_type=_error_field(raw_error, "errorType"),
        error_name=_error_field(raw_error, "errorName"),
    )


def _error_field(error: dict[object, object], key: str) -> str:
    value = error.get(key)
    return value if isinstance(value, str) else ""
