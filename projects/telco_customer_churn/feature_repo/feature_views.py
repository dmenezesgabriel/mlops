from datetime import timedelta

from data_sources import customer_features_source
from entities import customer
from feast import FeatureView, Field
from feast.types import Float64, Int64

# Batch-only view (online=False): churn scoring reads the whole population
# through get_historical_features, so no online materialization is needed.
customer_subscription_view = FeatureView(
    name="customer_subscription",
    entities=[customer],
    ttl=timedelta(days=365),
    schema=[
        Field(name="senior_citizen", dtype=Int64),
        Field(name="partner", dtype=Int64),
        Field(name="dependents", dtype=Int64),
        Field(name="tenure_months", dtype=Int64),
        Field(name="paperless_billing", dtype=Int64),
        Field(name="month_to_month", dtype=Int64),
        Field(name="one_year_contract", dtype=Int64),
        Field(name="electronic_check", dtype=Int64),
        Field(name="dsl", dtype=Int64),
        Field(name="fiber_optic", dtype=Int64),
        Field(name="streaming_tv", dtype=Int64),
        Field(name="streaming_movies", dtype=Int64),
        Field(name="num_add_ons", dtype=Int64),
        Field(name="monthly_charges", dtype=Float64),
        Field(name="total_charges", dtype=Float64),
    ],
    online=False,
    source=customer_features_source,
)
