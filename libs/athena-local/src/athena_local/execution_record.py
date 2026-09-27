"""The stored query execution record (ADR-0003, ADR-0009).

Every started query is an execution record, matching moto's ``executions``
entries plus the wire transition contract Athena's ``QueryExecutionState``
enum declares (service-2.json): ``QUEUED → RUNNING → SUCCEEDED | FAILED |
CANCELLED``, terminal states immutable; a submit-time rejection may also
terminal FAILED straight from QUEUED. SUCCEEDED may only fire after the
executor persisted the result artifacts (ADR-0007, ADR-0009 #4), so read
consumers never race missing S3 objects. The runtime counters Athena
surfaces in ``GetQueryExecution`` Statistics are copied verbatim from the
Trino statement-protocol ``StatementStats`` JSON (``processedBytes`` →
``DataScannedInBytes``, ``wallTimeMillis`` → ``EngineExecutionTimeInMillis``;
field names from the trino ``client/trino-client/.../StatementStats.java``
class). ``ExecutionStore`` (executions.py) owns the registry and retention.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import time

from athena_local.common_schemas import (
    ResultConfiguration,
    ResultReuseByAgeConfiguration,
    result_configuration_payload,
    result_reuse_configuration_payload,
)
from athena_local.output_targets import OutputSnapshot
from athena_local.statement_classification import (
    ARTIFACT_OUTPUT_SUFFIX,
    artifact_output_kind,
    normalize_statement_text,
)

QUEUED = "QUEUED"
RUNNING = "RUNNING"
SUCCEEDED = "SUCCEEDED"
FAILED = "FAILED"
CANCELLED = "CANCELLED"

TERMINAL_STATES = frozenset({SUCCEEDED, FAILED, CANCELLED})

VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    QUEUED: frozenset({RUNNING, CANCELLED, FAILED}),
    RUNNING: frozenset({SUCCEEDED, FAILED, CANCELLED}),
    SUCCEEDED: frozenset(),
    FAILED: frozenset(),
    CANCELLED: frozenset(),
}

# AWS keeps a query history for 45 days (ListQueryExecutions API doc);
# terminal records older than the window read as absent from every lookup.
QUERY_HISTORY_TTL_SECONDS = 45 * 24 * 60 * 60


@dataclass
class QueryExecutionRecord:
    """A stored query execution; the wire shape is built by ``to_payload``."""

    query_execution_id: str
    query: str
    workgroup: str
    database: str | None = None
    catalog: str | None = None
    result_configuration: ResultConfiguration | None = None
    # Managed-results executions (a workgroup whose ManagedQueryResults
    # Configuration.Enabled is true) store an empty ResultConfiguration and
    # never receive S3 artifacts (ADR-0011): the executor skips its writer
    # for them, and inline GetQueryResults still serves the rows. Sticky and
    # internal — never serialized to the wire.
    managed_results: bool = False
    execution_parameters: list[str] | None = None
    state: str = QUEUED
    state_change_reason: str | None = None
    submission_time: float = field(default_factory=time)
    completion_time: float | None = None
    engine_execution_time_ms: int | None = None
    data_scanned_bytes: int | None = None
    data_manifest_location: str | None = None
    statement_type: str | None = None
    substatement_type: str | None = None
    # INSERT/UNLOAD manifest enumeration: the write target captured
    # before the statement was submitted, plus any reason it could not be
    # resolved. Sticky and internal — never serialized to the wire.
    output_snapshot: OutputSnapshot | None = None
    manifest_target_error: str | None = None
    # The (schema, table) Glue entry an UNLOAD's CTAS rewrite registered;
    # the executor drops it before SUCCEEDED because real UNLOAD leaves no
    # catalog residue. Sticky and internal — never serialized.
    unload_cleanup_table: tuple[str, str] | None = None
    # ``ALTER TABLE … ADD IF NOT EXISTS PARTITION`` submits Trino's
    # register_partition, whose ALREADY_EXISTS on a registered partition is
    # AWS's documented no-op — the executor succeeds on that error instead
    # of failing the execution. Sticky and internal — never serialized.
    partition_noop_on_exists: bool = False
    # The final Trino page the executor stashed before the terminal transition
    # (ADR-0009 #4): GetQueryResults serves rows from here without re-reading
    # S3, matching Athena's inline results endpoint (ADR-0007).
    result_columns: list[tuple[str, str]] = field(default_factory=list)
    result_rows: list[list[object]] = field(default_factory=list)
    # The in-flight nextUri cursor the executor cancels against (ADR-0009);
    # never serialized to the wire.
    active_next_uri: str | None = None
    # The SQL actually submitted to Trino when the wire ``Query`` is EXECUTE
    # text; never serialized. The artifact writer reads a CTAS
    # external_location from here because the stored — not the submitted —
    # statement carries it.
    resolved_statement: str | None = None
    # The effective ResultReuseByAgeConfiguration the request carried
    # (service-2.json). Echoed on GetQueryExecution as "the reuse behavior
    # that was used", and ``reused_previous_result`` reports whether a
    # previous result was actually re-answered.
    result_reuse_configuration: ResultReuseByAgeConfiguration | None = None
    reused_previous_result: bool = False
    # A reused execution writes no artifacts: its OutputLocation reports the
    # source execution's result file (AWS UG "Reusing query results").
    # Sticky and internal — never serialized.
    reused_output_location: str | None = None
    # Comment-stripped, whitespace-collapsed query computed once at
    # construction: ``find_reusable`` compares it against every candidate,
    # and normalizing the stored text per candidate made the scan
    # O(executions × query-len). ``query`` is never mutated post-create, so
    # the cached key cannot drift. Internal — never serialized.
    normalized_query: str = field(init=False)
    # The ClientRequestToken this record registered under, so eviction can
    # free its ``by_request_token`` entry without scanning the map. Sticky
    # and internal — never serialized.
    request_token: str | None = None

    def __post_init__(self) -> None:
        self.normalized_query = normalize_statement_text(self.query)

    def is_retention_expired(self, now: float) -> bool:
        """Whether the record is past AWS's 45-day query-history window.

        ``completion_time`` is set only by terminal transitions, so
        in-flight executions — which real Athena tracks outside history —
        never expire.
        """
        return (
            self.completion_time is not None
            and self.completion_time < now - QUERY_HISTORY_TTL_SECONDS
        )

    def transition_to(self, new_state: str, reason: str | None = None) -> None:
        """Move to ``new_state``; terminal states are immutable (ADR-0009)."""
        if new_state not in VALID_TRANSITIONS[self.state]:
            raise ValueError(
                f"Cannot transition query execution {self.query_execution_id} "
                f"from {self.state} to {new_state}"
            )
        self.state = new_state
        self.state_change_reason = reason
        if new_state in TERMINAL_STATES:
            self.completion_time = time()

    def apply_engine_statistics(self, stats: dict[str, object]) -> None:
        """Copy the Trino StatementStats counters Athena reports back."""
        processed_bytes = stats.get("processedBytes")
        if isinstance(processed_bytes, int):
            self.data_scanned_bytes = processed_bytes
        wall_time_ms = stats.get("wallTimeMillis")
        if isinstance(wall_time_ms, int):
            self.engine_execution_time_ms = wall_time_ms

    def cache_result_page(
        self,
        columns: list[tuple[str, str]],
        rows: list[list[object]],
    ) -> None:
        """Stash the final statement page as plain (name, type) + row lists.

        Cached in place of the TrinoPage itself so this module never sees
        trino_client types (architecture §8.5: only the executor speaks Trino).
        """
        self.result_columns = list(columns)
        self.result_rows = [list(row) for row in rows]

    def same_request(
        self,
        *,
        query: str,
        database: str | None,
        catalog: str | None,
        execution_parameters: list[str] | None,
        result_configuration: ResultConfiguration | None,
        result_reuse_configuration: ResultReuseByAgeConfiguration
        | None = None,
    ) -> bool:
        """Whether these are the fields of the original submission.

        A ClientRequestToken retry is idempotent only for identical
        parameters — the model documents "an error is returned if a
        parameter, such as QueryString, has changed" (service-2.json
        StartQueryExecution input). The workgroup is implicit: the
        store's token map already keys on it.
        """
        return (
            self.query == query
            and self.database == database
            and self.catalog == catalog
            and self.execution_parameters == execution_parameters
            and self.result_configuration == result_configuration
            and self.result_reuse_configuration == result_reuse_configuration
        )

    def reuse_results_from(self, source: QueryExecutionRecord) -> None:
        """Adopt a previous execution's result surface as this one's.

        Athena's reuse bypasses the engine and writes nothing: the new
        execution reports the source's OutputLocation so consumers read the
        original result file, and the cached page serves inline
        GetQueryResults exactly like a fresh run (UG "Reusing query
        results").
        """
        self.reused_previous_result = True
        self.reused_output_location = source._result_output_location()
        self.data_manifest_location = source.data_manifest_location
        self.result_columns = list(source.result_columns)
        self.result_rows = [list(row) for row in source.result_rows]

    def matches_reuse_identity(
        self,
        *,
        workgroup: str,
        query_key: str,
        database: str | None,
        catalog: str | None,
        execution_parameters: list[str] | None,
        result_configuration: ResultConfiguration | None,
    ) -> bool:
        """Whether this record's identity fields match a reuse request's."""
        return (
            self.workgroup == workgroup
            and self.database == database
            and self.catalog == catalog
            and self.execution_parameters == execution_parameters
            and self.result_configuration == result_configuration
            and self.normalized_query == query_key
        )

    def _result_output_location(self) -> str | None:
        """The full artifact path GetQueryExecution reports (ADR-0007 #2).

        The client-facing OutputLocation names the artifact file itself, not
        the request's folder: a DML run reports ``{prefix}{QueryID}.csv``
        because wrangler gates its file reads on ``endswith(".csv")``
        (awswrangler/athena/_read.py:220), DDL/UTILITY ``.txt``
        (athena/_utils.py:196), and manifest statements the bare
        ``{prefix}{QueryID}`` stem with ``Statistics.DataManifestLocation``
        naming the ``-manifest.csv`` (aws docs get-query-execution output).
        """
        if self.reused_output_location is not None:
            return self.reused_output_location
        if self.result_configuration is None:
            return None
        prefix = self.result_configuration.output_location
        if not prefix:
            return None
        stem = f"{prefix.rstrip('/')}/{self.query_execution_id}"
        kind = artifact_output_kind(
            self.statement_type, self.substatement_type
        )
        return stem + ARTIFACT_OUTPUT_SUFFIX[kind]

    def to_payload(self) -> dict[str, object]:
        """Serialize to the GetQueryExecution ``QueryExecution`` wire shape."""
        payload: dict[str, object] = {
            "QueryExecutionId": self.query_execution_id,
            "Query": self.query,
            "Status": self._status_payload(),
            "Statistics": self._statistics_payload(),
            "WorkGroup": self.workgroup,
        }
        if self.result_configuration is not None:
            configuration_payload = result_configuration_payload(
                self.result_configuration
            )
            output_location = self._result_output_location()
            if output_location is not None:
                configuration_payload["OutputLocation"] = output_location
            payload["ResultConfiguration"] = configuration_payload
        if self.result_reuse_configuration is not None:
            payload["ResultReuseConfiguration"] = (
                result_reuse_configuration_payload(
                    self.result_reuse_configuration
                )
            )
        if self.database is not None or self.catalog is not None:
            payload["QueryExecutionContext"] = self._context_payload()
        if self.statement_type is not None:
            payload["StatementType"] = self.statement_type
        if self.substatement_type is not None:
            payload["SubstatementType"] = self.substatement_type
        if self.execution_parameters is not None:
            payload["ExecutionParameters"] = self.execution_parameters
        return payload

    def _status_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "State": self.state,
            "SubmissionDateTime": self.submission_time,
        }
        if self.state_change_reason is not None:
            payload["StateChangeReason"] = self.state_change_reason
        if self.completion_time is not None:
            payload["CompletionDateTime"] = self.completion_time
        return payload

    def _context_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        if self.database is not None:
            payload["Database"] = self.database
        if self.catalog is not None:
            payload["Catalog"] = self.catalog
        return payload

    def _statistics_payload(self) -> dict[str, object]:
        # Real Athena always reports these counters; wrangler's cache flow
        # reads DataScannedInBytes without an existence check
        # (research_repos/aws-sdk-pandas/awswrangler/athena/_cache.py), so 0
        # must be present rather than the member being absent (ADR-0007).
        payload: dict[str, object] = {
            "DataScannedInBytes": self.data_scanned_bytes or 0,
            "EngineExecutionTimeInMillis": self.engine_execution_time_ms or 0,
        }
        if self.data_manifest_location is not None:
            payload["DataManifestLocation"] = self.data_manifest_location
        if self.result_reuse_configuration is not None:
            payload["ResultReuseInformation"] = {
                "ReusedPreviousResult": self.reused_previous_result
            }
        return payload
