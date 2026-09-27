"""Schema parsing/two-way tests for the workgroup wire shapes.

The dataclasses mirror the member names and optionality of the canonical
service-2.json WorkGroup* shapes. Every assertion here is a proxy for a model
member: field presence, type, and omission-when-absent. Deep members no
consumer reads (EngineConfiguration, MonitoringConfiguration,
IdentityCenterConfiguration, QueryResultsS3AccessGrantsConfiguration) are
preserved verbatim as validated JSON objects instead of hand-verified
nested dataclasses (evidence: awswrangler ``athena/_utils.py:158-187`` reads
only EnforceWorkGroupConfiguration / ResultConfiguration /
ManagedQueryResultsConfiguration).
"""

from __future__ import annotations

import pytest
from athena_local.common_schemas import (
    ResultReuseByAgeConfiguration,
    parse_result_reuse_configuration,
    result_reuse_configuration_payload,
)
from athena_local.errors import InvalidRequestException
from athena_local.schemas import (
    DEFAULT_ENGINE_VERSION,
    EncryptionConfiguration,
    ResultConfiguration,
    ResultConfigurationUpdates,
    Tag,
    WorkGroupConfiguration,
    WorkGroupConfigurationUpdates,
    parse_engine_version,
    parse_result_configuration,
    parse_tags,
    to_payload,
)


def test_parse_configuration_reads_typed_members() -> None:
    configuration = WorkGroupConfiguration.from_dict(
        {
            "ResultConfiguration": {
                "OutputLocation": "s3://results-bucket/analytics/",
                "EncryptionConfiguration": {
                    "EncryptionOption": "SSE_KMS",
                    "KmsKey": "arn:aws:kms:us-east-1:123:key/abc",
                },
            },
            "EnforceWorkGroupConfiguration": True,
            "PublishCloudWatchMetricsEnabled": True,
            "BytesScannedCutoffPerQuery": 10000000,
            "EngineVersion": {
                "SelectedEngineVersion": "AUTO",
                "EffectiveEngineVersion": "Athena engine version 3",
            },
        }
    )

    assert configuration.result_configuration == ResultConfiguration(
        output_location="s3://results-bucket/analytics/",
        encryption_configuration=EncryptionConfiguration(
            encryption_option="SSE_KMS",
            kms_key="arn:aws:kms:us-east-1:123:key/abc",
        ),
    )
    assert configuration.enforce_work_group_configuration is True
    assert configuration.publish_cloudwatch_metrics_enabled is True
    assert configuration.bytes_scanned_cutoff_per_query == 10000000
    assert configuration.engine_version == DEFAULT_ENGINE_VERSION


def test_parse_configuration_preserves_unmodeled_deep_members() -> None:
    configuration = WorkGroupConfiguration.from_dict(
        {"ExecutionRole": "arn:aws:iam::123:role/execution"}
    )

    assert configuration.execution_role == "arn:aws:iam::123:role/execution"


def test_parse_configuration_accepts_null_configuration() -> None:
    assert WorkGroupConfiguration.from_dict(None) == WorkGroupConfiguration()


def test_parse_configuration_rejects_wrong_member_types() -> None:
    with pytest.raises(
        InvalidRequestException, match="EnforceWorkGroupConfiguration"
    ):
        WorkGroupConfiguration.from_dict(
            {"EnforceWorkGroupConfiguration": "yes"}
        )


def test_parse_configuration_rejects_non_object() -> None:
    with pytest.raises(InvalidRequestException, match="Configuration"):
        WorkGroupConfiguration.from_dict("s3://not-an-object")


def test_parse_result_configuration_requires_object() -> None:
    with pytest.raises(InvalidRequestException, match="ResultConfiguration"):
        parse_result_configuration("s3://nope")


def test_parse_result_reuse_configuration_round_trip() -> None:
    raw = {
        "ResultReuseByAgeConfiguration": {
            "Enabled": True,
            "MaxAgeInMinutes": 30,
        }
    }

    parsed = parse_result_reuse_configuration(raw)

    assert parsed == ResultReuseByAgeConfiguration(
        enabled=True, max_age_in_minutes=30
    )
    assert result_reuse_configuration_payload(parsed) == raw


def test_parse_result_reuse_configuration_defaults_max_age() -> None:
    # The model documents MaxAgeInMinutes defaulting to 60 minutes when the
    # member is absent (service-2.json ResultReuseByAgeConfiguration).
    parsed = parse_result_reuse_configuration(
        {"ResultReuseByAgeConfiguration": {"Enabled": False}}
    )

    assert parsed == ResultReuseByAgeConfiguration(
        enabled=False, max_age_in_minutes=60
    )


