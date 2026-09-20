"""Step definitions for the resource tagging BDD feature (MD-6).

Steps exercise the handler layer directly against fresh in-memory workgroup and
data catalog stores per scenario — the same boundary pytest-bdd asserts for the
canonical model — so the feature runs without HTTP or docker while pinning the
JSON-1.1 wire behavior consumers depend on.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from athena_local.data_catalog_state import DataCatalogStore
from athena_local.data_catalogs import create_data_catalog
from athena_local.errors import (
    AthenaError,
    InvalidRequestException,
    ResourceNotFoundException,
)
from athena_local.state import WorkGroupStore
from athena_local.tags import (
    list_tags_for_resource,
    tag_resource,
    untag_resource,
)
from pytest_bdd import given, parsers, scenarios, then, when

PRIMARY_WORKGROUP_ARN = (
    "arn:aws:athena:us-east-1:123456789012:workgroup/primary"
)
DATA_CATALOG_ARN = (
    "arn:aws:athena:us-east-1:123456789012:datacatalog/dynamo_db_catalog"
)

scenarios("tags.feature")


@dataclass
class TagOutcome:
    """State shared between the when and then steps of a scenario."""

    error: AthenaError | None = None
    tags: list[dict[str, str]] | None = None


@pytest.fixture
def workgroups() -> WorkGroupStore:
    return WorkGroupStore()


@pytest.fixture
def catalogs() -> DataCatalogStore:
    return DataCatalogStore()


@pytest.fixture
def outcome() -> TagOutcome:
    return TagOutcome()


@given("a fresh tagging registry")
def _fresh_registry(
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
    outcome: TagOutcome,
) -> None:
    assert list(workgroups.by_name) == ["primary"]
    assert list(catalogs.by_name) == ["AwsDataCatalog"]
    outcome.error = None
    outcome.tags = None


@given("the primary workgroup has no tags")
def _untagged_primary_workgroup(
    workgroups: WorkGroupStore,
) -> None:
    assert workgroups.by_name["primary"].tags == []


@given(parsers.parse('a LAMBDA data catalog named "{name}"'))
def _create_lambda_catalog(catalogs: DataCatalogStore, name: str) -> None:
    create_data_catalog(catalogs, {"Name": name, "Type": "LAMBDA"})


@when(
    parsers.parse(
        'TagResource adds "{first}: {first_value}" and "{second}: {second_value}" to the primary workgroup'
    )
)
def _tag_primary_workgroup(
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
    first: str,
    first_value: str,
    second: str,
    second_value: str,
) -> None:
    tag_resource(
        workgroups,
        catalogs,
        {
            "ResourceARN": PRIMARY_WORKGROUP_ARN,
            "Tags": [
                {"Key": first, "Value": first_value},
                {"Key": second, "Value": second_value},
            ],
        },
    )


@when(
    parsers.parse(
        'UntagResource removes the "{key}" key from the primary workgroup'
    )
)
def _untag_primary_workgroup(
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
    key: str,
) -> None:
    untag_resource(
        workgroups,
        catalogs,
        {"ResourceARN": PRIMARY_WORKGROUP_ARN, "TagKeys": [key]},
    )


@when("ListTagsForResource targets the primary workgroup")
def _list_primary_workgroup(
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
    outcome: TagOutcome,
) -> None:
    outcome.tags = list_tags_for_resource(
        workgroups, catalogs, {"ResourceARN": PRIMARY_WORKGROUP_ARN}
    )["Tags"]


@when(parsers.parse('TagResource adds "{key}: {value}" to the data catalog'))
def _tag_data_catalog(
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
    key: str,
    value: str,
) -> None:
    tag_resource(
        workgroups,
        catalogs,
        {
            "ResourceARN": DATA_CATALOG_ARN,
            "Tags": [{"Key": key, "Value": value}],
        },
    )


@then("ListTagsForResource returns the catalog tag")
def _list_data_catalog(
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
    outcome: TagOutcome,
) -> None:
    outcome.tags = list_tags_for_resource(
        workgroups, catalogs, {"ResourceARN": DATA_CATALOG_ARN}
    )["Tags"]


@when("TagResource targets a non-existent workgroup ARN")
def _tag_missing_workgroup(
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
    outcome: TagOutcome,
) -> None:
    try:
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
    except AthenaError as error:
        outcome.error = error


@when(parsers.parse('TagResource targets the malformed ARN "{arn}"'))
def _tag_malformed_arn(
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
    outcome: TagOutcome,
    arn: str,
) -> None:
    try:
        tag_resource(
            workgroups,
            catalogs,
            {"ResourceARN": arn, "Tags": [{"Key": "k", "Value": "v"}]},
        )
    except AthenaError as error:
        outcome.error = error


@then("ListTagsForResource returns the two tags")
def _two_tags(
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
) -> None:
    tags = list_tags_for_resource(
        workgroups, catalogs, {"ResourceARN": PRIMARY_WORKGROUP_ARN}
    )["Tags"]
    assert tags == [
        {"Key": "Division", "Value": "West"},
        {"Key": "Team", "Value": "Big Data"},
    ]


@then(parsers.parse('ListTagsForResource returns only the "{key}" tag'))
def _only_tag(
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
    key: str,
) -> None:
    tags = list_tags_for_resource(
        workgroups, catalogs, {"ResourceARN": PRIMARY_WORKGROUP_ARN}
    )["Tags"]
    assert tags == [{"Key": key, "Value": "West"}]


@then("the response contains an empty tag list")
def _empty_tags(outcome: TagOutcome) -> None:
    assert outcome.tags == []


@then("TagResource answers ResourceNotFoundException")
def _error_is_not_found(outcome: TagOutcome) -> None:
    assert isinstance(outcome.error, ResourceNotFoundException)


@then("TagResource answers InvalidRequestException")
def _error_is_invalid_request(outcome: TagOutcome) -> None:
    assert isinstance(outcome.error, InvalidRequestException)
