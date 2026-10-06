from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest
from ml_specialization.configuration import CollectionConfig
from ml_specialization.data.collection import TlcYellowTaxiParquetCollector
from ml_specialization.data.preprocessing import YellowTaxiTripPreprocessor
from ml_specialization.data.supervised_dataset import (
    NextHourDemandDatasetBuilder,
)
from ml_specialization.features.feast_materialization import (
    LocalFeastMaterializer,
)
from ml_specialization.features.hourly_demand import HourlyDemandFeatureBuilder
from ml_specialization.models.tuning import DemandModelTuner


def _input_parquet(directory: Path) -> Path:
    path = directory / "input.parquet"
    pd.DataFrame({"pickup_count": [1]}).to_parquet(path, index=False)
    return path


@pytest.mark.parametrize(
    ("stub_call", "surface"),
    [
        pytest.param(
            lambda tmp: TlcYellowTaxiParquetCollector().collect(
                CollectionConfig(
                    year=2023,
                    months=(1,),
                    taxi_type="yellow",
                ),
                tmp,
            ),
            "TlcYellowTaxiParquetCollector.collect",
            id="collector",
        ),
        pytest.param(
            lambda tmp: YellowTaxiTripPreprocessor().preprocess(
                tmp, tmp / "interim"
            ),
            "YellowTaxiTripPreprocessor.preprocess",
            id="preprocessor",
        ),
        pytest.param(
            lambda tmp: NextHourDemandDatasetBuilder().build(
                _input_parquet(tmp), tmp / "dataset.parquet"
            ),
            "NextHourDemandDatasetBuilder.build",
            id="dataset_builder",
        ),
        pytest.param(
            lambda tmp: HourlyDemandFeatureBuilder().build(
                _input_parquet(tmp), tmp / "features.parquet"
            ),
            "HourlyDemandFeatureBuilder.build",
            id="feature_builder",
        ),
        pytest.param(
            lambda tmp: LocalFeastMaterializer().apply(tmp / "feature_repo"),
            "LocalFeastMaterializer.apply",
            id="feast_materializer",
        ),
        pytest.param(
            lambda tmp: DemandModelTuner().tune(pd.DataFrame(), n_trials=1),
            "DemandModelTuner.tune",
            id="model_tuner",
        ),
    ],
)
def test_domain_stub_raises_not_implemented(
    stub_call: Callable[[Path], object],
    surface: str,
    tmp_path: Path,
) -> None:
    # Act / Assert — a stub must fail loudly, never fabricate artifacts
    with pytest.raises(NotImplementedError, match=surface):
        stub_call(tmp_path)
