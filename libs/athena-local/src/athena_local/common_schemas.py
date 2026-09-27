"""Common typed wire shapes and primitive parsers for Athena JSON-1.1.

Member names, optionality, and nesting mirror the canonical service-2.json
shapes. Helpers enforce non-empty strings, booleans, and nested objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar, cast

from athena_local.errors import InvalidRequestException
from athena_local.request_fields import (
    as_object,
    optional_bool,
    optional_int,
    optional_string,
    required_bool,
    required_string,
)

T = TypeVar("T")


def defaulted(value: T | None, default: T) -> T:
    return default if value is None else value


def set_if_present(
    target: dict[str, object], member: str, value: object
) -> None:
    if value is not None:
        target[member] = value


def merge_field(
    current_value: T | None,
    update_value: T | None,
    remove_flag: bool | None,
) -> T | None:
    if remove_flag is True:
        return None
    if update_value is not None:
        return update_value
    return current_value


@dataclass(frozen=True)
class Tag:
    key: str
    value: str | None = None


def parse_tags(raw: object) -> list[Tag]:
    """Parse the model's TagList; absent Tags parse to an empty list."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise InvalidRequestException(f"Tags must be a list, got {raw!r}")
    tags: list[Tag] = []
    items: list[object] = raw
    for item in items:
        entry = cast(dict[str, object], item) if isinstance(item, dict) else {}
        key, value = entry.get("Key"), entry.get("Value")
        if not isinstance(key, str):
            raise InvalidRequestException(
                f"Tag entries must be objects with a Key string, got {item!r}"
            )
        if value is not None and not isinstance(value, str):
            raise InvalidRequestException(
                f"Tag Value must be a string, got {value!r}"
            )
        tags.append(Tag(key=key, value=value))
    return tags


@dataclass(frozen=True)
class EngineVersion:
    selected_engine_version: str | None = None
    effective_engine_version: str | None = None


DEFAULT_ENGINE_VERSION = EngineVersion(
    selected_engine_version="AUTO",
    effective_engine_version="Athena engine version 3",
)


def parse_engine_version(raw: object) -> EngineVersion | None:
    body = as_object(raw, "EngineVersion")
    if body is None:
        return None
    return EngineVersion(
        selected_engine_version=optional_string(body, "SelectedEngineVersion"),
        effective_engine_version=optional_string(
            body, "EffectiveEngineVersion"
        ),
    )


def engine_version_payload(engine_version: EngineVersion) -> dict[str, object]:
    return {
        "SelectedEngineVersion": engine_version.selected_engine_version,
        "EffectiveEngineVersion": engine_version.effective_engine_version,
    }


@dataclass(frozen=True)
class EncryptionConfiguration:
    encryption_option: str
    kms_key: str | None = None


def parse_encryption_configuration(
    raw: object,
) -> EncryptionConfiguration | None:
    body = as_object(raw, "EncryptionConfiguration")
    if body is None:
        return None
    return EncryptionConfiguration(
        encryption_option=required_string(body, "EncryptionOption"),
        kms_key=optional_string(body, "KmsKey"),
    )


def encryption_configuration_payload(
    encryption: EncryptionConfiguration,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "EncryptionOption": encryption.encryption_option
    }
    set_if_present(payload, "KmsKey", encryption.kms_key)
    return payload


@dataclass(frozen=True)
class AclConfiguration:
    s3_acl_option: str


def parse_acl_configuration(raw: object) -> AclConfiguration | None:
    body = as_object(raw, "AclConfiguration")
    if body is None:
        return None
    return AclConfiguration(s3_acl_option=required_string(body, "S3AclOption"))


def acl_configuration_payload(acl: AclConfiguration) -> dict[str, object]:
    return {"S3AclOption": acl.s3_acl_option}


@dataclass(frozen=True)
class ResultConfiguration:
    output_location: str | None = None
    encryption_configuration: EncryptionConfiguration | None = None
    expected_bucket_owner: str | None = None
    acl_configuration: AclConfiguration | None = None


def parse_result_configuration(raw: object) -> ResultConfiguration | None:
    body = as_object(raw, "ResultConfiguration")
    if body is None:
        return None
    return ResultConfiguration(
        output_location=optional_string(body, "OutputLocation"),
        encryption_configuration=parse_encryption_configuration(
            body.get("EncryptionConfiguration")
        ),
        expected_bucket_owner=optional_string(body, "ExpectedBucketOwner"),
        acl_configuration=parse_acl_configuration(
            body.get("AclConfiguration")
        ),
    )


def result_configuration_payload(
    result_configuration: ResultConfiguration,
) -> dict[str, object]:
    payload: dict[str, object] = {}
    set_if_present(
        payload, "OutputLocation", result_configuration.output_location
    )
    if result_configuration.encryption_configuration is not None:
        payload["EncryptionConfiguration"] = encryption_configuration_payload(
            result_configuration.encryption_configuration
        )
    set_if_present(
        payload,
        "ExpectedBucketOwner",
        result_configuration.expected_bucket_owner,
    )
    if result_configuration.acl_configuration is not None:
        payload["AclConfiguration"] = acl_configuration_payload(
            result_configuration.acl_configuration
        )
    return payload


@dataclass(frozen=True)
class ResultReuseByAgeConfiguration:
    """Effective ResultReuseByAgeConfiguration member (service-2.json).

    ``max_age_in_minutes`` carries the model's documented default (60)
    when the request leaves it out; the model's ``Age`` shape bounds it
    to 0..10080.
    """

    enabled: bool
    max_age_in_minutes: int = 60


