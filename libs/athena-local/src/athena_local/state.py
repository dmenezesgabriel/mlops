"""In-memory control-plane registries (ADR-0003) — workgroups and named queries.

Registry semantics mirror moto's Athena backend: ``primary`` is pre-seeded
(``research_repos/moto/moto/athena/models.py:263-269``), create fills the
moto defaults, and lists keep insertion order. Two deliberate divergences,
both pinned by the canonical model/AWS docs: missing workgroups raise
``InvalidRequestException`` (the service-2.json error list for the workgroup
operations has no ``ResourceNotFoundException``) and ``primary`` cannot be
deleted (AWS: "The primary workgroup cannot be deleted").

Named queries are scoped to workgroups and use UUID4 IDs (moto
``models.py:193-207``).

Prepared statements are scoped to workgroups and use user-provided names
as keys (service model ``PreparedStatement`` shape); ``GetPreparedStatement``
raises ``ResourceNotFoundException`` for missing statements per awswrangler
expectations (``research_repos/aws-sdk-pandas/awswrangler/athena/_statements.py:26-29``).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from time import time

from athena_local.errors import (
    InvalidRequestException,
    ResourceNotFoundException,
)
from athena_local.schemas import (
    Tag,
    WorkGroupConfiguration,
    WorkGroupConfigurationUpdates,
    apply_defaults,
    to_payload,
)

PRIMARY_WORKGROUP_NAME = "primary"
WORKGROUP_STATES = ("ENABLED", "DISABLED")


def missing_workgroup_error(name: str) -> InvalidRequestException:
    return InvalidRequestException(f"WorkGroup {name} does not exist")


def validated_state(state: str) -> str:
    if state not in WORKGROUP_STATES:
        raise InvalidRequestException(
            f"WorkGroupState must be one of {WORKGROUP_STATES}, got {state!r}"
        )
    return state


@dataclass
class WorkGroupRecord:
    """A stored workgroup; the wire shape is built by ``to_payload``."""

    name: str
    state: str = "ENABLED"
    configuration: WorkGroupConfiguration = field(
        default_factory=WorkGroupConfiguration
    )
    description: str | None = None
    creation_time: float = field(default_factory=time)
    tags: list[Tag] = field(default_factory=list)

    def to_payload(self) -> dict[str, object]:
        """Serialize to the GetWorkGroup ``WorkGroup`` wire shape."""
        payload: dict[str, object] = {
            "Name": self.name,
            "State": self.state,
            "Configuration": to_payload(self.configuration),
            "CreationTime": self.creation_time,
        }
        if self.description is not None:
            payload["Description"] = self.description
        return payload

    def to_summary_payload(self) -> dict[str, object]:
        """Serialize to the ListWorkGroups ``WorkGroupSummary`` wire shape."""
        payload: dict[str, object] = {
            "Name": self.name,
            "State": self.state,
            "CreationTime": self.creation_time,
        }
        if self.description is not None:
            payload["Description"] = self.description
        if self.configuration.engine_version is not None:
            payload["EngineVersion"] = {
                "SelectedEngineVersion": (
                    self.configuration.engine_version.selected_engine_version
                ),
                "EffectiveEngineVersion": (
                    self.configuration.engine_version.effective_engine_version
                ),
            }
        return payload


@dataclass
class WorkGroupStore:
    """In-memory workgroup registry; single-process, race-free (ADR-0003)."""

    by_name: dict[str, WorkGroupRecord] = field(
        default_factory=dict, init=False
    )

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Drop every workgroup and re-seed ``primary`` (test reset point)."""
        self.by_name = {
            PRIMARY_WORKGROUP_NAME: WorkGroupRecord(
                name=PRIMARY_WORKGROUP_NAME,
                # moto fills __init__ defaults even for the seed
                # (research_repos/moto/moto/athena/models.py:263-269).
                configuration=apply_defaults(
                    WorkGroupConfiguration(
                        enforce_work_group_configuration=False
                    )
                ),
                description="",
            )
        }

    def create(
        self,
        name: str,
        configuration: WorkGroupConfiguration,
        description: str | None,
        tags: list[Tag],
    ) -> WorkGroupRecord:
        if name == PRIMARY_WORKGROUP_NAME or name in self.by_name:
            raise InvalidRequestException(f"WorkGroup {name} already exists")
        record = WorkGroupRecord(
            name=name,
            configuration=apply_defaults(configuration),
            description=description,
            tags=tags,
        )
        self.by_name[name] = record
        return record

    def get(self, name: str) -> WorkGroupRecord:
        if name not in self.by_name:
            raise missing_workgroup_error(name)
        return self.by_name[name]

    def list(self) -> list[WorkGroupRecord]:
        return list(self.by_name.values())

    def update(
        self,
        name: str,
        description: str | None,
        state: str | None,
        updates: WorkGroupConfigurationUpdates | None,
    ) -> WorkGroupRecord:
        record = self.get(name)
        if state is not None:
            record.state = validated_state(state)
        if description is not None:
            record.description = description
        if updates is not None:
            record.configuration = WorkGroupConfiguration.apply_updates(
                record.configuration, updates
            )
        return record

    def delete(self, name: str) -> None:
        if name == PRIMARY_WORKGROUP_NAME:
            raise InvalidRequestException(
                "The primary workgroup cannot be deleted"
            )
        if name not in self.by_name:
            raise missing_workgroup_error(name)
        del self.by_name[name]


