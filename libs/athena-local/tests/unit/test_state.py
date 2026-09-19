"""Workgroup registry semantics (state.py) per ADR-0003 and moto parity.

Reference behavior mirrored from moto: the ``primary`` seed
(``research_repos/moto/moto/athena/models.py:263-269``), defaults applied on
create (``WorkGroup.__init__``), and insert-order listing. Divergences from
moto are deliberate and pinned here: missing workgroups raise
``InvalidRequestException`` (the canonical model declares no
``ResourceNotFoundException`` for the workgroup ops) and ``primary`` cannot be
deleted (AWS: "The primary workgroup cannot be deleted").
"""

from __future__ import annotations

import pytest
from athena_local.errors import InvalidRequestException
from athena_local.schemas import (
    EncryptionConfiguration,
    EngineVersion,
    ResultConfiguration,
    Tag,
    WorkGroupConfiguration,
    WorkGroupConfigurationUpdates,
)
from athena_local.state import PRIMARY_WORKGROUP_NAME, WorkGroupStore


@pytest.fixture()
def store() -> WorkGroupStore:
    return WorkGroupStore()


def test_primary_workgroup_is_preseeded(store: WorkGroupStore) -> None:
    primary = store.get(PRIMARY_WORKGROUP_NAME)

    assert primary.name == "primary"
    assert primary.state == "ENABLED"
    assert primary.description == ""
    assert primary.configuration.enforce_work_group_configuration is False
    assert primary.configuration.engine_version == EngineVersion(
        selected_engine_version="AUTO",
        effective_engine_version="Athena engine version 3",
    )


def test_create_workgroup_applies_moto_defaults(store: WorkGroupStore) -> None:
    record = store.create("analytics", WorkGroupConfiguration(), None, [])

    assert record.state == "ENABLED"
    assert record.configuration.enforce_work_group_configuration is True
    assert record.configuration.publish_cloudwatch_metrics_enabled is False
    assert record.configuration.requester_pays_enabled is False
    assert (
        record.configuration.enable_minimum_encryption_configuration is False
    )


def test_create_workgroup_keeps_provided_configuration(
    store: WorkGroupStore,
) -> None:
    configuration = WorkGroupConfiguration(
        result_configuration=ResultConfiguration(
            output_location="s3://results-bucket/analytics/",
            encryption_configuration=EncryptionConfiguration(
                encryption_option="SSE_S3",
            ),
        ),
        enforce_work_group_configuration=True,
    )

    record = store.create("analytics", configuration, "Analytics team", [])

    assert (
        record.configuration.result_configuration
        == configuration.result_configuration
    )
    assert record.configuration.enforce_work_group_configuration is True
    assert record.description == "Analytics team"


def test_create_duplicate_workgroup_raises_invalid_request(
    store: WorkGroupStore,
) -> None:
    store.create("analytics", WorkGroupConfiguration(), None, [])

    with pytest.raises(InvalidRequestException, match="analytics"):
        store.create("analytics", WorkGroupConfiguration(), None, [])


def test_create_primary_raises_invalid_request(store: WorkGroupStore) -> None:
    with pytest.raises(InvalidRequestException, match=PRIMARY_WORKGROUP_NAME):
        store.create(
            PRIMARY_WORKGROUP_NAME, WorkGroupConfiguration(), None, []
        )


def test_get_missing_workgroup_raises_invalid_request(
    store: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="missing"):
        store.get("missing")


def test_list_returns_records_in_insertion_order(
    store: WorkGroupStore,
) -> None:
    store.create("analytics", WorkGroupConfiguration(), None, [])
    store.create("data-eng", WorkGroupConfiguration(), None, [])

    names = [record.name for record in store.list()]

    assert names == ["primary", "analytics", "data-eng"]


def test_update_merges_description_state_and_configuration(
    store: WorkGroupStore,
) -> None:
    store.create("analytics", WorkGroupConfiguration(), None, [])

    updated = store.update(
        "analytics",
        description="Analytics team",
        state="DISABLED",
        updates=WorkGroupConfigurationUpdates(
            enforce_work_group_configuration=False,
        ),
    )

    assert updated.description == "Analytics team"
    assert updated.state == "DISABLED"
    assert updated.configuration.enforce_work_group_configuration is False
    # Members untouched by the update keep their values.
    assert updated.configuration.engine_version is not None


def test_update_absent_members_touch_nothing(store: WorkGroupStore) -> None:
    configuration = WorkGroupConfiguration(
        publish_cloudwatch_metrics_enabled=True
    )
    store.create("analytics", configuration, None, [])

    updated = store.update("analytics", None, None, None)

    assert updated.configuration.publish_cloudwatch_metrics_enabled is True
    assert updated.description is None


def test_update_missing_workgroup_raises_invalid_request(
    store: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="missing"):
        store.update("missing", None, None, None)


def test_delete_removes_workgroup(store: WorkGroupStore) -> None:
    store.create("analytics", WorkGroupConfiguration(), None, [])

    store.delete("analytics")

    with pytest.raises(InvalidRequestException, match="analytics"):
        store.get("analytics")


def test_delete_missing_workgroup_raises_invalid_request(
    store: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="missing"):
        store.delete("missing")


def test_delete_primary_is_blocked(store: WorkGroupStore) -> None:
    with pytest.raises(InvalidRequestException, match="primary"):
        store.delete(PRIMARY_WORKGROUP_NAME)


def test_reset_restores_only_primary(store: WorkGroupStore) -> None:
    store.create("analytics", WorkGroupConfiguration(), None, [])

    store.reset()

    assert [record.name for record in store.list()] == ["primary"]


def test_tags_are_stored_on_record(store: WorkGroupStore) -> None:
    tags = [Tag(key="Division", value="Analytics")]

    record = store.create("analytics", WorkGroupConfiguration(), None, tags)

    assert record.tags == tags
