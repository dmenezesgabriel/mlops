"""Unit tests for sagemaker_local.patches."""

import inspect
import json
import logging
import subprocess
import textwrap
from pathlib import Path

import pytest
import yaml
from sagemaker_local import patches
from sagemaker_local.config import LocalModeConfig


def make_config(**overrides) -> LocalModeConfig:
    values = {
        "s3_endpoint_url": "http://moto:5000",
        "bucket": "my-bucket",
        "network": "proj-net",
    }
    values.update(overrides)
    return LocalModeConfig(**values)


@pytest.fixture(autouse=True)
def restore_global_patches():
    """Every test starts and ends with unpatched SDK modules."""
    patches.reset_all()
    yield
    patches.reset_all()


class FakeRunner:
    """Named fake for subprocess.run calls issued by the patches.

    ``remove_*`` fields script the ``docker rm`` result — the CLI echoes each
    removed id on stdout, so ``remove_stdout=None`` echoes ``listed_ids``
    (all removed) while a partial removal echoes fewer than listed. Emulates
    ``check=`` semantics: a non-zero remove result raises
    ``CalledProcessError`` when the call requests it.
    """

    def __init__(
        self,
        listed_ids: list[str] | None = None,
        remove_rc: int = 0,
        remove_stdout: str | None = None,
        remove_stderr: str = "",
    ):
        self.listed_ids = listed_ids or []
        self.remove_rc = remove_rc
        self.remove_stdout = remove_stdout
        self.remove_stderr = remove_stderr
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **kwargs):  # noqa: ANN003
        self.calls.append(cmd)
        if "--filter" in cmd:
            return type(
                "R",
                (),
                {
                    "stdout": "\n".join(self.listed_ids),
                    "returncode": 0,
                    "stderr": "",
                },
            )()
        if kwargs.get("check") and self.remove_rc:
            raise subprocess.CalledProcessError(
                self.remove_rc, cmd, stderr=self.remove_stderr
            )
        removed_echo = (
            "\n".join(self.listed_ids)
            if self.remove_stdout is None
            else self.remove_stdout
        )
        return type(
            "R",
            (),
            {
                "stdout": removed_echo,
                "stderr": self.remove_stderr,
                "returncode": self.remove_rc,
            },
        )()


class TestInjectNetwork:
    def test_adds_external_network_and_per_service_membership(self):
        compose = {"services": {"alpha": {}, "beta": {}}}

        patches.inject_network(compose, network="proj-net")

        assert compose["services"]["alpha"]["networks"] == {"proj-net": {}}
        assert compose["services"]["beta"]["networks"] == {"proj-net": {}}
        assert compose["networks"]["proj-net"] == {
            "external": True,
            "name": "proj-net",
        }

    def test_preserves_existing_service_keys(self):
        compose = {
            "services": {"alpha": {"image": "img:1", "environment": ["A=B"]}}
        }

        patches.inject_network(compose, network="proj-net")

        assert compose["services"]["alpha"]["image"] == "img:1"
        assert compose["services"]["alpha"]["environment"] == ["A=B"]
        assert compose["services"]["alpha"]["networks"] == {"proj-net": {}}

    def test_idempotent_for_repeated_calls(self):
        compose: dict = {"services": {"alpha": {}}}

        patches.inject_network(compose, network="proj-net")
        patches.inject_network(compose, network="proj-net")

        assert compose["services"]["alpha"]["networks"] == {"proj-net": {}}


class TestHardenService:
    def test_adds_init_log_rotation_and_label(self):
        service: dict = {}

        patches.harden_service(service)

        assert service["init"] is True
        assert service["logging"]["driver"] == "json-file"
        assert service["logging"]["options"]["max-size"] == "10m"
        assert service["labels"]["sagemaker.local"] == "true"
        assert service["labels"]["sagemaker.local.role"] == "job"

    def test_stamps_serve_role_on_sdk_serving_service(self):
        # The SDK writes `command: serve` only for serving services
        # (image.py); it is the role marker the cleanup filter keys on.
        service = {"command": "serve"}

        patches.harden_service(service)

        assert service["labels"]["sagemaker.local"] == "true"
        assert service["labels"]["sagemaker.local.role"] == "serve"

    @pytest.mark.parametrize(
        "service",
        [{"command": "train"}, {"entrypoint": ["python", "train.py"]}],
        ids=["train-command", "entrypoint-only"],
    )
    def test_stamps_job_role_on_non_serving_service(self, service):
        patches.harden_service(service)

        assert service["labels"]["sagemaker.local.role"] == "job"

    def test_stamps_role_labels_in_list_form(self):
        service = {"command": "serve", "labels": ["team=ml"]}

        patches.harden_service(service)

        assert service["labels"] == [
            "team=ml",
            "sagemaker.local=true",
            "sagemaker.local.role=serve",
        ]

    def test_role_labels_idempotent_on_repeated_calls(self):
        service = {"command": "serve"}

        patches.harden_service(service)
        patches.harden_service(service)

        assert service["labels"] == {
            "sagemaker.local": "true",
            "sagemaker.local.role": "serve",
        }

    def test_preserves_existing_settings(self):
        service = {"ports": ["8080:8080"], "mem_limit": "512m", "init": None}

        patches.harden_service(service)

        assert service["mem_limit"] == "512m"
        assert service["ports"] == ["8080:8080"]
        assert (
            service["init"] is None
        )  # pre-existing explicit choice respected


