from pathlib import Path

import pytest
from fakes import FakeRequestsModule
from nyc_taxi_demand_forecasting.configuration import CollectionConfig
from nyc_taxi_demand_forecasting.data import collection as collection_module
from nyc_taxi_demand_forecasting.data.collection import (
    TlcYellowTaxiParquetCollector,
)


def _collection_config() -> CollectionConfig:
    return CollectionConfig(
        year=2023,
        months=(1,),
        taxi_type="yellow",
        source_url_template=(
            "https://example.test/{taxi_type}_{year}-{month:02d}.parquet"
        ),
    )


def test_collector_downloads_missing_months(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    requests = FakeRequestsModule(content=b"PARQUET-BYTES")
    monkeypatch.setattr(collection_module, "requests", requests)

    # Act
    written = TlcYellowTaxiParquetCollector().collect(
        _collection_config(), tmp_path
    )

    # Assert
    assert written == (tmp_path / "yellow_tripdata_2023-01.parquet",)
    assert written[0].read_bytes() == b"PARQUET-BYTES"
    assert requests.urls == ["https://example.test/yellow_2023-01.parquet"]


def test_collector_skips_existing_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    existing = tmp_path / "yellow_tripdata_2023-01.parquet"
    existing.write_bytes(b"already-here")
    requests = FakeRequestsModule()
    monkeypatch.setattr(collection_module, "requests", requests)

    # Act
    written = TlcYellowTaxiParquetCollector().collect(
        _collection_config(), tmp_path
    )

    # Assert
    assert written == (existing,)
    assert requests.urls == []
    assert existing.read_bytes() == b"already-here"


def test_collector_propagates_http_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    requests = FakeRequestsModule(error=RuntimeError("HTTP 404"))
    monkeypatch.setattr(collection_module, "requests", requests)

    # Act / Assert
    with pytest.raises(RuntimeError, match="HTTP 404"):
        TlcYellowTaxiParquetCollector().collect(_collection_config(), tmp_path)
