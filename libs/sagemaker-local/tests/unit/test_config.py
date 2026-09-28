"""Unit tests for sagemaker_local.config."""

import dataclasses

import pytest
from sagemaker_local.config import LocalModeConfig, config_from_env


class TestLocalModeConfigDefaults:
    def test_required_fields_are_s3_endpoint_and_bucket(self):
        cfg = LocalModeConfig(
            s3_endpoint_url="http://moto:5000", bucket="my-bucket"
        )

        assert cfg.s3_endpoint_url == "http://moto:5000"
        assert cfg.bucket == "my-bucket"

    @pytest.mark.parametrize(
        ("field", "expected"),
        [
            ("region", "us-east-1"),
            ("serving_port", 8080),
            ("image_tag", "sagemaker-local:latest"),
            ("aws_access_key_id", "test"),
            ("aws_secret_access_key", "test"),
            ("network", None),
            ("container_root", None),
            ("inject_compose_network", True),
            ("harden_containers", True),
        ],
    )
    def test_sensible_defaults_for_offline_usage(self, field, expected):
        cfg = LocalModeConfig(
            s3_endpoint_url="http://moto:5000", bucket="my-bucket"
        )

        assert getattr(cfg, field) == expected

    def test_role_arn_defaults_to_fake_iam_role(self):
        cfg = LocalModeConfig(
            s3_endpoint_url="http://moto:5000", bucket="my-bucket"
        )

        assert cfg.role_arn.startswith("arn:aws:iam::123456789012:role/")

    def test_config_is_immutable(self):
        cfg = LocalModeConfig(
            s3_endpoint_url="http://moto:5000", bucket="my-bucket"
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.bucket = "other"  # type: ignore[misc]


class TestLocalModeConfigValidation:
    @pytest.mark.parametrize(
        "bad_url", ["moto:5000", "ftp://moto:5000", "", "http://"]
    )
    def test_rejects_non_http_endpoint_with_offending_value(
        self, bad_url: str
    ):
        with pytest.raises(ValueError, match=bad_url):
            LocalModeConfig(s3_endpoint_url=bad_url, bucket="my-bucket")

    def test_rejects_non_positive_serving_port(self):
        with pytest.raises(ValueError, match="serving_port"):
            LocalModeConfig(
                s3_endpoint_url="http://moto:5000",
                bucket="my-bucket",
                serving_port=0,
            )

    def test_rejects_empty_bucket_name(self):
        with pytest.raises(ValueError, match="bucket"):
            LocalModeConfig(s3_endpoint_url="http://moto:5000", bucket="")


ENV_VARS = {
    "SAGEMAKER_LOCAL_S3_ENDPOINT_URL": "http://moto-infra:9000",
    "SAGEMAKER_LOCAL_BUCKET": "env-bucket",
    "SAGEMAKER_LOCAL_REGION": "eu-west-1",
    "SAGEMAKER_LOCAL_NETWORK": "proj-net",
    "SAGEMAKER_LOCAL_SERVING_PORT": "9090",
    "SAGEMAKER_LOCAL_CONTAINER_ROOT": "/workspace/.sm-tmp",
    "SAGEMAKER_LOCAL_IMAGE_TAG": "my-sm:v2",
}


class TestConfigFromEnv:
    def test_reads_all_variables_from_environment(self, monkeypatch):
        for key, value in ENV_VARS.items():
            monkeypatch.setenv(key, value)

        cfg = config_from_env()

        assert cfg.s3_endpoint_url == "http://moto-infra:9000"
        assert cfg.bucket == "env-bucket"
        assert cfg.region == "eu-west-1"
        assert cfg.network == "proj-net"
        assert cfg.serving_port == 9090
        assert cfg.container_root == "/workspace/.sm-tmp"
        assert cfg.image_tag == "my-sm:v2"

    def test_missing_required_variable_raises_with_variable_name(
        self, monkeypatch
    ):
        for key in ENV_VARS:
            monkeypatch.delenv(key, raising=False)

        with pytest.raises(
            ValueError, match="SAGEMAKER_LOCAL_S3_ENDPOINT_URL"
        ):
            config_from_env()
