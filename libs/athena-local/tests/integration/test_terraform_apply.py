"""Real terraform CLI lifecycle against the live stack.

CS-4 verified the provider's op shapes through a pinned AWS SDK Go v2 module;
this test runs the actual ``terraform`` binary — provider plugin resolved
from the registry and pinned by the committed ``.terraform.lock.hcl`` — over
the five ``aws_athena_*`` resources, the same ``init → apply → plan
-detailed-exitcode → apply -destroy`` sequence moto's own terraform-examples
workflow uses (``research_repos/moto/.github/workflows/
tests_terraform_examples.yml``).

The intermediate ``plan -detailed-exitcode`` is the drift oracle: terraform
re-reads every resource after apply, so an emulator field the provider set
but we dropped (or a computed member we echo wrongly) surfaces as a non-empty
plan rather than an SDK assertion. boto3 witnesses confirm state actually
landed in the emulator/moto and that destroy removed it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from athena_local.catalog_metadata import register_catalog_metadata_handlers
from athena_local.glue_proxy import GlueProxy
from athena_local.main import data_catalog_store
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from tests.integration._consumer_harness import (
    ConsumerHarness,
    consumer_harness_scope,
)
from tests.integration._terraform_harness import (
    TERRAFORM_MODULE,
    TERRAFORM_PLUGIN_CACHE,
    require_terraform_binary,
    run_terraform,
)
from tests.integration.conftest import LiveAthenaServer

_INIT_OFFLINE_MARKERS = (
    "registry.terraform.io",
    "Failed to request discovery document",
    "no such host",
    "Temporary failure in name resolution",
    "dial tcp",
    "i/o timeout",
)


def _require_success(
    result: subprocess.CompletedProcess[str], step: str
) -> None:
    if result.returncode == 0:
        return
    pytest.fail(
        f"terraform {step} failed (exit {result.returncode}):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def _init_or_skip(
    binary: Path, working: Path, environment: dict[str, str]
) -> None:
    result = run_terraform(
        binary, ["init", "-input=false", "-no-color"], working, environment
    )
    if result.returncode == 0:
        return
    if any(marker in result.stderr for marker in _INIT_OFFLINE_MARKERS):
        pytest.skip(f"terraform registry unreachable: {result.stderr[-300:]}")
    _require_success(result, "init")


def _terraform_environment(
    endpoint: str,
    bridge: str,
    harness: ConsumerHarness,
    suffix: str,
) -> dict[str, str]:
    # The aws provider download is ~60 MB; a repo-local cache keeps repeat
    # gate runs offline-capable after the first init.
    TERRAFORM_PLUGIN_CACHE.mkdir(parents=True, exist_ok=True)
    return {
        "TF_IN_AUTOMATION": "1",
        "TF_INPUT": "0",
        "TF_PLUGIN_CACHE_DIR": str(TERRAFORM_PLUGIN_CACHE),
        "TF_VAR_athena_endpoint": endpoint,
        "TF_VAR_data_plane_endpoint": bridge,
        "TF_VAR_bucket": harness.bucket,
        "TF_VAR_name_suffix": suffix,
    }


def _terraform_outputs(
    binary: Path, working: Path, environment: dict[str, str]
) -> dict[str, str]:
    result = run_terraform(binary, ["output", "-json"], working, environment)
    _require_success(result, "output -json")
    decoded = json.loads(result.stdout)
    return {name: str(entry["value"]) for name, entry in decoded.items()}


def _assert_resources_present(
    athena: BaseClient, glue: BaseClient, outputs: dict[str, str]
) -> None:
    workgroup = athena.get_work_group(WorkGroup=outputs["workgroup_name"])[
        "WorkGroup"
    ]
    assert workgroup["State"] == "ENABLED"
    assert workgroup["Description"] == "terraform apply parity"
    glue.get_database(Name=outputs["database_name"])
    named = athena.get_named_query(NamedQueryId=outputs["named_query_id"])[
        "NamedQuery"
    ]
    assert named["QueryString"] == "SELECT 1"
    catalog = athena.get_data_catalog(Name=outputs["data_catalog_name"])[
        "DataCatalog"
    ]
    assert catalog["Type"] == "LAMBDA"
    statement = athena.get_prepared_statement(
        StatementName=outputs["prepared_statement_name"],
        WorkGroup=outputs["workgroup_name"],
    )["PreparedStatement"]
    assert statement["QueryStatement"] == "SELECT ?"


def _assert_resources_absent(
    athena: BaseClient, glue: BaseClient, outputs: dict[str, str]
) -> None:
    with pytest.raises(ClientError):
        athena.get_work_group(WorkGroup=outputs["workgroup_name"])
    with pytest.raises(ClientError):
        glue.get_database(Name=outputs["database_name"])
    with pytest.raises(ClientError):
        athena.get_named_query(NamedQueryId=outputs["named_query_id"])
    with pytest.raises(ClientError):
        athena.get_data_catalog(Name=outputs["data_catalog_name"])
    with pytest.raises(ClientError):
        athena.get_prepared_statement(
            StatementName=outputs["prepared_statement_name"],
            WorkGroup=outputs["workgroup_name"],
        )


def test_terraform_apply(
    live_athena_server: LiveAthenaServer,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    binary = require_terraform_binary()
    suffix = uuid.uuid4().hex
    with consumer_harness_scope(
        live_athena_server, monkeypatch, "tfapply"
    ) as harness:
        bridge = harness.glue.meta.endpoint_url
        assert isinstance(bridge, str)
        register_catalog_metadata_handlers(
            data_catalog_store, GlueProxy.for_endpoint(bridge)
        )
        try:
            # State and the .terraform plugin dir must not land in the repo:
            # the module is copied to a pytest tmp dir per run.
            working = tmp_path / "apply"
            shutil.copytree(
                TERRAFORM_MODULE,
                working,
                ignore=shutil.ignore_patterns(
                    ".plugin-cache", ".terraform", "*.tfstate*"
                ),
            )
            environment = _terraform_environment(
                live_athena_server.endpoint_url, bridge, harness, suffix
            )
            _init_or_skip(binary, working, environment)
            _require_success(
                run_terraform(
                    binary,
                    ["apply", "-auto-approve", "-input=false", "-no-color"],
                    working,
                    environment,
                ),
                "apply",
            )
            outputs = _terraform_outputs(binary, working, environment)
            _assert_resources_present(harness.athena, harness.glue, outputs)
            plan = run_terraform(
                binary,
                ["plan", "-detailed-exitcode", "-input=false", "-no-color"],
                working,
                environment,
            )
            assert plan.returncode == 0, (
                f"terraform plan reports drift after apply:\n{plan.stdout}"
                f"\n{plan.stderr}"
            )
            _require_success(
                run_terraform(
                    binary,
                    [
                        "apply",
                        "-destroy",
                        "-auto-approve",
                        "-input=false",
                        "-no-color",
                    ],
                    working,
                    environment,
                ),
                "destroy",
            )
            _assert_resources_absent(harness.athena, harness.glue, outputs)
        finally:
            register_catalog_metadata_handlers(data_catalog_store)