@dataclass
class NamedQueryRecord:
    """A stored named query; the wire shape is built by ``to_payload``."""

    id: str
    name: str
    description: str
    database: str
    query_string: str
    workgroup: str
    creation_time: float = field(default_factory=time)

    def to_payload(self) -> dict[str, object]:
        """Serialize to the GetNamedQuery ``NamedQuery`` wire shape."""
        return {
            "NamedQueryId": self.id,
            "Name": self.name,
            "Description": self.description,
            "Database": self.database,
            "QueryString": self.query_string,
            "WorkGroup": self.workgroup,
        }


@dataclass
class NamedQueryStore:
    """In-memory named query registry; single-process, race-free (ADR-0003)."""

    by_id: dict[str, NamedQueryRecord] = field(
        default_factory=dict, init=False
    )
    by_workgroup: dict[str, list[str]] = field(
        default_factory=dict, init=False
    )

    def reset(self) -> None:
        """Drop every named query (test reset point)."""
        self.by_id = {}
        self.by_workgroup = {}

    def create(
        self,
        name: str,
        description: str,
        database: str,
        query_string: str,
        workgroup: str,
    ) -> NamedQueryRecord:
        query_id = str(uuid.uuid4())
        record = NamedQueryRecord(
            id=query_id,
            name=name,
            description=description,
            database=database,
            query_string=query_string,
            workgroup=workgroup,
        )
        self.by_id[query_id] = record
        if workgroup not in self.by_workgroup:
            self.by_workgroup[workgroup] = []
        self.by_workgroup[workgroup].append(query_id)
        return record

    def get(self, query_id: str) -> NamedQueryRecord:
        if query_id not in self.by_id:
            raise InvalidRequestException(
                f"NamedQuery {query_id} does not exist"
            )
        return self.by_id[query_id]

    def list(
        self,
        workgroup: str,
        max_results: int | None = None,
        next_token: str | None = None,
    ) -> tuple[list[str], str | None]:
        """Return query IDs for a workgroup with pagination.

        Returns a tuple of (query_ids, next_token). ``next_token`` is None
        when there are no more results.
        """
        all_ids = self.by_workgroup.get(workgroup, [])
        start_index = 0
        if next_token is not None:
            try:
                start_index = int(next_token)
            except ValueError:
                raise InvalidRequestException(
                    f"Invalid NextToken: {next_token}"
                ) from None
        if start_index >= len(all_ids):
            return [], None
        end_index = len(all_ids)
        if max_results is not None and max_results > 0:
            end_index = min(start_index + max_results, len(all_ids))
        page_ids = all_ids[start_index:end_index]
        next_token_out = str(end_index) if end_index < len(all_ids) else None
        return page_ids, next_token_out

    def delete(self, query_id: str) -> None:
        record = self.get(query_id)
        workgroup = record.workgroup
        del self.by_id[query_id]
        if workgroup in self.by_workgroup:
            self.by_workgroup[workgroup] = [
                qid for qid in self.by_workgroup[workgroup] if qid != query_id
            ]

    def batch_get(
        self, query_ids: list[str]
    ) -> tuple[list[NamedQueryRecord], list[str]]:
        """Return found records and list of unprocessed IDs.

        Returns a tuple of (found_records, unprocessed_ids).
        """
        found: list[NamedQueryRecord] = []
        unprocessed: list[str] = []
        for query_id in query_ids:
            if query_id in self.by_id:
                found.append(self.by_id[query_id])
            else:
                unprocessed.append(query_id)
        return found, unprocessed