MAX_RESULT_REUSE_AGE_MINUTES = 10080


def parse_result_reuse_configuration(
    raw: object,
) -> ResultReuseByAgeConfiguration | None:
    """Parse ``ResultReuseConfiguration``; the outer object carries only the
    by-age member, so an absent/empty member parses to None."""
    body = as_object(raw, "ResultReuseConfiguration")
    if body is None:
        return None
    by_age = as_object(
        body.get("ResultReuseByAgeConfiguration"),
        "ResultReuseByAgeConfiguration",
    )
    if by_age is None:
        return None
    max_age = optional_int(by_age, "MaxAgeInMinutes")
    if (
        max_age is not None
        and not 0 <= max_age <= MAX_RESULT_REUSE_AGE_MINUTES
    ):
        raise InvalidRequestException(
            f"MaxAgeInMinutes must be between 0 and "
            f"{MAX_RESULT_REUSE_AGE_MINUTES}, got {max_age}"
        )
    return ResultReuseByAgeConfiguration(
        enabled=required_bool(by_age, "Enabled"),
        max_age_in_minutes=defaulted(max_age, 60),
    )


def result_reuse_configuration_payload(
    reuse: ResultReuseByAgeConfiguration,
) -> dict[str, object]:
    return {
        "ResultReuseByAgeConfiguration": {
            "Enabled": reuse.enabled,
            "MaxAgeInMinutes": reuse.max_age_in_minutes,
        }
    }


@dataclass(frozen=True)
class ResultConfigurationUpdates:
    output_location: str | None = None
    remove_output_location: bool | None = None
    encryption_configuration: EncryptionConfiguration | None = None
    remove_encryption_configuration: bool | None = None
    expected_bucket_owner: str | None = None
    remove_expected_bucket_owner: bool | None = None
    acl_configuration: AclConfiguration | None = None
    remove_acl_configuration: bool | None = None


def parse_result_configuration_updates(
    raw: object,
) -> ResultConfigurationUpdates | None:
    body = as_object(raw, "ResultConfigurationUpdates")
    if body is None:
        return None
    return ResultConfigurationUpdates(
        output_location=optional_string(body, "OutputLocation"),
        remove_output_location=optional_bool(body, "RemoveOutputLocation"),
        encryption_configuration=parse_encryption_configuration(
            body.get("EncryptionConfiguration")
        ),
        remove_encryption_configuration=optional_bool(
            body, "RemoveEncryptionConfiguration"
        ),
        expected_bucket_owner=optional_string(body, "ExpectedBucketOwner"),
        remove_expected_bucket_owner=optional_bool(
            body, "RemoveExpectedBucketOwner"
        ),
        acl_configuration=parse_acl_configuration(
            body.get("AclConfiguration")
        ),
        remove_acl_configuration=optional_bool(body, "RemoveAclConfiguration"),
    )


@dataclass(frozen=True)
class ManagedQueryResultsEncryptionConfiguration:
    kms_key: str


@dataclass(frozen=True)
class ManagedQueryResultsConfiguration:
    enabled: bool
    encryption_configuration: (
        ManagedQueryResultsEncryptionConfiguration | None
    ) = None


@dataclass(frozen=True)
class ManagedQueryResultsConfigurationUpdates:
    enabled: bool | None = None
    encryption_configuration: (
        ManagedQueryResultsEncryptionConfiguration | None
    ) = None
    remove_encryption_configuration: bool | None = None


def parse_managed_query_results_configuration(
    raw: object,
) -> ManagedQueryResultsConfiguration | None:
    body = as_object(raw, "ManagedQueryResultsConfiguration")
    if body is None:
        return None
    encryption = as_object(
        body.get("EncryptionConfiguration"), "EncryptionConfiguration"
    )
    encryption_configuration = None
    if encryption is not None:
        encryption_configuration = ManagedQueryResultsEncryptionConfiguration(
            kms_key=required_string(encryption, "KmsKey")
        )
    return ManagedQueryResultsConfiguration(
        enabled=required_bool(body, "Enabled"),
        encryption_configuration=encryption_configuration,
    )


def parse_managed_query_results_configuration_updates(
    raw: object,
) -> ManagedQueryResultsConfigurationUpdates | None:
    body = as_object(raw, "ManagedQueryResultsConfigurationUpdates")
    if body is None:
        return None
    encryption = as_object(
        body.get("EncryptionConfiguration"), "EncryptionConfiguration"
    )
    encryption_configuration = None
    if encryption is not None:
        encryption_configuration = ManagedQueryResultsEncryptionConfiguration(
            kms_key=required_string(encryption, "KmsKey")
        )
    return ManagedQueryResultsConfigurationUpdates(
        enabled=optional_bool(body, "Enabled"),
        encryption_configuration=encryption_configuration,
        remove_encryption_configuration=optional_bool(
            body, "RemoveEncryptionConfiguration"
        ),
    )


def managed_query_results_payload(
    managed: ManagedQueryResultsConfiguration,
) -> dict[str, object]:
    payload: dict[str, object] = {"Enabled": managed.enabled}
    if managed.encryption_configuration is not None:
        payload["EncryptionConfiguration"] = {
            "KmsKey": managed.encryption_configuration.kms_key
        }
    return payload
