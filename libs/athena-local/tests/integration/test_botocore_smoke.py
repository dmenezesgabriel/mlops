"""End-to-end smoke: a real boto3/botocore client against the live app.

This is the M1 stub-driven round-trip: no docker, no moto — just botocore
sending ``X-Amz-Target: AmazonAthena.GetSession`` over real HTTP and parsing
the shaped error back out of the JSON-1.1 response. ``GetSession`` is a
Studio operation that stays permanently unhandled (ADR-0004), so the probe is
stable even as the control/query plane fills in.
"""

from __future__ import annotations

import boto3
import pytest
from botocore.exceptions import ClientError
from tests.integration.conftest import LiveAthenaServer


def test_botocore_parses_shaped_error_from_live_server(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = boto3.client(
        "athena",
        endpoint_url=live_athena_server.endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )

    with pytest.raises(ClientError) as exc_info:
        client.get_session(SessionId="probe-session")

    response = exc_info.value.response
    assert response["Error"]["Code"] == "InvalidRequestException"
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert "GetSession" in response["Error"]["Message"]
