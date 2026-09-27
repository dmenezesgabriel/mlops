"""The AWS CLI athena example suite over the live stack.

Drives the commands awscli ships in ``examples/athena/*.rst`` (read from the
installed awscli package via ``_cli_examples`` — the frozen
``research_repos/aws-cli/awscli/examples/athena/`` checkout is the
byte-identical reference) through the real ``aws`` binary against an
in-process emulator and the compose moto container as shared data plane,
the same stack the awswrangler suite uses. Sample identifiers from the docs (workgroups,
catalogs, ``amzn-s3-demo-bucket``) are swapped for the throwaway resources
each chain seeds; assertions check wire shape, not the docs' illustrative
output.

Two upstream quirks are pinned here, both engine/CLI facts not emulator
behavior: ``update-data-catalog``'s doc ``--function`` flag is rejected by
the CLI itself (the model has only ``Parameters``) so the chain runs the
corrected form, and the doc SELECT's ``status = 200`` compares a varchar
column to an integer (Trino 483: ``Cannot apply operator: varchar(3) =
integer``) so the chain quotes the literal.
"""

from __future__ import annotations

import os
import subprocess

import awscli
import pytest
from tests.integration._cli_examples import example_stems, load_example
from tests.integration._cli_harness import (
    as_dict,
    as_list,
    as_str,
    aws_binary,
    cli_scope,
    parsed_json,
    substitute_tokens,
)
from tests.integration.conftest import LiveAthenaServer

SAMPLE_NQ_ID = "a1b2c3d4-5678-90ab-cdef-EXAMPLE11111"
SAMPLE_NQ_ID_2 = "a1b2c3d4-5678-90ab-cdef-EXAMPLE22222"
SAMPLE_NQ_ID_3 = "a1b2c3d4-5678-90ab-cdef-EXAMPLE33333"
SAMPLE_QE_ID = "a1b2c3d4-5678-90ab-cdef-EXAMPLE11111"
SAMPLE_QE_ID_2 = "a1b2c3d4-5678-90ab-cdef-EXAMPLE22222"

EXPECTED_EXAMPLE_STEMS = [
    "batch-get-named-query",
    "batch-get-query-execution",
    "create-data-catalog",
    "create-named-query",
    "create-work-group",
    "delete-data-catalog",
    "delete-named-query",
    "delete-work-group",
    "get-data-catalog",
    "get-database",
    "get-named-query",
    "get-query-execution",
    "get-query-results",
    "get-table-metadata",
    "get-work-group",
    "list-data-catalogs",
    "list-databases",
    "list-named-queries",
    "list-query-executions",
    "list-table-metadata",
    "list-tags-for-resource",
    "list-work-groups",
    "start-query-execution",
    "stop-query-execution",
    "tag-resource",
    "untag-resource",
    "update-data-catalog",
    "update-work-group",
]


def test_cli_example_file_coverage() -> None:
    """Every example the CLI ships is either run or knowingly pinned here."""
    # The whole suite targets this pinned distribution: its console script
    # (aws_binary) runs every command and its example files are the input.
    assert awscli.__version__ == "1.46.1"
    assert example_stems() == EXPECTED_EXAMPLE_STEMS


def test_cli_update_data_catalog_doc_function_flag_is_rejected() -> None:
    """Pin the upstream quirk that makes the doc command un-runnable.

    The awscli example for ``update-data-catalog`` passes ``--function=``,
    but the CLI rejects it (``Unknown options``): the canonical model's
    UpdateDataCatalogInput has only Name/Type/Description/Parameters. This
    needs no emulator — the argument parser fails before any request.
    """
    binary = aws_binary()
    if binary is None:
        pytest.skip("aws CLI not installed; add awscli to the dev group")
    argv = [
        str(binary),
        "athena",
        "update-data-catalog",
        "--name",
        "cw_logs_catalog",
        "--type",
        "LAMBDA",
        "--function=arn:aws:lambda:us-west-2:111122223333:function:new_cw_logs_lambda",
        "--endpoint-url",
        "http://127.0.0.1:9",
    ]
    proc = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        env={**os.environ, "AWS_PAGER": ""},
        timeout=30,
    )

    assert proc.returncode != 0
    assert "Unknown options" in proc.stderr


