"""Docker-backed integration tests for sagemaker_local.images."""

import subprocess

import pytest
from sagemaker_local.images import build_image

IMAGE_TAG = "sagemaker-local:latest"


@pytest.mark.integration
class TestDockerImage:
    def test_builds_image_idempotently(self):
        assert build_image(IMAGE_TAG) == IMAGE_TAG

    def test_image_is_usable_by_docker(self):
        result = subprocess.run(  # noqa: S603
            ["docker", "image", "inspect", IMAGE_TAG],
            capture_output=True,
            text=True,
            check=True,
        )
        assert IMAGE_TAG in result.stdout
