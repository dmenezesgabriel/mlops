"""The StartQueryExecution submit path (ADR-0009).

``SubmissionPlanner`` owns everything ``QueryExecutor.start`` decides before
a poll task exists: ClientRequestToken replay (the canonical model marks
StartQueryExecution idempotent), result reuse, failed-statement resolution,
the Athena→Trino statement mapping (UNLOAD / ADD PARTITION / Iceberg /
dialect), the pre-submit manifest capture, and the bounded preflight —
submit + one nextUri fetch — that makes a syntax error a submit-time 400,
mirroring how real Athena rejects bad SQL at StartQueryExecution.
Trino-speak stops here and in ``executor``: handlers depend on the executor,
never on this module or ``trino_client`` (architecture §8.5).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from athena_local.common_schemas import (
    ResultConfiguration,
    ResultReuseByAgeConfiguration,
)
from athena_local.dialect import to_trino_dialect, unload_trino_submission
from athena_local.error_mapping import (
    is_syntax_error,
    syntax_error_invalid_request,
)
from athena_local.errors import InvalidRequestException
from athena_local.executions import (
    FAILED,
    RUNNING,
    SUCCEEDED,
    ExecutionStore,
    QueryExecutionRecord,
)
from athena_local.iceberg import iceberg_trino_submission
from athena_local.iceberg_probe import IcebergTableProbe
from athena_local.output_targets import (
    ManifestTargetError,
    OutputSnapshot,
)
from athena_local.partition_alter import add_partition_trino_call
from athena_local.statement_classification import StatementClassification
from athena_local.trino_client import (
    TrinoPage,
    TrinoTransportError,
)

TRINO_CATALOG = "hive"
TRINO_USER = "athena-local"


class StatementClient(Protocol):
    """The Trino statement-protocol surface the submit path drives.

    ``TrinoClient`` implements it structurally; tests inject scripted fakes
    for F.I.R.S.T. lifecycle tests (no docker). Parameter names mirror the
    concrete transports so pyright can type-check the composition root
    (``main.build_query_executor``).
    """

    async def submit_statement(
        self,
        query: str,
        catalog: str,
        schema: str,
        user: str,
        session_properties: dict[str, str] | None = None,
    ) -> TrinoPage: ...

    async def fetch_next(self, next_uri: str) -> TrinoPage: ...

    async def cancel(self, next_uri: str) -> None: ...


class ManifestSnapshotSource(Protocol):
    """Resolves and snapshots an INSERT/UNLOAD write target before submit.

    Implemented by ``output_targets.OutputSnapshotter`` (GlueProxy + S3Writer
    boundaries); the submit path only records the outcome. Returns None for
    statements whose artifacts need no manifest enumeration — CTAS keeps its
    fresh external_location path.
    """

    async def capture(
        self,
        query: str,
        database: str | None,
        catalog: str | None,
        substatement_type: str | None,
    ) -> OutputSnapshot | None: ...

    def drop_table(self, database: str, table: str) -> None:
        """Remove a transient catalog entry (the UNLOAD temp table)."""
        ...


@dataclass(frozen=True)
class StartRequest:
    """One StartQueryExecution call's fields, packed for the submit path.

    Grouping the request keeps the replay/reuse/record helpers from each
    re-listing a dozen parameters; field names mirror
    ``QueryExecutor.start``'s signature exactly.
    """

    query: str
    workgroup: str
    database: str | None = None
    catalog: str | None = None
    result_configuration: ResultConfiguration | None = None
    managed_results: bool = False
    execution_parameters: list[str] | None = None
    client_request_token: str | None = None
    statement_classification: StatementClassification | None = None
    resolved_statement: str | None = None
    resolution_failure_reason: str | None = None
    result_reuse_configuration: ResultReuseByAgeConfiguration | None = None


@dataclass(frozen=True)
class PreflightVerdict:
    """Outcome of the start-time Trino check (ADR-0009 #2).

    ``page`` is the QueryResults document the poll task resumes from — the
    statement is never re-submitted — or None when ``failure_reason`` is set
    and the execution must start FAILED because Trino was unreachable.
    """

    page: TrinoPage | None
    failure_reason: str | None


@dataclass(frozen=True)
class PreparedSubmission:
    """Everything record creation and dispatch need after ``prepare``.

    ``page``/``failure_reason`` are the preflight outcome; the snapshot,
    cleanup-table and partition-noop flags ride the record the executor
    creates. All fields default so the replay/reuse paths can create a
    record without a prepared submission.
    """

    page: TrinoPage | None = None
    failure_reason: str | None = None
    output_snapshot: OutputSnapshot | None = None
    manifest_target_error: str | None = None
    unload_cleanup_table: tuple[str, str] | None = None
    partition_noop_on_exists: bool = False


@dataclass(frozen=True)
class _MappedSubmission:
    """The Trino text a statement maps to, with each rewrite's side-flags."""

    sql: str
    session_properties: dict[str, str] | None = None
    unload_cleanup_table: tuple[str, str] | None = None
    partition_noop_on_exists: bool = False


class SubmissionPlanner:
    """Decides what ``executor.start`` answers before a poll task exists."""

    def __init__(
        self,
        store: ExecutionStore,
        client: StatementClient,
        snapshotter: ManifestSnapshotSource | None = None,
        iceberg_probe: IcebergTableProbe | None = None,
        trino_user: str = TRINO_USER,
    ) -> None:
        self._store = store
        self._client = client
        self._snapshotter = snapshotter
        self._iceberg_probe = iceberg_probe
        self._trino_user = trino_user

    def resolve_record(
        self, request: StartRequest
    ) -> QueryExecutionRecord | None:
        """The record ``start`` answers without submitting, if any.

        A replayed token answers the earlier identical submission; a failed
        statement resolution creates an immediately-FAILED record (real
        Athena fails such EXECUTEs, it never 400s them); a reuse hit creates
        a SUCCEEDED copy of the earlier result. None means the request must
        actually submit to Trino.
        """
        replayed = self._request_token_replay(request)
        if replayed is not None:
            return replayed
        if request.resolution_failure_reason is not None:
            record = self.create_record(request)
            record.transition_to(FAILED, request.resolution_failure_reason)
            return record
        reusable = self._reusable_source(request)
        if reusable is None:
            return None
        record = self.create_record(request)
        record.reuse_results_from(reusable)
        record.transition_to(RUNNING)
        record.transition_to(SUCCEEDED)
        return record

    def create_record(
        self,
        request: StartRequest,
        prepared: PreparedSubmission | None = None,
    ) -> QueryExecutionRecord:
        """Create the execution record with the submit-time wire fields."""
        prepared = prepared or PreparedSubmission()
        classification = request.statement_classification
        return self._store.create(
            query=request.query,
            workgroup=request.workgroup,
            database=request.database,
            catalog=request.catalog,
            result_configuration=request.result_configuration,
            managed_results=request.managed_results,
            execution_parameters=request.execution_parameters,
            client_request_token=request.client_request_token,
            statement_type=(
                classification.statement_type
                if classification is not None
                else None
            ),
            substatement_type=(
                classification.substatement_type
                if classification is not None
                else None
            ),
            output_snapshot=prepared.output_snapshot,
            manifest_target_error=prepared.manifest_target_error,
            resolved_statement=request.resolved_statement,
            result_reuse_configuration=request.result_reuse_configuration,
            unload_cleanup_table=prepared.unload_cleanup_table,
            partition_noop_on_exists=prepared.partition_noop_on_exists,
        )

    async def prepare(self, request: StartRequest) -> PreparedSubmission:
        """Map the statement, snapshot its write target, run the preflight.

        Capture runs on the original statement text: the rewrites consume
        the very TO clause ``unload_location`` resolves for the manifest.
        """
        submit_query = request.resolved_statement or request.query
        mapped = self._map_statement(submit_query, request.database)
        snapshot, capture_error = await self._capture_manifest(
            submit_query,
            request.database,
            request.catalog,
            request.statement_classification,
        )
        verdict = await self._preflight(
            mapped.sql, request.database, mapped.session_properties
        )
        return PreparedSubmission(
            page=verdict.page,
            failure_reason=verdict.failure_reason,
            output_snapshot=snapshot,
            manifest_target_error=capture_error,
            unload_cleanup_table=mapped.unload_cleanup_table,
            partition_noop_on_exists=mapped.partition_noop_on_exists,
        )

    def _map_statement(
        self, submit_query: str, database: str | None
    ) -> _MappedSubmission:
        """The Trino text a statement maps to, with the rewrite's side-flags.

        UNLOAD has no Trino statement at all: the rewrite to a CTAS at the
        TO path also names the temp table the completion path must drop
        (dialect.py), and unsupported WITH properties reject in the rewrite,
        mirroring real Athena's submit-time validation. Athena's
        ``ALTER TABLE … ADD [IF NOT EXISTS] PARTITION`` has no Trino grammar
        either — it maps to a ``register_partition`` CALL whose
        ``IF NOT EXISTS`` flag rides the record (partition_alter.py).
        """
        unload = unload_trino_submission(submit_query, database)
        if unload is not None:
            return _MappedSubmission(
                sql=unload.sql,
                session_properties=unload.session_properties or None,
                unload_cleanup_table=unload.cleanup_table,
            )
        partition_call = add_partition_trino_call(submit_query, database)
        if partition_call is not None:
            return _MappedSubmission(
                sql=partition_call.sql,
                partition_noop_on_exists=partition_call.noop_if_exists,
            )
        return _MappedSubmission(
            sql=self._mapped_dialect(submit_query, database)
        )

    def _mapped_dialect(self, submit_query: str, database: str | None) -> str:
        """The Trino text a plain statement maps to (iceberg + dialect).

        Iceberg statements route first: Athena declares them via
        TBLPROPERTIES or a Glue table_type=ICEBERG target, and the dedicated
        Trino catalog cannot be expressed through the session — the rewrite
        catalog-qualifies the bound table references instead (iceberg.py).
        The dialect map then runs on whatever text survives: Athena accepts a
        few statements Trino's grammar rejects (e.g. CREATE DATABASE, MSCK
        REPAIR TABLE); the record keeps the query as written (dialect.py) and
        the database context feeds the rewrite's schema fallback.
        """
        if self._iceberg_probe is not None:
            submit_query = (
                iceberg_trino_submission(
                    submit_query, database, self._iceberg_probe
                )
                or submit_query
            )
        return to_trino_dialect(submit_query, database)

    def _request_token_replay(
        self, request: StartRequest
    ) -> QueryExecutionRecord | None:
        """The earlier identical submission a ClientRequestToken replays.

        The canonical model marks StartQueryExecution idempotent
        (service-2.json): a retried token answers the original
        QueryExecutionId without re-executing, while the same token
        submitted with changed parameters errors instead.
        """
        if request.client_request_token is None:
            return None
        existing = self._store.find_by_request_token(
            request.workgroup, request.client_request_token
        )
        if existing is None:
            return None
        if not existing.same_request(
            query=request.query,
            database=request.database,
            catalog=request.catalog,
            execution_parameters=request.execution_parameters,
            result_configuration=request.result_configuration,
            result_reuse_configuration=request.result_reuse_configuration,
        ):
            raise InvalidRequestException(
                f"ClientRequestToken {request.client_request_token!r} was "
                "already used with different request parameters"
            )
        return existing

    def _reusable_source(
        self, request: StartRequest
    ) -> QueryExecutionRecord | None:
        """The previous execution Athena would re-answer for this request.

        Reuse applies only when the request enabled it, the statement
        produces a result set (SELECT, including a resolved
        EXECUTE-of-SELECT), and the workgroup doesn't own managed results;
        every other submission runs fresh (AWS UG "Reusing query results"
        considerations).
        """
        reuse_configuration = request.result_reuse_configuration
        if reuse_configuration is None or not reuse_configuration.enabled:
            return None
        if request.managed_results:
            return None
        classification = request.statement_classification
        if (
            classification is None
            or classification.substatement_type != "SELECT"
        ):
            return None
        return self._store.find_reusable(
            workgroup=request.workgroup,
            query=request.query,
            database=request.database,
            catalog=request.catalog,
            execution_parameters=request.execution_parameters,
            result_configuration=request.result_configuration,
            max_age_minutes=reuse_configuration.max_age_in_minutes,
        )

    async def _capture_manifest(
        self,
        query: str,
        database: str | None,
        catalog: str | None,
        classification: StatementClassification | None,
    ) -> tuple[OutputSnapshot | None, str | None]:
        """Snapshot INSERT/UNLOAD write targets before the statement is submitted.

        Trino starts writing as soon as the statement is submitted, so the
        before-list must land here, ahead of ``_preflight``; listing at
        completion would count this query's own files as pre-existing.
        An unresolvable target leaves a reason for the artifact writer
        instead of failing submit, so Trino's own analysis error surfaces
        first when the target truly does not exist.
        """
        substatement_type = (
            classification.substatement_type
            if classification is not None
            else None
        )
        if substatement_type not in {"INSERT", "UNLOAD"}:
            return None, None
        if self._snapshotter is None:
            return (
                None,
                f"no manifest snapshotter configured for {substatement_type} "
                "statements",
            )
        try:
            snapshot = await self._snapshotter.capture(
                query, database, catalog, substatement_type
            )
        except ManifestTargetError as error:
            return None, str(error)
        return snapshot, None

    async def _preflight(
        self,
        query: str,
        database: str | None,
        session_properties: dict[str, str] | None = None,
    ) -> PreflightVerdict:
        """POST the statement and follow one nextUri (ADR-0009 #2).

        Trino's first page is always clean; syntax failures surface on the
        first following page (measured), which bounds syntax detection to a
        single fetch. A SYNTAX_ERROR page becomes the submit-time 400
        (error_mapping); any other page is forwarded for the poll task to
        continue from, and a transport failure becomes an immediate FAILED
        reason so a dead coordinator degrades gracefully.
        """
        try:
            first_page = await self._client.submit_statement(
                query,
                TRINO_CATALOG,
                database or "",
                self._trino_user,
                session_properties=session_properties,
            )
        except TrinoTransportError as error:
            return PreflightVerdict(
                page=None, failure_reason=f"Trino unreachable: {error}"
            )
        page = first_page
        if page.next_uri is not None:
            try:
                fetched = await self._client.fetch_next(page.next_uri)
            except TrinoTransportError as error:
                return PreflightVerdict(
                    page=None, failure_reason=f"Trino unreachable: {error}"
                )
            # Rows can arrive as early as the POST response itself; keep them
            # by folding them into the page forwarded to the poll task.
            page = replace(fetched, data=[*page.data, *fetched.data])
        if is_syntax_error(page.error):
            raise syntax_error_invalid_request(page.error)
        return PreflightVerdict(page=page, failure_reason=None)
