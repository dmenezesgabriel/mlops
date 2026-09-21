"""INSERT/UNLOAD manifest targets and pre-submit object snapshots.

A data manifest must list exactly the files a query wrote — real Athena's
manifest "tracks the files that the query was responsible for writing"
(INSERT example: awswrangler/athena/_read.py:135-206). Trino's statement
protocol never reports written file paths (the final page carries only
updateType/updateCount), and an existing table's location already holds files
from earlier writes, so listing it at write time would over-state the
manifest. This module resolves *where* an INSERT/UNLOAD writes — the Glue
StorageDescriptor.Location for INSERT (Trino's hive catalog uses the same
moto Glue as its metastore), the ``TO`` clause for UNLOAD — and captures the
object list *before* the statement is submitted, so the artifact writer can
emit exactly the new keys.

Only ``INSERT INTO`` (append) and ``UNLOAD`` are captured. CTAS needs no
snapshot: its ``external_location`` is fresh, because Athena rejects writing
into a non-empty target (HIVE_PATH_ALREADY_EXISTS), and other statements
write no manifest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from athena_local.errors import MetadataException
from athena_local.glue_proxy import GlueProxy
from athena_local.s3_writer import S3Writer
from athena_local.statement_classification import _strip_comments

UNLOAD_HEAD_RE = re.compile(r"^\s*unload\b", re.IGNORECASE)


class ManifestTargetError(Exception):
    """An INSERT/UNLOAD write target cannot be resolved for capture."""


@dataclass(frozen=True)
class OutputSnapshot:
    """The write target's object list captured before the statement is submitted.

    The artifact writer re-lists ``location`` at completion and subtracts
    ``before_paths``, so the manifest carries exactly the files this query
    wrote.
    """

    location: str
    before_paths: frozenset[str]


class OutputSnapshotter:
    """Resolves and snapshots INSERT/UNLOAD write targets.

    Third-party access stays behind the sanctioned boundaries — GlueProxy for
    the INSERT table's catalogue location, S3Writer for object listing
    (architecture §8.5). Returns None for statements with no manifest, so the
    CTAS path (its fresh external_location) is untouched.
    """

    def __init__(self, glue: GlueProxy, s3: S3Writer) -> None:
        self._glue = glue
        self._s3 = s3

    async def capture(
        self,
        query: str,
        database: str | None,
        catalog: str | None,
        substatement_type: str | None,
    ) -> OutputSnapshot | None:
        if substatement_type == "INSERT":
            return self._capture_insert(query, database)
        if substatement_type == "UNLOAD":
            return self._capture_unload(query)
        return None

    def _capture_insert(
        self, query: str, database: str | None
    ) -> OutputSnapshot:
        reference = insert_table_reference(query)
        if reference is None:
            raise ManifestTargetError(
                f"INSERT statement has no INTO target table to capture; "
                f"query: {query!r}"
            )
        resolved = self._resolve_insert_target(reference, database)
        return self._snapshot(self._insert_table_location(resolved))

    def _resolve_insert_target(
        self, reference: tuple[str | None, str], database: str | None
    ) -> tuple[str, str]:
        reference_database, table = reference
        resolved_database = reference_database or database
        if resolved_database is None:
            raise ManifestTargetError(
                f"INSERT target {table!r} needs a database; qualify the table "
                "name or pass QueryExecutionContext.Database"
            )
        return resolved_database, table

    def _insert_table_location(self, resolved: tuple[str, str]) -> str:
        database, table = resolved
        try:
            metadata = self._glue.get_table(database, table)
        except MetadataException as error:
            raise ManifestTargetError(
                f"INSERT target table {database}.{table} does not exist in "
                "the catalogue"
            ) from error
        location = metadata.location
        if not location:
            raise ManifestTargetError(
                f"Glue table {database}.{table} has no S3 location to capture"
            )
        return location

    def _capture_unload(self, query: str) -> OutputSnapshot:
        location = unload_location(query)
        if location is None:
            raise ManifestTargetError(
                f"UNLOAD statement has no TO location to capture; "
                f"query: {query!r}"
            )
        return self._snapshot(location)

    def _snapshot(self, location: str) -> OutputSnapshot:
        return OutputSnapshot(
            location=_prefix(location),
            before_paths=frozenset(self._s3.list_object_paths(location)),
        )


def insert_table_reference(query: str) -> tuple[str | None, str] | None:
    """The INSERT INTO target as (database, table); None when not INSERT INTO.

    Comments are stripped for scanning; the original query always reaches
    Trino. ``catalog.database.table`` resolves to (database, table), quoted
    identifiers keep their case, and unquoted parts fold to lowercase the way
    Athena folds identifiers.
    """
    parts = _identifier_tokens(_strip_comments(query))
    if (
        len(parts) < 3
        or parts[0].upper() != "INSERT"
        or parts[1].upper() != "INTO"
    ):
        return None
    return _qualified_name(parts[2])


def unload_location(query: str) -> str | None:
    """The ``TO`` location of an UNLOAD statement; None when not an UNLOAD.

    Paren depth keeps the search at the top level: keys and literals inside
    the parenthesized query cannot collide with the TO clause, and a quoted
    string's contents (including its ``''`` escapes) are skipped verbatim.
    """
    stripped = _strip_comments(query)
    if UNLOAD_HEAD_RE.search(stripped) is None:
        return None
    return _scan_unload_location(stripped)


def _scan_unload_location(text: str) -> str | None:
    depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char == "'":
            string_end = _string_end(text, index)
            if string_end is None:
                return None
            index = string_end
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and _to_clause_at(text, index):
            return _quoted_string_at(text, index + 2)
        index += 1
    return None


def _identifier_tokens(sql: str) -> list[str]:
    """Split on whitespace while keeping double-quoted names glued together.

    ``"event log"`` holds a space a plain ``split()`` would shatter.
    """
    tokens: list[str] = []
    current: list[str] = []
    in_quotes = False
    for char in sql:
        if char == '"':
            in_quotes = not in_quotes
        if char.isspace() and not in_quotes:
            if current:
                tokens.append("".join(current))
                current = []
            continue
        current.append(char)
    if current:
        tokens.append("".join(current))
    return tokens


def _qualified_name(reference: str) -> tuple[str | None, str] | None:
    """Split a (catalog.)database.table reference into (database, table)."""
    names = [
        _fold_identifier(segment)
        for segment in _split_segments(reference)
        if segment
    ]
    if not names:
        return None
    if len(names) == 1:
        return None, names[0]
    return names[-2], names[-1]


def _split_segments(reference: str) -> list[str]:
    """Split a qualified name on dots that sit outside double quotes."""
    segments: list[str] = []
    current: list[str] = []
    in_quotes = False
    for char in reference:
        if char == "." and not in_quotes:
            segments.append("".join(current))
            current = []
            continue
        if char == '"':
            in_quotes = not in_quotes
        current.append(char)
    segments.append("".join(current))
    return segments


def _fold_identifier(segment: str) -> str:
    if '"' in segment:
        return segment.replace('"', "")
    return segment.lower()


def _escaped_quote_at(text: str, index: int) -> bool:
    return (
        index + 1 < len(text) and text[index] == "'" and text[index + 1] == "'"
    )


def _string_end(text: str, start: int) -> int | None:
    """Index just past the quoted literal at ``start``, or None if unterminated."""
    cursor = start + 1
    while cursor < len(text):
        if text[cursor] != "'":
            cursor += 1
            continue
        if _escaped_quote_at(text, cursor):
            cursor += 2
            continue
        return cursor + 1
    return None


def _to_clause_at(text: str, index: int) -> bool:
    """True when ``text[index:]`` starts a top-level ``to '<uri>'`` clause."""
    if text[index : index + 2].casefold() != "to":
        return False
    before = text[index - 1] if index > 0 else ""
    if before and (before.isalnum() or before == "_"):
        return False
    return text[index + 2 :].lstrip().startswith("'")


def _quoted_string_at(text: str, start: int) -> str:
    """The SQL single-quoted literal at or after ``start``, ``''`` unescaped."""
    quote = text.find("'", start)
    end = _string_end(text, quote)
    if end is None:
        return text[quote + 1 :]
    return text[quote + 1 : end - 1].replace("''", "'")


def _prefix(location: str) -> str:
    return location.rstrip("/") + "/"
