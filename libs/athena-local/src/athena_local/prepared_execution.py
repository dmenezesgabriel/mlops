"""Server-side prepared-statement execution: resolve EXECUTE at submit.

Real Athena keeps prepared statements in the workgroup and re-runs their
stored ``QueryStatement`` when a client submits ``EXECUTE <name> [USING
<expr>, ...]`` (aws docs "Use prepared statements",
docs.aws.amazon.com/athena/latest/ug/querying-with-prepared-statements-querying.html).
The emulator mirrors that before Trino submit, because the Trino statement
protocol has no prepared-statement persistence (measured:
PREPARE/DEALLOCATE do not survive across HTTP requests,
``/tmp/opencode/trino_probe.py``); a bound copy of the stored SQL is what
actually runs.

Values for EXECUTE are SQL expression text, spliced verbatim into the stored
query at each ``?`` and paren-wrapped so each stays one atomic expression.
Athena treats EXECUTE values the same way — the launch blog's
``EXECUTE get_user USING 1 OR 1=1`` fails with ``SYNTAX_ERROR: Line 1:24:
Left side of logical expression must evaluate to a boolean`` (SQL-injection
resistance is the caller's job), strings must arrive single-quoted, and
``CAST('2014-07-05' AS DATE)`` is the documented way to type a value
(aws docs "Use parameterized queries",
docs.aws.amazon.com/athena/latest/ug/querying-with-prepared-statements.html).
Wrangler ships inline ``USING`` values as that same expression text, but its
``params`` + ``paramstyle="qmark"`` path sends ``StartQueryExecution.
ExecutionParameters`` as bare values — ``["Washington"]``, ``["1"]`` —
that Athena binds by the parameter's context type: ``encode_execution_parameter``
mirrors that (a complete literal/expression travels verbatim, a bare
identifier becomes a quoted string), so both spellings resolve identically.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from athena_local.errors import (
    InvalidRequestException,
    ResourceNotFoundException,
)
from athena_local.sql_lexing import quoted_end, strip_comments
from athena_local.state import PreparedStatementStore
from athena_local.statement_classification import (
    StatementClassification,
    classify_statement,
)

# ``EXECUTE`` is matched as a whole word so ``EXECUTER``-style tokens never
# trigger resolution; IGNORECASE keeps lowercase ``execute`` valid.
_EXECUTE_PREFIX_RE = re.compile(r"^\bEXECUTE\b", re.IGNORECASE)
_USING_RE = re.compile(r"^USING(?:\s|$)", re.IGNORECASE)
_BARE_NAME_RE = re.compile(r"[^\s(]+")

# An ``ExecutionParameters`` value that already spells a complete SQL literal
# or typed expression travels verbatim into ``bind_parameters``; anything
# else is a bare value real Athena coerces by the parameter's context type —
# most commonly a varchar, so it binds single-quoted. The alternation covers
# the spellings wrangler's real-AWS qmark suite exercises
# (awswrangler/tests/unit/test_athena.py:936-937), plus the CAST expression
# the aws parameterized-query docs recommend.
_LITERAL_OR_EXPRESSION_RE = re.compile(
    r"^(?:"
    r"'(?:[^']|'')*'"  # 'string' literal
    r'|"(?:[^"]|"")*"'  # "identifier"
    r"|[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"  # numeric literal
    r"|(?:DATE|TIME|TIMESTAMP|INTERVAL)\s+'[^']*'"  # typed literal
    r"|(?:TRY_)?CAST\s*\(.*\)"  # cast expression
    r"|(?:NULL|TRUE|FALSE)"  # keyword literal
    r"|\(.*\)"  # already-parenthesized expression
    r")$",
    re.IGNORECASE | re.DOTALL,
)

# One pass over the stored query emits each ``?`` marker and every
# string-literal / quoted-identifier / comment span as its own segment, so
# binding can never rewrite a marker inside a literal (Athena forbids ``?``
# in quotes anyway — aws docs "Use parameterized queries"). The alternation
# order mirrors ``sql_lexing._COMMENT_ISOLATING_RE``.
_PLACEHOLDER_SCAN_RE = re.compile(
    r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|--[^\n]*"
    r"|/\*.*?\*/|/\*.*|\?"
)


class ParameterCountError(ValueError):
    """The stored statement's ``?`` count does not match the supplied values."""


@dataclass(frozen=True)
class ExecuteParts:
    """The pieces of a parsed ``EXECUTE <name> [USING <expr>, ...]`` statement.

    ``values`` is None when the statement has no ``USING`` clause — the
    resolver falls back to ``ExecutionParameters`` then — and the parsed
    inline list otherwise.
    """

    name: str
    values: list[str] | None


