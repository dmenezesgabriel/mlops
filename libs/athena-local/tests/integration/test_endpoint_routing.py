"""Per-service endpoint routing across the supported consumer clients.

The Athena emulator and moto expose deliberately different protocols. Successful
operations therefore prove that Athena-only configuration does not redirect the
S3 or Glue data plane (ADR-0002).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import awswrangler as wr
import boto3
import pytest
from botocore.client import Config
from tests.integration._cli_harness import CliResult, aws_binary, run_aws_cli
from tests.integration._terraform_harness import require_go_binary, run_go_test
from tests.integration.conftest import LiveAthenaServer, LiveMotoServer


@dataclass(frozen=True)
class RoutingEndpoints:
    """Distinct live endpoints used to detect service cross-routing."""

    athena: str
    moto: str


@pytest.fixture()
def routing_endpoints(
    live_athena_server: LiveAthenaServer,
    live_moto_server: LiveMotoServer,
    monkeypatch: pytest.MonkeyPatch,
) -> RoutingEndpoints:
    """Configure moto globally and override only the Athena service endpoint."""
    environment = {
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_ENDPOINT_URL": live_moto_server.url,
        "AWS_ENDPOINT_URL_ATHENA": live_athena_server.endpoint_url,
        "AWS_CONFIG_FILE": os.devnull,
        "AWS_SHARED_CREDENTIALS_FILE": os.devnull,
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    for name in (
        "AWS_PROFILE",
        "AWS_ENDPOINT_URL_GLUE",
        "AWS_ENDPOINT_URL_S3",
    ):
        monkeypatch.delenv(name, raising=False)
    return RoutingEndpoints(
        athena=live_athena_server.endpoint_url,
        moto=live_moto_server.url,
    )


def test_boto3_routes_only_athena_to_the_emulator(
    routing_endpoints: RoutingEndpoints,
) -> None:
    """Service-specific botocore configuration preserves the data plane."""
    config = Config(retries={"max_attempts": 0})
    session = boto3.Session()
    athena = session.client("athena", config=config)
    s3 = session.client("s3", config=config)
    glue = session.client("glue", config=config)

    assert athena.meta.endpoint_url == routing_endpoints.athena
    assert s3.meta.endpoint_url == routing_endpoints.moto
    assert glue.meta.endpoint_url == routing_endpoints.moto
    assert "primary" in {
        group["Name"] for group in athena.list_work_groups()["WorkGroups"]
    }
    buckets = s3.list_buckets()["Buckets"]
    assert isinstance(buckets, list)
    assert all("Name" in bucket for bucket in buckets)
    assert isinstance(glue.get_databases()["DatabaseList"], list)


def test_awswrangler_routes_only_athena_to_the_emulator(
    routing_endpoints: RoutingEndpoints,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """awswrangler's Athena override does not capture S3 or Glue clients."""
    monkeypatch.setattr(
        wr.config, "athena_endpoint_url", routing_endpoints.athena
    )
    monkeypatch.setattr(wr.config, "s3_endpoint_url", None)
    monkeypatch.setattr(wr.config, "glue_endpoint_url", None)

    work_group = wr.athena.get_work_group(workgroup="primary")
    buckets = wr.s3.list_buckets()
    databases = list(wr.catalog.get_databases())

    assert work_group["WorkGroup"]["Name"] == "primary"
    assert isinstance(buckets, list)
    assert all(isinstance(bucket, str) for bucket in buckets)
    assert all(isinstance(database, dict) for database in databases)


def test_aws_cli_routes_environment_and_explicit_athena_endpoints(
    routing_endpoints: RoutingEndpoints,
) -> None:
    """The CLI honors both its endpoint flag and botocore service precedence."""
    binary = aws_binary()
    if binary is None:
        pytest.skip("aws CLI not installed; add awscli to the dev group")
    athena_tokens = ["athena", "get-work-group", "--work-group", "primary"]

    environment_result = run_aws_cli(binary, athena_tokens)
    explicit_result = run_aws_cli(
        binary, [*athena_tokens, "--endpoint-url", routing_endpoints.athena]
    )
    s3_result = run_aws_cli(binary, ["s3api", "list-buckets"])
    glue_result = run_aws_cli(binary, ["glue", "get-databases"])

    assert (
        assert_json_object(environment_result)["WorkGroup"]["Name"]
        == "primary"
    )
    assert (
        assert_json_object(explicit_result)["WorkGroup"]["Name"] == "primary"
    )
    assert isinstance(assert_json_object(s3_result)["Buckets"], list)
    assert isinstance(assert_json_object(glue_result)["DatabaseList"], list)


def test_terraform_sdk_routes_only_athena_to_the_emulator(
    routing_endpoints: RoutingEndpoints,
) -> None:
    """The provider's pinned Go SDK resolves each service-specific endpoint."""
    run_go_test(
        require_go_binary(),
        "TestEndpointRouting",
        {
            "AWS_ENDPOINT_URL": routing_endpoints.moto,
            "AWS_ENDPOINT_URL_ATHENA": routing_endpoints.athena,
        },
    )


def assert_json_object(result: CliResult) -> dict[str, object]:
    """Return one successful CLI JSON object with a useful failure message."""
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), f"expected JSON object, got {payload!r}"
    return payload
