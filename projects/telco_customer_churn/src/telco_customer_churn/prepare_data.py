"""Build the churn feature tables from the raw Telco CSV.

Pipeline: raw CSV -> interim clean parquet -> Feast offline source parquet +
label entity_df + scoring entity_df + a JSON schema sidecar the notebooks
use to order batch-transform inputs. Timestamps are tz-aware UTC (a naive
``event_timestamp`` breaks ``feast materialize``/point-in-time joins — the
duckdb binder rejects comparing TIMESTAMP to TIMESTAMPTZ).

Example:
    python -m telco_customer_churn.prepare_data
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from .feature_contract import (
        ENTITY_COLUMN,
        FEATURE_COLUMNS,
        LABEL_COLUMN,
        TIMESTAMP_COLUMN,
    )
else:
    try:
        from .feature_contract import (
            ENTITY_COLUMN,
            FEATURE_COLUMNS,
            LABEL_COLUMN,
            TIMESTAMP_COLUMN,
        )
    except ImportError:  # flat layout when mounted under /opt/ml/code
        from feature_contract import (
            ENTITY_COLUMN,
            FEATURE_COLUMNS,
            LABEL_COLUMN,
            TIMESTAMP_COLUMN,
        )

PROJECT_DIR = Path(__file__).resolve().parents[2]
# Public mirror of the IBM Telco churn sample (7043 rows, ~1 MB).
RAW_URL = "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv"
RAW_CSV = PROJECT_DIR / "data" / "raw" / "WA_Fn-UseC_-Telco-Customer-Churn.csv"
INTERIM_DIR = PROJECT_DIR / "data" / "interim"
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"

# The raw export is a CRM snapshot: every customer shares one reference date.
SNAPSHOT_DATE = "2023-02-01"

_ADD_ON_COLUMNS = [
    "OnlineSecurity",
    "OnlineBackup",
    "DeviceProtection",
    "TechSupport",
    "StreamingTV",
    "StreamingMovies",
]


def _yes(series: pd.Series) -> pd.Series:
    return (series == "Yes").astype("int64")


def _ensure_raw() -> None:
    if RAW_CSV.exists():
        return
    RAW_CSV.parent.mkdir(parents=True, exist_ok=True)
    # Pinned public dataset URL — the fetch is part of the collection stage.
    urllib.request.urlretrieve(RAW_URL, RAW_CSV)  # nosec B310  # noqa: S310  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected


def load_clean() -> pd.DataFrame:
    """Read the raw CSV and normalize types (TotalCharges arrives with blanks)."""
    _ensure_raw()
    frame = pd.read_csv(RAW_CSV)
    frame["TotalCharges"] = pd.to_numeric(
        frame["TotalCharges"], errors="coerce"
    )
    # New sign-ups have no billing history yet: tenure==0, TotalCharges blank.
    frame["TotalCharges"] = frame["TotalCharges"].fillna(0.0)
    frame[ENTITY_COLUMN] = frame.pop("customerID")
    frame[LABEL_COLUMN] = _yes(frame.pop("Churn"))
    return frame


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Project the cleaned CRM rows into the model feature contract."""
    features = pd.DataFrame(
        {
            ENTITY_COLUMN: frame[ENTITY_COLUMN],
            TIMESTAMP_COLUMN: pd.to_datetime(SNAPSHOT_DATE, utc=True),
            "senior_citizen": frame["SeniorCitizen"].astype("int64"),
            "partner": _yes(frame["Partner"]),
            "dependents": _yes(frame["Dependents"]),
            "tenure_months": frame["tenure"].astype("int64"),
            "paperless_billing": _yes(frame["PaperlessBilling"]),
            "month_to_month": (frame["Contract"] == "Month-to-month").astype(
                "int64"
            ),
            "one_year_contract": (frame["Contract"] == "One year").astype(
                "int64"
            ),
            "electronic_check": (
                frame["PaymentMethod"] == "Electronic check"
            ).astype("int64"),
            "dsl": (frame["InternetService"] == "DSL").astype("int64"),
            "fiber_optic": (frame["InternetService"] == "Fiber optic").astype(
                "int64"
            ),
            "streaming_tv": _yes(frame["StreamingTV"]),
            "streaming_movies": _yes(frame["StreamingMovies"]),
            "num_add_ons": (
                (frame[_ADD_ON_COLUMNS] == "Yes").sum(axis=1).astype("int64")
            ),
            "monthly_charges": frame["MonthlyCharges"].astype("float64"),
            "total_charges": frame["TotalCharges"].astype("float64"),
        }
    )
    return features[[ENTITY_COLUMN, TIMESTAMP_COLUMN, *FEATURE_COLUMNS]]


def main() -> None:
    clean = load_clean()
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    clean.to_parquet(INTERIM_DIR / "customers_clean.parquet", index=False)

    features = build_features(clean)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    features.to_parquet(
        PROCESSED_DIR / "customer_features.parquet", index=False
    )
    labels = features[[ENTITY_COLUMN, TIMESTAMP_COLUMN]].assign(
        **{LABEL_COLUMN: clean[LABEL_COLUMN]}
    )
    labels.to_parquet(PROCESSED_DIR / "churn_labels.parquet", index=False)
    features[[ENTITY_COLUMN, TIMESTAMP_COLUMN]].to_parquet(
        PROCESSED_DIR / "scoring_entities.parquet", index=False
    )
    schema = {
        "entity": ENTITY_COLUMN,
        "timestamp": TIMESTAMP_COLUMN,
        "label": LABEL_COLUMN,
        "features": FEATURE_COLUMNS,
    }
    (PROCESSED_DIR / "feature_schema.json").write_text(
        json.dumps(schema, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(features)} feature rows to {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
