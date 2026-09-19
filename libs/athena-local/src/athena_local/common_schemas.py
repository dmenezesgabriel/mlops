"""Common typed wire shapes and primitive parsers for Athena JSON-1.1 (PC-2).

Member names, optionality, and nesting mirror the canonical service-2.json
shapes. Helpers enforce non-empty strings, booleans, and nested objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from athena_local.errors import InvalidRequestException

T = TypeVar("T")


def _defaulted(value: T | None, default: T) -> T:
    return default if value is None else value


def _as_object(raw: object, member: str) -> dict[str, object] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise InvalidRequestException(
            f"{member} must be a JSON object, got {raw!r}"
        )
    return raw


def _optional_bool(body: dict[str, object], member: str) -> bool | None:
    raw = body.get(member)
    if raw is None:
        return None
    if not isinstance(raw, bool):
        raise InvalidRequestException(
            f"{member} must be a boolean, got {raw!r}"
        )
    return raw


def _required_bool(body: dict[str, object], member: str) -> bool:
    raw = body.get(member)
    if not isinstance(raw, bool):
        raise InvalidRequestException(
            f"{member} is required and must be a boolean, got {raw!r}"
        )
    return raw


def _optional_int(body: dict[str, object], member: str) -> int | None:
    raw = body.get(member)
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise InvalidRequestException(
            f"{member} must be an integer, got {raw!r}"
        )
    return raw


def _optional_string(body: dict[str, object], member: str) -> str | None:
    raw = body.get(member)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise InvalidRequestException(
            f"{member} must be a string, got {raw!r}"
        )
    return raw


def _required_string(body: dict[str, object], member: str) -> str:
    raw = body.get(member)
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidRequestException(
            f"{member} is required and must be a non-empty string, got {raw!r}"
        )
    return raw


def _set_if_present(
    target: dict[str, object], member: str, value: object
) -> None:
    if value is not None:
        target[member] = value


def _merge_field(
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
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("Key"), str):
            raise InvalidRequestException(
                f"Tag entries must be objects with a Key string, got {item!r}"
            )
        value = item.get("Value")
        if value is not None and not isinstance(value, str):
            raise InvalidRequestException(
                f"Tag Value must be a string, got {value!r}"
            )
        tags.append(Tag(key=item["Key"], value=value))
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
    body = _as_object(raw, "EngineVersion")
    if body is None:
        return None
    return EngineVersion(
        selected_engine_version=_optional_string(
            body, "SelectedEngineVersion"
        ),
        effective_engine_version=_optional_string(
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
    body = _as_object(raw, "EncryptionConfiguration")
    if body is None:
        return None
    return EncryptionConfiguration(
        encryption_option=_required_string(body, "EncryptionOption"),
        kms_key=_optional_string(body, "KmsKey"),
    )


def encryption_configuration_payload(
    encryption: EncryptionConfiguration,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "EncryptionOption": encryption.encryption_option
    }
    _set_if_present(payload, "KmsKey", encryption.kms_key)
    return payload


@dataclass(frozen=True)
class AclConfiguration:
    s3_acl_option: str


def parse_acl_configuration(raw: object) -> AclConfiguration | None:
    body = _as_object(raw, "AclConfiguration")
    if body is None:
        return None
    return AclConfiguration(
        s3_acl_option=_required_string(body, "S3AclOption")
    )


def acl_configuration_payload(acl: AclConfiguration) -> dict[str, object]:
    return {"S3AclOption": acl.s3_acl_option}


@dataclass(frozen=True)
class ResultConfiguration:
    output_location: str | None = None
    encryption_configuration: EncryptionConfiguration | None = None
    expected_bucket_owner: str | None = None
    acl_configuration: AclConfiguration | None = None


def parse_result_configuration(raw: object) -> ResultConfiguration | None:
    body = _as_object(raw, "ResultConfiguration")
    if body is None:
        return None
    return ResultConfiguration(
        output_location=_optional_string(body, "OutputLocation"),
        encryption_configuration=parse_encryption_configuration(
            body.get("EncryptionConfiguration")
        ),
        expected_bucket_owner=_optional_string(body, "ExpectedBucketOwner"),
        acl_configuration=parse_acl_configuration(
            body.get("AclConfiguration")
        ),
    )


def result_configuration_payload(
    result_configuration: ResultConfiguration,
) -> dict[str, object]:
    payload: dict[str, object] = {}
    _set_if_present(
        payload, "OutputLocation", result_configuration.output_location
    )
    if result_configuration.encryption_configuration is not None:
        payload["EncryptionConfiguration"] = encryption_configuration_payload(
            result_configuration.encryption_configuration
        )
    _set_if_present(
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
    body = _as_object(raw, "ResultConfigurationUpdates")
    if body is None:
        return None
    return ResultConfigurationUpdates(
        output_location=_optional_string(body, "OutputLocation"),
        remove_output_location=_optional_bool(body, "RemoveOutputLocation"),
        encryption_configuration=parse_encryption_configuration(
            body.get("EncryptionConfiguration")
        ),
        remove_encryption_configuration=_optional_bool(
            body, "RemoveEncryptionConfiguration"
        ),
        expected_bucket_owner=_optional_string(body, "ExpectedBucketOwner"),
        remove_expected_bucket_owner=_optional_bool(
            body, "RemoveExpectedBucketOwner"
        ),
        acl_configuration=parse_acl_configuration(
            body.get("AclConfiguration")
        ),
        remove_acl_configuration=_optional_bool(
            body, "RemoveAclConfiguration"
        ),
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
    body = _as_object(raw, "ManagedQueryResultsConfiguration")
    if body is None:
        return None
    encryption = _as_object(
        body.get("EncryptionConfiguration"), "EncryptionConfiguration"
    )
    encryption_configuration = None
    if encryption is not None:
        encryption_configuration = ManagedQueryResultsEncryptionConfiguration(
            kms_key=_required_string(encryption, "KmsKey")
        )
    return ManagedQueryResultsConfiguration(
        enabled=_required_bool(body, "Enabled"),
        encryption_configuration=encryption_configuration,
    )


def parse_managed_query_results_configuration_updates(
    raw: object,
) -> ManagedQueryResultsConfigurationUpdates | None:
    body = _as_object(raw, "ManagedQueryResultsConfigurationUpdates")
    if body is None:
        return None
    encryption = _as_object(
        body.get("EncryptionConfiguration"), "EncryptionConfiguration"
    )
    encryption_configuration = None
    if encryption is not None:
        encryption_configuration = ManagedQueryResultsEncryptionConfiguration(
            kms_key=_required_string(encryption, "KmsKey")
        )
    return ManagedQueryResultsConfigurationUpdates(
        enabled=_optional_bool(body, "Enabled"),
        encryption_configuration=encryption_configuration,
        remove_encryption_configuration=_optional_bool(
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
