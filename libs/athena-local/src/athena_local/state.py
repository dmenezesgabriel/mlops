"""In-memory control-plane registries (ADR-0003) — workgroups first.

Registry semantics mirror moto's Athena backend: ``primary`` is pre-seeded
(``research_repos/moto/moto/athena/models.py:263-269``), create fills the
moto defaults, and lists keep insertion order. Two deliberate divergences,
both pinned by the canonical model/AWS docs: missing workgroups raise
``InvalidRequestException`` (the service-2.json error list for the workgroup
operations has no ``ResourceNotFoundException``) and ``primary`` cannot be
deleted (AWS: "The primary workgroup cannot be deleted").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import time

from athena_local.errors import InvalidRequestException
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
