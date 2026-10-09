"""Handler tests for the three resource tagging operations.

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


@pytest.mark.parametrize("member_key", ["", "k" * 129])
def test_untag_resource_rejects_non_canonical_tag_key_members(
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
    member_key: str,
) -> None:
    # TagKeyList members are TagKey-shaped: 1..128 (service-2.json). An
    # empty key used to untag nothing and return success (AU-27 probe P-E).
    _create_analytics(workgroups)
    with pytest.raises(InvalidRequestException, match=r"TagKeys\[0\]"):
        untag_resource(
            workgroups,
            catalogs,
            {
                "ResourceARN": WORKGROUP_ARN,
                "TagKeys": [member_key],
            },
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


def test_tag_resource_rejects_tags_beyond_quota(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    # Athena resources hold at most 50 tags (service-side; TagList carries no
    # model max). Two 40-key requests used to reach 80 tags untouched (AU-27
    # probe P-A), and the failed request must not leave a partial merge behind.
    _create_analytics(workgroups)
    tag_resource(
        workgroups,
        catalogs,
        {
            "ResourceARN": WORKGROUP_ARN,
            "Tags": [{"Key": f"key{i}", "Value": "v"} for i in range(40)],
        },
    )

    with pytest.raises(InvalidRequestException, match="at most 50 tags"):
        tag_resource(
            workgroups,
            catalogs,
            {
                "ResourceARN": WORKGROUP_ARN,
                "Tags": [
                    {"Key": f"other{i}", "Value": "v"} for i in range(40)
                ],
            },
        )

    assert len(workgroups.by_name["analytics"].tags) == 40


def test_tag_resource_accepts_fifty_tags_and_rejects_fifty_one(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    _create_analytics(workgroups)
    tag_resource(
        workgroups,
        catalogs,
        {
            "ResourceARN": WORKGROUP_ARN,
            "Tags": [{"Key": f"key{i}", "Value": "v"} for i in range(50)],
        },
    )

    with pytest.raises(InvalidRequestException, match="got 51"):
        tag_resource(
            workgroups,
            catalogs,
            {
                "ResourceARN": WORKGROUP_ARN,
                "Tags": [{"Key": "overflow", "Value": "v"}],
            },
        )

    assert len(workgroups.by_name["analytics"].tags) == 50


def test_tag_resource_replaces_key_at_quota(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    # Replacing an existing key reuses its slot, so the distinct-key count
    # stays at 50 and the request is legal.
    _create_analytics(workgroups)
    tag_resource(
        workgroups,
        catalogs,
        {
            "ResourceARN": WORKGROUP_ARN,
            "Tags": [{"Key": f"key{i}", "Value": "v"} for i in range(50)],
        },
    )
    tag_resource(
        workgroups,
        catalogs,
        {
            "ResourceARN": WORKGROUP_ARN,
            "Tags": [{"Key": "key0", "Value": "x"}],
        },
    )

    stored = workgroups.by_name["analytics"].tags
    assert len(stored) == 50
    assert {tag.key: tag.value for tag in stored}["key0"] == "x"


def test_list_tags_for_resource_rejects_non_canonical_next_token(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    # A token can never be issued (MaxTagsCount floors MaxResults at 75 while
    # resources hold at most 50 tags), but a supplied non-canonical token must
    # still answer 400 like every other list op (G-248 class).
    _create_analytics(workgroups)
    with pytest.raises(InvalidRequestException, match="Invalid NextToken"):
        list_tags_for_resource(
            workgroups,
            catalogs,
            {"ResourceARN": WORKGROUP_ARN, "NextToken": "not-a-token"},
        )


def test_list_tags_for_resource_honours_offset_token(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    _create_analytics(workgroups)
    tag_resource(
        workgroups,
        catalogs,
        {
            "ResourceARN": WORKGROUP_ARN,
            "Tags": [{"Key": f"key{i}", "Value": "v"} for i in range(3)],
        },
    )

    output = list_tags_for_resource(
        workgroups, catalogs, {"ResourceARN": WORKGROUP_ARN, "NextToken": "1"}
    )

    assert output == {
        "Tags": [
            {"Key": "key1", "Value": "v"},
            {"Key": "key2", "Value": "v"},
        ]
    }
