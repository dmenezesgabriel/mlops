"""Handler tests for the three resource tagging operations (MD-6).

TagResource, UntagResource, and ListTagsForResource operate on workgroup and
data catalog ARNs (``arn:aws:athena:<region>:<account>:<type>/<name>`` —
matching the CLI ``tag-resource``/``list-tags-for-resource`` examples). The
service-2.json declares ``ResourceNotFoundException`` for all three ops, so a
well-formed ARN pointing at an unknown resource answers 404 while a malformed
ARN answers ``InvalidRequestException``.
"""

from __future__ import annotations

import pytest
from athena_local.data_catalog_state import DataCatalogStore
from athena_local.data_catalogs import create_data_catalog
from athena_local.dispatch import implemented_operations
from athena_local.errors import (
    InvalidRequestException,
    ResourceNotFoundException,
)
from athena_local.schemas import WorkGroupConfiguration
from athena_local.state import WorkGroupStore
from athena_local.tags import (
    list_tags_for_resource,
    tag_resource,
    untag_resource,
)

TAG_OPERATIONS = {"TagResource", "UntagResource", "ListTagsForResource"}

WORKGROUP_ARN = "arn:aws:athena:us-east-1:123456789012:workgroup/analytics"
PRIMARY_WORKGROUP_ARN = (
    "arn:aws:athena:us-east-1:123456789012:workgroup/primary"
)
DATA_CATALOG_ARN = (
    "arn:aws:athena:us-east-1:123456789012:datacatalog/dynamo_db_catalog"
)


@pytest.fixture()
def workgroups() -> WorkGroupStore:
    return WorkGroupStore()


@pytest.fixture()
def catalogs() -> DataCatalogStore:
    return DataCatalogStore()


def _create_analytics(workgroups: WorkGroupStore) -> None:
    workgroups.create(
        name="analytics",
        configuration=WorkGroupConfiguration(),
        description=None,
        tags=[],
    )


def test_tag_operations_are_registered() -> None:
    import athena_local.main  # noqa: F401

    assert TAG_OPERATIONS <= implemented_operations()


