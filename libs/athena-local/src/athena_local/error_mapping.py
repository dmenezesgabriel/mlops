"""Map Trino statement errors onto Athena's wire error vocabulary (ADR-0008).

Real Athena rejects syntactically invalid SQL at StartQueryExecution with a
400 InvalidRequestException whose message starts "Exception parsing query",
while analysis errors fail the execution and surface in StateChangeReason
instead; wrangler sniffs both surfaces
(research_repos/aws-sdk-pandas/awswrangler/athena/_utils.py:888-898,
_read.py:806-811). Trino reports both classes alike — USER_ERROR pages — so
the errorName decides the mapping: only SYNTAX_ERROR becomes the submit-time
400; every other error passes verbatim as the failed-execution reason.
"""

from __future__ import annotations

from typing import TypeGuard

from athena_local.errors import InvalidRequestException
from athena_local.trino_client import TrinoQueryError

SYNTAX_ERROR = "SYNTAX_ERROR"
EXCEPTION_PARSING_QUERY_PREFIX = "Exception parsing query"


def is_syntax_error(
    trino_error: TrinoQueryError | None,
) -> TypeGuard[TrinoQueryError]:
    """Whether a Trino error is a parse failure rejectable at submit time."""
    return trino_error is not None and trino_error.error_name == SYNTAX_ERROR


def syntax_error_invalid_request(
    trino_error: TrinoQueryError,
) -> InvalidRequestException:
    """The Athena 400 for a syntax failure, wrangler's prefix preserved."""
    return InvalidRequestException(
        f"{EXCEPTION_PARSING_QUERY_PREFIX}: {trino_error.message}"
    )
