# pyright: reportPrivateUsage=false
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
  The replacement first resolves a running ``sagemaker.local.role=serve``
  container that sits on one of the caller's connected subnets — the bridge
  gateway is unreachable from sibling containers on hosts that drop
  same-bridge DNAT traffic — then the default-route gateway, then the SDK's
  own resolution.

These functions reassign private attributes of a third-party untyped module,
so the boundary is the only place in this lib that reaches into private SDK
interfaces on purpose.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import yaml

from sagemaker_local.config import LocalModeConfig

logger = logging.getLogger(__name__)

_PROC_NET_ROUTE = Path("/proc/net/route")
_DOCKERENV_PATH = Path("/.dockerenv")

_SERVE_ROLE_LABEL = "sagemaker.local.role=serve"
_SERVE_IP_WAIT_S = 15.0
_SERVE_IP_POLL_S = 0.5
_PENDING_CONTAINER_STATES = frozenset({"created", "running", "restarting"})

_COMPOSE_FILE_LABEL = "-f"
_COMPOSE_CALLBACK = Callable[..., list[str]]
_original_compose: _COMPOSE_CALLBACK | None = None
_original_prefix: _COMPOSE_CALLBACK | None = None
_original_get_docker_host: tuple[Callable[[], str], ...] | None = None


def inject_network(compose: dict[str, Any], network: str) -> None:
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
    top_level: dict[str, Any] = compose.setdefault("networks", {})
    top_level.setdefault(network, external)


def harden_service(service: dict[str, Any]) -> None:
    """Add zombie-reaping init, bounded logs and cleanup labels (idempotent).

    The ``sagemaker.local.role`` label is ``serve`` only when the service
    carries the SDK's ``command: serve`` marker — ``_create_docker_host``
    writes it for serving containers alone (sagemaker 2.257.1 image.py), so
    ``cleanup_stale_serving_containers`` can reap port-holders without
    touching running train/process jobs.
    """
    service.setdefault("init", True)
    logging_cfg = service.setdefault("logging", {})
    logging_cfg.setdefault("driver", "json-file")
    logging_cfg.setdefault("options", {}).setdefault("max-size", "10m")
    role = "serve" if service.get("command") == "serve" else "job"
    labels = service.setdefault("labels", {})
    if isinstance(labels, list):
        labels_list = cast(list[str], labels)
        for label in ("sagemaker.local=true", f"sagemaker.local.role={role}"):
            if label not in labels_list:
                labels_list.append(label)
    else:
        labels.setdefault("sagemaker.local", "true")
        labels.setdefault("sagemaker.local.role", role)


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
    global _original_compose, _original_prefix
    if _original_compose is not None:
        return
    import sagemaker.local.image as sm_image

    _original_compose = sm_image._SageMakerContainer._compose
    _original_prefix = sm_image._SageMakerContainer._get_compose_cmd_prefix

    container_cls = sm_image._SageMakerContainer

    def patched_compose(self: object, detached: bool = False) -> list[str]:
        assert _original_compose is not None
        compose_cmd = _original_compose(self, detached)
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


def _route_lines() -> list[str]:
    try:
        return _PROC_NET_ROUTE.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("cannot read %s: %s", _PROC_NET_ROUTE, exc)
        return []


def _gateway_from_proc() -> str | None:
    return resolve_gateway_from_routes(_route_lines())


def _route_hex_to_int(raw: str) -> int:
    return int.from_bytes(bytes.fromhex(raw)[::-1])


def _connected_subnets(route_lines: list[str]) -> list[tuple[int, int]]:
    """(network, mask) int pairs for directly-reachable routes (no gateway)."""
    subnets: list[tuple[int, int]] = []
    for line in route_lines:
        fields = line.split()
        if len(fields) < 8:
            continue
        destination, gateway, mask = fields[1], fields[2], fields[7]
        if (
            destination == "00000000"
            or gateway != "00000000"
            or mask == "00000000"
        ):
            continue
        try:
            subnets.append(
                (_route_hex_to_int(destination), _route_hex_to_int(mask))
            )
        except ValueError:
            continue
    return subnets


