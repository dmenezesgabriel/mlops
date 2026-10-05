"""Configuration for running SageMaker local mode fully offline."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

# The account ID moto returns for the static "test" credentials, and a role ARN
# under it. Local mode never contacts IAM; SageMaker only stores the ARN.
MOTO_ACCOUNT_ID = "123456789012"
DEFAULT_ROLE_ARN = (
    f"arn:aws:iam::{MOTO_ACCOUNT_ID}:role/SageMakerLocalExecutionRole"
)

_ENV_PREFIX = "SAGEMAKER_LOCAL_"


@dataclass(frozen=True)
class LocalModeConfig:
    """Settings controlling offline SageMaker local mode.

    Attributes:
        s3_endpoint_url: HTTP(S) endpoint serving S3/STS (e.g. a moto server
            reachable as ``http://moto:5000`` from job containers).
        bucket: Default S3 bucket used for artifacts; must already exist or be
            creatable on the endpoint.
        region: AWS region name stamped into sessions.
        network: External docker network injected into SageMaker-generated
            compose files so job containers resolve ``s3_endpoint_url`` hosts.
            ``None`` disables network injection.
        serving_port: Host port used by local serving containers.
        container_root: Directory (identical inside caller container and on the
            docker host) where compose projects are written. ``None`` uses /tmp,
            which requires mounting host /tmp into the caller container.
        image_tag: Tag of the locally built training/serving image.
        role_arn: Dummy execution role recorded in jobs; never validated.
        aws_access_key_id/aws_secret_access_key: Static credentials accepted by
            moto.
        inject_compose_network: Master switch for the compose network patch.
        harden_containers: Add ``init: true`` and json-file log rotation to
            generated services.

    Example:
        >>> cfg = LocalModeConfig(
        ...     s3_endpoint_url="http://moto:5000", bucket="artifacts"
        ... )
    """

    s3_endpoint_url: str
    bucket: str
    region: str = "us-east-1"
    network: str | None = None
    serving_port: int = 8080
    container_root: str | None = None
    image_tag: str = "sagemaker-local:latest"
    role_arn: str = DEFAULT_ROLE_ARN
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    inject_compose_network: bool = True
    harden_containers: bool = True

    def __post_init__(self) -> None:
        _validate_endpoint(self.s3_endpoint_url)
        _validate_bucket_name(self.bucket)
        if not 1 <= self.serving_port <= 65535:
            raise ValueError(
                f"serving_port must be a TCP port in 1..65535, "
                f"got: {self.serving_port}"
            )
        if self.network == "":
            raise ValueError(
                "network must be a docker network name or None, got: ''"
            )


# S3's documented character set and 3-63 length, checked in one match; the
# finer rules (no adjacent dots, no IP format) stay S3's job — moto enforces
# the same contract and errors surface with the bucket name.
_S3_BUCKET_NAME = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]")


def _validate_endpoint(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(
            f"s3_endpoint_url must be an http(s) URL with a host, got: {url!r}"
        )


def _validate_bucket_name(bucket: str) -> None:
    if _S3_BUCKET_NAME.fullmatch(bucket) is None:
        raise ValueError(
            "bucket must be a valid S3 bucket name (3-63 chars of a-z, "
            f"0-9, '.', '-', starting and ending alphanumeric), got: {bucket!r}"
        )


def _env(name: str) -> str | None:
    return os.environ.get(_ENV_PREFIX + name)


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(
            f"{_ENV_PREFIX}{name} must be an integer, got: {raw!r}"
        ) from exc


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    lowered = raw.casefold()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise ValueError(
        f"{_ENV_PREFIX}{name} must be 'true' or 'false', got: {raw!r}"
    )


def config_from_env() -> LocalModeConfig:
    """Build a config from ``SAGEMAKER_LOCAL_*`` environment variables.

    Recognized variables mirror the dataclass fields upper-cased, e.g.
    ``SAGEMAKER_LOCAL_S3_ENDPOINT_URL``, ``SAGEMAKER_LOCAL_BUCKET``,
    ``SAGEMAKER_LOCAL_SERVING_PORT``. Unset optionals fall back to defaults.

    Raises:
        ValueError: when a required variable is missing or a value is invalid.

    Example:
        >>> cfg = config_from_env()  # doctest: +SKIP
    """
    endpoint = _env("S3_ENDPOINT_URL")
    bucket = _env("BUCKET")
    if not endpoint or not bucket:
        missing = [
            f"{_ENV_PREFIX}{name}"
            for name, value in (
                ("S3_ENDPOINT_URL", endpoint),
                ("BUCKET", bucket),
            )
            if not value
        ]
        raise ValueError(
            f"missing required environment variable(s): {', '.join(missing)}"
        )

    return LocalModeConfig(
        s3_endpoint_url=endpoint,
        bucket=bucket,
        region=_env("REGION") or "us-east-1",
        network=_env("NETWORK"),
        serving_port=_env_int("SERVING_PORT", 8080),
        container_root=_env("CONTAINER_ROOT"),
        image_tag=_env("IMAGE_TAG") or "sagemaker-local:latest",
        role_arn=_env("ROLE_ARN") or DEFAULT_ROLE_ARN,
        aws_access_key_id=_env("AWS_ACCESS_KEY_ID") or "test",
        aws_secret_access_key=_env("AWS_SECRET_ACCESS_KEY") or "test",
        inject_compose_network=_env_bool("INJECT_COMPOSE_NETWORK", True),
        harden_containers=_env_bool("HARDEN_CONTAINERS", True),
    )
