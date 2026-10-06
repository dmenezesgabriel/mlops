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
    requests = FakeRequestsModule(content=b"PAR1" + b"payload" + b"PAR1")
    monkeypatch.setattr(collection_module, "requests", requests)

    # Act
    written = TlcYellowTaxiParquetCollector().collect(
        _collection_config(), tmp_path
    )

    # Assert
    assert written == (tmp_path / "yellow_tripdata_2023-01.parquet",)
    assert written[0].read_bytes() == b"PAR1" + b"payload" + b"PAR1"
    assert requests.urls == ["https://example.test/yellow_2023-01.parquet"]
    assert list(tmp_path.glob("*.tmp")) == []


def test_collector_skips_valid_existing_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    existing = tmp_path / "yellow_tripdata_2023-01.parquet"
    existing.write_bytes(b"PAR1" + b"already-here" + b"PAR1")
    requests = FakeRequestsModule()
    monkeypatch.setattr(collection_module, "requests", requests)

    # Act
    written = TlcYellowTaxiParquetCollector().collect(
        _collection_config(), tmp_path
    )

    # Assert
    assert written == (existing,)
    assert requests.urls == []
    assert existing.read_bytes() == b"PAR1" + b"already-here" + b"PAR1"


def test_collector_redownloads_corrupt_cached_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange — a cache entry holding an HTML error page is not parquet
    corrupt = tmp_path / "yellow_tripdata_2023-01.parquet"
    corrupt.write_bytes(b"<html>Access Denied</html>")
    requests = FakeRequestsModule(content=b"PAR1" + b"fresh" + b"PAR1")
    monkeypatch.setattr(collection_module, "requests", requests)

    # Act
    written = TlcYellowTaxiParquetCollector().collect(
        _collection_config(), tmp_path
    )

    # Assert
    assert written == (corrupt,)
    assert requests.urls == ["https://example.test/yellow_2023-01.parquet"]
    assert corrupt.read_bytes() == b"PAR1" + b"fresh" + b"PAR1"


def test_collector_redownloads_truncated_cached_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange — a crashed write leaves the header magic but no footer
    truncated = tmp_path / "yellow_tripdata_2023-01.parquet"
    truncated.write_bytes(b"PAR1" + b"partial-payload")
    requests = FakeRequestsModule(content=b"PAR1" + b"full" + b"PAR1")
    monkeypatch.setattr(collection_module, "requests", requests)

    # Act
    written = TlcYellowTaxiParquetCollector().collect(
        _collection_config(), tmp_path
    )

    # Assert
    assert written == (truncated,)
    assert requests.urls == ["https://example.test/yellow_2023-01.parquet"]
    assert truncated.read_bytes() == b"PAR1" + b"full" + b"PAR1"


@pytest.mark.parametrize(
    "stale_bytes",
    [pytest.param(b"", id="empty"), pytest.param(b"PAR1", id="magic_only")],
)
def test_collector_redownloads_undersized_cached_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stale_bytes: bytes,
) -> None:
    # Arrange — under 8 bytes can't hold both magic words; treat as corrupt
    undersized = tmp_path / "yellow_tripdata_2023-01.parquet"
    undersized.write_bytes(stale_bytes)
    requests = FakeRequestsModule(content=b"PAR1" + b"full" + b"PAR1")
    monkeypatch.setattr(collection_module, "requests", requests)

    # Act
    TlcYellowTaxiParquetCollector().collect(_collection_config(), tmp_path)

    # Assert
    assert requests.urls == ["https://example.test/yellow_2023-01.parquet"]
    assert undersized.read_bytes() == b"PAR1" + b"full" + b"PAR1"


def test_collector_rejects_non_parquet_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange — an HTTP 200 error page must not become a cached "parquet"
    requests = FakeRequestsModule(content=b"<html>Access Denied</html>")
    monkeypatch.setattr(collection_module, "requests", requests)

    # Act / Assert
    with pytest.raises(ValueError, match="expected parquet"):
        TlcYellowTaxiParquetCollector().collect(_collection_config(), tmp_path)
    assert list(tmp_path.glob("*.parquet")) == []


def test_collector_propagates_http_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    requests = FakeRequestsModule(error=RuntimeError("HTTP 404"))
    monkeypatch.setattr(collection_module, "requests", requests)

    # Act / Assert
    with pytest.raises(RuntimeError, match="HTTP 404"):
        TlcYellowTaxiParquetCollector().collect(_collection_config(), tmp_path)
