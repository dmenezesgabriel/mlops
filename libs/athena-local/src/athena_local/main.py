"""FastAPI application exposing the Athena JSON-1.1 protocol (ADR-0008).

Service entry point: ``POST /`` catch-all dispatches ``X-Amz-Target`` through
``athena_local.dispatch``; ``GET /health`` is an operational probe for compose
``depends_on``, outside the AWS wire protocol.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import Response

from athena_local.dispatch import dispatch
from athena_local.errors import serialize_error

app = FastAPI(title="Athena Local Emulator")


@app.get("/health")  # noqa (route handler bound by FastAPI)
def health() -> dict[str, str]:
    """Liveness probe; intentionally NOT part of the AWS wire protocol."""
    return {"status": "ok"}


@app.post("/")  # noqa (route handler bound by FastAPI)
async def athena_endpoint(request: Request) -> Response:
    """Dispatch a JSON-1.1 request addressed by its X-Amz-Target header."""
    error = dispatch(request.headers.get("x-amz-target"))
    status, headers, body = serialize_error(error)
    return Response(content=body, status_code=status, headers=headers)