COMPOSE_TEMPLATE = {
    "services": {"sm-alpha": {"image": "sagemaker-local:latest"}},
    "networks": {"sagemaker-local": {"name": "sagemaker-local"}},
}


@pytest.fixture()
def compose_project(tmp_path: Path, monkeypatch) -> Path:
    """Fake SDK ``_compose`` that writes a minimal project; returns its path."""
    import sagemaker.local.image as sm_image

    def fake_original_compose(self, detached=False):  # noqa: ANN001, ARG001
        path = tmp_path / "job" / "docker-compose.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.dump(COMPOSE_TEMPLATE), encoding="utf-8")
        return ["docker", "compose", "-f", str(path), "up"]

    monkeypatch.setattr(
        sm_image._SageMakerContainer, "_compose", fake_original_compose
    )
    return tmp_path / "job" / "docker-compose.yaml"


def invoke_patched_compose() -> dict:
    import sagemaker.local.image as sm_image

    container = sm_image._SageMakerContainer.__new__(
        sm_image._SageMakerContainer
    )
    compose_cmd = container._compose()
    compose_path = Path(compose_cmd[compose_cmd.index("-f") + 1])
    return yaml.safe_load(compose_path.read_text(encoding="utf-8"))


class TestApplyComposePatches:
    def test_generated_file_gains_network_and_hardening(self, compose_project):
        patches.apply_compose_patches(make_config())

        compose = invoke_patched_compose()

        service = compose["services"]["sm-alpha"]
        assert service["networks"] == {"proj-net": {}}
        assert service["init"] is True
        assert compose["networks"]["proj-net"]["external"] is True
        # The SDK's own network definition survives untouched.
        assert compose["networks"]["sagemaker-local"] == {
            "name": "sagemaker-local"
        }

    def test_repeated_application_is_a_noop(self, compose_project):
        patches.apply_compose_patches(make_config())
        patches.apply_compose_patches(make_config(network="other-net"))

        compose = invoke_patched_compose()

        # First configuration wins; later calls do not stack wrappers.
        assert compose["services"]["sm-alpha"]["networks"] == {"proj-net": {}}
        assert "other-net" not in compose["services"]["sm-alpha"]["networks"]

    def test_disabled_flags_leave_services_untouched(self, compose_project):
        patches.apply_compose_patches(
            make_config(
                network=None,
                inject_compose_network=False,
                harden_containers=False,
            )
        )

        compose = invoke_patched_compose()

        service = compose["services"]["sm-alpha"]
        assert "networks" not in service
        assert "init" not in service
        assert set(compose.get("networks", {})) == {"sagemaker-local"}


