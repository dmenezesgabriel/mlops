"""Tests for ``prepare_data`` — the collection/preprocessing contract."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from telco_customer_churn import prepare_data
from telco_customer_churn.feature_contract import (
    ENTITY_COLUMN,
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    TIMESTAMP_COLUMN,
)

_RAW_ROW = (
    "0000-TEST,{gender},0,{partner},{dependents},{tenure},{phone},"
    "{multiple},{internet},{sec},{backup},{dev},{tech},{tv},{movies},"
    "{contract},{paperless},{payment},{monthly},{total},{churn}\n"
)

_HEADER = (
    "customerID,gender,SeniorCitizen,Partner,Dependents,tenure,"
    "PhoneService,MultipleLines,InternetService,OnlineSecurity,"
    "OnlineBackup,DeviceProtection,TechSupport,StreamingTV,"
    "StreamingMovies,Contract,PaperlessBilling,PaymentMethod,"
    "MonthlyCharges,TotalCharges,Churn\n"
)


def _row(
    customer_id: str = "0000-TEST",
    *,
    contract: str = "Month-to-month",
    payment: str = "Electronic check",
    internet: str = "DSL",
    total: str = "100.0",
    churn: str = "No",
) -> str:
    return _RAW_ROW.format(
        gender="Female",
        partner="Yes",
        dependents="No",
        tenure=12,
        phone="Yes",
        multiple="No",
        internet=internet,
        sec="Yes",
        backup="No",
        dev="Yes",
        tech="No",
        tv="Yes",
        movies="No",
        contract=contract,
        paperless="Yes",
        payment=payment,
        monthly="50.0",
        total=total,
        churn=churn,
    ).replace("0000-TEST", customer_id)


@pytest.fixture()
def raw_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    csv_path = tmp_path / "raw.csv"
    csv_path.write_text(
        _HEADER
        + _row("a-1", contract="Two year", payment="Credit card (automatic)")
        + _row("b-2", churn="Yes", internet="Fiber optic")
        + _row("c-3", total=" "),
        encoding="utf-8",
    )
    monkeypatch.setattr(prepare_data, "RAW_CSV", csv_path)
    monkeypatch.setattr(prepare_data, "INTERIM_DIR", tmp_path / "interim")
    monkeypatch.setattr(prepare_data, "PROCESSED_DIR", tmp_path / "processed")
    return csv_path


def test_load_clean_normalizes_types(raw_csv: Path) -> None:
    frame = prepare_data.load_clean()
    assert list(frame[LABEL_COLUMN]) == [0, 1, 0]
    # The blank TotalCharges becomes 0.0 rather than a fabricated charge.
    assert frame["TotalCharges"].iloc[2] == 0.0
    assert frame[ENTITY_COLUMN].tolist() == ["a-1", "b-2", "c-3"]


def test_build_features_projects_contract(raw_csv: Path) -> None:
    features = prepare_data.build_features(prepare_data.load_clean())
    assert list(features.columns) == [
        ENTITY_COLUMN,
        TIMESTAMP_COLUMN,
        *FEATURE_COLUMNS,
    ]
    first = features.iloc[0]
    assert first["one_year_contract"] == 0
    assert first["month_to_month"] == 0
    assert first["electronic_check"] == 0
    second = features.iloc[1]
    assert second["month_to_month"] == 1
    assert second["electronic_check"] == 1
    assert second["fiber_optic"] == 1
    assert second["num_add_ons"] == 3  # sec + dev + tv


def test_main_writes_the_full_artifact_set(raw_csv: Path) -> None:
    prepare_data.main()
    processed = raw_csv.parent / "processed"
    features = pd.read_parquet(processed / "customer_features.parquet")
    labels = pd.read_parquet(processed / "churn_labels.parquet")
    entities = pd.read_parquet(processed / "scoring_entities.parquet")
    schema = json.loads(
        (processed / "feature_schema.json").read_text(encoding="utf-8")
    )
    assert len(features) == 3
    assert labels[LABEL_COLUMN].tolist() == [0, 1, 0]
    assert list(entities.columns) == [ENTITY_COLUMN, TIMESTAMP_COLUMN]
    assert schema["features"] == FEATURE_COLUMNS
    assert features[TIMESTAMP_COLUMN].dt.tz is not None
