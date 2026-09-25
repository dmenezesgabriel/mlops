"""CS-3 live-stack machinery: drive the real ``aws`` CLI at the emulator.

The suite runs the example commands awscli ships in
``examples/athena/*.rst`` (read from the installed awscli package) against an
in-process uvicorn emulator with the **compose moto container** as shared
data plane — exactly the CS-2b stack: Trino writes query results to moto
internally (``moto:5000``), the emulator's artifact writer and Glue reads
point at the same moto over its bridge IP, and each test seeds throwaway
buckets/databases there.

The CLI under test is the awscli release pinned in the lib dev group (the
frozen ``research_repos/aws-cli`` checkout is its byte-identical reference);
the suite skips when the binary, Trino, or the bridge moto is missing, so a
cold stack never fails CI (the M5 compose stack is what later milestones
pin instead).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest
from athena_local.catalog_metadata import register_catalog_metadata_handlers
from athena_local.glue_proxy import GlueProxy
from athena_local.main import data_catalog_store
from tests.integration._consumer_harness import (
    ConsumerHarness,
    _bridge_url,
    consumer_harness_scope,
)
from tests.integration.conftest import LiveAthenaServer

CLI_TIMEOUT_SECONDS = 60.0
TERMINAL_STATES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED"})


@dataclass
class CliResult:
    """One ``aws`` subprocess outcome."""

    returncode: int
    stdout: str
    stderr: str

    def parsed(self) -> object | None:
        """The stdout decoded as JSON, or None for an empty response."""
        if not self.stdout.strip():
            return None
        return json.loads(self.stdout)


def aws_binary() -> Path | None:
    """The ``aws`` console script bound to this venv, or None if absent.

    ``sys.executable`` under uv is a symlink into the uv-managed toolchain,
    so the parent is taken without resolving — the venv's ``bin/`` holds the
    console script next to the interpreter.
    """
    candidate = Path(sys.executable).parent / "aws"
    if candidate.is_file():
        return candidate
    found = shutil.which("aws")
    if found is not None:
        return Path(found)
    return None


def substitute_tokens(
    tokens: list[str],
    exact: dict[str, str | list[str]] | None = None,
    fragments: dict[str, str] | None = None,
) -> list[str]:
    """Swap real identifiers into a doc command's argv tokens.

    ``exact`` replaces whole tokens (a list value splices several argv tokens
    in — the doc's single ``--function=…`` token becomes
    ``--parameters function=…``); ``fragments`` replaces substrings inside a
    token (the doc's ``--configuration`` and ``--query-string`` values embed
    their sample identifiers). CS-3 runs each example with seeded resources
    (workgroup/catalog/database names, bucket, captured IDs) in place of the
    doc's ``amzn-s3-demo-bucket``-style samples.
    """
    result = []
    for token in tokens:
        if exact and token in exact:
            replacement = exact[token]
            if isinstance(replacement, list):
                result.extend(replacement)
            else:
                result.append(replacement)
            continue
        if fragments:
            for old, new in fragments.items():
                token = token.replace(old, new)
        result.append(token)
    return result


@dataclass
class CliStack:
    """A live emulator + shared moto with a CLI runner bound to both."""

    harness: ConsumerHarness
    binary: Path
    athena_url: str

    def run(self, *tokens: str) -> CliResult:
        """One ``aws athena … --endpoint-url <emulator>`` invocation.

        ``tokens`` are the extracted doc argv (which lead with the ``aws``
        word); the harness swaps the console script in for that word.
        """
        if tokens and tokens[0] == "aws":
            tokens = tokens[1:]
        argv = [
            str(self.binary),
            *tokens,
            "--endpoint-url",
            self.athena_url,
        ]
        env = {
            **os.environ,
            "AWS_PAGER": "",
            "AWS_DEFAULT_REGION": "us-east-1",
        }
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                env=env,
                timeout=CLI_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as error:
            pytest.fail(
                f"aws command timed out after {CLI_TIMEOUT_SECONDS}s: {error}"
            )
        return CliResult(proc.returncode, proc.stdout, proc.stderr)

    def wait_terminal(
        self, execution_id: str, timeout_seconds: float = 60.0
    ) -> dict[str, object]:
        """Poll the get-query-execution example until a terminal state."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            result = self.run(
                "athena",
                "get-query-execution",
                "--query-execution-id",
                execution_id,
            )
            assert result.returncode == 0, (
                f"get-query-execution failed: {result.stderr}"
            )
            payload = result.parsed()
            assert isinstance(payload, dict), (
                f"unexpected response {payload!r}"
            )
            execution = payload.get("QueryExecution")
            assert isinstance(execution, dict)
            state = execution["Status"]["State"]
            if state in TERMINAL_STATES:
                return execution
            time.sleep(0.3)
        pytest.fail(
            f"execution {execution_id} not terminal within {timeout_seconds}s"
        )


@contextmanager
def cli_scope(
    live_athena_server: LiveAthenaServer,
    monkeypatch: pytest.MonkeyPatch,
    tag: str,
) -> Iterator[CliStack]:
    """A live CLI stack: in-process emulator + bridge moto data plane."""
    binary = aws_binary()
    if binary is None:
        pytest.skip(
            f"aws CLI not installed next to {sys.executable}; add awscli to "
            "the athena-local dev group"
        )
    with consumer_harness_scope(
        live_athena_server, monkeypatch, tag
    ) as harness:
        # The catalog-metadata ops bind their Glue proxy at import time to
        # ATHENA_MOTO_ENDPOINT_URL / 127.0.0.1:5000; this suite reads the same
        # shared moto it seeds, so rebind like the parity fixture does and
        # restore the import-time default on exit.
        bridge = _bridge_url()
        register_catalog_metadata_handlers(
            data_catalog_store, GlueProxy.for_endpoint(bridge)
        )
        try:
            yield CliStack(
                harness=harness,
                binary=binary,
                athena_url=live_athena_server.endpoint_url,
            )
        finally:
            register_catalog_metadata_handlers(data_catalog_store)
