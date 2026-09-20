"""Resource tagging operations (MD-6): handlers bound into the dispatch registry.

TagResource, UntagResource, and ListTagsForResource address resources by
Athena ARN (``arn:aws:athena:<region>:<account>:<type>/<name>`` — the shape in
the CLI ``tag-resource``/``list-tags-for-resource`` examples). Workgroups and
data catalogs are the taggable records; their ``tags`` lists are mutated in
place so the store record sees the change. Region and account are accepted but
ignored: the emulator holds a single account's state (ADR-0003).

The three ops declare ``ResourceNotFoundException`` in the service model, so a
well-formed ARN for an unknown resource answers 404 while a malformed ARN (or
an unmodeled resource type) answers ``InvalidRequestException``.
"""

from __future__ import annotations

from athena_local.data_catalog_state import DataCatalogStore
from athena_local.dispatch import register_handler
from athena_local.errors import (
    InvalidRequestException,
    ResourceNotFoundException,
)
from athena_local.schemas import Tag, parse_tags
from athena_local.state import WorkGroupStore

ATHENA_ARN_PREFIX = "arn:aws:athena:"
TAGGABLE_RESOURCE_TYPES = ("workgroup", "datacatalog")


def _required_string(payload: dict[str, object] | None, member: str) -> str:
    raw = payload.get(member) if payload is not None else None
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidRequestException(
            f"{member} is required and must be a non-empty string, got {raw!r}"
        )
    return raw


def _required_string_list(
    payload: dict[str, object] | None, member: str
) -> list[str]:
    raw = payload.get(member) if payload is not None else None
    if not isinstance(raw, list):
        raise InvalidRequestException(f"{member} must be a list, got {raw!r}")
    if not raw:
        raise InvalidRequestException(f"{member} must not be empty")
    for item in raw:
        if not isinstance(item, str):
            raise InvalidRequestException(
                f"{member} must contain only strings, got {item!r}"
            )
    return raw


def _parse_arn(resource_arn: str) -> tuple[str, str]:
    """Split ``arn:aws:athena:<region>:<account>:<type>/<name>``.

    Raises InvalidRequestException for anything that does not match the Athena
    ARN structure (the resource-type/name fragment is required to exist).
    """
    if not resource_arn.startswith(ATHENA_ARN_PREFIX):
        raise InvalidRequestException(
            f"Invalid Athena resource ARN: {resource_arn!r}"
        )
    parts = resource_arn.split(":")
    if len(parts) != 6:
        raise InvalidRequestException(
            f"Invalid Athena resource ARN: {resource_arn!r}"
        )
    fragment = parts[5]
    if "/" not in fragment:
        raise InvalidRequestException(
            f"Invalid Athena resource ARN: {resource_arn!r}"
        )
    resource_type, name = fragment.split("/", 1)
    if not resource_type or not name:
        raise InvalidRequestException(
            f"Invalid Athena resource ARN: {resource_arn!r}"
        )
    return resource_type, name


def _resolve_tags(
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
    resource_type: str,
    name: str,
) -> list[Tag]:
    if resource_type not in TAGGABLE_RESOURCE_TYPES:
        raise InvalidRequestException(
            f"Resource type {resource_type!r} cannot be tagged by Athena"
        )
    if resource_type == "workgroup":
        if name not in workgroups.by_name:
            raise ResourceNotFoundException(f"WorkGroup {name} does not exist")
        return workgroups.by_name[name].tags
    if name not in catalogs.by_name:
        raise ResourceNotFoundException(f"DataCatalog {name} does not exist")
    return catalogs.by_name[name].tags


def _tags_payload(tags: list[Tag]) -> list[dict[str, str]]:
    payload: list[dict[str, str]] = []
    for tag in tags:
        entry: dict[str, str] = {"Key": tag.key}
        if tag.value is not None:
            entry["Value"] = tag.value
        payload.append(entry)
    return payload


def tag_resource(
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
    payload: dict[str, object] | None,
) -> dict[str, object]:
    resource_type, name = _parse_arn(_required_string(payload, "ResourceARN"))
    tags = _resolve_tags(workgroups, catalogs, resource_type, name)
    new_tags = parse_tags(payload.get("Tags") if payload is not None else None)
    if not new_tags:
        raise InvalidRequestException(
            "Tags must be a non-empty list of key/value objects"
        )
    by_key = {tag.key: tag for tag in tags}
    by_key.update({tag.key: tag for tag in new_tags})
    tags[:] = list(by_key.values())
    return {}


def untag_resource(
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
    payload: dict[str, object] | None,
) -> dict[str, object]:
    resource_type, name = _parse_arn(_required_string(payload, "ResourceARN"))
    tags = _resolve_tags(workgroups, catalogs, resource_type, name)
    tag_keys = _required_string_list(payload, "TagKeys")
    tags[:] = [tag for tag in tags if tag.key not in tag_keys]
    return {}


def list_tags_for_resource(
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
    payload: dict[str, object] | None,
) -> dict[str, object]:
    resource_type, name = _parse_arn(_required_string(payload, "ResourceARN"))
    tags = _resolve_tags(workgroups, catalogs, resource_type, name)
    # MaxResults/NextToken are accepted for model compat but never produce a
    # second page: the model caps MaxResults at 75 while Athena resources hold
    # at most 50 tags, so a single response always fits every tag.
    return {"Tags": _tags_payload(tags)}


def register_tag_handlers(
    workgroups: WorkGroupStore, catalogs: DataCatalogStore
) -> None:
    """Bind the three tagging operations to the taggable stores."""
    register_handler(
        "TagResource",
        lambda payload: tag_resource(workgroups, catalogs, payload),
    )
    register_handler(
        "UntagResource",
        lambda payload: untag_resource(workgroups, catalogs, payload),
    )
    register_handler(
        "ListTagsForResource",
        lambda payload: list_tags_for_resource(workgroups, catalogs, payload),
    )
