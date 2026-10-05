"""Named fakes for the docker CLI / /proc/net/route seams (ADR-0005).

Shared by the docker-host and compose patch test files so the scripted
boundary objects live in one place.
"""

from __future__ import annotations

import json
import subprocess
import textwrap

ROUTE_TABLE = textwrap.dedent(
    """\
    Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT
    eth0\t00000000\t010012AC\t0003\t0\t0\t0\t00000000\t0\t0\t0
    eth0\t000012AC\t00000000\t0001\t0\t0\t0\t000CFFFF\t0\t0\t0
    lo\t00000000\t00000000\t0001\t0\t0\t0\t000000FF\t0\t0\t0
    """
)

CONTAINER_ROUTE_TABLE = textwrap.dedent(
    """\
    Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT
    eth0\t00000000\t010013AC\t0003\t0\t0\t0\t00000000\t0\t0\t0
    eth0\t000013AC\t00000000\t0001\t0\t0\t0\t0000FFFF\t0\t0\t0
    """
)


def inspect_doc(status: str, networks: dict[str, str]) -> dict:
    """Scripted ``docker container inspect`` body: status + IP per network."""
    return {
        "State": {"Status": status},
        "NetworkSettings": {
            "Networks": {
                name: {"IPAddress": ip, "IPPrefixLen": 16}
                for name, ip in networks.items()
            }
        },
    }


class FakeDocker:
    """Named fake for the docker CLI calls the docker-host patch issues.

    ``ls`` returns ``serve_ids``, or pops the next id list from ``ls_script``
    when given (the last entry repeats once exhausted) so a test can script a
    container that only exists on a later poll — the SDK spawns
    ``compose up`` asynchronously. ``inspect <cid>`` pops the next scripted
    document for that id (the last one repeats once exhausted); an empty
    scripted list answers ``[]`` so the bare-docs guard arm is reachable.
    Inspecting an unlisted id fails like real docker (rc=1); any other
    command raises — the gateway arm must not depend on the daemon.
    """

    def __init__(
        self,
        serve_ids: list[str] | None = None,
        inspect_docs: dict[str, list[dict]] | None = None,
        ls_script: list[list[str]] | None = None,
    ) -> None:
        self.serve_ids = serve_ids or []
        self.ls_script = list(ls_script) if ls_script is not None else None
        self.inspect_docs = {
            cid: list(docs) for cid, docs in (inspect_docs or {}).items()
        }
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **_kwargs):  # noqa: ANN003
        self.calls.append(list(cmd))
        if "inspect" in cmd:
            docs = self.inspect_docs.get(cmd[-1])
            if docs is None:
                raise subprocess.CalledProcessError(1, list(cmd))
            if not docs:
                return subprocess.CompletedProcess(cmd, 0, stdout="[]")
            doc = docs.pop(0) if len(docs) > 1 else docs[0]
            return subprocess.CompletedProcess(
                cmd, 0, stdout=json.dumps([doc])
            )
        if "ls" in cmd:
            ids = self.serve_ids
            if self.ls_script is not None:
                ids = (
                    self.ls_script.pop(0)
                    if len(self.ls_script) > 1
                    else self.ls_script[0]
                )
            return subprocess.CompletedProcess(cmd, 0, stdout="\n".join(ids))
        raise AssertionError(f"unexpected docker call: {cmd}")


class DockerCliAbsent:
    """Raises FileNotFoundError on any call — docker binary not on PATH."""

    def __call__(self, cmd, **_kwargs):  # noqa: ANN003
        raise FileNotFoundError(cmd[0])
