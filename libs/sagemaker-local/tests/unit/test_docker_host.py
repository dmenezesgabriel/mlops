"""Unit tests for the docker-host resolution side of sagemaker_local.patches.

The compose-side tests live in test_patches.py; this file covers the
/proc/net/route parsing, serve-container IP scan, and patch lifecycle arms.
"""

import logging
import subprocess
import textwrap
from pathlib import Path

import pytest
from sagemaker_local import patches

from tests._fakes import CONTAINER_ROUTE_TABLE, FakeDocker

# A default route but no directly-connected subnet: _await_serving_ip has no
# subnets to match against and returns before ever querying the daemon.
GATEWAY_ONLY_ROUTE_TABLE = textwrap.dedent(
    """\
    Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT
    eth0\t00000000\t010013AC\t0003\t0\t0\t0\t00000000\t0\t0\t0
    lo\t00000000\t00000000\t0001\t0\t0\t0\t000000FF\t0\t0\t0
    """
)

# A connected subnet but no default route: the gateway arm finds nothing and
# resolution falls through to the SDK's own get_docker_host.
CONNECTED_ONLY_ROUTE_TABLE = textwrap.dedent(
    """\
    Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT
    eth0\t000013AC\t00000000\t0001\t0\t0\t0\t0000FFFF\t0\t0\t0
    """
)


def _patch_routes(monkeypatch, tmp_path: Path, table: str) -> None:
    routes = tmp_path / "route"
    routes.write_text(table, encoding="utf-8")
    monkeypatch.setattr(patches, "_PROC_NET_ROUTE", routes)


def _docker_host() -> str:
    import sagemaker.local.utils as sm_utils

    return sm_utils.get_docker_host()


class TestRouteParsing:
    def test_gateway_parse_skips_lines_too_short_for_fields(self):
        lines = [
            "eth0\t00000000",
            "eth0\t00000000\t010012AC\t0003\t0\t0\t0\t00000000\t0\t0\t0",
        ]

        assert patches.resolve_gateway_from_routes(lines) == "172.18.0.1"

    def test_unreadable_route_table_warns_and_returns_empty(
        self, monkeypatch, tmp_path: Path, caplog
    ):
        monkeypatch.setattr(
            patches, "_PROC_NET_ROUTE", tmp_path / "absent-route"
        )

        with caplog.at_level(logging.WARNING):
            subnets = patches._route_lines()

        assert subnets == []
        assert "cannot read" in caplog.text

    def test_connected_subnets_skips_short_and_malformed_lines(self):
        lines = [
            "eth0\t000013AC",  # fewer than 8 fields
            "eth0\tZZZZZZZZ\t00000000\t0001\t0\t0\t0\t0000FFFF",  # bad hex
            "eth0\t000013AC\t00000000\t0001\t0\t0\t0\tBADHEX!!",  # bad mask
            "eth0\t000013AC\t00000000\t0001\t0\t0\t0\t0000FFFF",
        ]

        subnets = patches._connected_subnets(lines)

        assert len(subnets) == 1
        assert patches._ip_on_subnets("172.19.0.4", subnets)
        assert not patches._ip_on_subnets("10.9.0.4", subnets)

    def test_ip_on_subnets_rejects_malformed_ip(self):
        subnets = patches._connected_subnets(
            CONTAINER_ROUTE_TABLE.splitlines()
        )

        assert patches._ip_on_subnets("not-an-ip", subnets) is False


class TestServingContainerScan:
    """Malformed daemon responses must degrade to the gateway, never raise."""

    @pytest.fixture()
    def container_routes(self, monkeypatch, tmp_path: Path):
        _patch_routes(monkeypatch, tmp_path, CONTAINER_ROUTE_TABLE)
        monkeypatch.setattr(patches, "_SERVE_IP_WAIT_S", 0.0)

    def test_empty_inspect_result_uses_gateway(
        self, monkeypatch, container_routes
    ):
        docker = FakeDocker(serve_ids=["c1"], inspect_docs={"c1": []})
        monkeypatch.setattr(patches.subprocess, "run", docker)
        patches.apply_docker_host_patch(force=True)

        assert _docker_host() == "172.19.0.1"
        assert [cmd[2] for cmd in docker.calls] == ["ls", "inspect"]

    def test_malformed_network_shape_uses_gateway(
        self, monkeypatch, container_routes
    ):
        docker = FakeDocker(
            serve_ids=["c1"],
            inspect_docs={
                "c1": [
                    {
                        "State": {"Status": "running"},
                        "NetworkSettings": {"Networks": {"mlops_net": "oops"}},
                    }
                ]
            },
        )
        monkeypatch.setattr(patches.subprocess, "run", docker)
        patches.apply_docker_host_patch(force=True)

        assert _docker_host() == "172.19.0.1"

    def test_unparseable_inspect_json_returns_none(self, monkeypatch, caplog):
        def bad_json(cmd, **_kwargs):  # noqa: ANN001, ANN003
            return subprocess.CompletedProcess(cmd, 0, stdout="not json")

        monkeypatch.setattr(patches.subprocess, "run", bad_json)

        with caplog.at_level(logging.WARNING):
            assert patches._inspect_serving_container("c1") is None

        assert "cannot inspect" in caplog.text

    def test_fake_docker_rejects_unexpected_calls(self):
        # The fake must fail loudly on a docker subcommand it does not
        # script — a silent default would mask a regressed call site.
        docker = FakeDocker()

        with pytest.raises(AssertionError, match="unexpected docker call"):
            docker(["docker", "rm", "-f", "a1"])


class TestApplyDockerHostPatchLifecycle:
    def test_second_apply_is_a_noop(self, monkeypatch, tmp_path: Path):
        import sagemaker.local.utils as sm_utils

        original = sm_utils.get_docker_host
        _patch_routes(monkeypatch, tmp_path, CONTAINER_ROUTE_TABLE)
        monkeypatch.setattr(patches.subprocess, "run", FakeDocker())

        patches.apply_docker_host_patch(force=True)
        patches.apply_docker_host_patch(force=True)
        patches.reset_all()

        # A re-capture would have stored the patched getter and "restored"
        # it — the original function object must come back instead.
        assert sm_utils.get_docker_host is original

    def test_no_connected_subnet_returns_gateway_without_daemon(
        self, monkeypatch, tmp_path: Path
    ):
        _patch_routes(monkeypatch, tmp_path, GATEWAY_ONLY_ROUTE_TABLE)
        docker = FakeDocker()
        monkeypatch.setattr(patches.subprocess, "run", docker)
        patches.apply_docker_host_patch(force=True)

        assert _docker_host() == "172.19.0.1"
        assert docker.calls == []

    def test_no_gateway_falls_back_to_sdk_getter(
        self, monkeypatch, tmp_path: Path
    ):
        import sagemaker.local.utils as sm_utils

        sdk_result = sm_utils.get_docker_host()
        _patch_routes(monkeypatch, tmp_path, CONNECTED_ONLY_ROUTE_TABLE)
        monkeypatch.setattr(patches, "_SERVE_IP_WAIT_S", 0.0)
        monkeypatch.setattr(patches.subprocess, "run", FakeDocker())
        patches.apply_docker_host_patch(force=True)

        assert _docker_host() == sdk_result
