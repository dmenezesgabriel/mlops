"""Feast entity: one measured wine sample."""

from feast import Entity, ValueType

wine = Entity(
    name="wine",
    join_keys=["wine_id"],
    description="Wine sample identifier.",
    value_type=ValueType.STRING,
)