def _ip_on_subnets(ip: str, subnets: list[tuple[int, int]]) -> bool:
    try:
        value = int(ipaddress.IPv4Address(ip))
    except ValueError:
        return False
    return any(value & mask == base for base, mask in subnets)


def _serve_container_ids() -> list[str] | None:
    """``None`` when the daemon can't be queried (vs an empty listing)."""
    try:
        return _list_sagemaker_local_containers(None, _SERVE_ROLE_LABEL)
    except (OSError, subprocess.CalledProcessError) as exc:
        logger.warning("cannot list serving containers: %s", exc)
        return None


def _inspect_serving_container(cid: str) -> dict[str, Any] | None:
    try:
        inspected = subprocess.run(  # noqa: S603
            ["docker", "container", "inspect", cid],
            capture_output=True,
            text=True,
            check=True,
        )
        docs = cast(list[dict[str, Any]], json.loads(inspected.stdout))
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        logger.warning("cannot inspect container %s: %s", cid, exc)
        return None
    return docs[0] if docs else None


def _as_str_dict(value: Any) -> dict[str, Any]:
    """Narrow untyped ``docker inspect`` JSON to a mapping (else ``{}``)."""
    if not isinstance(value, dict):
        return {}
    return cast(dict[str, Any], value)


def _container_pending(doc: dict[str, Any]) -> bool:
    status = _as_str_dict(doc.get("State")).get("Status")
    return status in _PENDING_CONTAINER_STATES


def _shared_subnet_ip(
    doc: dict[str, Any], subnets: list[tuple[int, int]]
) -> str | None:
    networks = _as_str_dict(
        _as_str_dict(doc.get("NetworkSettings")).get("Networks")
    )
    for net in networks.values():
        ip = _as_str_dict(net).get("IPAddress")
        if isinstance(ip, str) and ip and _ip_on_subnets(ip, subnets):
            return ip
    return None


def _scan_serving_ips(
    subnets: list[tuple[int, int]],
) -> tuple[str | None, bool]:
    """One poll round: (shared-network IP if found, result may still change)."""
    ids = _serve_container_ids()
    if ids is None:
        return None, False  # daemon unreachable — retrying won't help
    if not ids:
        # Every get_docker_host call site runs while the SDK's async
        # `compose up` (Popen in _HostingContainer.start) may still be
        # creating the serve container, so an empty listing is pending.
        return None, True
    pending = False
    for cid in ids:
        doc = _inspect_serving_container(cid)
        if doc is None:
            continue
        pending = pending or _container_pending(doc)
        ip = _shared_subnet_ip(doc, subnets)
        if ip is not None:
            return ip, pending
    return None, pending


def _await_serving_ip() -> str | None:
    """IP of a ``role=serve`` container reachable on a shared docker network.

    Polls briefly while the serve container is still being created or has no
    assigned IP yet — ``_SageMakerContainer.serve`` launches ``compose up``
    via ``Popen``, so this getter races container creation, and the SDK builds
    its ``/ping`` URL once from this result: falling through to the gateway
    early is unrecoverable downstream.
    """
    subnets = _connected_subnets(_route_lines())
    if not subnets:
        return None
    deadline = time.monotonic() + _SERVE_IP_WAIT_S
    while True:
        ip, pending = _scan_serving_ips(subnets)
        if ip is not None:
            return ip
        if not pending or time.monotonic() >= deadline:
            return None
        time.sleep(_SERVE_IP_POLL_S)


def _running_inside_container() -> bool:
    return _DOCKERENV_PATH.exists()


def _replace_module_attr(
    module: ModuleType, name: str, value: Callable[[], str]
) -> None:
    # setattr(ModuleType, str): the target SDK modules ship without py.typed,
    # so both ruff's B010 and pyright's private-usage checks are moot here.
    setattr(module, name, value)  # noqa: B010


