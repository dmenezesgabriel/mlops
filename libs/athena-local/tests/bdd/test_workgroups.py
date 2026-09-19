"""Step definitions for the workgroup BDD feature (MD-1).

Steps exercise the handler layer directly against a fresh in-memory registry
per scenario — the same boundary pytest-bdd asserts for the canonical model —
so the feature runs without HTTP or docker while pinning the JSON-1.1 wire
behavior consumers depend on. Parametrized steps use ``parsers.parse`` so the
quoted values in the feature file are captured (pytest-bdd 8 no longer turns
plain step strings into capture patterns).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from athena_local.errors import AthenaError, InvalidRequestException
from athena_local.state import PRIMARY_WORKGROUP_NAME, WorkGroupStore
from athena_local.workgroups import (
    create_work_group,
    delete_work_group,
    get_work_group,
    update_work_group,
)
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("workgroups.feature")

OUTPUT_LOCATION = "s3://results-bucket/analytics/"


@dataclass
class WorkgroupOutcome:
    """State shared between the when and then steps of a scenario."""

    error: AthenaError | None = None
    last_success: dict[str, object] | None = None


@pytest.fixture
def workgroup_store() -> WorkGroupStore:
    return WorkGroupStore()


@pytest.fixture
def outcome() -> WorkgroupOutcome:
    return WorkgroupOutcome()


@given("a fresh workgroup registry")
def _fresh_registry(workgroup_store: WorkGroupStore) -> None:
    assert workgroup_store.list()


@given('the emulator boots with a "primary" workgroup')
def _primary_exists(workgroup_store: WorkGroupStore) -> None:
    assert workgroup_store.get(PRIMARY_WORKGROUP_NAME).name == "primary"


@when(
    parsers.parse(
        'a workgroup named "{name}" is created with an output location'
    )
)
def _create_with_output_location(
    workgroup_store: WorkGroupStore, name: str
) -> None:
    create_work_group(
        workgroup_store,
        {
            "Name": name,
            "Configuration": {
                "ResultConfiguration": {"OutputLocation": OUTPUT_LOCATION}
            },
        },
    )


@when(parsers.parse('a workgroup named "{name}" is created'))
def _create_workgroup(workgroup_store: WorkGroupStore, name: str) -> None:
    create_work_group(workgroup_store, {"Name": name})


@when(parsers.parse('a second CreateWorkGroup reuses the name "{name}"'))
def _create_duplicate(
    outcome: WorkgroupOutcome, workgroup_store: WorkGroupStore, name: str
) -> None:
    try:
        create_work_group(workgroup_store, {"Name": name})
    except AthenaError as error:
        outcome.error = error


@when(
    parsers.parse(
        'UpdateWorkGroup disables "{name}" without touching the configuration'
    )
)
def _disable_workgroup(workgroup_store: WorkGroupStore, name: str) -> None:
    update_work_group(
        workgroup_store, {"WorkGroup": name, "State": "DISABLED"}
    )


@when(parsers.parse('DeleteWorkGroup targets "{name}"'))
def _delete_workgroup(
    outcome: WorkgroupOutcome, workgroup_store: WorkGroupStore, name: str
) -> None:
    try:
        delete_work_group(workgroup_store, {"WorkGroup": name})
    except AthenaError as error:
        outcome.error = error


@then("GetWorkGroup returns the same output location")
def _get_has_output_location(workgroup_store: WorkGroupStore) -> None:
    workgroup = get_work_group(workgroup_store, {"WorkGroup": "analytics"})[
        "WorkGroup"
    ]
    configuration = workgroup["Configuration"]
    assert (
        configuration["ResultConfiguration"]["OutputLocation"]
        == OUTPUT_LOCATION
    )


@then(
    parsers.parse(
        'GetWorkGroup returns the output location and state "{state}"'
    )
)
def _get_has_output_location_and_state(
    workgroup_store: WorkGroupStore, state: str
) -> None:
    workgroup = get_work_group(workgroup_store, {"WorkGroup": "analytics"})[
        "WorkGroup"
    ]
    assert workgroup["State"] == state
    assert workgroup["Configuration"]["ResultConfiguration"][
        "OutputLocation"
    ] == (OUTPUT_LOCATION)


@then("the workgroup state is ENABLED")
def _state_enabled(workgroup_store: WorkGroupStore) -> None:
    workgroup = get_work_group(workgroup_store, {"WorkGroup": "analytics"})[
        "WorkGroup"
    ]
    assert workgroup["State"] == "ENABLED"


@then("CreateWorkGroup answers InvalidRequestException with HTTP 400")
def _duplicate_error_shape(outcome: WorkgroupOutcome) -> None:
    assert isinstance(outcome.error, InvalidRequestException)
    assert outcome.error.status_code == 400
    assert "analytics" in outcome.error.message


@then(
    parsers.parse(
        'DeleteWorkGroup answers InvalidRequestException naming "{name}"'
    )
)
def _delete_primary_error_shape(outcome: WorkgroupOutcome, name: str) -> None:
    assert isinstance(outcome.error, InvalidRequestException)
    assert name in outcome.error.message