@dataclass(frozen=True)
class ExecuteResolution:
    """Outcome of resolving a submitted query against the statement store.

    Non-EXECUTE statements pass through untouched (``statement`` equals the
    submitted query). A missing statement or a ``?``-count mismatch sets
    ``failure_reason``: real Athena fails those executions instead of 400ing
    them, and the record is created with the submitted EXECUTE text as its
    ``Query``, which wrangler's cache compares on the wire
    (awswrangler/athena/_cache.py:114-129).
    """

    statement: str
    statement_classification: StatementClassification
    failure_reason: str | None = None


def parse_execute_statement(query: str) -> ExecuteParts | None:
    """Parse ``EXECUTE <name> [USING <expr>, ...]``; None for other statements.

    Statement names may be bare identifiers or double-quoted
    (``EXECUTE "my stmt"`` — the shape wrangler emits), and the keywords are
    case-insensitive. A malformed EXECUTE (missing name, trailing junk, or a
    dangling ``USING``) raises ``InvalidRequestException``, the submit-time
    400 Athena answers. Example::

        parse_execute_statement("EXECUTE \\"st\\" USING 'Washington'")
        # -> ExecuteParts(name="st", values=["'Washington'"])
    """
    without_comments = strip_comments(query).strip()
    rest = _EXECUTE_PREFIX_RE.sub("", without_comments, count=1).lstrip()
    if rest == without_comments:
        return None
    name, remainder = _parse_statement_name(rest)
    if not remainder.strip():
        return ExecuteParts(name, None)
    remainder = remainder.strip()
    if _USING_RE.match(remainder) is None:
        raise InvalidRequestException(
            f"EXECUTE expects only [USING ...] after the statement name, "
            f"got {remainder!r}"
        )
    values_text = _USING_RE.sub("", remainder, count=1).strip()
    if not values_text:
        raise InvalidRequestException(
            "EXECUTE USING requires at least one value"
        )
    return ExecuteParts(name, _split_top_level_values(values_text))


def bind_parameters(stored_query: str, values: list[str]) -> str:
    """Splice each value verbatim into the stored query at its ``?`` marker.

    Values are paren-wrapped ``({value})`` so they stay one atomic SQL
    expression — ``'Washington'``, ``2012`` and ``CAST(...)`` pass through
    unchanged. A count mismatch raises ``ParameterCountError`` naming both
    counts, mirroring Trino's ``INVALID_PARAMETER_USAGE: Incorrect number of
    parameters`` phrasing (measured in ``/tmp/opencode/trino_probe.py``).
    """
    expected = _count_placeholders(stored_query)
    if expected != len(values):
        raise ParameterCountError(
            f"Incorrect number of parameters: expected {expected} "
            f"but found {len(values)}"
        )
    supplied = iter(values)
    output: list[str] = []
    for segment in _placeholder_segments(stored_query):
        if segment != "?":
            output.append(segment)
            continue
        output.append(f"({next(supplied)})")
    return "".join(output)


def encode_execution_parameter(value: str) -> str:
    """Encode a ``StartQueryExecution.ExecutionParameters`` value as SQL text.

    Real Athena binds execution parameters by the parameter's context type:
    a value that already spells a complete literal or typed expression
    (``'Washington'``, ``2012``, ``DATE '2020-01-01'``, ``CAST(...)``)
    passes verbatim, while a bare identifier — how wrangler's qmark suite
    sends ``"Washington"`` (awswrangler/tests/unit/test_athena.py:936-937) —
    becomes a single-quoted string. Embedded quote characters are doubled so
    user text cannot break out of the literal. Example::

        encode_execution_parameter("Washington")
        # -> "'Washington'"
    """
    stripped = value.strip()
    if _LITERAL_OR_EXPRESSION_RE.match(stripped):
        return stripped
    return f"'{stripped.replace(chr(39), chr(39) * 2)}'"


def _encode_execution_parameters(execution_parameters: list[str]) -> list[str]:
    return [
        encode_execution_parameter(value) for value in execution_parameters
    ]


