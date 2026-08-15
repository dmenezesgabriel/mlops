from feast import Entity

pickup_location = Entity(
    name="pickup_location_id",
    join_keys=["pickup_location_id"],
    description="NYC TLC pickup taxi zone identifier.",
)
