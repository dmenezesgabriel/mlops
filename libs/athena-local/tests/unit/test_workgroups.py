"""Handler tests for the five workgroup operations.

Handlers translate a parsed JSON payload into the operation's output shape,
delegating registry semantics to ``WorkGroupStore``. The payload-shape
contract lives in ``schemas.py``; these tests fix the wire-facing behavior:
output keys match the canonical service-2.json output members.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from athena_local.dispatch import implemented_operations
from athena_local.errors import InvalidRequestException
from athena_local.state import WorkGroupStore
from athena_local.workgroups import (
    create_work_group,
    delete_work_group,
    get_work_group,
    list_work_groups,
    update_work_group,
)

WORKGROUP_OPERATIONS = {
    "CreateWorkGroup",
    "GetWorkGroup",
    "ListWorkGroups",
    "UpdateWorkGroup",
    "DeleteWorkGroup",
}


@pytest.fixture()
def store() -> WorkGroupStore:
    return WorkGroupStore()


def test_workgroup_operations_are_registered() -> None:
    # main.py is the composition root (ADR-0003); importing it registers the
    # five workgroup operations against the app's store exactly once.
    import athena_local.main  # noqa: F401

    assert WORKGROUP_OPERATIONS <= implemented_operations()


def test_create_work_group_returns_empty_output(store: WorkGroupStore) -> None:
    output = create_work_group(
        store,
        {"Name": "analytics", "Description": "Analytics team"},
    )

    assert output == {}
    assert store.get("analytics").description == "Analytics team"


def test_create_work_group_requires_name(store: WorkGroupStore) -> None:
    with pytest.raises(InvalidRequestException, match="Name"):
        create_work_group(store, {"Description": "no name"})


def test_create_work_group_rejects_empty_body(store: WorkGroupStore) -> None:
    with pytest.raises(InvalidRequestException, match="Name"):
        create_work_group(store, None)


def test_get_work_group_returns_workgroup_members(
    store: WorkGroupStore,
) -> None:
    create_work_group(
        store,
        {
            "Name": "AthenaAdmin",
            "Configuration": {
                "ResultConfiguration": {
                    "OutputLocation": "s3://amzn-s3-demo-bucket/"
                },
                "PublishCloudWatchMetricsEnabled": True,
            },
            "Description": "Workgroup for Athena administrators",
        },
    )

    output = get_work_group(store, {"WorkGroup": "AthenaAdmin"})

    workgroup = output["WorkGroup"]
    assert workgroup["Name"] == "AthenaAdmin"
    assert workgroup["State"] == "ENABLED"
    assert workgroup["Description"] == "Workgroup for Athena administrators"
    assert workgroup["Configuration"]["ResultConfiguration"] == {
        "OutputLocation": "s3://amzn-s3-demo-bucket/"
    }
    assert (
        workgroup["Configuration"]["PublishCloudWatchMetricsEnabled"] is True
    )
    assert workgroup["Configuration"]["RequesterPaysEnabled"] is False
    assert "CreationTime" in workgroup


def test_get_work_group_missing_raises_invalid_request(
    store: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="missing"):
        get_work_group(store, {"WorkGroup": "missing"})


def test_list_work_groups_returns_summaries(store: WorkGroupStore) -> None:
    create_work_group(store, {"Name": "analytics"})

    output = list_work_groups(store, None)

    names = [summary["Name"] for summary in output["WorkGroups"]]
    assert names == ["primary", "analytics"]
    primary = output["WorkGroups"][0]
    assert primary["State"] == "ENABLED"
    assert primary["Description"] == ""
    assert primary["EngineVersion"]["EffectiveEngineVersion"] == (
        "Athena engine version 3"
    )
    assert "NextToken" not in output


def test_list_work_groups_paginates_with_max_results(
    store: WorkGroupStore,
) -> None:
    for index in range(4):
        create_work_group(store, {"Name": f"wg-{index}"})

    first = list_work_groups(store, {"MaxResults": 2})
    assert [item["Name"] for item in first["WorkGroups"]] == [
        "primary",
        "wg-0",
    ]
    assert "NextToken" in first

    second = list_work_groups(
        store, {"MaxResults": 2, "NextToken": first["NextToken"]}
    )
    assert [item["Name"] for item in second["WorkGroups"]] == [
        "wg-1",
        "wg-2",
    ]
    assert "NextToken" in second

    third = list_work_groups(
        store, {"MaxResults": 2, "NextToken": second["NextToken"]}
    )
    assert [item["Name"] for item in third["WorkGroups"]] == ["wg-3"]
    assert "NextToken" not in third


def test_list_work_groups_next_token_past_end_returns_empty_page(
    store: WorkGroupStore,
) -> None:
    create_work_group(store, {"Name": "analytics"})

    output = list_work_groups(store, {"NextToken": "2"})

    assert output == {"WorkGroups": []}


def test_list_work_groups_rejects_non_integer_max_results(
    store: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="MaxResults"):
        list_work_groups(store, {"MaxResults": "2"})


@pytest.mark.parametrize("max_results", [0, -1, 51])
def test_list_work_groups_rejects_out_of_bounds_max_results(
    store: WorkGroupStore, max_results: int
) -> None:
    with pytest.raises(InvalidRequestException, match="MaxResults"):
        list_work_groups(store, {"MaxResults": max_results})


def test_list_work_groups_rejects_invalid_next_token(
    store: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="Invalid NextToken"):
        list_work_groups(store, {"NextToken": "not-a-token"})


def test_list_work_groups_rejects_non_string_next_token(
    store: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="NextToken"):
        list_work_groups(store, {"NextToken": 5})


def test_update_work_group_changes_state_only(store: WorkGroupStore) -> None:
    create_work_group(store, {"Name": "Data_Analyst_Group"})

    output = update_work_group(
        store,
        {"WorkGroup": "Data_Analyst_Group", "State": "DISABLED"},
    )

    assert output == {}
    assert store.get("Data_Analyst_Group").state == "DISABLED"


def test_update_work_group_merges_result_configuration(
    store: WorkGroupStore,
) -> None:
    create_work_group(store, {"Name": "analytics"})

    update_work_group(
        store,
        {
            "WorkGroup": "analytics",
            "ConfigurationUpdates": {
                "ResultConfigurationUpdates": {
                    "OutputLocation": "s3://results-bucket/analytics/"
                }
            },
        },
    )

    workgroup = get_work_group(store, {"WorkGroup": "analytics"})["WorkGroup"]
    assert workgroup["Configuration"]["ResultConfiguration"] == {
        "OutputLocation": "s3://results-bucket/analytics/"
    }


def test_update_work_group_rejects_invalid_state(
    store: WorkGroupStore,
) -> None:
    create_work_group(store, {"Name": "analytics"})

    with pytest.raises(InvalidRequestException, match="DISABLED"):
        update_work_group(
            store,
            {"WorkGroup": "analytics", "State": "PAUSED"},
        )


def test_delete_work_group_returns_empty_output(store: WorkGroupStore) -> None:
    create_work_group(store, {"Name": "TeamB"})

    output = delete_work_group(store, {"WorkGroup": "TeamB"})

    assert output == {}
    with pytest.raises(InvalidRequestException, match="TeamB"):
        get_work_group(store, {"WorkGroup": "TeamB"})


def test_delete_primary_is_blocked(store: WorkGroupStore) -> None:
    with pytest.raises(InvalidRequestException, match="primary"):
        delete_work_group(store, {"WorkGroup": "primary"})


NON_CANONICAL_WORKGROUP_NAMES = [
    "a" * 129,
    "bad name!",
    "../escape",
    "with space",
    "with/slash",
]


@pytest.mark.parametrize("name", NON_CANONICAL_WORKGROUP_NAMES)
def test_create_work_group_rejects_non_canonical_name(
    store: WorkGroupStore, name: str
) -> None:
    # WorkGroupName pattern [a-zA-Z0-9._-]{1,128} (service-2.json) is not
    # client-side checked by botocore — these shapes reach the wire.
    with pytest.raises(InvalidRequestException, match="Name"):
        create_work_group(store, {"Name": name})


@pytest.mark.parametrize(
    "operation", [get_work_group, update_work_group, delete_work_group]
)
@pytest.mark.parametrize("name", NON_CANONICAL_WORKGROUP_NAMES)
def test_work_group_member_rejects_non_canonical_name(
    store: WorkGroupStore,
    operation: Callable[[WorkGroupStore, dict[str, object]], object],
    name: str,
) -> None:
    # match the constraint message — "WorkGroup <name> does not exist" would
    # satisfy a bare "WorkGroup" match without any parse-layer check.
    with pytest.raises(InvalidRequestException, match="must match pattern"):
        operation(store, {"WorkGroup": name})


@pytest.mark.parametrize("description", ["x" * 1025])
def test_create_work_group_rejects_oversized_description(
    store: WorkGroupStore, description: str
) -> None:
    with pytest.raises(InvalidRequestException, match="Description"):
        create_work_group(
            store, {"Name": "analytics", "Description": description}
        )


def test_update_work_group_rejects_oversized_description(
    store: WorkGroupStore,
) -> None:
    create_work_group(store, {"Name": "analytics"})

    with pytest.raises(InvalidRequestException, match="Description"):
        update_work_group(
            store,
            {"WorkGroup": "analytics", "Description": "x" * 1025},
        )


def test_create_work_group_accepts_empty_description(
    store: WorkGroupStore,
) -> None:
    # WorkGroupDescriptionString is min 0 in the model — empty is legal.
    create_work_group(store, {"Name": "analytics", "Description": ""})
    assert store.get("analytics").description == ""


@pytest.mark.parametrize("cutoff", [0, 5, 9_999_999])
def test_configuration_rejects_cutoff_below_model_minimum(
    store: WorkGroupStore, cutoff: int
) -> None:
    with pytest.raises(
        InvalidRequestException, match="BytesScannedCutoffPerQuery"
    ):
        create_work_group(
            store,
            {
                "Name": "analytics",
                "Configuration": {"BytesScannedCutoffPerQuery": cutoff},
            },
        )


@pytest.mark.parametrize("cutoff", [0, 9_999_999])
def test_configuration_updates_reject_cutoff_below_model_minimum(
    store: WorkGroupStore, cutoff: int
) -> None:
    create_work_group(store, {"Name": "analytics"})

    with pytest.raises(
        InvalidRequestException, match="BytesScannedCutoffPerQuery"
    ):
        update_work_group(
            store,
            {
                "WorkGroup": "analytics",
                "ConfigurationUpdates": {"BytesScannedCutoffPerQuery": cutoff},
            },
        )


def test_configuration_accepts_model_minimum_cutoff(
    store: WorkGroupStore,
) -> None:
    create_work_group(
        store,
        {
            "Name": "analytics",
            "Configuration": {"BytesScannedCutoffPerQuery": 10_000_000},
        },
    )

    workgroup = get_work_group(store, {"WorkGroup": "analytics"})["WorkGroup"]
    assert (
        workgroup["Configuration"]["BytesScannedCutoffPerQuery"] == 10_000_000
    )


@pytest.mark.parametrize("additional", ["", "x" * 129])
def test_additional_configuration_enforces_name_string_bounds(
    store: WorkGroupStore, additional: str
) -> None:
    with pytest.raises(
        InvalidRequestException, match="AdditionalConfiguration"
    ):
        create_work_group(
            store,
            {
                "Name": "analytics",
                "Configuration": {"AdditionalConfiguration": additional},
            },
        )


@pytest.mark.parametrize(
    "role",
    [
        "not-an-arn",
        "arn:aws:iam::123:role/execution",
        "arn:aws:s3:::amzn-s3-demo-bucket",
    ],
)
def test_configuration_rejects_non_role_arn_execution_role(
    store: WorkGroupStore, role: str
) -> None:
    with pytest.raises(InvalidRequestException, match="ExecutionRole"):
        create_work_group(
            store,
            {"Name": "analytics", "Configuration": {"ExecutionRole": role}},
        )


def test_configuration_updates_reject_non_role_arn_execution_role(
    store: WorkGroupStore,
) -> None:
    create_work_group(store, {"Name": "analytics"})

    with pytest.raises(InvalidRequestException, match="ExecutionRole"):
        update_work_group(
            store,
            {
                "WorkGroup": "analytics",
                "ConfigurationUpdates": {"ExecutionRole": "not-an-arn"},
            },
        )


@pytest.mark.parametrize(
    "tags",
    [
        [{"Key": ""}],
        [{"Key": "k" * 129}],
        [{"Key": "ok", "Value": "v" * 257}],
    ],
)
def test_create_work_group_rejects_out_of_bounds_tags(
    store: WorkGroupStore, tags: list[dict[str, str]]
) -> None:
    with pytest.raises(InvalidRequestException, match="Tag"):
        create_work_group(store, {"Name": "analytics", "Tags": tags})


def test_create_work_group_accepts_tags_at_model_bounds(
    store: WorkGroupStore,
) -> None:
    create_work_group(
        store,
        {
            "Name": "analytics",
            "Tags": [
                {"Key": "k" * 128, "Value": "v" * 256},
                {"Key": "a", "Value": ""},
            ],
        },
    )


@pytest.mark.parametrize(
    "owner", ["not-digits", "12345678901", "1234567890123"]
)
def test_result_configuration_rejects_non_account_id_owner(
    store: WorkGroupStore, owner: str
) -> None:
    with pytest.raises(InvalidRequestException, match="ExpectedBucketOwner"):
        create_work_group(
            store,
            {
                "Name": "analytics",
                "Configuration": {
                    "ResultConfiguration": {"ExpectedBucketOwner": owner}
                },
            },
        )


def test_result_configuration_updates_reject_non_account_id_owner(
    store: WorkGroupStore,
) -> None:
    create_work_group(store, {"Name": "analytics"})

    with pytest.raises(InvalidRequestException, match="ExpectedBucketOwner"):
        update_work_group(
            store,
            {
                "WorkGroup": "analytics",
                "ConfigurationUpdates": {
                    "ResultConfigurationUpdates": {
                        "ExpectedBucketOwner": "abc"
                    }
                },
            },
        )


def test_encryption_configuration_rejects_unknown_option(
    store: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="EncryptionOption"):
        create_work_group(
            store,
            {
                "Name": "analytics",
                "Configuration": {
                    "ResultConfiguration": {
                        "EncryptionConfiguration": {
                            "EncryptionOption": "GUESS"
                        }
                    }
                },
            },
        )


def test_acl_configuration_rejects_unknown_option(
    store: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="S3AclOption"):
        create_work_group(
            store,
            {
                "Name": "analytics",
                "Configuration": {
                    "ResultConfiguration": {
                        "AclConfiguration": {"S3AclOption": "BUCKET_OWNER"}
                    }
                },
            },
        )


@pytest.mark.parametrize(
    "kms_key", ["not-a-key", "arn:aws:kms:us-east-1:123:key/abc"]
)
def test_encryption_configuration_rejects_malformed_kms_key(
    store: WorkGroupStore, kms_key: str
) -> None:
    with pytest.raises(InvalidRequestException, match="KmsKey"):
        create_work_group(
            store,
            {
                "Name": "analytics",
                "Configuration": {
                    "ResultConfiguration": {
                        "EncryptionConfiguration": {
                            "EncryptionOption": "SSE_KMS",
                            "KmsKey": kms_key,
                        }
                    }
                },
            },
        )


def test_managed_results_reject_malformed_kms_key(
    store: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="KmsKey"):
        create_work_group(
            store,
            {
                "Name": "analytics",
                "Configuration": {
                    "ManagedQueryResultsConfiguration": {
                        "Enabled": True,
                        "EncryptionConfiguration": {"KmsKey": "not-a-key"},
                    }
                },
            },
        )


def test_create_work_group_accepts_canonical_members(
    store: WorkGroupStore,
) -> None:
    create_work_group(
        store,
        {
            "Name": "wg-OK._1",
            "Description": "",
            "Tags": [{"Key": "k" * 128, "Value": "v" * 256}],
            "Configuration": {
                "BytesScannedCutoffPerQuery": 10_000_000,
                "AdditionalConfiguration": "{}",
                "ExecutionRole": "arn:aws:iam::123456789012:role/execution",
                "ResultConfiguration": {
                    "EncryptionConfiguration": {
                        "EncryptionOption": "SSE_KMS",
                        "KmsKey": (
                            "arn:aws:kms:us-east-1:123456789012:key/abc"
                        ),
                    },
                    "AclConfiguration": {
                        "S3AclOption": "BUCKET_OWNER_FULL_CONTROL"
                    },
                    "ExpectedBucketOwner": "123456789012",
                },
                "ManagedQueryResultsConfiguration": {
                    "Enabled": True,
                    "EncryptionConfiguration": {"KmsKey": "alias/aws/athena"},
                },
            },
        },
    )

    workgroup = get_work_group(store, {"WorkGroup": "wg-OK._1"})["WorkGroup"]
    assert workgroup["Configuration"]["ExecutionRole"] == (
        "arn:aws:iam::123456789012:role/execution"
    )
