"""The WorkGroupConfigurationUpdates wire shape (UpdateWorkGroup input).

Split from ``workgroup_schemas`` purely for size — member names,
optionality and the preserved-member pass-through follow the same
canonical-model rules. Merging an updates shape into a stored configuration
stays on ``WorkGroupConfiguration.apply_updates``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from athena_local.common_schemas import (
    EngineVersion,
    ManagedQueryResultsConfigurationUpdates,
    ResultConfigurationUpdates,
    parse_engine_version,
    parse_managed_query_results_configuration_updates,
    parse_result_configuration_updates,
)
from athena_local.request_fields import (
    BYTES_SCANNED_CUTOFF_MINIMUM,
    NAME_STRING_MAX_LENGTH,
    NAME_STRING_MIN_LENGTH,
    ROLE_ARN_MAX_LENGTH,
    ROLE_ARN_PATTERN,
    as_object,
    optional_bool,
    optional_int,
    optional_string,
)

# Canonical member names of WorkGroupConfigurationUpdates; the update shape has
# no twin for IdentityCenterConfiguration.
_UPDATES_MEMBERS = frozenset(
    {
        "EnforceWorkGroupConfiguration",
        "ResultConfigurationUpdates",
        "ManagedQueryResultsConfigurationUpdates",
        "PublishCloudWatchMetricsEnabled",
        "BytesScannedCutoffPerQuery",
        "RemoveBytesScannedCutoffPerQuery",
        "RequesterPaysEnabled",
        "EngineVersion",
        "RemoveCustomerContentEncryptionConfiguration",
        "AdditionalConfiguration",
        "ExecutionRole",
        "CustomerContentEncryptionConfiguration",
        "EnableMinimumEncryptionConfiguration",
        "QueryResultsS3AccessGrantsConfiguration",
        "MonitoringConfiguration",
        "EngineConfiguration",
    }
)


@dataclass(frozen=True)
class WorkGroupConfigurationUpdates:
    enforce_work_group_configuration: bool | None = None
    result_configuration_updates: ResultConfigurationUpdates | None = None
    managed_query_results_configuration_updates: (
        ManagedQueryResultsConfigurationUpdates | None
    ) = None
    publish_cloudwatch_metrics_enabled: bool | None = None
    bytes_scanned_cutoff_per_query: int | None = None
    remove_bytes_scanned_cutoff_per_query: bool | None = None
    requester_pays_enabled: bool | None = None
    engine_version: EngineVersion | None = None
    remove_customer_content_encryption_configuration: bool | None = None
    additional_configuration: str | None = None
    execution_role: str | None = None
    customer_content_encryption_configuration: dict[str, object] | None = None
    enable_minimum_encryption_configuration: bool | None = None
    query_results_s3_access_grants_configuration: dict[str, object] | None = (
        None
    )
    monitoring_configuration: dict[str, object] | None = None
    engine_configuration: dict[str, object] | None = None
    preserved: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: object) -> WorkGroupConfigurationUpdates:
        """Parse the ConfigurationUpdates member of UpdateWorkGroup."""
        body = as_object(raw, "ConfigurationUpdates")
        if body is None:
            return cls()
        preserved = {
            member: body[member]
            for member in body
            if member not in _UPDATES_MEMBERS
        }
        return cls(
            enforce_work_group_configuration=optional_bool(
                body, "EnforceWorkGroupConfiguration"
            ),
            result_configuration_updates=parse_result_configuration_updates(
                body.get("ResultConfigurationUpdates")
            ),
            managed_query_results_configuration_updates=(
                parse_managed_query_results_configuration_updates(
                    body.get("ManagedQueryResultsConfigurationUpdates")
                )
            ),
            publish_cloudwatch_metrics_enabled=optional_bool(
                body, "PublishCloudWatchMetricsEnabled"
            ),
            bytes_scanned_cutoff_per_query=optional_int(
                body,
                "BytesScannedCutoffPerQuery",
                minimum=BYTES_SCANNED_CUTOFF_MINIMUM,
            ),
            remove_bytes_scanned_cutoff_per_query=optional_bool(
                body, "RemoveBytesScannedCutoffPerQuery"
            ),
            requester_pays_enabled=optional_bool(body, "RequesterPaysEnabled"),
            engine_version=parse_engine_version(body.get("EngineVersion")),
            remove_customer_content_encryption_configuration=optional_bool(
                body, "RemoveCustomerContentEncryptionConfiguration"
            ),
            additional_configuration=optional_string(
                body,
                "AdditionalConfiguration",
                min_length=NAME_STRING_MIN_LENGTH,
                max_length=NAME_STRING_MAX_LENGTH,
            ),
            execution_role=optional_string(
                body,
                "ExecutionRole",
                max_length=ROLE_ARN_MAX_LENGTH,
                pattern=ROLE_ARN_PATTERN,
            ),
            customer_content_encryption_configuration=as_object(
                body.get("CustomerContentEncryptionConfiguration"),
                "configuration member",
            ),
            enable_minimum_encryption_configuration=optional_bool(
                body, "EnableMinimumEncryptionConfiguration"
            ),
            query_results_s3_access_grants_configuration=as_object(
                body.get("QueryResultsS3AccessGrantsConfiguration"),
                "configuration member",
            ),
            monitoring_configuration=as_object(
                body.get("MonitoringConfiguration"), "configuration member"
            ),
            engine_configuration=as_object(
                body.get("EngineConfiguration"), "configuration member"
            ),
            preserved=preserved,
        )
