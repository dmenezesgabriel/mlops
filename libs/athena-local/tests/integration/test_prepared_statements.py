"""Consumer-parity integration: real boto3 and awswrangler against the live app.

MD-3 acceptance check. Uses the LiveAthenaServer fixture (threaded uvicorn on
a random port) — the same pattern the MD-1/MD-2 slices use, so no docker stack
is needed for the prepared statement control plane. Tests verify boto3 can do
CRUD, pagination, and batch gets, and that awswrangler's prepared statement
API (which resolves statements via ResourceNotFoundException) runs against the
emulator through the ``athena_endpoint_url`` override.
"""

from __future__ import annotations

import awswrangler as wr
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


def test_prepared_statement_crud_round_trip_with_botocore(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    client.create_prepared_statement(
        StatementName="flights_stmt",
        WorkGroup="analytics",
        QueryStatement="SELECT * FROM flights WHERE origin = ?",
        Description="Flights query with a bind parameter",
    )

    statement = client.get_prepared_statement(
        StatementName="flights_stmt", WorkGroup="analytics"
    )["PreparedStatement"]
    assert statement["StatementName"] == "flights_stmt"
    assert (
        statement["QueryStatement"] == "SELECT * FROM flights WHERE origin = ?"
    )
    assert statement["WorkGroupName"] == "analytics"
    assert statement["Description"] == "Flights query with a bind parameter"
    assert "LastModifiedTime" in statement

    client.update_prepared_statement(
        StatementName="flights_stmt",
        WorkGroup="analytics",
        QueryStatement="SELECT * FROM flights WHERE dest = ?",
        Description="Updated destinations query",
    )
    updated = client.get_prepared_statement(
        StatementName="flights_stmt", WorkGroup="analytics"
    )["PreparedStatement"]
    assert updated["QueryStatement"] == "SELECT * FROM flights WHERE dest = ?"

    listed = client.list_prepared_statements(WorkGroup="analytics")[
        "PreparedStatements"
    ]
    assert [item["StatementName"] for item in listed] == ["flights_stmt"]
    # ListPreparedStatements honors the PreparedStatementSummary shape.
    assert set(listed[0].keys()) == {"StatementName", "LastModifiedTime"}

    client.delete_prepared_statement(
        StatementName="flights_stmt", WorkGroup="analytics"
    )
    with pytest.raises(ClientError) as exc_info:
        client.get_prepared_statement(
            StatementName="flights_stmt", WorkGroup="analytics"
        )
    assert (
        exc_info.value.response["Error"]["Code"] == "ResourceNotFoundException"
    )


def test_get_missing_prepared_statement_is_shaped_404(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    with pytest.raises(ClientError) as exc_info:
        client.get_prepared_statement(
            StatementName="missing-stmt", WorkGroup="primary"
        )

    error = exc_info.value.response["Error"]
    assert error["Code"] == "ResourceNotFoundException"
    assert "missing-stmt" in error["Message"]


def test_list_prepared_statements_with_pagination(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    for i in range(5):
        client.create_prepared_statement(
            StatementName=f"stmt{i}",
            WorkGroup="analytics",
            QueryStatement=f"SELECT {i}",
        )

    page1 = client.list_prepared_statements(
        WorkGroup="analytics", MaxResults=2
    )
    assert len(page1["PreparedStatements"]) == 2
    assert "NextToken" in page1

    page2 = client.list_prepared_statements(
        WorkGroup="analytics", MaxResults=2, NextToken=page1["NextToken"]
    )
    assert len(page2["PreparedStatements"]) == 2
    assert "NextToken" in page2

    page3 = client.list_prepared_statements(
        WorkGroup="analytics", MaxResults=2, NextToken=page2["NextToken"]
    )
    assert len(page3["PreparedStatements"]) == 1
    assert "NextToken" not in page3


def test_list_prepared_statements_workgroup_scoping(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    client.create_prepared_statement(
        StatementName="analytics_stmt",
        WorkGroup="analytics",
        QueryStatement="SELECT 1",
    )
    client.create_prepared_statement(
        StatementName="primary_stmt",
        WorkGroup="primary",
        QueryStatement="SELECT 2",
    )

    analytics_names = [
        item["StatementName"]
        for item in client.list_prepared_statements(WorkGroup="analytics")[
            "PreparedStatements"
        ]
    ]
    primary_names = [
        item["StatementName"]
        for item in client.list_prepared_statements(WorkGroup="primary")[
            "PreparedStatements"
        ]
    ]

    assert analytics_names == ["analytics_stmt"]
    assert primary_names == ["primary_stmt"]


def test_batch_get_prepared_statement_unprocessed_is_structured(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    client.create_prepared_statement(
        StatementName="stmt1",
        WorkGroup="primary",
        QueryStatement="SELECT 1",
    )

    response = client.batch_get_prepared_statement(
        PreparedStatementNames=["stmt1", "missing-1", "missing-2"],
        WorkGroup="primary",
    )

    assert len(response["PreparedStatements"]) == 1
    assert response["PreparedStatements"][0]["StatementName"] == "stmt1"
    assert len(response["UnprocessedPreparedStatementNames"]) == 2
    unprocessed_names = {
        item["StatementName"]
        for item in response["UnprocessedPreparedStatementNames"]
    }
    assert unprocessed_names == {"missing-1", "missing-2"}


def test_awswrangler_prepared_statements_against_live_server(
    live_athena_server: LiveAthenaServer,
) -> None:
    wr.config.athena_endpoint_url = live_athena_server.endpoint_url
    session = boto3.Session(
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )

    wr.athena.create_prepared_statement(
        sql="SELECT * FROM flights WHERE origin = ?",
        statement_name="wrangler_stmt",
        workgroup="analytics",
        boto3_session=session,
    )

    statements = wr.athena.list_prepared_statements(
        workgroup="analytics", boto3_session=session
    )
    assert [item["StatementName"] for item in statements] == ["wrangler_stmt"]
