from feast import Entity

customer = Entity(
    name="customer_id",
    join_keys=["customer_id"],
    description="Telco customer identifier from the CRM snapshot export.",
)
