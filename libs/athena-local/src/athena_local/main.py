"""FastAPI application exposing the Athena JSON-1.1 protocol (ADR-0008).

Service entry point: ``POST /`` catch-all dispatches ``X-Amz-Target`` through
``athena_local.dispatch``; ``GET /health`` is an operational probe for compose
``depends_on``, outside the AWS wire protocol. ``POST /`` is the composition
root for control-plane state: it owns the in-memory workgroup and named query
stores and binds their handlers (ADR-0003, MD-1, MD-2).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import Response

from athena_local.dispatch import WireResponse, dispatch
from athena_local.errors import serialize_error
from athena_local.named_queries import register_named_query_handlers
from athena_local.state import NamedQueryStore, WorkGroupStore
from athena_local.workgroups import register_workgroup_handlers

app = FastAPI(title="Athena Local Emulator")

workgroup_store = WorkGroupStore()
register_workgroup_handlers(workgroup_store)

named_query_store = NamedQueryStore()
register_named_query_handlers(named_query_store)


@app.get("/health")  # noqa (route handler bound by FastAPI)
def health() -> dict[str, str]:
    """Liveness probe; intentionally NOT part of the AWS wire protocol."""
    return {"status": "ok"}


@app.post("/")  # noqa (route handler bound by FastAPI)
async def athena_endpoint(request: Request) -> Response:
    """Dispatch a JSON-1.1 request addressed by its X-Amz-Target header."""
    result = dispatch(
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
