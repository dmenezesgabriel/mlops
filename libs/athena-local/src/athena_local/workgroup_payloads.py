"""Serialization and default application for Athena WorkGroup payloads (MD-1).

Serializes WorkGroupConfiguration to wire dictionary shapes and fills
creation defaults mirroring moto Athena models.
"""

from __future__ import annotations

from dataclasses import replace

from athena_local.common_schemas import (
    DEFAULT_ENGINE_VERSION,
    _defaulted,
    _set_if_present,
    engine_version_payload,
    managed_query_results_payload,
    result_configuration_payload,
)
from athena_local.workgroup_schemas import WorkGroupConfiguration


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