def apply_docker_host_patch(force: bool = False) -> None:
    """Resolve the serving host for in-container callers.

    Order: a running ``role=serve`` container's IP when it shares a docker
    network with the caller (subnet membership — the bridge gateway is
    unreachable for same-bridge traffic on some hosts), then the default-route
    gateway, then the SDK's own ``get_docker_host``.

    Only activates when running inside a container unless ``force`` is set.
    Replaces ``get_docker_host`` in the three modules that import it by name.
    """
    global _original_get_docker_host
    if _original_get_docker_host is not None:
        return
    if not force and not _running_inside_container():
        logger.debug("not inside a container; skipping docker host patch")
        return

    import sagemaker.local.entities as sm_entities
    import sagemaker.local.local_session as sm_local_session
    import sagemaker.local.utils as sm_utils

    fallback = cast(Callable[[], str], sm_utils.get_docker_host)

    def docker_host() -> str:
        serving_ip = _await_serving_ip()
        if serving_ip is not None:
            logger.info(
                "resolved serving container ip on shared network: %s",
                serving_ip,
            )
            return serving_ip
        gateway = _gateway_from_proc()
        if gateway:
            logger.info("resolved docker host gateway: %s", gateway)
            return gateway
        return fallback()

    _original_get_docker_host = (
        sm_utils.get_docker_host,
        getattr(sm_entities, "get_docker_host"),  # noqa: B009
        getattr(sm_local_session, "get_docker_host"),  # noqa: B009
    )
    for module in (sm_utils, sm_entities, sm_local_session):
        _replace_module_attr(module, "get_docker_host", docker_host)
    logger.info("sagemaker-local docker-host patch installed")


def _list_sagemaker_local_containers(
    status: str | None, label: str
) -> list[str]:
    cmd = [
        "docker",
        "container",
        "ls",
        "-a",
        "--filter",
        f"label={label}",
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
    return _remove_containers(
        _list_sagemaker_local_containers("exited", "sagemaker.local=true")
    )


def cleanup_stale_serving_containers() -> int:
    """Remove every ``sagemaker.local.role=serve`` container regardless of state.

    Serving containers live on without a bound host process, so on process
    death (or a killed predict) they linger and grab the serving port.
    ``harden_service`` stamps the role only on services the SDK marks
    ``command: serve`` — running train/process jobs carry ``role=job`` (or
    no role) and are never reaped here.

    Returns:
        Number of containers removed.

    Example:
        >>> cleanup_stale_serving_containers()  # doctest: +SKIP
        3
    """
    return _remove_containers(
        _list_sagemaker_local_containers(None, _SERVE_ROLE_LABEL)
    )


def reset_all() -> None:
    """Undo every patch applied by this module (used by tests and teardown)."""
    global _original_compose, _original_prefix, _original_get_docker_host
    if _original_compose is not None:
        import sagemaker.local.image as sm_image

        container_cls = sm_image._SageMakerContainer
        container_cls._compose = _original_compose
        # pyright cannot type the staticmethod slot, so disassemble the raw
        # wrapper here; ruff's B010 does not apply to this roundabout restore.
        setattr(container_cls, "_get_compose_cmd_prefix", _original_prefix)  # noqa: B010
        _original_compose = None
        _original_prefix = None
    if _original_get_docker_host is not None:
        import sagemaker.local.entities as sm_entities
        import sagemaker.local.local_session as sm_local_session
        import sagemaker.local.utils as sm_utils

        utils_ref, entities_ref, session_ref = _original_get_docker_host
        for module, ref in (
            (sm_utils, utils_ref),
            (sm_entities, entities_ref),
            (sm_local_session, session_ref),
        ):
            _replace_module_attr(module, "get_docker_host", ref)
        _original_get_docker_host = None
