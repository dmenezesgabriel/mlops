"""Workgroup operations: handlers bound into the dispatch registry.

Each handler parses its request payload against the typed schemas, delegates
registry semantics to ``WorkGroupStore``, and returns the operation's output
object. Registration is explicit (composition root: ``main.py``) so handlers
stay injectable and tests bind their own store.
"""

from __future__ import annotations

from athena_local.dispatch import register_handler
from athena_local.request_fields import (
    member,
    optional_max_results,
    optional_string,
    required_string,
)
from athena_local.schemas import (
    WorkGroupConfiguration,
    WorkGroupConfigurationUpdates,
    parse_tags,
)
from athena_local.state import WorkGroupStore

MAX_LIST_WORKGROUPS = 50  # model MaxWorkGroupsCount (service-2.json)


def create_work_group(
    store: WorkGroupStore, payload: dict[str, object] | None
) -> dict[str, object]:
    name = required_string(payload, "Name")
    configuration = WorkGroupConfiguration.from_dict(
        member(payload, "Configuration")
    )
    store.create(
        name=name,
        configuration=configuration,
        description=optional_string(payload, "Description"),
        tags=parse_tags(member(payload, "Tags")),
    )
    return {}


def get_work_group(
    store: WorkGroupStore, payload: dict[str, object] | None
) -> dict[str, object]:
    name = required_string(payload, "WorkGroup")
    return {"WorkGroup": store.get(name).to_payload()}


def list_work_groups(
    store: WorkGroupStore, payload: dict[str, object] | None
) -> dict[str, object]:
    records, next_token_out = store.list(
        max_results=optional_max_results(
            payload, "MaxResults", MAX_LIST_WORKGROUPS
        ),
        next_token=optional_string(payload, "NextToken"),
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
    name = required_string(payload, "WorkGroup")
    updates = WorkGroupConfigurationUpdates.from_dict(
        member(payload, "ConfigurationUpdates")
    )
    store.update(
        name=name,
        description=optional_string(payload, "Description"),
        state=optional_string(payload, "State"),
        updates=updates,
    )
    return {}


def delete_work_group(
    store: WorkGroupStore, payload: dict[str, object] | None
) -> dict[str, object]:
    store.delete(required_string(payload, "WorkGroup"))
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