def test_parse_result_reuse_configuration_absent_members() -> None:
    assert parse_result_reuse_configuration(None) is None
    assert parse_result_reuse_configuration({}) is None


def test_parse_result_reuse_configuration_requires_object() -> None:
    with pytest.raises(
        InvalidRequestException, match="ResultReuseConfiguration"
    ):
        parse_result_reuse_configuration("Enabled=true")
    with pytest.raises(
        InvalidRequestException, match="ResultReuseByAgeConfiguration"
    ):
        parse_result_reuse_configuration({"ResultReuseByAgeConfiguration": 1})


def test_parse_result_reuse_configuration_requires_enabled() -> None:
    with pytest.raises(InvalidRequestException, match="Enabled"):
        parse_result_reuse_configuration({"ResultReuseByAgeConfiguration": {}})
    with pytest.raises(InvalidRequestException, match="Enabled"):
        parse_result_reuse_configuration(
            {"ResultReuseByAgeConfiguration": {"Enabled": "yes"}}
        )


def test_parse_result_reuse_configuration_bounds_max_age() -> None:
    # MaxAgeInMinutes is the model's Age shape, bounded 0..10080
    # (service-2.json); out-of-range values 400 like other bounded members.
    for bad_age in ("60", True, -1, 10081):
        with pytest.raises(InvalidRequestException, match="MaxAgeInMinutes"):
            parse_result_reuse_configuration(
                {
                    "ResultReuseByAgeConfiguration": {
                        "Enabled": True,
                        "MaxAgeInMinutes": bad_age,
                    }
                }
            )


def test_parse_engine_version_requires_object() -> None:
    with pytest.raises(InvalidRequestException, match="EngineVersion"):
        parse_engine_version("AUTO")


def test_parse_tags_accepts_key_value_pairs() -> None:
    tags = [Tag(key="Division", value="West"), Tag(key="Team", value=None)]

    assert (
        parse_tags([{"Key": "Division", "Value": "West"}, {"Key": "Team"}])
        == tags
    )


def test_parse_tags_rejects_non_list() -> None:
    with pytest.raises(InvalidRequestException, match="Tags"):
        parse_tags({"Key": "Division"})


def test_to_payload_omits_absent_members() -> None:
    configuration = WorkGroupConfiguration(
        enforce_work_group_configuration=True,
    )

    assert to_payload(configuration) == {"EnforceWorkGroupConfiguration": True}


def test_to_payload_round_trips_result_configuration() -> None:
    payload = to_payload(
        WorkGroupConfiguration(
            result_configuration=ResultConfiguration(
                output_location="s3://results-bucket/analytics/",
                encryption_configuration=EncryptionConfiguration(
                    encryption_option="SSE_S3",
                ),
            )
        )
    )

    assert payload["ResultConfiguration"] == {
        "OutputLocation": "s3://results-bucket/analytics/",
        "EncryptionConfiguration": {"EncryptionOption": "SSE_S3"},
    }


def test_parse_configuration_updates_reads_typed_members() -> None:
    updates = WorkGroupConfigurationUpdates.from_dict(
        {
            "EnforceWorkGroupConfiguration": False,
            "ResultConfigurationUpdates": {
                "OutputLocation": "s3://results-bucket/analytics/",
                "RemoveOutputLocation": True,
            },
            "RemoveBytesScannedCutoffPerQuery": True,
        }
    )

    assert updates.enforce_work_group_configuration is False
    assert updates.result_configuration_updates == ResultConfigurationUpdates(
        output_location="s3://results-bucket/analytics/",
        remove_output_location=True,
    )
    assert updates.remove_bytes_scanned_cutoff_per_query is True


def test_apply_configuration_updates_merges_partial_edges() -> None:
    current = WorkGroupConfiguration(
        result_configuration=ResultConfiguration(
            output_location="s3://original/",
            expected_bucket_owner="111122223333",
        ),
        enforce_work_group_configuration=True,
    )
    updates = WorkGroupConfigurationUpdates.from_dict(
        {
            "ResultConfigurationUpdates": {
                "OutputLocation": "s3://updated/",
                "RemoveExpectedBucketOwner": True,
            }
        }
    )

    merged = WorkGroupConfiguration.apply_updates(current, updates)

    assert merged.result_configuration == ResultConfiguration(
        output_location="s3://updated/",
    )
    assert merged.enforce_work_group_configuration is True


