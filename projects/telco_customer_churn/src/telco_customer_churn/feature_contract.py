"""Single source of truth for the churn feature contract.

The ordered feature list is shared by ``prepare_data`` (which writes the
Feast offline source parquet), the SageMaker ``train.py`` entrypoint (which
runs inside the job container with this module mounted flat under
``/opt/ml/code``), and the batch-transform input builder in the notebooks —
column order is positional at serving time, so one constant list keeps all
three writers aligned.
"""

ENTITY_COLUMN: str = "customer_id"
TIMESTAMP_COLUMN: str = "event_timestamp"
LABEL_COLUMN: str = "churn"

FEATURE_COLUMNS: list[str] = [
    "senior_citizen",
    "partner",
    "dependents",
    "tenure_months",
    "paperless_billing",
    "month_to_month",
    "one_year_contract",
    "electronic_check",
    "dsl",
    "fiber_optic",
    "streaming_tv",
    "streaming_movies",
    "num_add_ons",
    "monthly_charges",
    "total_charges",
]

NON_FEATURE_COLUMNS: tuple[str, ...] = (
    ENTITY_COLUMN,
    TIMESTAMP_COLUMN,
    LABEL_COLUMN,
)