class TestComposeCommandDetection:
    """Regression: docker compose v5+ lacks the literal 'v2' substring the SDK
    greps for (measured: 'Docker Compose version v5.3.1')."""

    def test_v5_output_is_accepted(self, monkeypatch):
        import subprocess

        monkeypatch.setattr(
            subprocess,
            "check_output",
            lambda *_, **__: "Docker Compose version v5.3.1\n",
        )
        monkeypatch.setattr(patches.shutil, "which", lambda _name: None)

        assert patches.tolerant_compose_cmd_prefix() == ["docker", "compose"]

    def test_legacy_fallback_when_plugin_missing(self, monkeypatch):
        import subprocess

        def boom(*a, **__):  # noqa: ANN002, ANN003
            raise subprocess.CalledProcessError(1, a[0] if a else "docker")

        monkeypatch.setattr(subprocess, "check_output", boom)
        monkeypatch.setattr(
            patches.shutil, "which", lambda _name: "/usr/bin/docker-compose"
        )

        assert patches.tolerant_compose_cmd_prefix() == ["docker-compose"]

    def test_import_error_when_nothing_available(self, monkeypatch):
        import subprocess

        def boom(*a, **__):  # noqa: ANN002, ANN003
            raise subprocess.CalledProcessError(1, a[0] if a else "docker")

        monkeypatch.setattr(subprocess, "check_output", boom)
        monkeypatch.setattr(patches.shutil, "which", lambda _name: None)

        with pytest.raises(ImportError, match="docker compose"):
            patches.tolerant_compose_cmd_prefix()

    def test_docker_cli_absent_falls_back_to_legacy_binary(self, monkeypatch):
        monkeypatch.setattr(subprocess, "check_output", DockerCliAbsent())
        monkeypatch.setattr(
            patches.shutil, "which", lambda _name: "/usr/bin/docker-compose"
        )

        assert patches.tolerant_compose_cmd_prefix() == ["docker-compose"]

    def test_docker_cli_absent_raises_named_import_error(self, monkeypatch):
        monkeypatch.setattr(subprocess, "check_output", DockerCliAbsent())
        monkeypatch.setattr(patches.shutil, "which", lambda _name: None)

        with pytest.raises(ImportError, match="docker compose"):
            patches.tolerant_compose_cmd_prefix()

    def test_applied_patch_survives_container_init(self, monkeypatch):
        import subprocess

        monkeypatch.setattr(
            subprocess,
            "check_output",
            lambda *_, **__: "Docker Compose version v5.3.1\n",
        )
        monkeypatch.setattr(patches.shutil, "which", lambda _name: None)

        patches.apply_compose_patches(make_config())

        import sagemaker.local.image as sm_image

        assert sm_image._SageMakerContainer._get_compose_cmd_prefix() == [
            "docker",
            "compose",
        ]


class TestResetAll:
    """``reset_all`` must restore the SDK's descriptor shape, not just the
    callable — pre-patch ``_get_compose_cmd_prefix`` is a ``@staticmethod``
    (image.py:139), so a plain-function restore breaks instance calls."""

    def test_reset_restores_staticmethod_descriptor(self, monkeypatch):
        import sagemaker.local.image as sm_image

        monkeypatch.setattr(
            subprocess,
            "check_output",
            lambda *_, **__: "Docker Compose version v2.29.0\n",
        )
        monkeypatch.setattr(patches.shutil, "which", lambda _name: None)
        patches.apply_compose_patches(make_config())

        patches.reset_all()

        container_cls = sm_image._SageMakerContainer
        assert isinstance(
            inspect.getattr_static(container_cls, "_get_compose_cmd_prefix"),
            staticmethod,
        )
        instance = container_cls.__new__(container_cls)
        assert instance._get_compose_cmd_prefix() == ["docker", "compose"]


ROUTE_TABLE = textwrap.dedent(
    """\
    Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT
    eth0\t00000000\t010012AC\t0003\t0\t0\t0\t00000000\t0\t0\t0
    eth0\t000012AC\t00000000\t0001\t0\t0\t0\t000CFFFF\t0\t0\t0
    lo\t00000000\t00000000\t0001\t0\t0\t0\t000000FF\t0\t0\t0
    """
)


class TestResolveGatewayFromRoutes:
    def test_parses_default_route_gateway_little_endian_hex(self):
        result = patches.resolve_gateway_from_routes(ROUTE_TABLE.splitlines())

        assert result == "172.18.0.1"

    def test_returns_none_when_no_default_route(self):
        routes = ROUTE_TABLE.replace(
            "00000000\t010012AC", "00000000\t00000000"
        ).splitlines()

        assert patches.resolve_gateway_from_routes(routes) is None


class TestCleanupStoppedContainers:
    def test_removes_only_exited_sagemaker_labelled_containers(
        self, monkeypatch
    ):
        runner = FakeRunner(listed_ids=["abc123", "def456"])
        monkeypatch.setattr(patches.subprocess, "run", runner)

        removed = patches.cleanup_stopped_containers()

        assert removed == 2
        list_cmd, remove_cmd = runner.calls
        assert "label=sagemaker.local=true" in list_cmd
        assert "status=exited" in list_cmd
        assert remove_cmd == ["docker", "rm", "-f", "abc123", "def456"]

    def test_failed_removal_reports_actual_count(self, monkeypatch, caplog):
        # docker rm echoes only the ids it removed on stdout; rc=1 + stderr
        # names the ones it could not (measured on docker 29.8.0).
        runner = FakeRunner(
            listed_ids=["a1", "b2", "c3"],
            remove_rc=1,
            remove_stdout="a1\n",
            remove_stderr="denied",
        )
        monkeypatch.setattr(patches.subprocess, "run", runner)

        with caplog.at_level(logging.WARNING):
            assert patches.cleanup_stopped_containers() == 1

        assert "denied" in caplog.text

    def test_noop_when_none_found(self, monkeypatch):
        runner = FakeRunner(listed_ids=[])
        monkeypatch.setattr(patches.subprocess, "run", runner)

        assert patches.cleanup_stopped_containers() == 0
        assert len(runner.calls) == 1


