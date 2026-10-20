"""Feast entity: one half-hour market tick."""

from feast import Entity, ValueType

market_tick = Entity(
    name="market_tick",
    join_keys=["market_tick_id"],
    description="Half-hourly NSW/VIC market tick.",
    value_type=ValueType.STRING,
)
