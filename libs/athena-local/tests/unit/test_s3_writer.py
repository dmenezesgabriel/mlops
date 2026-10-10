"""S3 write boundary (s3_writer.py) per architecture §8.5.

``S3Writer`` is the project-owned interface over the boto3 S3 client the
artifact writers use to place ``{QueryID}.csv`` / ``.txt`` / manifest files on
moto S3 (ADR-0006, ADR-0007). It absorbs boto3 error taxonomy the same way
``GlueProxy`` does for Glue, so ``artifacts.py`` only sees project-owned
exceptions. Tests drive a real ``S3Writer`` over the named
``RecordingObjectStore`` fake — the boundary code under test is exactly what
ships (F.I.R.S.T., no moto server needed).
"""

from __future__ import annotations

import pytest
from athena_local.s3_writer import S3Writer, S3WriterError
from botocore.exceptions import EndpointConnectionError
from tests.unit._s3_fakes import RecordingObjectStore, s3_client_error

PREFIX = "s3://results-bucket/analytics/"


class TokenlessTruncatingStore(RecordingObjectStore):
    """Answers IsTruncated without a NextContinuationToken — a broken page."""

    def list_objects_v2(  # noqa: N803 (mirrors the botocore keyword vocabulary)
        self,
        Bucket: str,  # noqa: N803
        Prefix: str = "",  # noqa: N803
        ContinuationToken: str | None = None,  # noqa: N803
    ) -> dict[str, object]:
        self.list_calls.append((Bucket, Prefix))
        return {
            "Contents": [{"Key": f"{Prefix}a.csv"}],
            "IsTruncated": True,
        }


def test_put_object_stores_bytes_at_the_uri_path() -> None:
    store = RecordingObjectStore()
    writer = S3Writer(store)

    writer.put_object(f"{PREFIX}abc.csv", b"a,b\n")

    assert store.objects == {("results-bucket", "analytics/abc.csv"): b"a,b\n"}
    assert store.put_calls == [
        ("results-bucket", "analytics/abc.csv", b"a,b\n")
    ]


def test_list_object_paths_returns_full_s3_uris_under_the_prefix() -> None:
    store = RecordingObjectStore()
    store.objects = {
        ("bucket", "prefix/a.parquet"): b"",
        ("bucket", "prefix/b.parquet"): b"",
        ("bucket", "other/c.parquet"): b"",
    }
    writer = S3Writer(store)

    paths = writer.list_object_paths("s3://bucket/prefix/")

    assert paths == [
        "s3://bucket/prefix/a.parquet",
        "s3://bucket/prefix/b.parquet",
    ]


def test_list_object_paths_follows_continuation_tokens() -> None:
    store = RecordingObjectStore()
    store.objects = {
        ("bucket", f"prefix/f{i:02d}.parquet"): b"" for i in range(5)
    }
    store.page_size = 2
    writer = S3Writer(store)

    paths = writer.list_object_paths("s3://bucket/prefix/")

    # Two truncated pages (2 + 2) plus a final full page: three calls total.
    assert len(store.list_calls) == 3
    assert [path.rsplit("/", 1)[-1] for path in paths] == [
        f"f{i:02d}.parquet" for i in range(5)
    ]


def test_list_object_paths_truncated_without_token_raises() -> None:
    """A truncated page with no continuation token is a broken contract —
    following it would loop forever, so the listing fails instead."""
    writer = S3Writer(TokenlessTruncatingStore())

    with pytest.raises(S3WriterError, match="without a NextContinuationToken"):
        writer.list_object_paths("s3://bucket/prefix/")


def test_put_object_absorbs_client_error_as_s3_writer_error() -> None:
    store = RecordingObjectStore()
    store.put_error = s3_client_error("NoSuchBucket", "bucket missing")
    writer = S3Writer(store)

    with pytest.raises(S3WriterError) as exc_info:
        writer.put_object(f"{PREFIX}abc.csv", b"")

    assert "NoSuchBucket" in str(exc_info.value)


def test_put_object_absorbs_transport_error_as_s3_writer_error() -> None:
    store = RecordingObjectStore()
    store.put_error = EndpointConnectionError(endpoint_url="http://moto:5000")
    writer = S3Writer(store)

    with pytest.raises(S3WriterError) as exc_info:
        writer.put_object(f"{PREFIX}abc.csv", b"")

    assert "transport" in str(exc_info.value).lower()


def test_list_object_paths_absorbs_transport_error_as_s3_writer_error() -> (
    None
):
    store = RecordingObjectStore()
    store.list_error = EndpointConnectionError(endpoint_url="http://moto:5000")
    writer = S3Writer(store)

    with pytest.raises(S3WriterError) as exc_info:
        writer.list_object_paths(f"{PREFIX}")

    assert "transport" in str(exc_info.value).lower()


@pytest.mark.parametrize(
    "path", ["ftp://host/x", "relative", "bucket/key", "S3://host/x"]
)
def test_put_object_rejects_non_s3_scheme(path: str) -> None:
    """Only ``s3://`` URIs reach the client: a foreign scheme or a bare path
    must fail here, not inside the boto3 call as a mangled bucket name."""
    store = RecordingObjectStore()
    writer = S3Writer(store)

    with pytest.raises(S3WriterError, match="s3://"):
        writer.put_object(path, b"")

    assert store.put_calls == []


@pytest.mark.parametrize("path", ["ftp://host/x", "relative", "bucket/key"])
def test_list_object_paths_rejects_non_s3_scheme(path: str) -> None:
    store = RecordingObjectStore()
    writer = S3Writer(store)

    with pytest.raises(S3WriterError, match="s3://"):
        writer.list_object_paths(path)

    assert store.list_calls == []


def test_list_object_paths_rejects_s3_uri_without_bucket() -> None:
    writer = S3Writer(RecordingObjectStore())

    with pytest.raises(S3WriterError, match="no bucket"):
        writer.list_object_paths("s3://")
