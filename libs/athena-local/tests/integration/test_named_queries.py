"""Consumer-parity integration: real boto3 against the live app.

MD-2 acceptance check. Uses the LiveAthenaServer fixture (threaded uvicorn on
a random port) — the same pattern the M1 smoke already uses, so no docker
stack is needed for the named query control plane. Tests verify that boto3
clients can perform CRUD operations, pagination, and batch gets against the
running emulator.
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


def test_named_query_crud_round_trip_with_botocore(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    create_response = client.create_named_query(
        Name="flights_query",
        Description="Flights from Seattle to New York",
        Database="sampledb",
        QueryString="SELECT * FROM flights WHERE origin = 'SEA' AND dest = 'JFK'",
        WorkGroup="analytics",
    )

    query_id = create_response["NamedQueryId"]
    assert isinstance(query_id, str)

    query = client.get_named_query(NamedQueryId=query_id)["NamedQuery"]
    assert query["Name"] == "flights_query"
    assert query["Description"] == "Flights from Seattle to New York"
    assert query["Database"] == "sampledb"
    assert query["QueryString"] == (
        "SELECT * FROM flights WHERE origin = 'SEA' AND dest = 'JFK'"
    )
    assert query["WorkGroup"] == "analytics"

    ids = client.list_named_queries(WorkGroup="analytics")["NamedQueryIds"]
    assert query_id in ids

    client.delete_named_query(NamedQueryId=query_id)
    ids_after = client.list_named_queries(WorkGroup="analytics")[
        "NamedQueryIds"
    ]
    assert query_id not in ids_after


def test_create_named_query_defaults_to_primary_workgroup(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    create_response = client.create_named_query(
        Name="test_query",
        Database="db",
        QueryString="SELECT 1",
    )

    query_id = create_response["NamedQueryId"]
    query = client.get_named_query(NamedQueryId=query_id)["NamedQuery"]
    assert query["WorkGroup"] == "primary"


def test_get_missing_named_query_is_shaped_400(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    with pytest.raises(ClientError) as exc_info:
        client.get_named_query(NamedQueryId="missing-id")

    error = exc_info.value.response["Error"]
    assert error["Code"] == "InvalidRequestException"
    assert "missing-id" in error["Message"]


def test_delete_missing_named_query_is_shaped_400(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    with pytest.raises(ClientError) as exc_info:
        client.delete_named_query(NamedQueryId="missing-id")

    error = exc_info.value.response["Error"]
    assert error["Code"] == "InvalidRequestException"
    assert "missing-id" in error["Message"]


def test_list_named_queries_with_pagination(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    for i in range(5):
        client.create_named_query(
            Name=f"query{i}",
            Database="db",
            QueryString=f"SELECT {i}",
            WorkGroup="analytics",
        )

    page1 = client.list_named_queries(WorkGroup="analytics", MaxResults=2)
    assert len(page1["NamedQueryIds"]) == 2
    assert "NextToken" in page1

    page2 = client.list_named_queries(
        WorkGroup="analytics", MaxResults=2, NextToken=page1["NextToken"]
    )
    assert len(page2["NamedQueryIds"]) == 2
    assert "NextToken" in page2

    page3 = client.list_named_queries(
        WorkGroup="analytics", MaxResults=2, NextToken=page2["NextToken"]
    )
    assert len(page3["NamedQueryIds"]) == 1
    assert "NextToken" not in page3


def test_list_named_queries_workgroup_scoping(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    client.create_named_query(
        Name="analytics_query",
        Database="db",
        QueryString="SELECT 1",
        WorkGroup="analytics",
    )
    client.create_named_query(
        Name="primary_query",
        Database="db",
        QueryString="SELECT 2",
    )

    analytics_ids = client.list_named_queries(WorkGroup="analytics")[
        "NamedQueryIds"
    ]
    primary_ids = client.list_named_queries()["NamedQueryIds"]

    assert len(analytics_ids) == 1
    assert len(primary_ids) == 1
    assert analytics_ids != primary_ids


def test_batch_get_named_query_returns_multiple_queries(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    id1 = client.create_named_query(
        Name="query1",
        Database="db",
        QueryString="SELECT 1",
    )["NamedQueryId"]
    id2 = client.create_named_query(
        Name="query2",
        Database="db",
        QueryString="SELECT 2",
    )["NamedQueryId"]

    response = client.batch_get_named_query(NamedQueryIds=[id1, id2])

    assert len(response["NamedQueries"]) == 2
    assert "UnprocessedNamedQueryIds" not in response
    names = {q["Name"] for q in response["NamedQueries"]}
    assert names == {"query1", "query2"}


def test_batch_get_named_query_unprocessed_missing_ids(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    id1 = client.create_named_query(
        Name="query1",
        Database="db",
        QueryString="SELECT 1",
    )["NamedQueryId"]

    response = client.batch_get_named_query(
        NamedQueryIds=[id1, "missing-id-1", "missing-id-2"]
    )

    assert len(response["NamedQueries"]) == 1
    assert response["NamedQueries"][0]["Name"] == "query1"
    assert len(response["UnprocessedNamedQueryIds"]) == 2
    unprocessed_ids = {
        item["NamedQueryId"] for item in response["UnprocessedNamedQueryIds"]
    }
    assert unprocessed_ids == {"missing-id-1", "missing-id-2"}


def test_cli_example_flow(
    live_athena_server: LiveAthenaServer,
) -> None:
    """Replicate the AWS CLI example from research_repos/aws-cli/examples/athena/create-named-query.rst."""
    client = _client(live_athena_server.endpoint_url)

    response = client.create_named_query(
        Name="SEA to JFK delayed flights Jan 2016",
        Description="Both arrival and departure delayed more than 10 minutes.",
        Database="sampledb",
        QueryString=(
            "SELECT flightdate, carrier, flightnum, origin, dest, "
            "depdelayminutes, arrdelayminutes FROM sampledb.flights_parquet "
            "WHERE yr = 2016 AND month = 1 AND origin = '\"SEA\"' "
            "AND dest = '\"JFK\"' AND depdelayminutes > 10 "
            "AND arrdelayminutes > 10"
        ),
        WorkGroup="AthenaAdmin",
    )

    query_id = response["NamedQueryId"]
    assert isinstance(query_id, str)

    query = client.get_named_query(NamedQueryId=query_id)["NamedQuery"]
    assert query["Name"] == "SEA to JFK delayed flights Jan 2016"
    assert query["Database"] == "sampledb"
    assert query["WorkGroup"] == "AthenaAdmin"
