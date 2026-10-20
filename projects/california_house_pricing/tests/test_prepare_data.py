"""Unit tests for prepare_data (sklearn fetch is monkeypatched — no network)."""

import pandas as pd
import pytest
from california_house_pricing import prepare_data


class _FakeDataset:
    frame = pd.DataFrame(
        {
            "MedInc": [8.0, 3.0],
            "HouseAge": [40.0, 20.0],
            "AveRooms": [6.0, 5.0],
            "AveBedrms": [1.0, 1.1],
            "Population": [300.0, 500.0],
            "AveOccup": [2.5, 3.0],
            "Latitude": [37.8, 34.0],
            "Longitude": [-122.4, -118.3],
            "MedHouseVal": [4.5, 1.9],
        }
    )


def test_load_frame_renames_to_business_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        prepare_data,
        "fetch_california_housing",
        lambda as_frame=True: _FakeDataset(),
    )
    frame = prepare_data.load_frame()
    assert "median_income" in frame.columns and "MedInc" not in frame.columns
    assert "median_house_value" in frame.columns


def test_build_tables_mints_entities_and_splits_label() -> None:
    features, labels = prepare_data.build_tables(
        _FakeDataset.frame.rename(
            columns=prepare_data.RENAME | {"MedHouseVal": "median_house_value"}
        )
    )
    assert features["block_group_id"].tolist() == ["bg-00000", "bg-00001"]
    assert "median_house_value" not in features.columns
    assert labels["median_house_value"].tolist() == [4.5, 1.9]
