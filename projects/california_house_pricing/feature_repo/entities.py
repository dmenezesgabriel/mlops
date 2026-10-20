"""Feast entity: one census block group."""

from feast import Entity, ValueType

block_group = Entity(
    name="block_group",
    join_keys=["block_group_id"],
    description="Census block group identifier.",
    value_type=ValueType.STRING,
)
