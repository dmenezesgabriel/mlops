"""Unit tests for prepare_data."""

from wine_quality_classification import prepare_data


def test_load_frame_produces_int_labels() -> None:
    frame = prepare_data.load_frame()
    assert frame["cultivar"].isin([0, 1, 2]).all()
    assert "od280_od315_of_diluted_wines" in frame.columns


def test_build_tables_mints_wine_entities() -> None:
    features, labels = prepare_data.build_tables(
        prepare_data.load_frame().head(5)
    )
    assert features["wine_id"].tolist() == [f"wine-{i:03d}" for i in range(5)]
    assert "cultivar" not in features.columns
    assert labels.columns.tolist() == [
        "wine_id",
        "event_timestamp",
        "cultivar",
    ]
