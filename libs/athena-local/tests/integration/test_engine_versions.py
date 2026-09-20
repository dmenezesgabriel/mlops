"""Consumer-parity integration: real boto3 ListEngineVersions round-trip.

MD-5 acceptance check: botocore's ``list_engine_versions`` against the live
app returns the pinned ``EngineVersion`` list (AUTO / Athena engine version 3),
the probe wrangler and the CLI use to resolve engine capabilities.
"""

from __future__ import annotations

import boto3
from botocore.client import BaseClient
from tests.integration.conftest import LiveAthenaServer


def _client(endpoint_url: str) -> BaseClient:
    return boto3.client(
        "athena",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def test_list_engine_versions_with_botocore(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    response = client.list_engine_versions()

    assert response["EngineVersions"] == [
        {
            "SelectedEngineVersion": "AUTO",
            "EffectiveEngineVersion": "Athena engine version 3",
        }
    ]
    assert "NextToken" not in response