def test_apply_configuration_updates_removal_beats_set() -> None:
    current = WorkGroupConfiguration(
        result_configuration=ResultConfiguration(
            output_location="s3://original/",
        )
    )
    updates = WorkGroupConfigurationUpdates.from_dict(
        {
            "ResultConfigurationUpdates": {
                "OutputLocation": "s3://updated/",
                "RemoveOutputLocation": True,
            }
        }
    )

    merged = WorkGroupConfiguration.apply_updates(current, updates)

    assert merged.result_configuration == ResultConfiguration()


def test_parse_tags_rejects_invalid_elements() -> None:
    with pytest.raises(InvalidRequestException, match="Tag entries"):
        parse_tags(["not-a-dict"])
    with pytest.raises(InvalidRequestException, match="Tag entries"):
        parse_tags([{"Key": 123}])
    with pytest.raises(InvalidRequestException, match="Tag Value"):
        parse_tags([{"Key": "k", "Value": 456}])


def test_parse_acl_configuration_and_payload() -> None:
    from athena_local.schemas import (
        AclConfiguration,
        acl_configuration_payload,
        parse_acl_configuration,
    )

    acl = parse_acl_configuration({"S3AclOption": "BUCKET_OWNER_FULL_CONTROL"})
    assert acl == AclConfiguration(s3_acl_option="BUCKET_OWNER_FULL_CONTROL")
    assert acl_configuration_payload(acl) == {
        "S3AclOption": "BUCKET_OWNER_FULL_CONTROL"
    }


def test_managed_query_results_round_trip() -> None:
    from athena_local.schemas import (
        ManagedQueryResultsConfiguration,
        ManagedQueryResultsConfigurationUpdates,
        ManagedQueryResultsEncryptionConfiguration,
        managed_query_results_payload,
        parse_managed_query_results_configuration,
        parse_managed_query_results_configuration_updates,
    )

    raw = {
        "Enabled": True,
        "EncryptionConfiguration": {"KmsKey": "arn:aws:kms:123"},
    }
    parsed = parse_managed_query_results_configuration(raw)
    assert parsed == ManagedQueryResultsConfiguration(
        enabled=True,
        encryption_configuration=ManagedQueryResultsEncryptionConfiguration(
            kms_key="arn:aws:kms:123"
        ),
    )
    assert managed_query_results_payload(parsed) == raw

    updates = parse_managed_query_results_configuration_updates(
        {
            "Enabled": False,
            "EncryptionConfiguration": {"KmsKey": "arn:aws:kms:456"},
            "RemoveEncryptionConfiguration": True,
        }
    )
    assert updates == ManagedQueryResultsConfigurationUpdates(
        enabled=False,
        encryption_configuration=ManagedQueryResultsEncryptionConfiguration(
            kms_key="arn:aws:kms:456"
        ),
        remove_encryption_configuration=True,
    )


def test_apply_configuration_updates_managed_results_and_fields() -> None:
    from athena_local.schemas import (
        AclConfiguration,
        EncryptionConfiguration,
        ManagedQueryResultsConfiguration,
    )

    current = WorkGroupConfiguration(
        managed_query_results_configuration=ManagedQueryResultsConfiguration(
            enabled=True
        ),
        customer_content_encryption_configuration={"KmsKey": "k1"},
    )
    updates = WorkGroupConfigurationUpdates.from_dict(
        {
            "ManagedQueryResultsConfigurationUpdates": {
                "Enabled": False,
                "RemoveEncryptionConfiguration": True,
            },
            "ResultConfigurationUpdates": {
                "EncryptionConfiguration": {
                    "EncryptionOption": "SSE_S3",
                    "KmsKey": "k2",
                },
                "AclConfiguration": {"S3AclOption": "BUCKET_OWNER"},
                "ExpectedBucketOwner": "123456789012",
            },
            "RemoveCustomerContentEncryptionConfiguration": True,
        }
    )
    merged = WorkGroupConfiguration.apply_updates(current, updates)
    assert merged.managed_query_results_configuration is not None
    assert merged.managed_query_results_configuration.enabled is False
    assert merged.customer_content_encryption_configuration is None
    assert merged.result_configuration == ResultConfiguration(
        encryption_configuration=EncryptionConfiguration(
            encryption_option="SSE_S3", kms_key="k2"
        ),
        expected_bucket_owner="123456789012",
        acl_configuration=AclConfiguration(s3_acl_option="BUCKET_OWNER"),
    )
