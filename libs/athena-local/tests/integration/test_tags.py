"""Consumer-parity integration: real boto3 tagging against the live app.

MD-6 acceptance check. TagResource, UntagResource, and ListTagsForResource
round-trip through the JSON-1.1 wire protocol against the ``LiveAthenaServer``
fixture, addressing workgroup and data catalog ARNs (the shape in
``tag-resource``/``list-tags-for-resource.rst``). Unknown resources answer a
shaped 404 ``ResourceNotFoundException``.
"""

from __future__ import annotations

import boto3
import pytest
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from tests.integration.conftest import LiveAthenaServer

PRIMARY_WORKGROUP_ARN = (
    "arn:aws:athena:us-east-1:123456789012:workgroup/primary"
)
DATA_CATALOG_ARN = (
    "arn:aws:athena:us-east-1:123456789012:datacatalog/dynamo_db_catalog"
)


def _client(endpoint_url: str) -> BaseClient:
    return boto3.client(
        "athena",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def test_tag_round_trip_on_workgroup_with_botocore(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    client.tag_resource(
        ResourceARN=PRIMARY_WORKGROUP_ARN,
        Tags=[
            {"Key": "Division", "Value": "West"},
            {"Key": "Team", "Value": "Big Data"},
        ],
    )

    tags = client.list_tags_for_resource(ResourceARN=PRIMARY_WORKGROUP_ARN)[
        "Tags"
    ]
    assert tags == [
        {"Key": "Division", "Value": "West"},
        {"Key": "Team", "Value": "Big Data"},
    ]

    client.untag_resource(ResourceARN=PRIMARY_WORKGROUP_ARN, TagKeys=["Team"])
    tags = client.list_tags_for_resource(ResourceARN=PRIMARY_WORKGROUP_ARN)[
        "Tags"
    ]
    assert tags == [{"Key": "Division", "Value": "West"}]


def test_tag_data_catalog_with_botocore(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)
    client.create_data_catalog(
        Name="dynamo_db_catalog",
        Type="LAMBDA",
    )

    client.tag_resource(
        ResourceARN=DATA_CATALOG_ARN,
        Tags=[{"Key": "Division", "Value": "Mountain"}],
    )

    tags = client.list_tags_for_resource(ResourceARN=DATA_CATALOG_ARN)["Tags"]
    assert tags == [{"Key": "Division", "Value": "Mountain"}]


def test_list_tags_for_untagged_resource_returns_empty(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    tags = client.list_tags_for_resource(ResourceARN=PRIMARY_WORKGROUP_ARN)[
        "Tags"
    ]

    assert tags == []


def test_tag_unknown_resource_is_shaped_404(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    with pytest.raises(ClientError) as exc_info:
        client.list_tags_for_resource(
            ResourceARN=(
                "arn:aws:athena:us-east-1:123456789012:"
                "workgroup/does-not-exist"
            )
        )

    error = exc_info.value.response["Error"]
    assert error["Code"] == "ResourceNotFoundException"
    assert exc_info.value.response["ResponseMetadata"]["HTTPStatusCode"] == 404
    assert "does-not-exist" in error["Message"]


def test_list_tags_for_resource_returns_all_tags_in_one_page(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)
    client.tag_resource(
        ResourceARN=PRIMARY_WORKGROUP_ARN,
        Tags=[{"Key": f"key{i}", "Value": f"value{i}"} for i in range(5)],
    )

    response = client.list_tags_for_resource(
        ResourceARN=PRIMARY_WORKGROUP_ARN, MaxResults=75
    )

    assert response["Tags"] == [
        {"Key": f"key{i}", "Value": f"value{i}"} for i in range(5)
    ]
    assert "NextToken" not in response
