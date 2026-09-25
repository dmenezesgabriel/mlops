"""CS-4: Terraform-provider operation shapes through Go v2 and boto3.

The provider's five Athena resources use the same JSON-1.1 operations as the
other consumers.  The Go test module is pinned to the AWS SDK versions used by
terraform-provider-aws and sends the provider-shaped create/read/update/delete
requests through the live emulator.  This test runs that module as a subprocess,
then repeats the resource-family witnesses with boto3 so a wire change cannot
pass one SDK while breaking the other.

The shared consumer harness supplies Trino, moto S3/Glue, a seeded database, and
an output bucket.  That is required for ``aws_athena_database``: the provider
starts DDL, polls the execution, reads Glue metadata, and starts the drop DDL.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import boto3
import pytest
from athena_local.catalog_metadata import register_catalog_metadata_handlers
from athena_local.glue_proxy import GlueProxy
from athena_local.main import data_catalog_store
from botocore.client import BaseClient, Config
from botocore.exceptions import ClientError
from tests.integration._consumer_harness import (
    ConsumerHarness,
    consumer_harness_scope,
)
from tests.integration.conftest import LiveAthenaServer

GO_MODULE = Path(__file__).parents[1] / "terraform"
GO_TEST_TIMEOUT_SECONDS = 180.0
QUERY_TIMEOUT_SECONDS = 30.0
TERMINAL_QUERY_STATES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED"})


def _go_binary() -> Path | None:
    configured = os.environ.get("ATHENA_GO_BINARY")
    if configured:
        path = Path(configured)
        if path.is_file():
            return path
        pytest.fail(f"ATHENA_GO_BINARY does not point to a file: {configured}")
    found = shutil.which("go")
    return Path(found) if found is not None else None


def _run_go_test(
    binary: Path, harness: ConsumerHarness, endpoint: str
) -> None:
    environment = {
        **os.environ,
        "ATHENA_ENDPOINT_URL": endpoint,
        "ATHENA_PROVIDER_BUCKET": harness.bucket,
        "ATHENA_PROVIDER_DATABASE": harness.database,
        "ATHENA_PROVIDER_OUTPUT_LOCATION": f"s3://{harness.bucket}",
        "ATHENA_PROVIDER_WORKGROUP": "primary",
        "GOFLAGS": "-mod=readonly",
        "GOTOOLCHAIN": "local",
    }
    command = [
        str(binary),
        "test",
        "-run",
        "^TestProviderOperationShapes$",
        "-count=1",
        "-v",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=GO_MODULE,
            env=environment,
            capture_output=True,
            text=True,
            timeout=GO_TEST_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        pytest.fail(
            "AWS SDK for Go v2 parity test timed out: "
            f"stdout={error.stdout!r}, stderr={error.stderr!r}"
        )
    if result.returncode != 0:
        pytest.fail(
            "AWS SDK for Go v2 parity test failed:\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def _poll_boto3_query(client: BaseClient, query_id: str) -> None:
    deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        response = client.get_query_execution(QueryExecutionId=query_id)
        execution = response["QueryExecution"]
        assert isinstance(execution, dict)
        status = execution["Status"]
        assert isinstance(status, dict)
        state = status["State"]
        assert isinstance(state, str)
        if state in TERMINAL_QUERY_STATES:
            assert state == "SUCCEEDED", status.get("StateChangeReason")
            return
        time.sleep(0.1)
    pytest.fail(f"boto3 query {query_id} did not finish within 30s")


def _exercise_boto3_control_plane(
    client: BaseClient, database: str, suffix: str
) -> None:
    workgroup = f"boto3_wg_{suffix}"
    client.create_work_group(
        Name=workgroup,
        Description="CS-4 boto3 witness",
        Configuration={"EnforceWorkGroupConfiguration": True},
    )
    try:
        fetched = client.get_work_group(WorkGroup=workgroup)["WorkGroup"]
        assert fetched["Name"] == workgroup
        client.update_work_group(
            WorkGroup=workgroup,
            Description="CS-4 boto3 witness updated",
            State="DISABLED",
        )
        assert (
            client.get_work_group(WorkGroup=workgroup)["WorkGroup"]["State"]
            == "DISABLED"
        )
    finally:
        try:
            client.delete_work_group(WorkGroup=workgroup)
        except ClientError:
            pass

    named_query = client.create_named_query(
        Name=f"boto3_named_query_{suffix}",
        Database=database,
        QueryString="SELECT 1",
        Description="CS-4 boto3 witness",
    )["NamedQueryId"]
    try:
        fetched = client.get_named_query(NamedQueryId=named_query)[
            "NamedQuery"
        ]
        assert fetched["QueryString"] == "SELECT 1"
    finally:
        try:
            client.delete_named_query(NamedQueryId=named_query)
        except ClientError:
            pass

    catalog_name = f"boto3_catalog_{suffix}"
    client.create_data_catalog(
        Name=catalog_name,
        Type="LAMBDA",
        Description="CS-4 boto3 witness",
        Parameters={
            "function": "arn:aws:lambda:us-east-1:123456789012:function:one"
        },
    )
    try:
        fetched = client.get_data_catalog(Name=catalog_name)["DataCatalog"]
        assert fetched["Type"] == "LAMBDA"
        client.update_data_catalog(
            Name=catalog_name,
            Type="LAMBDA",
            Description="CS-4 boto3 witness updated",
            Parameters={
                "function": "arn:aws:lambda:us-east-1:123456789012:function:two"
            },
        )
        assert (
            client.get_data_catalog(Name=catalog_name)["DataCatalog"][
                "Description"
            ]
            == "CS-4 boto3 witness updated"
        )
    finally:
        try:
            client.delete_data_catalog(Name=catalog_name)
        except ClientError:
            pass

    statement_name = f"boto3_statement_{suffix}"
    client.create_prepared_statement(
        StatementName=statement_name,
        WorkGroup="primary",
        QueryStatement="SELECT ?",
        Description="CS-4 boto3 witness",
    )
    try:
        fetched = client.get_prepared_statement(
            StatementName=statement_name, WorkGroup="primary"
        )["PreparedStatement"]
        assert fetched["QueryStatement"] == "SELECT ?"
        client.update_prepared_statement(
            StatementName=statement_name,
            WorkGroup="primary",
            QueryStatement="SELECT ? + 1",
            Description="CS-4 boto3 witness updated",
        )
    finally:
        try:
            client.delete_prepared_statement(
                StatementName=statement_name, WorkGroup="primary"
            )
        except ClientError:
            pass


def test_terraform_provider_operation_shapes(
    live_athena_server: LiveAthenaServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binary = _go_binary()
    if binary is None:
        if os.environ.get("ATHENA_GO_REQUIRED") == "1":
            pytest.fail("Go toolchain is required for CS-4 but was not found")
        pytest.skip("Go toolchain unavailable; set PATH or ATHENA_GO_BINARY")

    suffix = uuid.uuid4().hex
    with consumer_harness_scope(
        live_athena_server, monkeypatch, "cs4"
    ) as harness:
        bridge = harness.glue.meta.endpoint_url
        assert isinstance(bridge, str)
        register_catalog_metadata_handlers(
            data_catalog_store, GlueProxy.for_endpoint(bridge)
        )
        try:
            _run_go_test(binary, harness, live_athena_server.endpoint_url)
            client = boto3.client(
                "athena",
                endpoint_url=live_athena_server.endpoint_url,
                region_name="us-east-1",
                aws_access_key_id="test",
                aws_secret_access_key="test",
                config=Config(retries={"max_attempts": 0}),
            )
            _exercise_boto3_control_plane(client, harness.database, suffix)
            database = client.get_database(
                CatalogName="AwsDataCatalog", DatabaseName=harness.database
            )["Database"]
            assert database["Name"] == harness.database
            started = client.start_query_execution(
                QueryString="SELECT 1",
                ResultConfiguration={"OutputLocation": harness.prefix},
                WorkGroup="primary",
            )
            _poll_boto3_query(client, started["QueryExecutionId"])
        finally:
            register_catalog_metadata_handlers(data_catalog_store)
