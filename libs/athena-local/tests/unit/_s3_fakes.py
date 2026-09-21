"""Shared named fakes for S3-backed artifact tests (AR-1).

``RecordingObjectStore`` mirrors the moto S3 surface the writer boundary
touches (put_object / list_objects_v2 with continuation-token pagination).
Unit tests construct a real ``S3Writer`` over this fake, so the boundary code
under test is exactly what ships; the integration suite exercises the same
methods against the live moto server.
"""

from __future__ import annotations

from botocore.exceptions import BotoCoreError, ClientError

S3_REGION = "us-east-1"


def s3_client_error(code: str, message: str) -> ClientError:
    """A shaped botocore ClientError, as the boto3 S3 client raises."""
    return ClientError(
        error_response={
            "Error": {"Code": code, "Message": message},
            "ResponseMetadata": {"HTTPStatusCode": 400},
        },
        operation_name="Probe",
    )


class RecordingObjectStore:
    """In-memory double for the boto3 S3 client (F.I.R.S.T., no moto).

    Mirrors the moto S3 backend shapes the writer relies on: put_object stores
    bytes by (bucket, key) and list_objects_v2 paginates with a continuation
    token. Failure modes are injected per-call so the writer's error
    absorption is testable.
    """

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.put_calls: list[tuple[str, str, bytes]] = []
        self.list_calls: list[tuple[str, str]] = []
        self.put_error: ClientError | BotoCoreError | None = None
        self.list_error: ClientError | BotoCoreError | None = None
        self.page_size: int | None = None

    def put_object(  # noqa: N803 (mirrors the botocore keyword vocabulary)
        self,
        Bucket: str,  # noqa: N803
        Key: str,  # noqa: N803
        Body: bytes,  # noqa: N803
    ) -> dict[str, object]:
        self.put_calls.append((Bucket, Key, Body))
        if self.put_error is not None:
            error = self.put_error
            self.put_error = None
            raise error
        self.objects[(Bucket, Key)] = Body
        return {"ETag": '""'}

    def list_objects_v2(  # noqa: N803
        self,
        Bucket: str,  # noqa: N803
        Prefix: str = "",  # noqa: N803
        ContinuationToken: str | None = None,  # noqa: N803
    ) -> dict[str, object]:
        self.list_calls.append((Bucket, Prefix))
        if self.list_error is not None:
            error = self.list_error
            self.list_error = None
            raise error
        keys = [
            key
            for (bucket, key) in self.objects
            if bucket == Bucket and key.startswith(Prefix)
        ]
        keys.sort()
        start = 0
        if ContinuationToken is not None:
            start = int(ContinuationToken)
        if self.page_size is not None:
            page = keys[start : start + self.page_size]
            truncated = start + self.page_size < len(keys)
            next_token = str(start + self.page_size) if truncated else None
            return {
                "Contents": [{"Key": key} for key in page],
                "IsTruncated": truncated,
                "NextContinuationToken": next_token,
            }
        return {
            "Contents": [{"Key": key} for key in keys],
            "IsTruncated": False,
            "NextContinuationToken": None,
        }

    def bytes_of(self, path: str) -> bytes | None:
        """The stored body under an ``s3://bucket/key`` path, for asserts."""
        return self.objects.get(_split(path))

    def paths(self) -> list[str]:
        return [f"s3://{bucket}/{key}" for bucket, key in sorted(self.objects)]


def _split(path: str) -> tuple[str, str]:
    rest = path.removeprefix("s3://")
    bucket, _, key = rest.partition("/")
    return bucket, key
