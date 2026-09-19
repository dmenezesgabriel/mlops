"""Typed wire shapes for Athena WorkGroup operations (MD-1).

Member names, optionality, and nesting mirror the canonical service-2.json
WorkGroup* shapes. Unknown members are preserved verbatim in ``preserved``
so a GetWorkGroup round-trip loses nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TypeVar

from athena_local.common_schemas import (
    DEFAULT_ENGINE_VERSION,
    EngineVersion,
    ManagedQueryResultsConfiguration,
    ManagedQueryResultsConfigurationUpdates,
    ResultConfiguration,
    ResultConfigurationUpdates,
    _as_object,
    _defaulted,
    _merge_field,
    _optional_bool,
    _optional_int,
    _optional_string,
    _set_if_present,
    engine_version_payload,
    managed_query_results_payload,
    parse_engine_version,
    parse_managed_query_results_configuration,
    parse_managed_query_results_configuration_updates,
    parse_result_configuration,
    parse_result_configuration_updates,
    result_configuration_payload,
)

T = TypeVar("T")

# Canonical member names of WorkGroupConfiguration, used to separate known
# members from preserved pass-through members during parsing.
_CONFIGURATION_MEMBERS = frozenset(
    {
        "ResultConfiguration",
        "ManagedQueryResultsConfiguration",
        "EnforceWorkGroupConfiguration",
        "PublishCloudWatchMetricsEnabled",
        "BytesScannedCutoffPerQuery",
        "RequesterPaysEnabled",
        "EngineVersion",
        "AdditionalConfiguration",
        "ExecutionRole",
        "MonitoringConfiguration",
        "EngineConfiguration",
        "CustomerContentEncryptionConfiguration",
        "EnableMinimumEncryptionConfiguration",
        "IdentityCenterConfiguration",
        "QueryResultsS3AccessGrantsConfiguration",
    }
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


def _validated_map(raw: object) -> dict[str, object] | None:
    return _as_object(raw, "configuration member")


def _updated(current: T | None, update_value: T | None) -> T | None:
    return current if update_value is None else update_value


def _merge_result_configuration(
    current: ResultConfiguration | None,
    updates: ResultConfigurationUpdates | None,
) -> ResultConfiguration | None:
    if updates is None:
        return current
    base = current or ResultConfiguration()
    return ResultConfiguration(
        output_location=_merge_field(
            base.output_location,
            updates.output_location,
            updates.remove_output_location,
        ),
        encryption_configuration=_merge_field(
            base.encryption_configuration,
            updates.encryption_configuration,
            updates.remove_encryption_configuration,
        ),
        expected_bucket_owner=_merge_field(
            base.expected_bucket_owner,
            updates.expected_bucket_owner,
            updates.remove_expected_bucket_owner,
        ),
        acl_configuration=_merge_field(
            base.acl_configuration,
            updates.acl_configuration,
            updates.remove_acl_configuration,
        ),
    )


def _merge_managed_updates(
    current: ManagedQueryResultsConfiguration | None,
    updates: ManagedQueryResultsConfigurationUpdates | None,
) -> ManagedQueryResultsConfiguration | None:
    if updates is None:
        return current
    if (
        current is None
        and updates.enabled is None
        and updates.encryption_configuration is None
    ):
        return None
    enabled = current.enabled if current is not None else False
    if updates.enabled is not None:
        enabled = updates.enabled
    current_enc = (
        current.encryption_configuration if current is not None else None
    )
    encryption = _merge_field(
        current_enc,
        updates.encryption_configuration,
        updates.remove_encryption_configuration,
    )
    return ManagedQueryResultsConfiguration(
        enabled=enabled, encryption_configuration=encryption
    )


def _merge_customer_content(
    current: dict[str, object] | None,
    updates: WorkGroupConfigurationUpdates,
) -> dict[str, object] | None:
    return _merge_field(
        current,
        updates.customer_content_encryption_configuration,
        updates.remove_customer_content_encryption_configuration,
    )


def _merge_bytes_scanned(
    current: int | None, updates: WorkGroupConfigurationUpdates
) -> int | None:
    return _merge_field(
        current,
        updates.bytes_scanned_cutoff_per_query,
        updates.remove_bytes_scanned_cutoff_per_query,
    )


@dataclass(frozen=True)
class WorkGroupConfiguration:
    """WorkGroupConfiguration shape; every member optional per the model."""

    result_configuration: ResultConfiguration | None = None
    managed_query_results_configuration: (
        ManagedQueryResultsConfiguration | None
    ) = None
    enforce_work_group_configuration: bool | None = None
    publish_cloudwatch_metrics_enabled: bool | None = None
    bytes_scanned_cutoff_per_query: int | None = None
    requester_pays_enabled: bool | None = None
    engine_version: EngineVersion | None = None
    additional_configuration: str | None = None
    execution_role: str | None = None
    monitoring_configuration: dict[str, object] | None = None
    engine_configuration: dict[str, object] | None = None
    customer_content_encryption_configuration: dict[str, object] | None = None
    enable_minimum_encryption_configuration: bool | None = None
    identity_center_configuration: dict[str, object] | None = None
    query_results_s3_access_grants_configuration: dict[str, object] | None = (
        None
    )
    preserved: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: object) -> WorkGroupConfiguration:
        """Parse the Configuration member of CreateWorkGroup."""
        body = _as_object(raw, "Configuration")
        if body is None:
            return cls()
        known = {member: body.get(member) for member in _CONFIGURATION_MEMBERS}
        preserved = {
            member: body[member]
            for member in body
            if member not in _CONFIGURATION_MEMBERS
        }
        return cls(
            result_configuration=parse_result_configuration(
                known.get("ResultConfiguration")
            ),
            managed_query_results_configuration=(
                parse_managed_query_results_configuration(
                    known.get("ManagedQueryResultsConfiguration")
                )
            ),
            enforce_work_group_configuration=_optional_bool(
                body, "EnforceWorkGroupConfiguration"
            ),
            publish_cloudwatch_metrics_enabled=_optional_bool(
                body, "PublishCloudWatchMetricsEnabled"
            ),
            bytes_scanned_cutoff_per_query=_optional_int(
                body, "BytesScannedCutoffPerQuery"
            ),
            requester_pays_enabled=_optional_bool(
                body, "RequesterPaysEnabled"
            ),
            engine_version=parse_engine_version(known.get("EngineVersion")),
            additional_configuration=_optional_string(
                body, "AdditionalConfiguration"
            ),
            execution_role=_optional_string(body, "ExecutionRole"),
            monitoring_configuration=_validated_map(
                known.get("MonitoringConfiguration")
            ),
            engine_configuration=_validated_map(
                known.get("EngineConfiguration")
            ),
            customer_content_encryption_configuration=_validated_map(
                known.get("CustomerContentEncryptionConfiguration")
            ),
            enable_minimum_encryption_configuration=_optional_bool(
                body, "EnableMinimumEncryptionConfiguration"
            ),
            identity_center_configuration=_validated_map(
                known.get("IdentityCenterConfiguration")
            ),
            query_results_s3_access_grants_configuration=_validated_map(
                known.get("QueryResultsS3AccessGrantsConfiguration")
            ),
            preserved=preserved,
        )

    @staticmethod
    def apply_updates(
        current: WorkGroupConfiguration,
        updates: WorkGroupConfigurationUpdates,
    ) -> WorkGroupConfiguration:
        """Merge an UpdateWorkGroup ConfigurationUpdates into the stored config."""
        return replace(
            current,
            enforce_work_group_configuration=_updated(
                current.enforce_work_group_configuration,
                updates.enforce_work_group_configuration,
            ),
            publish_cloudwatch_metrics_enabled=_updated(
                current.publish_cloudwatch_metrics_enabled,
                updates.publish_cloudwatch_metrics_enabled,
            ),
            requester_pays_enabled=_updated(
                current.requester_pays_enabled, updates.requester_pays_enabled
            ),
            engine_version=_updated(
                current.engine_version, updates.engine_version
            ),
            additional_configuration=_updated(
                current.additional_configuration,
                updates.additional_configuration,
            ),
            execution_role=_updated(
                current.execution_role, updates.execution_role
            ),
            enable_minimum_encryption_configuration=_updated(
                current.enable_minimum_encryption_configuration,
                updates.enable_minimum_encryption_configuration,
            ),
            monitoring_configuration=_updated(
                current.monitoring_configuration,
                updates.monitoring_configuration,
            ),
            engine_configuration=_updated(
                current.engine_configuration, updates.engine_configuration
            ),
            query_results_s3_access_grants_configuration=_updated(
                current.query_results_s3_access_grants_configuration,
                updates.query_results_s3_access_grants_configuration,
            ),
            result_configuration=_merge_result_configuration(
                current.result_configuration,
                updates.result_configuration_updates,
            ),
            managed_query_results_configuration=_merge_managed_updates(
                current.managed_query_results_configuration,
                updates.managed_query_results_configuration_updates,
            ),
            customer_content_encryption_configuration=_merge_customer_content(
                current.customer_content_encryption_configuration,
                updates,
            ),
            bytes_scanned_cutoff_per_query=_merge_bytes_scanned(
                current.bytes_scanned_cutoff_per_query, updates
            ),
            identity_center_configuration=current.identity_center_configuration,
            preserved={**current.preserved, **updates.preserved},
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
        body = _as_object(raw, "ConfigurationUpdates")
        if body is None:
            return cls()
        preserved = {
            member: body[member]
            for member in body
            if member not in _UPDATES_MEMBERS
        }
        return cls(
            enforce_work_group_configuration=_optional_bool(
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
            publish_cloudwatch_metrics_enabled=_optional_bool(
                body, "PublishCloudWatchMetricsEnabled"
            ),
            bytes_scanned_cutoff_per_query=_optional_int(
                body, "BytesScannedCutoffPerQuery"
            ),
            remove_bytes_scanned_cutoff_per_query=_optional_bool(
                body, "RemoveBytesScannedCutoffPerQuery"
            ),
            requester_pays_enabled=_optional_bool(
                body, "RequesterPaysEnabled"
            ),
            engine_version=parse_engine_version(body.get("EngineVersion")),
            remove_customer_content_encryption_configuration=_optional_bool(
                body, "RemoveCustomerContentEncryptionConfiguration"
            ),
            additional_configuration=_optional_string(
                body, "AdditionalConfiguration"
            ),
            execution_role=_optional_string(body, "ExecutionRole"),
            customer_content_encryption_configuration=_validated_map(
                body.get("CustomerContentEncryptionConfiguration")
            ),
            enable_minimum_encryption_configuration=_optional_bool(
                body, "EnableMinimumEncryptionConfiguration"
            ),
            query_results_s3_access_grants_configuration=_validated_map(
                body.get("QueryResultsS3AccessGrantsConfiguration")
            ),
            monitoring_configuration=_validated_map(
                body.get("MonitoringConfiguration")
            ),
            engine_configuration=_validated_map(
                body.get("EngineConfiguration")
            ),
            preserved=preserved,
        )


def _write_config_flags(
    payload: dict[str, object], configuration: WorkGroupConfiguration
) -> None:
    _set_if_present(
        payload,
        "EnforceWorkGroupConfiguration",
        configuration.enforce_work_group_configuration,
    )
    _set_if_present(
        payload,
        "PublishCloudWatchMetricsEnabled",
        configuration.publish_cloudwatch_metrics_enabled,
    )
    _set_if_present(
        payload,
        "BytesScannedCutoffPerQuery",
        configuration.bytes_scanned_cutoff_per_query,
    )
    _set_if_present(
        payload, "RequesterPaysEnabled", configuration.requester_pays_enabled
    )
    _set_if_present(
        payload,
        "AdditionalConfiguration",
        configuration.additional_configuration,
    )
    _set_if_present(payload, "ExecutionRole", configuration.execution_role)


def _write_config_maps(
    payload: dict[str, object], configuration: WorkGroupConfiguration
) -> None:
    _set_if_present(
        payload,
        "MonitoringConfiguration",
        configuration.monitoring_configuration,
    )
    _set_if_present(
        payload, "EngineConfiguration", configuration.engine_configuration
    )
    _set_if_present(
        payload,
        "CustomerContentEncryptionConfiguration",
        configuration.customer_content_encryption_configuration,
    )
    _set_if_present(
        payload,
        "EnableMinimumEncryptionConfiguration",
        configuration.enable_minimum_encryption_configuration,
    )
    _set_if_present(
        payload,
        "IdentityCenterConfiguration",
        configuration.identity_center_configuration,
    )
    _set_if_present(
        payload,
        "QueryResultsS3AccessGrantsConfiguration",
        configuration.query_results_s3_access_grants_configuration,
    )


def to_payload(configuration: WorkGroupConfiguration) -> dict[str, object]:
    """Serialize a stored configuration to the GetWorkGroup wire shape."""
    payload: dict[str, object] = {}
    if configuration.result_configuration is not None:
        payload["ResultConfiguration"] = result_configuration_payload(
            configuration.result_configuration
        )
    if configuration.managed_query_results_configuration is not None:
        payload["ManagedQueryResultsConfiguration"] = (
            managed_query_results_payload(
                configuration.managed_query_results_configuration
            )
        )
    if configuration.engine_version is not None:
        payload["EngineVersion"] = engine_version_payload(
            configuration.engine_version
        )
    _write_config_flags(payload, configuration)
    _write_config_maps(payload, configuration)
    payload.update(configuration.preserved)
    return payload


def apply_defaults(
    configuration: WorkGroupConfiguration,
) -> WorkGroupConfiguration:
    """Fill create-time defaults exactly as moto ``WorkGroup.__init__`` does."""
    return replace(
        configuration,
        enforce_work_group_configuration=_defaulted(
            configuration.enforce_work_group_configuration, True
        ),
        publish_cloudwatch_metrics_enabled=_defaulted(
            configuration.publish_cloudwatch_metrics_enabled, False
        ),
        requester_pays_enabled=_defaulted(
            configuration.requester_pays_enabled, False
        ),
        enable_minimum_encryption_configuration=_defaulted(
            configuration.enable_minimum_encryption_configuration, False
        ),
        engine_version=_defaulted(
            configuration.engine_version, DEFAULT_ENGINE_VERSION
        ),
    )
