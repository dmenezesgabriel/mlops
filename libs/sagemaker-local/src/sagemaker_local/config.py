"""Configuration for running SageMaker local mode fully offline."""

from __future__ import annotations

import os
from dataclasses import dataclass

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
        if not self.bucket:
            raise ValueError(
                f"bucket must be a non-empty S3 bucket name, got: {self.bucket!r}"
            )
        if self.serving_port <= 0:
            raise ValueError(
                f"serving_port must be a positive TCP port, got: {self.serving_port}"
            )


def _validate_endpoint(url: str) -> None:
    if (
        not url.startswith(("http://", "https://"))
        or not url[len("http://") :]
    ):
        raise ValueError(
            f"s3_endpoint_url must be an http(s) URL with a host, got: {url!r}"
        )


def _env(name: str) -> str | None:
    return os.environ.get(_ENV_PREFIX + name)


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
    missing = [
        f"{_ENV_PREFIX}{name}"
        for name, value in (("S3_ENDPOINT_URL", endpoint), ("BUCKET", bucket))
        if not value
    ]
    if missing:
        raise ValueError(
            f"missing required environment variable(s): {', '.join(missing)}"
        )

    port_raw = _env("SERVING_PORT")
    return LocalModeConfig(
        s3_endpoint_url=endpoint,  # type: ignore[arg-type]
        bucket=bucket,  # type: ignore[arg-type]
        region=_env("REGION") or "us-east-1",
        network=_env("NETWORK"),
        serving_port=int(port_raw) if port_raw else 8080,
        container_root=_env("CONTAINER_ROOT"),
        image_tag=_env("IMAGE_TAG") or "sagemaker-local:latest",
        role_arn=_env("ROLE_ARN") or DEFAULT_ROLE_ARN,
    )
