"""Unit tests for the awswrangler consumer-harness teardown.

The teardown drops a throwaway bucket on the shared compose moto. These tests
drive it against the named ``RecordingObjectStore`` fake so the >1000-key
``ListObjectsV2`` page cap and the ``BucketNotEmpty`` leak signal are pinned
without a live stack (compose-gated integration runs are invisible to CI).
"""

from __future__ import annotations

import botocore.exceptions
import pytest
from tests.integration._consumer_harness import (
    _delete_objects_and_bucket,
    _discard_bucket,
)
from tests.unit._s3_fakes import RecordingObjectStore, s3_client_error

BUCKET = "athena-probe"


def _seed(store: RecordingObjectStore, count: int) -> None:
    for index in range(count):
        store.objects[(BUCKET, f"k{index:04d}")] = b"payload"


def test_teardown_pages_past_the_listing_cap() -> None:
    store = RecordingObjectStore()
    store.page_size = 1000  # moto caps a ListObjectsV2 response at 1000 keys
    _seed(store, 1001)

    _delete_objects_and_bucket(store, BUCKET)

    assert store.objects == {}
    assert len(store.list_calls) == 2
    assert store.delete_bucket_calls == [BUCKET]


def test_teardown_surfaces_bucket_not_empty() -> None:
    store = RecordingObjectStore()
    store.delete_bucket_error = s3_client_error(
        "BucketNotEmpty", "The bucket you tried to delete is not empty"
    )

    with pytest.raises(botocore.exceptions.ClientError) as raised:
        _discard_bucket(store, BUCKET)

    assert raised.value.response["Error"]["Code"] == "BucketNotEmpty"


@pytest.mark.parametrize(
    "error",
    [
        s3_client_error("NoSuchBucket", "bucket already gone"),
        botocore.exceptions.EndpointConnectionError(
            endpoint_url="http://moto"
        ),
    ],
    ids=["client-not-found", "transport"],
)
def test_teardown_swallows_benign_failures(error: Exception) -> None:
    store = RecordingObjectStore()
    store.delete_bucket_error = error

    _discard_bucket(store, BUCKET)