class TestCleanupStaleServingContainers:
    """Serving containers persist across host-process death and hold the
    bound port; they must be reaped regardless of run state. Only the
    ``role=serve`` label marks them — job containers must survive."""

    def test_removes_running_and_exited_labelled_containers(self, monkeypatch):
        runner = FakeRunner(listed_ids=["a1", "b2", "c3"])
        monkeypatch.setattr(patches.subprocess, "run", runner)

        assert patches.cleanup_stale_serving_containers() == 3

        list_cmd, remove_cmd = runner.calls
        assert list_cmd == [
            "docker",
            "container",
            "ls",
            "-a",
            "--filter",
            "label=sagemaker.local.role=serve",
            "-q",
        ]
        assert remove_cmd == ["docker", "rm", "-f", "a1", "b2", "c3"]

    def test_noop_when_none_found(self, monkeypatch):
        runner = FakeRunner(listed_ids=[])
        monkeypatch.setattr(patches.subprocess, "run", runner)

        assert patches.cleanup_stale_serving_containers() == 0
        assert len(runner.calls) == 1


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
    document for that id (the last one repeats once exhausted). Inspecting an
    unlisted id fails like real docker (rc=1); any other command raises —
    the gateway arm must not depend on the daemon.
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


class TestApplyDockerHostPatch:
    @pytest.fixture()
    def fake_host_env(self, monkeypatch, tmp_path: Path):
        routes = tmp_path / "route"
        routes.write_text(ROUTE_TABLE, encoding="utf-8")
        marker = tmp_path / ".dockerenv"
        marker.touch()
        monkeypatch.setattr(patches, "_PROC_NET_ROUTE", routes)
        monkeypatch.setattr(patches, "_DOCKERENV_PATH", marker)
        monkeypatch.setattr(patches.subprocess, "run", FakeDocker())
        return marker

    def _all_getters(self) -> list:
        import sagemaker.local.entities as sm_entities
        import sagemaker.local.local_session as sm_local_session
        import sagemaker.local.utils as sm_utils

        return [
            sm_utils.get_docker_host,
            sm_entities.get_docker_host,
            sm_local_session.get_docker_host,
        ]

    def test_inside_container_returns_gateway_for_every_import_site(
        self, fake_host_env
    ):
        patches.apply_docker_host_patch(force=False)

        for getter in self._all_getters():
            assert getter() == "172.18.0.1"

    def test_outside_container_keeps_sdk_default(self, monkeypatch, tmp_path):
        routes = tmp_path / "route"
        routes.write_text(ROUTE_TABLE, encoding="utf-8")
        monkeypatch.setattr(patches, "_PROC_NET_ROUTE", routes)
        monkeypatch.setattr(
            patches, "_DOCKERENV_PATH", tmp_path / ".dockerenv"
        )

        patches.apply_docker_host_patch(force=False)

        for getter in self._all_getters():
            assert getter() != "172.18.0.1"

    def test_force_overrides_container_detection(self, monkeypatch, tmp_path):
        routes = tmp_path / "route"
        routes.write_text(ROUTE_TABLE, encoding="utf-8")
        monkeypatch.setattr(patches, "_PROC_NET_ROUTE", routes)
        monkeypatch.setattr(
            patches, "_DOCKERENV_PATH", tmp_path / "absent-marker"
        )
        monkeypatch.setattr(patches.subprocess, "run", FakeDocker())

        patches.apply_docker_host_patch(force=True)

        for getter in self._all_getters():
            assert getter() == "172.18.0.1"