def test_cli_workgroup_examples(
    live_athena_server: LiveAthenaServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """create/get/update/list/delete-work-group + list-tags (workgroup ARN)."""
    with cli_scope(live_athena_server, monkeypatch, "cs3workgroup") as stack:
        bucket = stack.harness.bucket
        result = stack.run(
            *substitute_tokens(
                load_example("create-work-group")[0],
                fragments={"s3://amzn-s3-demo-bucket": f"s3://{bucket}"},
            )
        )
        assert result.returncode == 0, result.stderr

        # The docs assume AthenaAdmin exists and TeamB is deletable.
        for name in ("AthenaAdmin", "TeamB"):
            created = stack.run(
                "athena",
                "create-work-group",
                "--name",
                name,
                "--description",
                "cli-example seed",
            )
            assert created.returncode == 0, created.stderr

        result = stack.run(*load_example("get-work-group")[0])
        assert result.returncode == 0, result.stderr
        workgroup = as_dict(parsed_json(result)["WorkGroup"])
        assert workgroup["Name"] == "AthenaAdmin"
        assert workgroup["State"] == "ENABLED"

        result = stack.run(*load_example("list-tags-for-resource")[0])
        tags = {
            as_str(as_dict(tag)["Key"]): as_str(as_dict(tag)["Value"])
            for tag in as_list(parsed_json(result)["Tags"])
        }
        assert tags == {
            "Division": "West",
            "Location": "Seattle",
            "Team": "Big Data",
        }

        result = stack.run(*load_example("update-work-group")[0])
        assert result.returncode == 0, result.stderr
        result = stack.run(
            *substitute_tokens(
                load_example("get-work-group")[0],
                exact={"AthenaAdmin": "Data_Analyst_Group"},
            )
        )
        assert as_dict(parsed_json(result)["WorkGroup"])["State"] == "DISABLED"

        result = stack.run(*load_example("list-work-groups")[0])
        names = {
            as_str(as_dict(entry)["Name"])
            for entry in as_list(parsed_json(result)["WorkGroups"])
        }
        assert {"primary", "AthenaAdmin", "Data_Analyst_Group"} <= names

        result = stack.run(*load_example("delete-work-group")[0])
        assert result.returncode == 0, result.stderr
        result = stack.run(*load_example("list-work-groups")[0])
        names = {
            as_str(as_dict(entry)["Name"])
            for entry in as_list(parsed_json(result)["WorkGroups"])
        }
        assert "TeamB" not in names


def test_cli_data_catalog_examples(
    live_athena_server: LiveAthenaServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """create/get/update/list/delete-data-catalog + tag ops on a catalog ARN."""
    with cli_scope(live_athena_server, monkeypatch, "cs3catalog") as stack:
        result = stack.run(*load_example("create-data-catalog")[0])
        assert result.returncode == 0, result.stderr

        result = stack.run(*load_example("get-data-catalog")[0])
        catalog = as_dict(parsed_json(result)["DataCatalog"])
        assert catalog["Name"] == "dynamo_db_catalog"
        assert catalog["Type"] == "LAMBDA"
        parameters = as_dict(catalog["Parameters"])
        assert "metadata-function" in parameters
        assert "record-function" in parameters

        for name in ("cw_logs_catalog", "UnusedDataCatalog"):
            seeded = stack.run(
                "athena",
                "create-data-catalog",
                "--name",
                name,
                "--type",
                "LAMBDA",
                "--description",
                "cli-example seed",
            )
            assert seeded.returncode == 0, seeded.stderr

        # The doc --function flag is rejected by the CLI (pinned above); run
        # the example command in its model form.
        corrected = substitute_tokens(
            load_example("update-data-catalog")[0],
            exact={
                "--function=arn:aws:lambda:us-west-2:111122223333:function:new_cw_logs_lambda": [
                    "--parameters",
                    "function=arn:aws:lambda:us-west-2:111122223333:function:new_cw_logs_lambda",
                ]
            },
        )
        result = stack.run(*corrected)
        assert result.returncode == 0, result.stderr

        result = stack.run(*load_example("list-data-catalogs")[0])
        catalogs = {
            as_str(as_dict(entry)["CatalogName"]): as_str(
                as_dict(entry)["Type"]
            )
            for entry in as_list(parsed_json(result)["DataCatalogsSummary"])
        }
        assert catalogs["AwsDataCatalog"] == "GLUE"
        assert catalogs["dynamo_db_catalog"] == "LAMBDA"

        result = stack.run(*load_example("delete-data-catalog")[0])
        assert result.returncode == 0, result.stderr
        result = stack.run(*load_example("list-data-catalogs")[0])
        names = {
            as_str(as_dict(entry)["CatalogName"])
            for entry in as_list(parsed_json(result)["DataCatalogsSummary"])
        }
        assert "UnusedDataCatalog" not in names

        result = stack.run(*load_example("tag-resource")[0])
        assert result.returncode == 0, result.stderr
        result = stack.run(*load_example("list-tags-for-resource")[1])
        tags = {
            as_str(as_dict(tag)["Key"]): as_str(as_dict(tag)["Value"])
            for tag in as_list(parsed_json(result)["Tags"])
        }
        assert tags["Organization"] == "Retail"
        assert tags["Division"] == "Mountain"
        result = stack.run(*load_example("untag-resource")[0])
        assert result.returncode == 0, result.stderr
        result = stack.run(*load_example("list-tags-for-resource")[1])
        remaining = {
            as_str(as_dict(tag)["Key"])
            for tag in as_list(parsed_json(result)["Tags"])
        }
        assert "Organization" in remaining
        assert "Specialization" not in remaining


def test_cli_named_query_examples(
    live_athena_server: LiveAthenaServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """create/get/list/batch-get/delete-named-query with a real captured ID."""
    with cli_scope(live_athena_server, monkeypatch, "cs3namedquery") as stack:
        result = stack.run(*load_example("create-named-query")[0])
        assert result.returncode == 0, result.stderr
        named_query_id = as_str(parsed_json(result)["NamedQueryId"])

        result = stack.run(
            *substitute_tokens(
                load_example("get-named-query")[0],
                exact={SAMPLE_NQ_ID: named_query_id},
            )
        )
        named_query = as_dict(parsed_json(result)["NamedQuery"])
        assert named_query["Name"] == "SEA to JFK delayed flights Jan 2016"
        assert named_query["Database"] == "sampledb"
        assert named_query["WorkGroup"] == "AthenaAdmin"

        result = stack.run(*load_example("list-named-queries")[0])
        listed = {
            as_str(entry)
            for entry in as_list(parsed_json(result)["NamedQueryIds"])
        }
        assert named_query_id in listed

        result = stack.run(
            *substitute_tokens(
                load_example("batch-get-named-query")[0],
                exact={SAMPLE_NQ_ID: named_query_id},
            )
        )
        found = as_list(parsed_json(result)["NamedQueries"])
        assert [as_dict(entry)["NamedQueryId"] for entry in found] == [
            named_query_id
        ]
        unprocessed = {
            as_str(as_dict(entry)["NamedQueryId"])
            for entry in as_list(
                parsed_json(result)["UnprocessedNamedQueryIds"]
            )
        }
        assert unprocessed == {SAMPLE_NQ_ID_2, SAMPLE_NQ_ID_3}

        result = stack.run(
            *substitute_tokens(
                load_example("delete-named-query")[0],
                exact={SAMPLE_NQ_ID: named_query_id},
            )
        )
        assert result.returncode == 0, result.stderr
        result = stack.run(*load_example("list-named-queries")[0])
        listed = {
            as_str(entry)
            for entry in as_list(parsed_json(result)["NamedQueryIds"])
        }
        assert named_query_id not in listed


def test_cli_catalog_metadata_examples(
    live_athena_server: LiveAthenaServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """list/get-database + list/get-table-metadata against seeded Glue data."""
    with cli_scope(live_athena_server, monkeypatch, "cs3catalogmeta") as stack:
        glue = stack.harness.glue
        database = stack.harness.database
        suffix = database.split("_", 1)[1]
        sampledb = f"sampledb_{suffix}"
        geography = f"geography_{suffix}"
        for db_name in (sampledb, geography):
            glue.create_database(DatabaseInput={"Name": db_name})
        glue.create_table(
            DatabaseName=sampledb,
            TableInput={
                "Name": "counties",
                "TableType": "EXTERNAL_TABLE",
                "Parameters": {"EXTERNAL": "TRUE"},
            },
        )
        glue.create_table(
            DatabaseName=geography,
            TableInput={
                "Name": "regions",
                "TableType": "EXTERNAL_TABLE",
                "Parameters": {"EXTERNAL": "TRUE"},
            },
        )

        result = stack.run(*load_example("list-databases")[0])
        names = {
            as_str(as_dict(entry)["Name"])
            for entry in as_list(parsed_json(result)["DatabaseList"])
        }
        assert sampledb in names

        result = stack.run(
            *substitute_tokens(
                load_example("get-database")[0], exact={"sampledb": sampledb}
            )
        )
        assert as_dict(parsed_json(result)["Database"])["Name"] == sampledb

        result = stack.run(
            *substitute_tokens(
                load_example("list-table-metadata")[0],
                exact={"geography": geography},
            )
        )
        tables = [
            as_str(as_dict(entry)["Name"])
            for entry in as_list(parsed_json(result)["TableMetadataList"])
        ]
        assert "regions" in tables

        result = stack.run(
            *substitute_tokens(
                load_example("get-table-metadata")[0],
                exact={"sampledb": sampledb},
            )
        )
        metadata = as_dict(parsed_json(result)["TableMetadata"])
        assert metadata["Name"] == "counties"
