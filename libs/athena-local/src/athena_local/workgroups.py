"""Workgroup operations: handlers bound into the dispatch registry.

Each handler parses its request payload against the typed schemas, delegates
registry semantics to ``WorkGroupStore``, and returns the operation's output
object. Registration is explicit (composition root: ``main.py``) so handlers
stay injectable and tests bind their own store.
"""

from __future__ import annotations

from athena_local.dispatch import register_handler
from athena_local.errors import InvalidRequestException
from athena_local.schemas import (
    WorkGroupConfiguration,
    WorkGroupConfigurationUpdates,
    parse_tags,
)
from athena_local.state import WorkGroupStore


def _member(payload: dict[str, object] | None, member: str) -> object | None:
    if payload is None:
        return None
    return payload.get(member)


def _required_string(payload: dict[str, object] | None, member: str) -> str:
    raw = _member(payload, member)
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidRequestException(
            f"{member} is required and must be a non-empty string, got {raw!r}"
        )
    return raw


def _optional_string(
    payload: dict[str, object] | None, member: str
) -> str | None:
    raw = _member(payload, member)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise InvalidRequestException(
            f"{member} must be a string, got {raw!r}"
        )
    return raw


MAX_LIST_WORKGROUPS = 50  # model MaxWorkGroupsCount (service-2.json)


def _optional_max_results(payload: dict[str, object] | None) -> int | None:
    """Validate an optional ListWorkGroups MaxResults (1..50)."""
    raw = _member(payload, "MaxResults")
    if raw is None:
        return None
    if not isinstance(raw, int):
        raise InvalidRequestException(
            f"MaxResults must be an integer, got {raw!r}"
        )
    if raw < 1 or raw > MAX_LIST_WORKGROUPS:
        raise InvalidRequestException(
            f"MaxResults must be between 1 and {MAX_LIST_WORKGROUPS}, "
            f"got {raw}"
        )
    return raw


def create_work_group(
    store: WorkGroupStore, payload: dict[str, object] | None
) -> dict[str, object]:
    name = _required_string(payload, "Name")
    configuration = WorkGroupConfiguration.from_dict(
        _member(payload, "Configuration")
    )
    store.create(
        name=name,
        configuration=configuration,
        description=_optional_string(payload, "Description"),
        tags=parse_tags(_member(payload, "Tags")),
    )
    return {}


def get_work_group(
    store: WorkGroupStore, payload: dict[str, object] | None
) -> dict[str, object]:
    name = _required_string(payload, "WorkGroup")
    return {"WorkGroup": store.get(name).to_payload()}


def list_work_groups(
    store: WorkGroupStore, payload: dict[str, object] | None
) -> dict[str, object]:
    records, next_token_out = store.list(
        max_results=_optional_max_results(payload),
        next_token=_optional_string(payload, "NextToken"),
    )
    output: dict[str, object] = {
        "WorkGroups": [record.to_summary_payload() for record in records]
    }
    if next_token_out is not None:
        output["NextToken"] = next_token_out
    return output


def update_work_group(
    store: WorkGroupStore, payload: dict[str, object] | None
) -> dict[str, object]:
    name = _required_string(payload, "WorkGroup")
    updates = WorkGroupConfigurationUpdates.from_dict(
        _member(payload, "ConfigurationUpdates")
    )
    store.update(
        name=name,
        description=_optional_string(payload, "Description"),
        state=_optional_string(payload, "State"),
        updates=updates,
    )
    return {}


def delete_work_group(
    store: WorkGroupStore, payload: dict[str, object] | None
) -> dict[str, object]:
    store.delete(_required_string(payload, "WorkGroup"))
    return {}


def register_workgroup_handlers(store: WorkGroupStore) -> None:
    """Bind the five workgroup operations to ``store`` (explicit wiring)."""
    register_handler(
        "CreateWorkGroup", lambda payload: create_work_group(store, payload)
    )
    register_handler(
        "GetWorkGroup", lambda payload: get_work_group(store, payload)
    )
    register_handler(
        "ListWorkGroups", lambda payload: list_work_groups(store, payload)
    )
    register_handler(
        "UpdateWorkGroup", lambda payload: update_work_group(store, payload)
    )
    register_handler(
        "DeleteWorkGroup", lambda payload: delete_work_group(store, payload)
    )
