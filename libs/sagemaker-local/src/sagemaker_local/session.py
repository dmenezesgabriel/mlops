# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Factories for offline SageMaker sessions backed by a moto endpoint."""

from __future__ import annotations

from typing import Any, Protocol, cast

import boto3
from botocore.exceptions import ClientError
from sagemaker.local.local_session import LocalSession
from sagemaker.workflow.pipeline_context import LocalPipelineSession

from sagemaker_local.config import LocalModeConfig
from sagemaker_local.patches import (
    apply_compose_patches,
    apply_docker_host_patch,
)

# Disables the SDK's telemetry GET against real AWS endpoints.
_TELEMETRY_OPT_OUT_CONFIG = {
    "SchemaVersion": "1.0",
    "SageMaker": {"PythonSDK": {"Modules": {"TelemetryOptOut": True}}},
}


class _S3Client(Protocol):
    """The S3 operations ``_ensure_bucket`` uses (thin interface).

    ``Session.client()`` returns the service-agnostic ``BaseClient``, whose
    per-service operations are attached dynamically and invisible to strict
    pyright — this is the designated boundary, same pattern as
    ``athena_local.s3_writer.ObjectStoreClient``. Parameter names mirror the
    botocore S3 client keyword arguments, hence the PascalCase.
    """

    def head_bucket(self, Bucket: str) -> object: ...  # noqa: N803

    def create_bucket(  # noqa: N803
        self,
        Bucket: str,  # noqa: N803
        CreateBucketConfiguration: dict[str, str] | None = None,  # noqa: N803
    ) -> object: ...


def make_local_session(
    cfg: LocalModeConfig,
) -> tuple[boto3.Session, LocalSession]:
    """Create ``(boto_session, sagemaker_session)`` wired to ``cfg``.

    Installs the compose and docker-host patches on first use. The returned
    session never contacts AWS: S3/STS go to ``cfg.s3_endpoint_url``, the
    control plane is intercepted by local mode itself.

    Example:
        >>> cfg = LocalModeConfig(s3_endpoint_url="http://moto:5000",
        ...                       bucket="artifacts")
        >>> _, session = make_local_session(cfg)  # doctest: +SKIP
    """
    apply_compose_patches(cfg)
    apply_docker_host_patch(force=False)

    boto_session = _boto_session(cfg)
    _ensure_bucket(_s3_client(boto_session, cfg), cfg)
    sm_session = LocalSession(
        boto_session=boto_session,
        default_bucket=cfg.bucket,
        s3_endpoint_url=cfg.s3_endpoint_url,
        sagemaker_config=_TELEMETRY_OPT_OUT_CONFIG,
    )
    _apply_local_mode_config(sm_session, cfg)
    return boto_session, sm_session


def make_local_pipeline_session(
    cfg: LocalModeConfig,
) -> tuple[boto3.Session, LocalPipelineSession]:
    """Like :func:`make_local_session` but returns a ``LocalPipelineSession``
    so ``Pipeline.start()`` executes every step locally.

    Example:
        >>> cfg = LocalModeConfig(s3_endpoint_url="http://moto:5000",
        ...                       bucket="artifacts")
        >>> _, pipeline_session = make_local_pipeline_session(cfg)  # doctest: +SKIP
    """
    apply_compose_patches(cfg)
    apply_docker_host_patch(force=False)

    boto_session = _boto_session(cfg)
    _ensure_bucket(_s3_client(boto_session, cfg), cfg)
    # LocalPipelineSession.__init__ is a pure forwarder that drops the
    # sagemaker_config parameter (sagemaker 2.257.1 pipeline_context.py:251),
    # so the constructor would run load_sagemaker_config on ambient
    # ~/.sagemaker / SAGEMAKER_*_CONFIG_OVERRIDE files. Calling the LocalSession
    # constructor on the instance forwards the opt-out dict through the MRO
    # (PipelineSession.__init__ -> Session.__init__ -> LocalSession._initialize),
    # where it is schema-validated and assigned instead.
    pipeline_session = LocalPipelineSession.__new__(LocalPipelineSession)
    LocalSession.__init__(
        pipeline_session,
        boto_session=boto_session,
        default_bucket=cfg.bucket,
        s3_endpoint_url=cfg.s3_endpoint_url,
        sagemaker_config=_TELEMETRY_OPT_OUT_CONFIG,
    )
    _apply_local_mode_config(pipeline_session, cfg)
    return boto_session, pipeline_session


def _boto_session(cfg: LocalModeConfig) -> boto3.Session:
    return boto3.Session(
        aws_access_key_id=cfg.aws_access_key_id,
        aws_secret_access_key=cfg.aws_secret_access_key,
        region_name=cfg.region,
    )


def _s3_client(boto_session: boto3.Session, cfg: LocalModeConfig) -> _S3Client:
    return cast(
        _S3Client,
        boto_session.client("s3", endpoint_url=cfg.s3_endpoint_url),
    )


def _ensure_bucket(s3_client: _S3Client, cfg: LocalModeConfig) -> None:
    """Create ``cfg.bucket`` on the S3 endpoint if it does not yet exist.

    Local mode never provisions buckets, so the SDK's downstream upload of
    trained artifacts would fail with ``NoSuchBucket`` otherwise. Idempotent:
    a bucket already owned by moto's test account is left untouched.

    Example:
        >>> _ensure_bucket(_s3_client(boto_session, cfg), cfg)  # doctest: +SKIP
    """
    try:
        s3_client.head_bucket(Bucket=cfg.bucket)
        return
    except ClientError as exc:
        # response is a total=False TypedDict: Error/Code may be absent on
        # malformed replies, so read with .get rather than [] (strict pyright
        # enforces this once botocore-stubs resolves the type — a4d3d7a).
        code = exc.response.get("Error", {}).get("Code")
        if code == "403":
            return
        if code != "404":
            raise
    if cfg.region == "us-east-1":
        # AWS rejects LocationConstraint="us-east-1"; omit the payload.
        s3_client.create_bucket(Bucket=cfg.bucket)
        return
    s3_client.create_bucket(
        Bucket=cfg.bucket,
        CreateBucketConfiguration={"LocationConstraint": cfg.region},
    )


def _apply_local_mode_config(
    session: LocalSession, cfg: LocalModeConfig
) -> None:
    """Set the post-init local mode options (validated by the SDK setter)."""
    local_cfg: dict[str, Any] = {
        "local": {
            "serving_port": cfg.serving_port,
            "local_code": True,
        }
    }
    if cfg.container_root:
        local_cfg["local"]["container_root"] = cfg.container_root
    session.config = local_cfg
