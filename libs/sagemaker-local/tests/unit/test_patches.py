"""Unit tests for sagemaker_local.patches."""

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
    """Named fake for subprocess.run calls issued by the patches."""

    def __init__(self, listed_ids: list[str] | None = None):
        self.listed_ids = listed_ids or []
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **kwargs):  # noqa: ANN003
        self.calls.append(cmd)
        if "--filter" in cmd:
            return type(
                "R",
                (),
                {"stdout": "\n".join(self.listed_ids), "returncode": 0},
            )()
        return type("R", (), {"stdout": "", "returncode": 0})()


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
            lambda *a, **k: "Docker Compose version v5.3.1\n",
        )
        monkeypatch.setattr(patches.shutil, "which", lambda name: None)

        assert patches.tolerant_compose_cmd_prefix() == ["docker", "compose"]

    def test_legacy_fallback_when_plugin_missing(self, monkeypatch):
        import subprocess

        def boom(*a, **k):  # noqa: ANN002, ANN003
            raise subprocess.CalledProcessError(1, a[0] if a else "docker")

        monkeypatch.setattr(subprocess, "check_output", boom)
        monkeypatch.setattr(
            patches.shutil, "which", lambda name: "/usr/bin/docker-compose"
        )

        assert patches.tolerant_compose_cmd_prefix() == ["docker-compose"]

    def test_import_error_when_nothing_available(self, monkeypatch):
        import subprocess

        def boom(*a, **k):  # noqa: ANN002, ANN003
            raise subprocess.CalledProcessError(1, a[0] if a else "docker")

        monkeypatch.setattr(subprocess, "check_output", boom)
        monkeypatch.setattr(patches.shutil, "which", lambda name: None)

        with pytest.raises(ImportError, match="docker compose"):
            patches.tolerant_compose_cmd_prefix()

    def test_applied_patch_survives_container_init(self, monkeypatch):
        import subprocess

        monkeypatch.setattr(
            subprocess,
            "check_output",
            lambda *a, **k: "Docker Compose version v5.3.1\n",
        )
        monkeypatch.setattr(patches.shutil, "which", lambda name: None)

        patches.apply_compose_patches(make_config())

        import sagemaker.local.image as sm_image

        assert sm_image._SageMakerContainer._get_compose_cmd_prefix() == [
            "docker",
            "compose",
        ]


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

    def test_noop_when_none_found(self, monkeypatch):
        runner = FakeRunner(listed_ids=[])
        monkeypatch.setattr(patches.subprocess, "run", runner)

        assert patches.cleanup_stopped_containers() == 0
        assert len(runner.calls) == 1


class TestCleanupStaleServingContainers:
    """Serving containers persist across host-process death and hold the
    bound port; they must be reaped regardless of run state."""

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
            "label=sagemaker.local=true",
            "-q",
        ]
        assert remove_cmd == ["docker", "rm", "-f", "a1", "b2", "c3"]

    def test_noop_when_none_found(self, monkeypatch):
        runner = FakeRunner(listed_ids=[])
        monkeypatch.setattr(patches.subprocess, "run", runner)

        assert patches.cleanup_stale_serving_containers() == 0
        assert len(runner.calls) == 1


class DockerlessRunner:
    """Fails if anything tries to shell out — proves gateway came from routes."""

    def __call__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError(f"subprocess called unexpectedly: {args}")


class TestApplyDockerHostPatch:
    @pytest.fixture()
    def fake_host_env(self, monkeypatch, tmp_path: Path):
        routes = tmp_path / "route"
        routes.write_text(ROUTE_TABLE, encoding="utf-8")
        marker = tmp_path / ".dockerenv"
        marker.touch()
        monkeypatch.setattr(patches, "_PROC_NET_ROUTE", routes)
        monkeypatch.setattr(patches, "_DOCKERENV_PATH", marker)
        monkeypatch.setattr(patches.subprocess, "run", DockerlessRunner())
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
        monkeypatch.setattr(patches.subprocess, "run", DockerlessRunner())

        patches.apply_docker_host_patch(force=True)

        for getter in self._all_getters():
            assert getter() == "172.18.0.1"
