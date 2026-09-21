"""S3 write boundary over moto S3 (architecture §8.5, ADR-0006/0007).

``S3Writer`` is the project-owned interface the artifact writers use to place
``{QueryID}.csv`` / ``.txt`` / manifest + metadata files on moto S3. It is the
only module touching the boto3 S3 client (ADR-0008: no moto internals), and it
absorbs boto3 error taxonomy the same way ``GlueProxy`` does for Glue, so
``artifacts.py`` only raises project-owned exceptions. Bucket/key extraction
from ``s3://`` URIs lives here so ``artifacts.py`` composes paths only.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

from botocore.exceptions import BotoCoreError, ClientError
from botocore.session import Session

S3_REGION = "us-east-1"
S3_ACCESS_KEY_ID = "test"
S3_SECRET_ACCESS_KEY = "test"


class ObjectStoreClient(Protocol):
    """The two S3 operations this boundary uses (thin interface).

    Parameter names mirror the botocore S3 client keyword arguments, hence the
    PascalCase (ruff N803 ignores below).
    """

    def put_object(  # noqa: N803
        self,
        Bucket: str,  # noqa: N803
        Key: str,  # noqa: N803
        Body: bytes,  # noqa: N803
    ) -> dict[str, object]: ...

    def list_objects_v2(  # noqa: N803
        self,
        Bucket: str,  # noqa: N803
        Prefix: str = "",  # noqa: N803
        ContinuationToken: str | None = None,  # noqa: N803
    ) -> dict[str, object]: ...


class S3WriterError(Exception):
    """moto S3 was unreachable or answered outside the expected shape."""


class S3Writer:
    """Writes object bodies and lists object paths under ``s3://`` prefixes."""

    def __init__(self, client: ObjectStoreClient) -> None:
        self._client = client

    @classmethod
    def for_endpoint(cls, endpoint_url: str) -> S3Writer:
        """Build a writer against ``endpoint_url`` with the moto static keys."""
        session = Session()
        client = session.create_client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=S3_REGION,
            aws_access_key_id=S3_ACCESS_KEY_ID,
            aws_secret_access_key=S3_SECRET_ACCESS_KEY,
        )
        return cls(cast(ObjectStoreClient, client))

    def put_object(self, path: str, body: bytes) -> None:
        """Store ``body`` at the ``s3://bucket/key`` path, replacing any object."""
        bucket, key = _split_s3_path(path)
        self._run(
            "PutObject",
            lambda: self._client.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,  # noqa: N803
            ),
        )

    def list_object_paths(self, prefix: str) -> list[str]:
        """Every object's full ``s3://`` URI under ``prefix`` (pagination-safe).

        Common-prefix entries (keys ending in ``/``) are skipped: the
        artifact manifest lists files only, exactly as wrangler reads it
        (awswrangler/athena/_read.py:62-81).
        """
        bucket, key = _split_s3_path(prefix)
        paths: list[str] = []
        continuation_token: str | None = None
        while True:
            response = self._list_page(bucket, key, continuation_token)
            for item in _objects(response, "Contents"):
                object_key = _string(item, "Key")
                if object_key is not None and not object_key.endswith("/"):
                    paths.append(f"s3://{bucket}/{object_key}")
            if response.get("IsTruncated") is not True:
                return paths
            continuation_token = _string(response, "NextContinuationToken")
            if continuation_token is None:
                # Truncation without a token would loop forever; the listing
                # contract is broken, so fail rather than spin.
                raise S3WriterError(
                    f"S3 ListObjectsV2 truncated {prefix} without a "
                    "NextContinuationToken"
                )

    def _list_page(
        self,
        bucket: str,
        key: str,
        continuation_token: str | None,
    ) -> dict[str, object]:
        """One ListObjectsV2 page; token omitted when absent (boto3 rejects None)."""
        if continuation_token is None:
            return self._run(
                "ListObjectsV2",
                lambda: self._client.list_objects_v2(
                    Bucket=bucket,
                    Prefix=key,  # noqa: N803
                ),
            )
        return self._run(
            "ListObjectsV2",
            lambda: self._client.list_objects_v2(
                Bucket=bucket,  # noqa: N803
                Prefix=key,  # noqa: N803
                ContinuationToken=continuation_token,  # noqa: N803
            ),
        )

    def _run(
        self,
        operation: str,
        invoke: Callable[[], dict[str, object]],
    ) -> dict[str, object]:
        try:
            return invoke()
        except ClientError as error:
            raise S3WriterError(
                f"S3 {operation} failed with error code "
                f"{_error_code(error)}: {error}"
            ) from error
        except BotoCoreError as error:
            raise S3WriterError(
                f"S3 transport failure during {operation}: {error}"
            ) from error


def _split_s3_path(path: str) -> tuple[str, str]:
    rest = path.removeprefix("s3://")
    bucket, _, key = rest.partition("/")
    if not bucket:
        raise S3WriterError(f"S3 URI {path!r} has no bucket")
    return bucket, key


def _error_code(error: ClientError) -> str:
    raw = error.response.get("Error")
    if not isinstance(raw, dict):
        return ""
    code = raw.get("Code")
    return code if isinstance(code, str) else ""


def _objects(response: dict[str, object], key: str) -> list[dict[str, object]]:
    raw = response.get(key)
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _string(record: dict[str, object], key: str) -> str | None:
    raw = record.get(key)
    return raw if isinstance(raw, str) else None
