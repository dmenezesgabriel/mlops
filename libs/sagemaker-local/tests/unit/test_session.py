"""Unit tests for sagemaker_local.session (fast, no docker, no network)."""

import pytest
from sagemaker.config.config_schema import TELEMETRY_OPT_OUT_PATH
from sagemaker.local.local_session import LocalSession
from sagemaker.utils import resolve_value_from_config
from sagemaker.workflow.pipeline_context import LocalPipelineSession
from sagemaker_local.config import LocalModeConfig
from sagemaker_local.session import (
    _ensure_bucket,
    make_local_pipeline_session,
    make_local_session,
)


class ClientError(Exception):
    """Minimal stand-in for botocore's ClientError used to shape responses."""

    def __init__(self, code: str) -> None:
        self.response = {"Error": {"Code": code}}
        super().__init__(code)


class _FakeS3Client:
    """Offline stand-in that reports the bucket as missing (404) and no-ops
    creation, so the session factories never touch the network in unit tests."""

    head_bucket_calls = 0
    create_bucket_calls = 0

    # Mirrors boto3's s3.exceptions.ClientError so _ensure_bucket is unchanged.
    class exceptions:  # noqa: N801
        ClientError = ClientError

    def __init__(self) -> None:
        self.head_bucket_calls = 0
        self.create_bucket_calls = 0

    def head_bucket(self, **kwargs):
        self.head_bucket_calls += 1
        raise ClientError("404")

    def create_bucket(self, **kwargs):
        self.create_bucket_calls += 1


@pytest.fixture(autouse=True)
def _fake_s3(monkeypatch):
    import sagemaker_local.session as session_mod

    monkeypatch.setattr(
        session_mod, "_s3_client", lambda boto_session, cfg: _FakeS3Client()
    )
    return _FakeS3Client


def make_config(tmp_path=None) -> LocalModeConfig:
    overrides = {"s3_endpoint_url": "http://moto:5000", "bucket": "artifacts"}
    if tmp_path is not None:
        overrides["container_root"] = str(tmp_path / "sm-root")
    return LocalModeConfig(**overrides)


class TestMakeLocalSession:
    def test_returns_boto_and_local_sessions_with_static_credentials(self):
        boto_session, sm_session = make_local_session(make_config())

        assert isinstance(sm_session, LocalSession)
        assert boto_session.region_name == "us-east-1"
        creds = boto_session.get_credentials()
        assert (creds.access_key, creds.secret_key) == ("test", "test")

    def test_s3_client_targets_custom_endpoint(self):
        _, sm_session = make_local_session(make_config())

        assert sm_session.s3_client.meta.endpoint_url == "http://moto:5000"

    def test_default_bucket_is_recorded_without_aws_calls(self):
        _, sm_session = make_local_session(make_config())

        # The SDK's default_bucket() always HeadBuckets the endpoint; offline
        # behavior is verified in tests/integration against live moto.
        assert sm_session._default_bucket_name_override == "artifacts"

    def test_local_mode_flags_are_set(self, tmp_path):
        cfg = make_config(tmp_path)

        _, sm_session = make_local_session(cfg)

        assert sm_session.local_mode is True
        assert sm_session.config["local"]["serving_port"] == cfg.serving_port
        assert sm_session.config["local"]["container_root"].endswith("sm-root")
        assert sm_session.config["local"]["local_code"] is True

    def test_telemetry_opt_out_resolves_true(self):
        _, sm_session = make_local_session(make_config())

        opted_out = resolve_value_from_config(
            direct_input=None,
            config_path=TELEMETRY_OPT_OUT_PATH,
            default_value=False,
            sagemaker_session=sm_session,
        )

        assert opted_out is True


class TestMakeLocalPipelineSession:
    def test_returns_local_pipeline_session_sharing_settings(self, tmp_path):
        cfg = make_config(tmp_path)

        boto_session, pipeline_session = make_local_pipeline_session(cfg)

        assert isinstance(pipeline_session, LocalPipelineSession)
        assert pipeline_session.local_mode is True
        assert (
            pipeline_session.s3_client.meta.endpoint_url == "http://moto:5000"
        )
        assert pipeline_session._default_bucket_name_override == "artifacts"
        assert pipeline_session.boto_session is boto_session

    def test_telemetry_opt_out_applies_too(self, tmp_path):
        _, pipeline_session = make_local_pipeline_session(
            make_config(tmp_path)
        )

        opted_out = resolve_value_from_config(
            direct_input=None,
            config_path=TELEMETRY_OPT_OUT_PATH,
            default_value=False,
            sagemaker_session=pipeline_session,
        )

        assert opted_out is True


class TestEnsureBucket:
    def test_missing_bucket_gets_created(self):
        fake = _FakeS3Client()

        _ensure_bucket(fake, make_config())

        assert fake.create_bucket_calls == 1

    def test_forbidden_bucket_is_left_untouched(self):
        fake = _FakeS3Client()
        fake.head_bucket = lambda **kw: (_ for _ in ()).throw(
            ClientError("403")
        )

        _ensure_bucket(fake, make_config())

        assert fake.create_bucket_calls == 0