@dataclass
class PreparedStatementRecord:
    """A stored prepared statement; the wire shape is built by ``to_payload``."""

    statement_name: str
    query_statement: str
    workgroup: str
    description: str | None = None
    last_modified_time: float = field(default_factory=time)

    def to_payload(self) -> dict[str, object]:
        """Serialize to the GetPreparedStatement ``PreparedStatement`` wire shape."""
        payload: dict[str, object] = {
            "StatementName": self.statement_name,
            "QueryStatement": self.query_statement,
            "WorkGroupName": self.workgroup,
            "LastModifiedTime": self.last_modified_time,
        }
        if self.description is not None:
            payload["Description"] = self.description
        return payload

    def to_summary_payload(self) -> dict[str, object]:
        """Serialize to the ListPreparedStatements ``PreparedStatementSummary`` shape."""
        return {
            "StatementName": self.statement_name,
            "LastModifiedTime": self.last_modified_time,
        }


@dataclass
class PreparedStatementStore:
    """In-memory prepared statement registry; single-process, race-free (ADR-0003)."""

    by_key: dict[tuple[str, str], PreparedStatementRecord] = field(
        default_factory=dict, init=False
    )
    by_workgroup: dict[str, list[str]] = field(
        default_factory=dict, init=False
    )

    def reset(self) -> None:
        """Drop every prepared statement (test reset point)."""
        self.by_key = {}
        self.by_workgroup = {}

    def create(
        self,
        statement_name: str,
        query_statement: str,
        workgroup: str,
        description: str | None,
    ) -> PreparedStatementRecord:
        key = (workgroup, statement_name)
        if key in self.by_key:
            raise InvalidRequestException(
                f"PreparedStatement {statement_name} already exists in workgroup {workgroup}"
            )
        record = PreparedStatementRecord(
            statement_name=statement_name,
            query_statement=query_statement,
            workgroup=workgroup,
            description=description,
        )
        self.by_key[key] = record
        if workgroup not in self.by_workgroup:
            self.by_workgroup[workgroup] = []
        self.by_workgroup[workgroup].append(statement_name)
        return record

    def get(
        self, statement_name: str, workgroup: str
    ) -> PreparedStatementRecord:
        key = (workgroup, statement_name)
        if key not in self.by_key:
            raise ResourceNotFoundException(
                f"PreparedStatement {statement_name} does not exist in workgroup {workgroup}"
            )
        return self.by_key[key]

    def list(
        self,
        workgroup: str,
        max_results: int | None = None,
        next_token: str | None = None,
    ) -> tuple[list[str], str | None]:
        """Return statement names for a workgroup with pagination.

        Returns a tuple of (statement_names, next_token). ``next_token`` is None
        when there are no more results.
        """
        all_names = self.by_workgroup.get(workgroup, [])
        start_index = 0
        if next_token is not None:
            try:
                start_index = int(next_token)
            except ValueError:
                raise InvalidRequestException(
                    f"Invalid NextToken: {next_token}"
                ) from None
        if start_index >= len(all_names):
            return [], None
        end_index = len(all_names)
        if max_results is not None and max_results > 0:
            end_index = min(start_index + max_results, len(all_names))
        page_names = all_names[start_index:end_index]
        next_token_out = str(end_index) if end_index < len(all_names) else None
        return page_names, next_token_out

    def update(
        self,
        statement_name: str,
        workgroup: str,
        query_statement: str,
        description: str | None,
    ) -> PreparedStatementRecord:
        key = (workgroup, statement_name)
        if key not in self.by_key:
            raise ResourceNotFoundException(
                f"PreparedStatement {statement_name} does not exist in workgroup {workgroup}"
            )
        record = self.by_key[key]
        record.query_statement = query_statement
        record.description = description
        record.last_modified_time = time()
        return record

    def delete(self, statement_name: str, workgroup: str) -> None:
        key = (workgroup, statement_name)
        if key not in self.by_key:
            raise ResourceNotFoundException(
                f"PreparedStatement {statement_name} does not exist in workgroup {workgroup}"
            )
        del self.by_key[key]
        if workgroup in self.by_workgroup:
            self.by_workgroup[workgroup] = [
                name
                for name in self.by_workgroup[workgroup]
                if name != statement_name
            ]

    def batch_get(
        self, statement_names: list[str], workgroup: str
    ) -> tuple[list[PreparedStatementRecord], list[str]]:
        """Return found records and list of unprocessed names.

        Returns a tuple of (found_records, unprocessed_names).
        """
        found: list[PreparedStatementRecord] = []
        unprocessed: list[str] = []
        for statement_name in statement_names:
            key = (workgroup, statement_name)
            if key in self.by_key:
                found.append(self.by_key[key])
            else:
                unprocessed.append(statement_name)
        return found, unprocessed