def resolve_execute_statement(
    store: PreparedStatementStore,
    workgroup: str,
    query: str,
    execution_parameters: list[str] | None,
) -> ExecuteResolution:
    """Resolve a submitted query for execution.

    A plain parameterized query (``?`` markers plus ``ExecutionParameters``,
    the wrangler ``paramstyle="qmark"`` shape) binds its markers server-side;
    an EXECUTE resolves to the stored ``QueryStatement`` with the inline
    ``USING`` values — or, when the client supplied none, the
    ``ExecutionParameters`` — bound into its ``?`` placeholders; the bound
    text is what the executor submits. A missing statement or count mismatch
    becomes a ``failure_reason`` so the execution starts terminal FAILED
    instead of a 400, matching real Athena. Example::

        resolve_execute_statement(store, "primary", 'EXECUTE "st"', ["'Washington'"])
        # -> ExecuteResolution(statement="... origin = ('Washington')", ...)
    """
    parts = parse_execute_statement(query)
    if parts is None:
        if not execution_parameters:
            return ExecuteResolution(
                statement=query,
                statement_classification=classify_statement(query),
            )
        return _bind_or_fail(
            query, query, _encode_execution_parameters(execution_parameters)
        )
    stored = _stored_statement_or_failure(store, workgroup, query, parts)
    if stored.failure_reason is not None:
        return stored
    values = (
        parts.values
        if parts.values is not None
        else _encode_execution_parameters(execution_parameters or [])
    )
    return _bind_or_fail(query, stored.statement, values)


def _bind_or_fail(
    query: str, statement_to_bind: str, values: list[str]
) -> ExecuteResolution:
    """The bound statement, or the count-mismatch failure outcome.

    A mismatch keeps the submitted text as the wire ``Query`` and classifies
    from it — the same FAILED-not-400 contract the missing-statement path
    uses (wrangler's cache compares the submitted query, awswrangler/athena/
    _cache.py:114-129).
    """
    try:
        statement = bind_parameters(statement_to_bind, values)
    except ParameterCountError as error:
        return ExecuteResolution(
            statement=query,
            statement_classification=classify_statement(query),
            failure_reason=str(error),
        )
    return ExecuteResolution(
        statement=statement,
        statement_classification=classify_statement(statement),
    )


def _stored_statement_or_failure(
    store: PreparedStatementStore,
    workgroup: str,
    query: str,
    parts: ExecuteParts,
) -> ExecuteResolution:
    """The stored statement text, or the missing-statement failure outcome.

    Kept behind one exception boundary so the exact Athena
    ``StateChangeReason`` — from the launch blog's missing-statement error —
    is produced in exactly one place.
    """
    try:
        record = store.get(parts.name, workgroup)
    except ResourceNotFoundException:
        return ExecuteResolution(
            statement=query,
            statement_classification=classify_statement(query),
            failure_reason=(
                f"PreparedStatement {parts.name} was not found "
                f"in workGroup {workgroup}"
            ),
        )
    return ExecuteResolution(
        statement=record.query_statement,
        statement_classification=classify_statement(query),
    )


def _parse_statement_name(rest: str) -> tuple[str, str]:
    """Split ``<name>`` off the statement text; the name may be quoted."""
    if not rest:
        raise InvalidRequestException(
            "EXECUTE requires a statement name, nothing followed the keyword"
        )
    if rest.startswith('"'):
        end = quoted_end(rest, 0, '"')
        if end >= len(rest) and not rest.endswith('"'):
            raise InvalidRequestException(
                f"EXECUTE statement name is an unterminated quoted "
                f"identifier: {rest!r}"
            )
        return rest[1 : end - 1].replace('""', '"'), rest[end:]
    match = _BARE_NAME_RE.match(rest)
    if match is None:
        raise InvalidRequestException(
            f"EXECUTE statement name must be an identifier or quoted, "
            f"got {rest!r}"
        )
    name = match.group(0)
    return name, rest[len(name) :]


def _placeholder_segments(stored_query: str) -> list[str]:
    """Split the query into ``?`` markers and opaque text runs."""
    segments: list[str] = []
    position = 0
    for match in _PLACEHOLDER_SCAN_RE.finditer(stored_query):
        segments.append(stored_query[position : match.start()])
        segments.append(match.group(0))
        position = match.end()
    segments.append(stored_query[position:])
    return segments


def _count_placeholders(stored_query: str) -> int:
    return sum(
        1 for segment in _placeholder_segments(stored_query) if segment == "?"
    )


def _split_top_level_values(text: str) -> list[str]:
    """Split an inline USING list at top-level commas.

    Commas inside string literals, quoted identifiers, or balanced
    parentheses belong to one expression, so ``CAST('2014-07-05' AS DATE)``
    travels whole; only a comma at nesting depth zero splits.
    """
    values: list[str] = []
    start = 0
    depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char in {"'", '"'}:
            index = quoted_end(text, index, char)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            values.append(text[start:index].strip())
            start = index + 1
        index += 1
    values.append(text[start:].strip())
    if any(not value for value in values):
        raise InvalidRequestException(
            f"EXECUTE USING values must not be empty, got {text!r}"
        )
    return values
