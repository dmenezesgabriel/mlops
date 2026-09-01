"""Monkey-patches that make SageMaker local mode work offline and inside
containers. All patches are idempotent and reversible via :func:`reset_all`.

Evidence for each patch (sagemaker 2.257.1 source):
- ``_SageMakerContainer._compose`` builds the docker compose invocation after
  writing ``<container_root>/docker-compose.yaml``; wrapping it lets us rewrite
  the YAML before ``docker compose up`` runs.
- ``_get_compose_cmd_prefix`` only accepts plugin output containing the literal
  substring "v2"; docker compose v5+ reports e.g. "Docker Compose version
  v5.3.1" and would raise ImportError.
- ``get_docker_host`` defaults to "localhost", which points at the wrong
  network namespace when the caller itself runs in a container. It is imported
  by name into ``sagemaker.local.entities`` and
  ``sagemaker.local.local_session``, so all three sites must be replaced.

These functions reassign private attributes of a third-party untyped module,
so the boundary is the only place in this lib that reaches into private SDK
interfaces on purpose.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import yaml

from sagemaker_local.config import LocalModeConfig

logger = logging.getLogger(__name__)

_PROC_NET_ROUTE = Path("/proc/net/route")
_DOCKERENV_PATH = Path("/.dockerenv")

_COMPOSE_FILE_LABEL = "-f"
_COMPOSE_CALLBACK = Callable[..., list[str]]
_ORIGINAL_COMPOSE: _COMPOSE_CALLBACK | None = None
_ORIGINAL_PREFIX: _COMPOSE_CALLBACK | None = None
_ORIGINAL_GET_DOCKER_HOST: tuple[Callable[[], str], ...] | None = None


def inject_network(compose: dict, network: str) -> None:
    """Attach every service to an external docker network (idempotent).

    Example:
        >>> inject_network({"services": {"a": {}}}, "proj-net")
        >>> compose["services"]["a"]["networks"] == {"proj-net": {}}
        True
    """
    external = {"external": True, "name": network}
    for service in compose.get("services", {}).values():
        networks = service.setdefault("networks", {})
        networks.setdefault(network, {})
    top_level: dict = compose.setdefault("networks", {})
    top_level.setdefault(network, external)


def harden_service(service: dict) -> None:
    """Add zombie-reaping init, bounded logs and a cleanup label (idempotent)."""
    service.setdefault("init", True)
    logging_cfg = service.setdefault("logging", {})
    logging_cfg.setdefault("driver", "json-file")
    logging_cfg.setdefault("options", {}).setdefault("max-size", "10m")
    labels = service.setdefault("labels", {})
    if isinstance(labels, list):
        if "sagemaker.local=true" not in labels:
            labels.append("sagemaker.local=true")
    else:
        labels.setdefault("sagemaker.local", "true")


def tolerant_compose_cmd_prefix() -> list[str]:
    """Locate docker compose without the SDK's brittle 'v2' string check.

    Returns:
        Command prefix list usable as the head of a compose invocation.

    Raises:
        ImportError: when neither the plugin nor legacy binary is available.

    Example:
        >>> tolerant_compose_cmd_prefix()  # doctest: +SKIP
        ['docker', 'compose']
    """
    try:
        output = subprocess.check_output(  # noqa: S603
            ["docker", "compose", "version"],
            stderr=subprocess.DEVNULL,
            encoding="UTF-8",
        )
    except subprocess.CalledProcessError:
        output = ""
    if output.strip():
        return ["docker", "compose"]
    if shutil.which("docker-compose") is not None:
        return ["docker-compose"]
    raise ImportError(
        "docker compose is not installed; local mode requires either the "
        "'docker compose' plugin or a 'docker-compose' binary on PATH"
    )


def apply_compose_patches(cfg: LocalModeConfig) -> None:
    """Install compose rewriting + detection patches exactly once per process."""
    global _ORIGINAL_COMPOSE, _ORIGINAL_PREFIX
    if _ORIGINAL_COMPOSE is not None:
        return
    import sagemaker.local.image as sm_image

    _ORIGINAL_COMPOSE = sm_image._SageMakerContainer._compose
    _ORIGINAL_PREFIX = sm_image._SageMakerContainer._get_compose_cmd_prefix

    container_cls = sm_image._SageMakerContainer

    def patched_compose(self: object, detached: bool = False) -> list[str]:
        assert _ORIGINAL_COMPOSE is not None
        compose_cmd = _ORIGINAL_COMPOSE(self, detached)
        path = Path(compose_cmd[compose_cmd.index(_COMPOSE_FILE_LABEL) + 1])
        _rewrite_compose_file(path, cfg)
        return compose_cmd

    def patched_prefix() -> list[str]:
        return tolerant_compose_cmd_prefix()

    # Runtime reassignment of bound-method slots on a third-party class.
    container_cls._compose = patched_compose
    container_cls._get_compose_cmd_prefix = staticmethod(patched_prefix)
    logger.info("sagemaker-local compose patches installed")


def _rewrite_compose_file(path: Path, cfg: LocalModeConfig) -> None:
    compose = yaml.safe_load(path.read_text(encoding="utf-8"))
    services = compose.get("services", {})
    if cfg.inject_compose_network and cfg.network:
        inject_network(compose, cfg.network)
    if cfg.harden_containers:
        for service in services.values():
            harden_service(service)
    path.write_text(
        yaml.dump(compose, default_flow_style=False), encoding="utf-8"
    )
    logger.info("rewrote %s (network=%s)", path, cfg.network)


def resolve_gateway_from_routes(route_lines: list[str]) -> str | None:
    """Return the default-route gateway IP from /proc/net/route content.

    The gateway column stores the address as little-endian hex; byte pairs are
    read back-to-front (see proc(5)).

    Example:
        >>> resolve_gateway_from_routes(["eth0\\t00000000\\t010012AC\\t0"])
        '172.18.0.1'
    """
    for line in route_lines:
        fields = line.split()
        if len(fields) < 3:
            continue
        destination, gateway_hex = fields[1], fields[2]
        if destination != "00000000" or gateway_hex == "00000000":
            continue
        octets = (int(gateway_hex[i : i + 2], 16) for i in (6, 4, 2, 0))
        return ".".join(str(octet) for octet in octets)
    return None


def _gateway_from_proc() -> str | None:
    try:
        lines = _PROC_NET_ROUTE.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("cannot read %s: %s", _PROC_NET_ROUTE, exc)
        return None
    return resolve_gateway_from_routes(lines)


def _running_inside_container() -> bool:
    return _DOCKERENV_PATH.exists()


def _replace_module_attr(
    module: ModuleType, name: str, value: Callable[[], str]
) -> None:
    # setattr(ModuleType, str): the target SDK modules ship without py.typed,
    # so both ruff's B010 and pyright's private-usage checks are moot here.
    setattr(module, name, value)  # noqa: B010


def apply_docker_host_patch(force: bool = False) -> None:
    """Resolve serving containers via the docker bridge gateway.

    Only activates when running inside a container unless ``force`` is set.
    Replaces ``get_docker_host`` in the three modules that import it by name.
    """
    global _ORIGINAL_GET_DOCKER_HOST
    if _ORIGINAL_GET_DOCKER_HOST is not None:
        return
    if not force and not _running_inside_container():
        logger.debug("not inside a container; skipping docker host patch")
        return

    import sagemaker.local.entities as sm_entities
    import sagemaker.local.local_session as sm_local_session
    import sagemaker.local.utils as sm_utils

    fallback = sm_utils.get_docker_host

    def gateway_getter() -> str:
        gateway = _gateway_from_proc()
        if gateway:
            logger.info("resolved docker host gateway: %s", gateway)
            return gateway
        return fallback()

    _ORIGINAL_GET_DOCKER_HOST = (
        sm_utils.get_docker_host,
        getattr(sm_entities, "get_docker_host"),  # noqa: B009
        getattr(sm_local_session, "get_docker_host"),  # noqa: B009
    )
    for module in (sm_utils, sm_entities, sm_local_session):
        _replace_module_attr(module, "get_docker_host", gateway_getter)
    logger.info("sagemaker-local docker-host patch installed")


def _list_sagemaker_local_containers(status: str | None) -> list[str]:
    cmd = [
        "docker",
        "container",
        "ls",
        "-a",
        "--filter",
        "label=sagemaker.local=true",
    ]
    if status is not None:
        cmd += ["--filter", f"status={status}"]
    cmd += ["-q"]
    listed = subprocess.run(  # noqa: S603
        cmd, capture_output=True, text=True, check=True
    )
    return listed.stdout.split()


def _remove_containers(ids: list[str]) -> int:
    if not ids:
        return 0
    subprocess.run(  # noqa: S603
        ["docker", "rm", "-f", *ids],
        capture_output=True,
        text=True,
        check=False,
    )
    logger.info("removed %d stopped sagemaker-local container(s)", len(ids))
    return len(ids)


def cleanup_stopped_containers() -> int:
    """Remove exited, ``sagemaker.local=true`` labelled containers.

    Returns:
        Number of containers removed.

    Example:
        >>> cleanup_stopped_containers()  # doctest: +SKIP
        3
    """
    return _remove_containers(_list_sagemaker_local_containers("exited"))


def cleanup_stale_serving_containers() -> int:
    """Remove any ``sagemaker.local=true`` container regardless of run state.

    Serving containers live on without a bound host process, so on process
    death (or a killed predict) they linger and grab the serving port. Their
    label marks them as disposable.

    Returns:
        Number of containers removed.

    Example:
        >>> cleanup_stale_serving_containers()  # doctest: +SKIP
        3
    """
    return _remove_containers(_list_sagemaker_local_containers(None))


def reset_all() -> None:
    """Undo every patch applied by this module (used by tests and teardown)."""
    global _ORIGINAL_COMPOSE, _ORIGINAL_PREFIX, _ORIGINAL_GET_DOCKER_HOST
    if _ORIGINAL_COMPOSE is not None:
        import sagemaker.local.image as sm_image

        container_cls = sm_image._SageMakerContainer
        container_cls._compose = _ORIGINAL_COMPOSE
        # pyright cannot type the staticmethod slot, so disassemble the raw
        # wrapper here; ruff's B010 does not apply to this roundabout restore.
        setattr(container_cls, "_get_compose_cmd_prefix", _ORIGINAL_PREFIX)  # noqa: B010
        _ORIGINAL_COMPOSE = None
        _ORIGINAL_PREFIX = None
    if _ORIGINAL_GET_DOCKER_HOST is not None:
        import sagemaker.local.entities as sm_entities
        import sagemaker.local.local_session as sm_local_session
        import sagemaker.local.utils as sm_utils

        utils_ref, entities_ref, session_ref = _ORIGINAL_GET_DOCKER_HOST
        for module, ref in (
            (sm_utils, utils_ref),
            (sm_entities, entities_ref),
            (sm_local_session, session_ref),
        ):
            _replace_module_attr(module, "get_docker_host", ref)
        _ORIGINAL_GET_DOCKER_HOST = None