def test_tag_resource_adds_tags_to_workgroup(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    _create_analytics(workgroups)

    tag_resource(
        workgroups,
        catalogs,
        {
            "ResourceARN": WORKGROUP_ARN,
            "Tags": [
                {"Key": "Division", "Value": "West"},
                {"Key": "Team", "Value": "Big Data"},
            ],
        },
    )

    tags = workgroups.by_name["analytics"].tags
    assert {tag.key: tag.value for tag in tags} == {
        "Division": "West",
        "Team": "Big Data",
    }


def test_tag_resource_replaces_existing_key(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    _create_analytics(workgroups)

    tag_resource(
        workgroups,
        catalogs,
        {
            "ResourceARN": WORKGROUP_ARN,
            "Tags": [{"Key": "Division", "Value": "West"}],
        },
    )
    tag_resource(
        workgroups,
        catalogs,
        {
            "ResourceARN": WORKGROUP_ARN,
            "Tags": [{"Key": "Division", "Value": "East"}],
        },
    )

    tags = workgroups.by_name["analytics"].tags
    assert {tag.key: tag.value for tag in tags} == {"Division": "East"}


def test_tag_resource_requires_tags(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    with pytest.raises(InvalidRequestException, match="Tags"):
        tag_resource(
            workgroups, catalogs, {"ResourceARN": PRIMARY_WORKGROUP_ARN}
        )


def test_tag_resource_requires_non_empty_tags(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    with pytest.raises(InvalidRequestException, match="Tags"):
        tag_resource(
            workgroups,
            catalogs,
            {"ResourceARN": PRIMARY_WORKGROUP_ARN, "Tags": []},
        )


def test_untag_resource_removes_keys(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    _create_analytics(workgroups)
    tag_resource(
        workgroups,
        catalogs,
        {
            "ResourceARN": WORKGROUP_ARN,
            "Tags": [
                {"Key": "Division", "Value": "West"},
                {"Key": "Team", "Value": "Big Data"},
            ],
        },
    )

    untag_resource(
        workgroups,
        catalogs,
        {"ResourceARN": WORKGROUP_ARN, "TagKeys": ["Team"]},
    )

    tags = workgroups.by_name["analytics"].tags
    assert {tag.key for tag in tags} == {"Division"}


def test_untag_resource_unknown_key_is_noop(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    _create_analytics(workgroups)
    tag_resource(
        workgroups,
        catalogs,
        {
            "ResourceARN": WORKGROUP_ARN,
            "Tags": [{"Key": "Division", "Value": "West"}],
        },
    )

    untag_resource(
        workgroups,
        catalogs,
        {"ResourceARN": WORKGROUP_ARN, "TagKeys": ["Missing"]},
    )

    tags = workgroups.by_name["analytics"].tags
    assert {tag.key for tag in tags} == {"Division"}


def test_untag_resource_requires_tag_keys(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    with pytest.raises(InvalidRequestException, match="TagKeys"):
        untag_resource(
            workgroups, catalogs, {"ResourceARN": PRIMARY_WORKGROUP_ARN}
        )


def test_list_tags_for_resource_returns_tags(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    _create_analytics(workgroups)
    tag_resource(
        workgroups,
        catalogs,
        {
            "ResourceARN": WORKGROUP_ARN,
            "Tags": [
                {"Key": "Division", "Value": "West"},
                {"Key": "Team", "Value": "Big Data"},
            ],
        },
    )

    output = list_tags_for_resource(
        workgroups, catalogs, {"ResourceARN": WORKGROUP_ARN}
    )

    assert output["Tags"] == [
        {"Key": "Division", "Value": "West"},
        {"Key": "Team", "Value": "Big Data"},
    ]
    assert "NextToken" not in output


def test_list_tags_for_resource_untagged_resource_returns_empty(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    output = list_tags_for_resource(
        workgroups, catalogs, {"ResourceARN": PRIMARY_WORKGROUP_ARN}
    )

    assert output["Tags"] == []


def test_list_tags_for_resource_returns_all_tags_in_one_page(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    _create_analytics(workgroups)
    tag_resource(
        workgroups,
        catalogs,
        {
            "ResourceARN": WORKGROUP_ARN,
            "Tags": [
                {"Key": f"key{i}", "Value": f"value{i}"} for i in range(5)
            ],
        },
    )

    output = list_tags_for_resource(
        workgroups, catalogs, {"ResourceARN": WORKGROUP_ARN}
    )

    # MaxResults is bounded below at 75 by the model while resources hold at
    # most 50 tags, so a single response always carries every tag and no
    # NextToken can ever be produced.
    assert output == {
        "Tags": [{"Key": f"key{i}", "Value": f"value{i}"} for i in range(5)]
    }


def test_tag_operations_target_data_catalog(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    create_data_catalog(
        catalogs,
        {"Name": "dynamo_db_catalog", "Type": "LAMBDA"},
    )
    tag_resource(
        workgroups,
        catalogs,
        {
            "ResourceARN": DATA_CATALOG_ARN,
            "Tags": [{"Key": "Division", "Value": "Mountain"}],
        },
    )

    output = list_tags_for_resource(
        workgroups, catalogs, {"ResourceARN": DATA_CATALOG_ARN}
    )

    assert output["Tags"] == [{"Key": "Division", "Value": "Mountain"}]


def test_tag_unknown_resource_raises_not_found(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    with pytest.raises(ResourceNotFoundException, match="does-not-exist"):
        tag_resource(
            workgroups,
            catalogs,
            {
                "ResourceARN": (
                    "arn:aws:athena:us-east-1:123456789012:"
                    "workgroup/does-not-exist"
                ),
                "Tags": [{"Key": "k", "Value": "v"}],
            },
        )
    with pytest.raises(ResourceNotFoundException, match="does-not-exist"):
        list_tags_for_resource(
            workgroups,
            catalogs,
            {
                "ResourceARN": (
                    "arn:aws:athena:us-east-1:123456789012:"
                    "datacatalog/does-not-exist"
                )
            },
        )


def test_tag_unmodeled_resource_type_is_invalid_request(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    # Research executions carry no tag ARN; a well-formed fragment with an
    # unmodeled type is structurally invalid, so InvalidRequestException.
    with pytest.raises(InvalidRequestException, match="cannot be tagged"):
        tag_resource(
            workgroups,
            catalogs,
            {
                "ResourceARN": (
                    "arn:aws:athena:us-east-1:123456789012:execution/abc-123"
                ),
                "Tags": [{"Key": "k", "Value": "v"}],
            },
        )


def test_tag_malformed_arn_is_invalid_request(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    with pytest.raises(
        InvalidRequestException, match="Invalid Athena resource ARN"
    ):
        tag_resource(
            workgroups,
            catalogs,
            {
                "ResourceARN": "not-an-arn",
                "Tags": [{"Key": "k", "Value": "v"}],
            },
        )
