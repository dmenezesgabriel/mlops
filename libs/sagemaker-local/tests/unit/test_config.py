"""Unit tests for sagemaker_local.config."""

import dataclasses

import pytest
from sagemaker_local.config import (
    DEFAULT_ROLE_ARN,
    LocalModeConfig,
    config_from_env,
)


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
        "bad_url", ["moto:5000", "ftp://moto:5000", "http://", "https://"]
    )
    def test_rejects_non_http_endpoint_with_offending_value(
        self, bad_url: str
    ):
        with pytest.raises(ValueError, match=bad_url):
            LocalModeConfig(s3_endpoint_url=bad_url, bucket="my-bucket")

    def test_rejects_empty_endpoint_naming_the_field(self):
        # "" can never appear in the message, so this arm needs a real
        # pattern — match="" would vacuously pass any exception.
        with pytest.raises(ValueError, match="s3_endpoint_url"):
            LocalModeConfig(s3_endpoint_url="", bucket="my-bucket")

    def test_accepts_https_endpoint(self):
        cfg = LocalModeConfig(
            s3_endpoint_url="https://moto:5000", bucket="my-bucket"
        )

        assert cfg.s3_endpoint_url == "https://moto:5000"

    def test_rejects_non_positive_serving_port(self):
        with pytest.raises(ValueError, match="serving_port"):
            LocalModeConfig(
                s3_endpoint_url="http://moto:5000",
                bucket="my-bucket",
                serving_port=0,
            )

    @pytest.mark.parametrize("bad_port", [65536, 70000, 99999])
    def test_rejects_out_of_range_serving_port(self, bad_port: int):
        with pytest.raises(ValueError, match="serving_port"):
            LocalModeConfig(
                s3_endpoint_url="http://moto:5000",
                bucket="my-bucket",
                serving_port=bad_port,
            )

    def test_accepts_max_tcp_port(self):
        cfg = LocalModeConfig(
            s3_endpoint_url="http://moto:5000",
            bucket="my-bucket",
            serving_port=65535,
        )

        assert cfg.serving_port == 65535

    def test_rejects_empty_bucket_name(self):
        with pytest.raises(ValueError, match="bucket"):
            LocalModeConfig(s3_endpoint_url="http://moto:5000", bucket="")

    @pytest.mark.parametrize(
        "bad_bucket", ["x", "ab", "A-bucket", "a_b", "-abc", "abc-"]
    )
    def test_rejects_invalid_s3_bucket_name(self, bad_bucket: str):
        with pytest.raises(ValueError, match="bucket"):
            LocalModeConfig(
                s3_endpoint_url="http://moto:5000", bucket=bad_bucket
            )

    def test_rejects_empty_network_name(self):
        with pytest.raises(ValueError, match="network"):
            LocalModeConfig(
                s3_endpoint_url="http://moto:5000",
                bucket="my-bucket",
                network="",
            )


ENV_VARS = {
    "SAGEMAKER_LOCAL_S3_ENDPOINT_URL": "http://moto-infra:9000",
    "SAGEMAKER_LOCAL_BUCKET": "env-bucket",
    "SAGEMAKER_LOCAL_REGION": "eu-west-1",
    "SAGEMAKER_LOCAL_NETWORK": "proj-net",
    "SAGEMAKER_LOCAL_SERVING_PORT": "9090",
    "SAGEMAKER_LOCAL_CONTAINER_ROOT": "/workspace/.sm-tmp",
    "SAGEMAKER_LOCAL_IMAGE_TAG": "my-sm:v2",
    "SAGEMAKER_LOCAL_AWS_ACCESS_KEY_ID": "envkey",
    "SAGEMAKER_LOCAL_AWS_SECRET_ACCESS_KEY": "envsecret",
    "SAGEMAKER_LOCAL_INJECT_COMPOSE_NETWORK": "false",
    "SAGEMAKER_LOCAL_HARDEN_CONTAINERS": "false",
}

_REQUIRED_ENV = {
    "SAGEMAKER_LOCAL_S3_ENDPOINT_URL": "http://moto:5000",
    "SAGEMAKER_LOCAL_BUCKET": "env-bucket",
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

    def test_reads_credential_and_switch_variables(self, monkeypatch):
        for key, value in ENV_VARS.items():
            monkeypatch.setenv(key, value)

        cfg = config_from_env()

        assert cfg.aws_access_key_id == "envkey"
        assert cfg.aws_secret_access_key == "envsecret"
        assert cfg.inject_compose_network is False
        assert cfg.harden_containers is False

    def test_unset_optional_variables_use_defaults(self, monkeypatch):
        for key in ENV_VARS:
            monkeypatch.delenv(key, raising=False)
        for key, value in _REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)

        cfg = config_from_env()

        assert cfg == LocalModeConfig(
            s3_endpoint_url="http://moto:5000",
            bucket="env-bucket",
            role_arn=DEFAULT_ROLE_ARN,
        )

    @pytest.mark.parametrize(
        "bool_var",
        [
            "SAGEMAKER_LOCAL_INJECT_COMPOSE_NETWORK",
            "SAGEMAKER_LOCAL_HARDEN_CONTAINERS",
        ],
    )
    def test_explicit_true_boolean_value(self, monkeypatch, bool_var: str):
        # ENV_VARS only ever sets "false"; the "true" arm needs its own case.
        for key in ENV_VARS:
            monkeypatch.delenv(key, raising=False)
        for key, value in _REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv(bool_var, "true")

        cfg = config_from_env()

        field = bool_var.removeprefix("SAGEMAKER_LOCAL_").lower()
        assert getattr(cfg, field) is True

    def test_missing_required_variable_raises_with_variable_name(
        self, monkeypatch
    ):
        for key in ENV_VARS:
            monkeypatch.delenv(key, raising=False)

        with pytest.raises(
            ValueError, match="SAGEMAKER_LOCAL_S3_ENDPOINT_URL"
        ):
            config_from_env()

    def test_non_integer_serving_port_names_the_variable(self, monkeypatch):
        for key in ENV_VARS:
            monkeypatch.delenv(key, raising=False)
        for key, value in _REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("SAGEMAKER_LOCAL_SERVING_PORT", "abc")

        with pytest.raises(ValueError, match="SAGEMAKER_LOCAL_SERVING_PORT"):
            config_from_env()

    @pytest.mark.parametrize(
        "bad_bool_var",
        [
            "SAGEMAKER_LOCAL_INJECT_COMPOSE_NETWORK",
            "SAGEMAKER_LOCAL_HARDEN_CONTAINERS",
        ],
    )
    def test_non_boolean_value_names_the_variable(
        self, monkeypatch, bad_bool_var: str
    ):
        for key in ENV_VARS:
            monkeypatch.delenv(key, raising=False)
        for key, value in _REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv(bad_bool_var, "maybe")

        with pytest.raises(ValueError, match=bad_bool_var):
            config_from_env()
