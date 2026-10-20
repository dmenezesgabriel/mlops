"""Unit tests for prepare_data."""

import pandas as pd
from electricity_price_streaming import prepare_data


def test_load_frame_coerces_numeric_features() -> None:
    frame = prepare_data.load_frame()
    for col in prepare_data.FEATURE_COLUMNS:
        assert pd.api.types.is_numeric_dtype(frame[col])


def test_build_tables_mints_tick_entities_and_binary_labels() -> None:
    features, labels = prepare_data.build_tables(
        prepare_data.load_frame().head(4)
    )
    assert features["market_tick_id"].tolist() == [
        f"tick-{i:05d}" for i in range(4)
    ]
    assert labels["direction_up"].isin([0, 1]).all()
    assert "direction_up" not in features.columns
