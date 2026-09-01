"""Moto-backed integration tests for sagemaker_local.session."""

import pytest
from sagemaker_local.config import LocalModeConfig
from sagemaker_local.session import make_local_session


@pytest.mark.integration
class TestSessionAgainstLiveMoto:
    """Round-trips real S3/STS traffic through the session (no docker needed)."""

    def test_upload_and_download_data_via_session(self, live_moto_server):
        cfg = LocalModeConfig(
            s3_endpoint_url=live_moto_server.url,
            bucket="roundtrip",
            network=None,
        )
        boto_session, sm_session = make_local_session(cfg)
        boto_session.client(
            "s3", endpoint_url=live_moto_server.url
        ).create_bucket(Bucket="roundtrip")

        source = live_moto_server.tmpdir / "payload.csv"
        source.write_text("a,b\n1,2\n", encoding="utf-8")
        sm_session.upload_data(str(source), "roundtrip", "jobs/one")

        target_dir = live_moto_server.tmpdir / "out"
        sm_session.download_data(
            str(target_dir), "roundtrip", "jobs/one/payload.csv"
        )

        assert (target_dir / "payload.csv").read_text(
            encoding="utf-8"
        ) == "a,b\n1,2\n"

    def test_default_bucket_creates_and_returns_configured_bucket(
        self, live_moto_server
    ):
        cfg = LocalModeConfig(
            s3_endpoint_url=live_moto_server.url,
            bucket="defaulted",
            network=None,
        )
        _, sm_session = make_local_session(cfg)

        assert sm_session.default_bucket() == "defaulted"

    def test_sts_caller_identity_routes_to_moto(self, live_moto_server):
        boto_session, _ = make_local_session(
            LocalModeConfig(s3_endpoint_url=live_moto_server.url, bucket="x")
        )
        sts = boto_session.client("sts", endpoint_url=live_moto_server.url)

        assert sts.get_caller_identity()["Account"] == "123456789012"
