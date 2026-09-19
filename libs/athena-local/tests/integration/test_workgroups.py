"""Consumer-parity integration: real boto3 + awswrangler against the live app.

MD-1 acceptance check. Uses the LiveAthenaServer fixture (threaded uvicorn on
a random port) — the same pattern the M1 smoke already uses, so no docker
stack is needed for the workgroup control plane. The awswrangler config path
is the exact function wrangler runs before every query
(``awswrangler/athena/_utils.py:158-187``); its endpoint override is the
documented ``wr.config.athena_endpoint_url`` (``awswrangler/_utils.py:259-260``).
"""

from __future__ import annotations

import boto3
import pytest
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from tests.integration.conftest import LiveAthenaServer


def _client(endpoint_url: str) -> BaseClient:
    return boto3.client(
        "athena",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def test_workgroup_crud_round_trip_with_botocore(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    client.create_work_group(
        Name="analytics",
        Description="Analytics team",
        Configuration={"EnforceWorkGroupConfiguration": True},
        Tags=[{"Key": "Division", "Value": "Analytics"}],
    )

    workgroup = client.get_work_group(WorkGroup="analytics")["WorkGroup"]
    assert workgroup["Name"] == "analytics"
    assert workgroup["State"] == "ENABLED"
    assert workgroup["Description"] == "Analytics team"
    assert workgroup["Configuration"]["EnforceWorkGroupConfiguration"] is True

    names = [item["Name"] for item in client.list_work_groups()["WorkGroups"]]
    assert names == ["primary", "analytics"]

    client.update_work_group(WorkGroup="analytics", State="DISABLED")
    assert (
        client.get_work_group(WorkGroup="analytics")["WorkGroup"]["State"]
        == "DISABLED"
    )

    client.delete_work_group(WorkGroup="analytics")
    assert [
        item["Name"] for item in client.list_work_groups()["WorkGroups"]
    ] == ["primary"]


def test_duplicate_create_work_group_is_shaped_400(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)
    client.create_work_group(Name="analytics")

    with pytest.raises(ClientError) as exc_info:
        client.create_work_group(Name="analytics")

    error = exc_info.value.response["Error"]
    assert error["Code"] == "InvalidRequestException"
    assert exc_info.value.response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert "analytics" in error["Message"]


def test_get_missing_work_group_is_shaped_400(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    with pytest.raises(ClientError) as exc_info:
        client.get_work_group(WorkGroup="missing")

    error = exc_info.value.response["Error"]
    assert error["Code"] == "InvalidRequestException"
    assert "missing" in error["Message"]


def test_delete_primary_work_group_is_blocked(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    with pytest.raises(ClientError) as exc_info:
        client.delete_work_group(WorkGroup="primary")

    error = exc_info.value.response["Error"]
    assert error["Code"] == "InvalidRequestException"
    assert "primary" in error["Message"]


def test_awswrangler_get_work_group_config_reads_created_workgroup(
    live_athena_server: LiveAthenaServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import awswrangler as wr

    monkeypatch.setattr(
        wr.config, "athena_endpoint_url", live_athena_server.endpoint_url
    )
    session = _wrangler_session()
    session.client(
        "athena", endpoint_url=live_athena_server.endpoint_url
    ).create_work_group(
        Name="analytics",
        Configuration={
            "ResultConfiguration": {
                "OutputLocation": "s3://results-bucket/analytics/"
            },
            "EnforceWorkGroupConfiguration": True,
            "PublishCloudWatchMetricsEnabled": True,
        },
    )

    config = wr.athena._utils._get_workgroup_config(
        session=session, workgroup="analytics"
    )

    assert config.s3_output == "s3://results-bucket/analytics/"
    assert config.enforced is True
    assert config.encryption is None
    assert config.kms_key is None
    assert config.managed_results is False


def test_awswrangler_default_wrangler_path_reads_primary(
    live_athena_server: LiveAthenaServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import awswrangler as wr

    monkeypatch.setattr(
        wr.config, "athena_endpoint_url", live_athena_server.endpoint_url
    )

    # The exact call wrangler performs when a query names no workgroup.
    config = wr.athena._utils._get_workgroup_config(
        session=_wrangler_session(), workgroup="primary"
    )

    assert config.enforced is False
    assert config.s3_output is None
    assert config.encryption is None
    assert config.managed_results is False


def _wrangler_session() -> boto3.Session:
    return boto3.Session(
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