class TestServingContainerIpResolution:
    """Shared-network resolution (the patched getter must prefer a running
    ``role=serve`` container's IP when it sits on one of the caller's
    connected subnets — the bridge gateway is unreachable from sibling
    containers on hosts that drop same-bridge DNAT traffic)."""

    @pytest.fixture()
    def container_routes(self, monkeypatch, tmp_path: Path):
        routes = tmp_path / "route"
        routes.write_text(CONTAINER_ROUTE_TABLE, encoding="utf-8")
        monkeypatch.setattr(patches, "_PROC_NET_ROUTE", routes)

    def _docker_host(self) -> str:
        import sagemaker.local.utils as sm_utils

        return sm_utils.get_docker_host()

    def test_shared_network_container_ip_wins_over_gateway(
        self, monkeypatch, container_routes
    ):
        docker = FakeDocker(
            serve_ids=["c1"],
            inspect_docs={
                "c1": [
                    inspect_doc(
                        "running",
                        {
                            "foreign-net": "10.99.0.9",
                            "mlops_net": "172.19.0.4",
                        },
                    )
                ]
            },
        )
        monkeypatch.setattr(patches.subprocess, "run", docker)
        patches.apply_docker_host_patch(force=True)

        assert self._docker_host() == "172.19.0.4"

    def test_foreign_network_only_falls_back_to_gateway(
        self, monkeypatch, container_routes
    ):
        monkeypatch.setattr(patches, "_SERVE_IP_WAIT_S", 0.0)
        docker = FakeDocker(
            serve_ids=["c1"],
            inspect_docs={
                "c1": [inspect_doc("running", {"other-net": "10.99.0.9"})]
            },
        )
        monkeypatch.setattr(patches.subprocess, "run", docker)
        patches.apply_docker_host_patch(force=True)

        assert self._docker_host() == "172.19.0.1"

    def test_waits_while_running_container_lacks_shared_ip(
        self, monkeypatch, container_routes
    ):
        monkeypatch.setattr(patches, "_SERVE_IP_WAIT_S", 60.0)
        monkeypatch.setattr(patches, "_SERVE_IP_POLL_S", 0.0)
        docker = FakeDocker(
            serve_ids=["c1"],
            inspect_docs={
                "c1": [
                    inspect_doc("running", {"mlops_net": ""}),
                    inspect_doc("running", {"mlops_net": "172.19.0.4"}),
                ]
            },
        )
        monkeypatch.setattr(patches.subprocess, "run", docker)
        patches.apply_docker_host_patch(force=True)

        assert self._docker_host() == "172.19.0.4"
        assert [cmd[2] for cmd in docker.calls] == [
            "ls",
            "inspect",
            "ls",
            "inspect",
        ]

    def test_no_serving_container_uses_gateway(
        self, monkeypatch, container_routes
    ):
        # Zero wait budget: nothing can appear, so resolution is one `ls`.
        monkeypatch.setattr(patches, "_SERVE_IP_WAIT_S", 0.0)
        docker = FakeDocker()
        monkeypatch.setattr(patches.subprocess, "run", docker)
        patches.apply_docker_host_patch(force=True)

        assert self._docker_host() == "172.19.0.1"
        assert [cmd[2] for cmd in docker.calls] == ["ls"]

    def test_waits_for_serve_container_spawned_late(
        self, monkeypatch, container_routes
    ):
        # Real-stack regression (G-187): the SDK's container.serve() launches
        # `compose up` via Popen, so get_docker_host() races container
        # creation — the first `ls` can legitimately come back empty.
        monkeypatch.setattr(patches, "_SERVE_IP_WAIT_S", 60.0)
        monkeypatch.setattr(patches, "_SERVE_IP_POLL_S", 0.0)
        docker = FakeDocker(
            ls_script=[[], ["c1"]],
            inspect_docs={
                "c1": [inspect_doc("running", {"mlops_net": "172.19.0.4"})]
            },
        )
        monkeypatch.setattr(patches.subprocess, "run", docker)
        patches.apply_docker_host_patch(force=True)

        assert self._docker_host() == "172.19.0.4"
        assert [cmd[2] for cmd in docker.calls] == ["ls", "ls", "inspect"]

    def test_exited_serving_container_does_not_block(
        self, monkeypatch, container_routes
    ):
        monkeypatch.setattr(patches, "_SERVE_IP_WAIT_S", 60.0)
        docker = FakeDocker(
            serve_ids=["c1"],
            inspect_docs={"c1": [inspect_doc("exited", {})]},
        )
        monkeypatch.setattr(patches.subprocess, "run", docker)
        patches.apply_docker_host_patch(force=True)

        assert self._docker_host() == "172.19.0.1"
        assert [cmd[2] for cmd in docker.calls] == ["ls", "inspect"]

    def test_inspect_failure_uses_gateway(self, monkeypatch, container_routes):
        docker = FakeDocker(serve_ids=["c1"])  # no doc: inspect exits rc=1
        monkeypatch.setattr(patches.subprocess, "run", docker)
        patches.apply_docker_host_patch(force=True)

        assert self._docker_host() == "172.19.0.1"

    def test_docker_cli_absent_uses_gateway(
        self, monkeypatch, container_routes
    ):
        monkeypatch.setattr(patches.subprocess, "run", DockerCliAbsent())
        patches.apply_docker_host_patch(force=True)

        assert self._docker_host() == "172.19.0.1"
