"""Typed wire shapes for Athena JSON-1.1 operations (PC-2, MD-1, MD-2).

Re-exports shared Athena types, WorkGroup configuration shapes, and NamedQuery
shapes.
"""

from __future__ import annotations

from athena_local.common_schemas import (
    DEFAULT_ENGINE_VERSION,
    AclConfiguration,
    EncryptionConfiguration,
    EngineVersion,
    ManagedQueryResultsConfiguration,
    ManagedQueryResultsConfigurationUpdates,
    ManagedQueryResultsEncryptionConfiguration,
    ResultConfiguration,
    ResultConfigurationUpdates,
    Tag,
    acl_configuration_payload,
    encryption_configuration_payload,
    engine_version_payload,
    managed_query_results_payload,
    parse_acl_configuration,
    parse_encryption_configuration,
    parse_engine_version,
    parse_managed_query_results_configuration,
    parse_managed_query_results_configuration_updates,
    parse_result_configuration,
    parse_result_configuration_updates,
    parse_tags,
    result_configuration_payload,
)
from athena_local.workgroup_schemas import (
    WorkGroupConfiguration,
    WorkGroupConfigurationUpdates,
    apply_defaults,
    to_payload,
)

__all__ = [
    "DEFAULT_ENGINE_VERSION",
    "AclConfiguration",
    "EncryptionConfiguration",
    "EngineVersion",
    "ManagedQueryResultsConfiguration",
    "ManagedQueryResultsConfigurationUpdates",
    "ManagedQueryResultsEncryptionConfiguration",
    "ResultConfiguration",
    "ResultConfigurationUpdates",
    "Tag",
    "WorkGroupConfiguration",
    "WorkGroupConfigurationUpdates",
    "acl_configuration_payload",
    "apply_defaults",
    "encryption_configuration_payload",
    "engine_version_payload",
    "managed_query_results_payload",
    "parse_acl_configuration",
    "parse_encryption_configuration",
    "parse_engine_version",
    "parse_managed_query_results_configuration",
    "parse_managed_query_results_configuration_updates",
    "parse_result_configuration",
    "parse_result_configuration_updates",
    "parse_tags",
    "result_configuration_payload",
    "to_payload",
]
