"""FastAPI application exposing the Athena JSON-1.1 protocol (ADR-0008).

Service entry point: ``POST /`` catch-all dispatches ``X-Amz-Target`` through
``athena_local.dispatch``; ``GET /health`` is an operational probe for compose
``depends_on``, outside the AWS wire protocol. ``POST /`` is the composition
root for both planes: it owns the in-memory workgroup, named query, prepared
statement, data catalog, and query execution stores and binds their handlers,
and it wires the query executor to the compose Trino coordinator and moto
boundaries (ADR-0009) via ``ATHENA_LOCAL_TRINO_URL`` / ``ATHENA_MOTO_ENDPOINT_URL``.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import Response

from athena_local.artifacts import ArtifactWriter
from athena_local.catalog_metadata import (
    MOTO_ENDPOINT_DEFAULT,
    MOTO_ENDPOINT_ENV,
    register_catalog_metadata_handlers,
)
from athena_local.data_catalog_state import DataCatalogStore
from athena_local.data_catalogs import register_data_catalog_handlers
from athena_local.dispatch import WireResponse, dispatch
from athena_local.engine_versions import register_engine_version_handlers
from athena_local.errors import serialize_error
from athena_local.executions import ExecutionStore
from athena_local.executor import QueryExecutor
from athena_local.glue_proxy import GlueProxy
from athena_local.named_queries import register_named_query_handlers
from athena_local.output_targets import OutputSnapshotter
from athena_local.prepared_statements import (
    register_prepared_statement_handlers,
)
from athena_local.query_executions import register_query_execution_handlers
from athena_local.s3_writer import S3Writer
from athena_local.state import (
    NamedQueryStore,
    PreparedStatementStore,
    WorkGroupStore,
)
from athena_local.tags import register_tag_handlers
from athena_local.trino_client import create_trino_client
from athena_local.workgroups import register_workgroup_handlers

TRINO_URL_ENV = "ATHENA_LOCAL_TRINO_URL"
TRINO_URL_DEFAULT = "http://localhost:8080"


def build_query_executor(
    store: ExecutionStore,
    trino_url: str | None = None,
    moto_endpoint_url: str | None = None,
) -> QueryExecutor:
    """Compose the executor with its production Trino and moto boundaries.

    Endpoint args default to the environment (``ATHENA_LOCAL_TRINO_URL``,
    ``ATHENA_MOTO_ENDPOINT_URL``), falling back to the compose-stack ports
    (trino :8080, moto :5000). Example::

        executor = build_query_executor(execution_store)
    """
    trino_url = trino_url or os.getenv(TRINO_URL_ENV) or TRINO_URL_DEFAULT
    moto_endpoint_url = (
        moto_endpoint_url
        or os.getenv(MOTO_ENDPOINT_ENV)
        or MOTO_ENDPOINT_DEFAULT
    )
    return QueryExecutor(
        store=store,
        client=create_trino_client(trino_url),
        writer=ArtifactWriter(S3Writer.for_endpoint(moto_endpoint_url)),
        snapshotter=OutputSnapshotter(
            glue=GlueProxy.for_endpoint(moto_endpoint_url),
            s3=S3Writer.for_endpoint(moto_endpoint_url),
        ),
    )


app = FastAPI(title="Athena Local Emulator")

workgroup_store = WorkGroupStore()
register_workgroup_handlers(workgroup_store)

named_query_store = NamedQueryStore()
register_named_query_handlers(named_query_store)

prepared_statement_store = PreparedStatementStore()
register_prepared_statement_handlers(prepared_statement_store)

data_catalog_store = DataCatalogStore()
register_data_catalog_handlers(data_catalog_store)

register_catalog_metadata_handlers(data_catalog_store)

register_engine_version_handlers()

register_tag_handlers(workgroup_store, data_catalog_store)

execution_store = ExecutionStore()
executor = build_query_executor(execution_store)
register_query_execution_handlers(execution_store, executor, workgroup_store)


@app.get("/health")  # noqa (route handler bound by FastAPI)
def health() -> dict[str, str]:
    """Liveness probe; intentionally NOT part of the AWS wire protocol."""
    return {"status": "ok"}


@app.post("/")  # noqa (route handler bound by FastAPI)
async def athena_endpoint(request: Request) -> Response:
    """Dispatch a JSON-1.1 request addressed by its X-Amz-Target header."""
    result = await dispatch(
        request.headers.get("x-amz-target"), await request.body()
    )
    if isinstance(result, WireResponse):
        return Response(
            content=result.body,
            status_code=result.status_code,
            headers=result.headers,
        )
    status, headers, body = serialize_error(result)
    return Response(content=body, status_code=status, headers=headers)


def reset_query_plane() -> None:
    """Drop query-execution state and rebind the six query ops to the product.

    Handler-level and live test fixtures temporarily bind bespoke stores and
    writers into the registry; this restores main's composition so later
    requests use the module-level execution store and executor (ADR-0009).
    """
    execution_store.reset()
    register_query_execution_handlers(
        execution_store, executor, workgroup_store
    )
